# app/api/v1/endpoints/user/profile.py

import re
from datetime import timedelta
from typing import TYPE_CHECKING

from jose import JWTError, jwt

from fastapi import APIRouter, Security, Request, Depends, Response
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_api_tokens
from app.core.exceptions import (
    UserNotFoundException,
    UserAlreadyExistsException,
    IncorrectPhoneOrEmailException,
    UserBannedException,
    ForbiddenException,
    EmailOrPasswordInvalidException,
    PhoneOrPasswordInvalidException,
    TokenNotFoundException,
    InvalidJWTException,
    UserIdNotFoundException,
    TokenMismatchException,
    CredentialsValidationException,
)
from app.core.responses import register_resps, login_resps, logout_resps
from app.core.security.auth import get_current_user, response_access_refresh_token
from app.core.security.csfr import validate_csrf_token
from app.db.dao.user import UserDAO

from app.db.models import User, Profile, Role, UserRole, Token
from app.db.models.enums import TokenTypeEnum
from app.db.sessions import TransactionSessionDep
from app.db.schemas.user import EmailModel, PhoneModel, SuccessfulResponseSchema
from app.services.auth.authentication_service import authenticate_user
from app.services.auth.token_service import (
    creating_recording_all_token_to_user,
    creating_recording_access_token_to_user,
)
from app.services.mail_sender.logic import send_verify_email_to_user
from app.utils.logger import logger

if TYPE_CHECKING:
    from app.db.schemas.user import (
        SUserRegister,
        ProfileModel,
        SUserAddDB,
    )

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.post(
    "/register",
    responses=register_resps,
    # Описание для Swagger/OpenAPI документации:
    summary="Регистрация нового пользователя",
    response_description="Успешная регистрация. Возвращает access token и устанавливает cookies.",
)
async def register_user(
    user_data: SUserRegister,
    db: TransactionSessionDep,
    csrf_validation: None = Depends(validate_csrf_token),
) -> JSONResponse:
    """
    Регистрирует нового пользователя в системе.

    **Требования:**
    - Обязательно: пароль (5-50 символов) и подтверждение пароля
    - Хотя бы одно из полей: email или номер телефона

    **Процесс регистрации:**
    1. Проверка, что пользователь с таким email/телефоном не существует
    2. Создание учетной записи
    3. Назначение ролей:
       - USER - всем новым пользователям
       - SUPPORT - тех-поддержка
       Более подробная информация в схеме авторизации.
    4. Генерация токенов(пока нету, не делать эту логику):
       - Access token (в теле ответа и cookie)
       - Refresh token (только в cookie)
       - CSRF token (в cookie)
    5. Отправка письма с подтверждением для email

    **Возвращает:**
    - Access token в JSON и cookie
    - Refresh token в cookie (HttpOnly)
    - CSRF token в cookie

    **Параметры:**
    - email (опционально): Электронная почта
    - phone_number (опционально): Номер телефона в формате +7...
    - password: Пароль (5-50 символов)
    - confirm_password: Подтверждение пароля

    **Примечание:** Требует CSRF-токена в заголовках запроса.
    """
    user_email, user_phone = None, None
    email_mess, phone_mess = "", ""

    if user_data.email:
        email_mess = f"email {user_data.email}"
        user_email = await UserDAO.find_one_user_or_none(
            db=db, filters=EmailModel(email=user_data.email)
        )

    if user_data.phone_number:
        phone_mess = f"телефоном {user_data.phone_number}"
        user_phone = await UserDAO.find_one_user_or_none(
            db=db, filters=PhoneModel(phone_number=user_data.phone_number)
        )

    if user_data.email or user_data.phone_number:
        logger.info(
            f"Попытка регистрации нового пользователя с {', '.join([email_mess, phone_mess])}"
        )
    if user_email or user_phone:
        logger.remove()
        raise UserAlreadyExistsException
    user_data_dict = user_data.model_dump()
    del user_data_dict["confirm_password"]
    new_user = await UserDAO.add(db=db, values=SUserAddDB(**user_data_dict))
    new_user: User
    profile_data = ProfileModel(**user_data_dict)
    profile_data_dict = profile_data.model_dump()
    new_user.profile = Profile(**profile_data_dict)

    # Генерируем токен доступа
    scopes_rights = ["USER"]
    list_adm_email = ["dblmokdima@gmail.com"]
    if new_user.email in list_adm_email:
        scopes_rights.append("ADMIN")
        scopes_rights.append("SYSADMIN")
    list_dev_email = ["dblmokdima@gmail.com"]
    if new_user.email in list_dev_email:
        scopes_rights.append("DEVELOPER")

    for r_scope in scopes_rights:
        stmt = (
            select(Role)
            .options(selectinload(Role.users).joinedload(UserRole.user))
            .where(Role.name == r_scope)
        )
        roles = await db.scalars(stmt)
        for role in roles:
            role.users_assoc.append(UserRole(user=new_user))
    user = await UserDAO.find_one_user_or_none_by_id_with_tokens(
        db=db, data_id=new_user.id
    )
    access_token, refresh_token = await creating_recording_all_token_to_user(
        db=db, user=user, token_scopes=scopes_rights
    )
    response = await response_access_refresh_token(access_token, refresh_token)
    if user_data.email:
        await send_verify_email_to_user(email=user_data.email, db=db)

    logger.info(f"Пользователь {new_user.id}" f" успешно зарегистрирован.")
    return response


