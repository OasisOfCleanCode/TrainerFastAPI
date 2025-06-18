# app/api/v1/endpoints/user/me.py

from typing import TYPE_CHECKING

from fastapi import APIRouter, Security
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import (
    UserNotFoundException,
    ContactAvailableException,
    PhoneAlreadyExistsException,
    UpdateException,
    LastContactDeleteException,
    DuplicateEntryException,
    RefreshPasswordInvalidException,
)
from app.core.responses import (
    user_get_resps,
    role_get_resps,
    email_phone_resps,
    email_verify_resps,
)
from app.core.security.auth import get_current_user
from app.db.dao.user import UserDAO
from app.db.models import User
from app.db.sessions import SessionDep, TransactionSessionDep
from app.services.auth.authentication_service import verify_password
from app.services.mail_sender.logic import (
    send_verify_email_to_user,
    send_verify_change_email_to_user,
)
from app.utils.logger import logger

if TYPE_CHECKING:
    from app.db.schemas.user import (
        SUserInfoRole,
        SRoleInfo,
        CheckEmailModel,
        CheckPhoneModel,
        SUserRefreshPassword,
    )

me_router = APIRouter(prefix="/me", tags=["Me"])


@me_router.get("", responses=user_get_resps)
async def get_me(
    db: SessionDep,
    user_data: User = Security(get_current_user, scopes=["USER"]),
) -> SUserInfoRole:
    """
    ## Endpoint запроса данных пользователя системы.

    ### Описание
    - Возвращает данные пользователя сделавшего запрос.
    - Endpoint доступен для всех авторизовавшихся пользователей.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """

    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    user = SUserInfoRole.model_validate(user_data)
    return user


@me_router.get("/role", responses=role_get_resps)
async def get_roles(
    db: SessionDep,
    user_data: User = Security(
        get_current_user, scopes=["DEVELOPER", "ADMIN", "SYSADMIN"]
    ),
) -> SRoleInfo:
    """
    ## Endpoint информации о всех доступных ролях для пользователя

    ### Описание
    - Возвращает роли пользователя системы в виде списка.
    - Endpoint доступен для всех авторизовавшихся пользователей.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """
    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    roles = SRoleInfo.model_validate(user_data)
    return roles


@me_router.get("/email", responses=email_phone_resps)
async def get_email(
    db: SessionDep,
    user_data: User = Security(get_current_user, scopes=["USER"]),
) -> CheckEmailModel:
    """
    ## Endpoint запроса адреса email пользователя системы.

    ### Описание
    - Возвращает данные пользователя системы.
    - Проверяется уровень доступа, при положительном результате обрабатывает запрос.
        Данный функционал доступен только для администраторов.
        Если текущий пользователь не является ADMIN, SYSADMIN, доступ будет запрещен.
    - Определяет автоматически email и номер телефона.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """
    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    if user_data.email is None:
        logger.remove()
        raise ContactAvailableException
    email = CheckEmailModel.model_validate(user_data)
    return email


@me_router.post("/email", responses=user_get_resps)
async def post_email(
    email: CheckEmailModel,
    user_data: User = Security(get_current_user, scopes=["USER"]),
) -> SUserInfoRole:
    """
    ## Endpoint добавления email пользователя системы.

    ### Описание
    - Endpoint добавляет email, если его еще нет у пользователя
    - Endpoint доступен для всех авторизовавшихся пользователей.
    - Возвращает данные пользователя сделавшего запрос.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """

    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    res_user = await UserDAO.post_email_to_user(user=user_data, email=email)
    user = SUserInfoRole.model_validate(res_user)
    return user


async def put_email(self):
    @self.router.put("/email", responses=user_get_resps)
    async def put_email(
        email: CheckEmailModel,
        db: TransactionSessionDep,
        user_data: User = Security(self.get_current_user, scopes=["USER"]),
    ) -> SUserInfoRole:
        """
        ## Endpoint обновления email пользователя системы.

        ### Описание
        - Endpoint обновляет email пользователя
        - Endpoint доступен для всех авторизовавшихся пользователей.
        - Возвращает данные пользователя сделавшего запрос.

        ### Требования
        - Этот эндпоинт не требует передачи данных в теле запроса.
        - Пользователь должен быть авторизован (наличие токена в cookie-файле).
        """

        if user_data is None:
            logger.remove()
            raise UserNotFoundException
        res_user = await UserDAO.check_email_to_user(
            user=user_data, email=email, db=SessionDep
        )

        verify = await send_verify_change_email_to_user(
            db=db, email=user_data.email, new_email=email.email
        )
        return verify


@me_router.delete("/email", responses=user_get_resps)
async def delete_email(
    db: TransactionSessionDep,
    user_data: User = Security(
        get_current_user, scopes=["DEVELOPER", "ADMIN", "SYSADMIN"]
    ),
) -> SUserInfoRole:
    """
    ## Endpoint удаления email пользователя системы.

    ### Описание
    - Endpoint удаляет email пользователя, если есть номер телефона.
    - Endpoint доступен для всех авторизовавшихся пользователей.
    - Возвращает данные пользователя сделавшего запрос.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """

    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    if user_data.phone_number is None:
        logger.remove()
        raise LastContactDeleteException
    user_data.email = None
    await db.flush()
    user = SUserInfoRole.model_validate(user_data)
    return user