@auth_router.post(
    "/login",
    responses=login_resps,
    # Описание для Swagger/OpenAPI документации:
    summary="Аутентификация пользователя",
    response_description="Успешная аутентификация. Возвращает access token и устанавливает cookies.",
)
async def login_user(
    db: TransactionSessionDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    Аутентифицирует пользователя в системе и возвращает токены доступа.

    **Требования:**
    - Логин (email или телефон в международном формате)
    - Пароль
    - Опционально: запрашиваемые scope (роли)

    **Процесс аутентификации:**
    1. Определяет тип логина (email/телефон)
    2. Проверяет учетные данные:
       - Существование пользователя
       - Совпадение пароля
       - Отсутствие блокировки (ban)
    3. Проверяет запрошенные scopes (роли) на соответствие ролям пользователя
    4. Генерирует новые токены:
       - Access token (JWT)
       - Refresh token
       - CSRF token

    **Возвращает:**
    - Access token в JSON и cookie (HttpOnly)
    - Refresh token в cookie (HttpOnly)
    - CSRF token в cookie (доступен клиенту)

    **Параметры формы:**
    - username: Email или телефон (формат +7...)
    - password: Пароль пользователя
    - scope: Опциональные запрашиваемые роли (через пробел)

    **Ошибки:**
    - 400: Неверный формат email/телефона
    - 401: Неверные учетные данные
    - 403: Запрошены недоступные роли
    - 423: Пользователь заблокирован

    **Пример тела запроса (form-data):**
    username: user@example.com
    password: mypassword
    scope: USER ADMIN
    """
    username = form_data.username
    password = form_data.password

    # Проверка, является ли username email или телефон
    if re.match(r"[^@]+@[^@]+\.[^@]+", username):  # Если это email
        user_model = EmailModel(email=username)
        user = await authenticate_user(db=db, email=user_model.email, password=password)
        if user is None:
            logger.remove()
            raise EmailOrPasswordInvalidException
    elif re.match(r"^\+\d{5,15}$", username):  # Если это телефон
        user_model = PhoneModel(phone_number=username)
        user = await authenticate_user(
            db=db, phone=user_model.phone_number, password=password
        )
        if user is None:
            logger.remove()
            raise PhoneOrPasswordInvalidException
    else:
        raise IncorrectPhoneOrEmailException
    if user.is_banned:
        logger.remove()
        raise UserBannedException
    token_scopes_stmt = select(UserRole.role_name).where(UserRole.user_id == user.id)

    token_scopes_db = await db.scalars(token_scopes_stmt)
    token_scopes = {role.name for role in token_scopes_db}
    # Получаем запрошенные роли из токена
    scopes = set(form_data.scopes)  # Доступные роли из токена
    for sc in scopes:
        if not sc in token_scopes:
            logger.remove()
            raise ForbiddenException
    if scopes:
        # Находим пересечение ролей
        token_scopes = token_scopes.intersection(scopes)

    access_token, refresh_token = await creating_recording_all_token_to_user(
        db=db, user=user, token_scopes=token_scopes
    )
    response = await response_access_refresh_token(access_token, refresh_token)
    await db.commit()
    logger.info(
        f"Пользователь {user.id}"
        f" успешно вошел в систему. Доступы: {list(token_scopes)}"
    )
    return response


@auth_router.post("/logout", responses=logout_resps)
async def logout_user(
    response: Response,
    db: TransactionSessionDep,
    user_data: User = Security(get_current_user, scopes=["USER"]),
):
    """
    ## Endpoint выхода из системы (Logout)

    ### Описание
    Этот эндпоинт выполняет выход пользователя из системы, полностью завершая его сессию.
     При вызове удаляются все cookie, связанные с аутентификацией, включая токены доступа и защиты от CSRF.
     Также очищает активный токен из БД.

    ### Требования
    - Эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie).

    ### Действия
    - Удаляет следующие cookie:
      - `users_access_token` — токен доступа.
      - `refresh_token` — токен обновления.
      - `csrf_token` — токен защиты от CSRF.
    - Устанавливает заголовки для предотвращения кэширования.
    - Возвращает сообщение об успешном выходе из системы.
    """
    # Удаление всех токенов из куки
    user_data.tokens.ban = True
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    response.delete_cookie(key="site_token")
    response.delete_cookie(key="csrf_token")

    # Для безопасности можно добавить заголовки, запрещающие кэширование
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    logger.info(f"Пользователь {user_data.id} вышел из системы")

    return SuccessfulResponseSchema(
        **{"message": "Пользователь успешно вышел из системы"}
    )


@auth_router.put("/refresh", responses=login_resps)
async def refresh(request: Request, db: TransactionSessionDep):
    """
    🔄 **Обновление токена доступа**

    🔹 **Метод:** PUT
    🔹 **Путь:** /refresh

    🔹 **Параметры:**
       - `refresh_token` (cookie) — токен обновления

    🔹 **Возвращает:**
       - Новый `access_token` — в JSON-ответе (`access_token`, `token_type`)
       - Новый `access_token` — в cookie (`access_token`)
       - Новый `csrf_token` — в cookie (`csrf_token`, доступен на фронте)
       - Новый `refresh_token` — в cookie (`refresh_token`), если был сгенерирован заново (не всегда)

    🔹 **Возможные ошибки:**
       - `401 Unauthorized` — отсутствие или невалидность `refresh_token`
       - `403 Forbidden` — `refresh_token` не найден в БД
       - `404 Not Found` — пользователь не найден

    🔹 **Особенности:**
       - Проверяет валидность `refresh_token`
       - Находит и возвращает пересечение запрошенных и фактических ролей пользователя
       - Создаёт новый `access_token`, срок действия — 15 минут
       - Устанавливает CSRF токен
       - Логирует успешное обновление токена
    """
    try:
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            logger.remove()
            raise TokenNotFoundException
        try:
            payload_refresh_token = jwt.decode(
                refresh_token,
                get_api_tokens().TAPI_TOKEN_REFRESH_SECRET_KEY,
                algorithms=[get_api_tokens().ALGORITHM],
            )
            user_id: str = payload_refresh_token.get("sub")
            token_scopes = payload_refresh_token.get("scopes", [])
            expire: str = payload_refresh_token.get("exp")
        except JWTError:
            logger.remove()
            raise InvalidJWTException
        if not user_id:
            logger.remove()
            raise UserIdNotFoundException
        user_id = int(user_id)

        user = await UserDAO.find_one_user_or_none_by_id_with_tokens(
            data_id=user_id, db=db
        )
        if user is None:
            logger.remove()
            raise UserNotFoundException
        check_refresh_token = (
            await db.execute(
                select(Token).where(
                    Token.user_id == user.id,
                    Token.token_type == TokenTypeEnum.REFRESH,
                    Token.ban == False,
                    Token.token == refresh_token,
                )
            )
        ).scalar_one_or_none()
        if not check_refresh_token:
            logger.remove()
            raise TokenMismatchException
        access_token_expires = timedelta(minutes=15)

        token_scopes_stmt = select(UserRole.role_name).where(
            UserRole.user_id == user.id
        )
        token_scopes_db = await db.scalars(token_scopes_stmt)
        token_scopes_db = set(token_scopes_db.all())
        # Получаем запрошенные роли из токена

        if token_scopes:
            # Находим пересечение ролей
            token_scopes = token_scopes_db.intersection(token_scopes)

        access_token = await creating_recording_access_token_to_user(
            db=db, user=user, token_scopes=token_scopes
        )

        response = await response_access_refresh_token(access_token)

        logger.info(
            f"Пользователь {user.id}"
            f" успешно обновил refresh token. Доступы: {list(token_scopes)}"
        )
        return response

    except JWTError:
        raise CredentialsValidationException