@me_router.post("/email/verify", responses=email_verify_resps)
async def send_verify_email(
    db: TransactionSessionDep,
    user_data: User = Security(get_current_user, scopes=["USER"]),
):
    """
    ## Endpoint запроса на верификацию email адреса.

    ### Описание
    - Генерирует токен и с помощью его формирует ссылку для верификации.
    - Отправляет ссылку на email пользователя.
    - Верификация  проходит автоматически при переходе по ссылке.
    - Возвращает сообщение о статусе операции.
    - Endpoint доступен для всех авторизовавшихся пользователей.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """

    verify = await send_verify_email_to_user(db=db, email=user_data.email)
    return verify


@me_router.get("/phone", responses=email_phone_resps)
async def get_email(
    db: SessionDep,
    user_data: User = Security(get_current_user, scopes=["USER"]),
) -> CheckPhoneModel:
    """
    ## Endpoint запроса номера телефона пользователя системы.

    ### Описание
    - Возвращает данные пользователя системы.
    - Проверяется уровень доступа, при положительном результате обрабатывает запрос.
        Данный функционал доступен только для администраторов.
        Если текущий пользователь не является ADMIN, SYSADMIN, доступ будет запрещен.
    - Определяет автоматически email и номер телефона.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """
    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    if user_data.phone_number is None:
        logger.remove()
        raise ContactAvailableException("номера телефона")
    phone = CheckPhoneModel.model_validate(user_data)
    return phone


@me_router.post("/phone", responses=user_get_resps)
async def post_phone_number(
    phone_number: CheckPhoneModel,
    db: TransactionSessionDep,
    user_data: User = Security(get_current_user, scopes=["USER"]),
) -> SUserInfoRole:
    """
    ## Endpoint добавления номера телефона пользователя системы.

    ### Описание
    - Endpoint добавляет номер телефона, если его еще нет у пользователя
    - Автоматически конвертирует его в формат +79991234567
    - Endpoint доступен для всех авторизовавшихся пользователей.
    - Возвращает данные пользователя сделавшего запрос.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """

    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    check_phone_number = (
        await db.execute(
            select(User).where(User.phone_number == phone_number.phone_number)
        )
    ).scalar_one_or_none()
    if check_phone_number:
        logger.remove()
        raise PhoneAlreadyExistsException
    if user_data.phone_number:
        logger.remove()
        raise DuplicateEntryException
    user_data.phone_number = phone_number.phone_number
    await db.flush()
    user = SUserInfoRole.model_validate(user_data)
    return user


@me_router.put("/phone", responses=user_get_resps)
async def put_phone_number(
    phone_number: CheckPhoneModel,
    db: TransactionSessionDep,
    user_data: User = Security(get_current_user, scopes=["USER"]),
) -> SUserInfoRole:
    """
    ## Endpoint обновления номера телефона пользователя системы.

    ### Описание
    - Endpoint обновляет номер телефона пользователя
    - Endpoint доступен для всех авторизовавшихся пользователей.
    - Возвращает данные пользователя сделавшего запрос.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """

    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    check_phone_number = (
        await db.execute(
            select(User).where(User.phone_number == phone_number.phone_number)
        )
    ).scalar_one_or_none()
    if check_phone_number:
        logger.remove()
        raise PhoneAlreadyExistsException
    try:
        user_data.phone_number = phone_number.phone_number
        await db.flush()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при обновлении номера телефона: {e}")
        raise UpdateException
    user = SUserInfoRole.model_validate(user_data)
    return user


@me_router.delete("/phone", responses=user_get_resps)
async def put_phone_number(
    db: TransactionSessionDep,
    user_data: User = Security(
        get_current_user, scopes=["DEVELOPER", "ADMIN", "SYSADMIN"]
    ),
) -> SUserInfoRole:
    """
    ## Endpoint удаления номера телефона пользователя системы.

    ### Описание
    - Endpoint удаляет номер телефона пользователя, если есть email.
    - Endpoint доступен для всех авторизовавшихся пользователей.
    - Возвращает данные пользователя сделавшего запрос.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """

    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    if user_data.email is None:
        logger.remove()
        raise LastContactDeleteException
    user_data.phone_number = None
    await db.flush()
    user = SUserInfoRole.model_validate(user_data)
    return user


@me_router.put("/password", responses=user_get_resps)
async def put_password(
    schema: SUserRefreshPassword,
    db: TransactionSessionDep,
    user_data: User = Security(get_current_user, scopes=["USER"]),
) -> SUserInfoRole:
    """
    ## Endpoint обновления email пользователя системы.

    ### Описание
    - Endpoint обновляет email пользователя
    - Endpoint доступен для всех авторизовавшихся пользователей.
    - Возвращает данные пользователя сделавшего запрос.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """

    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    pass_verify = await verify_password(schema.password, user_data.password)
    if not pass_verify:
        logger.remove()
        raise RefreshPasswordInvalidException
    try:
        user_data.password = schema.new_password
        await db.flush()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при обновлении пароля: {e}")
        raise UpdateException
    return JSONResponse(
        status_code=200, content={"message": "Пароль успешно обновлен."}
    )
