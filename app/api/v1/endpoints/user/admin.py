import re
from datetime import datetime, timezone
from typing import List

from loguru import logger
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Response, Depends, Security
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    UserNotFoundException,
    RoleAlreadyAssignedException,
    RoleNotAssignedException,
)
from app.core.responses import (
    users_get_resps,
    user_get_resps,
    email_verify_resps,
    role_get_resps,
    role_post_resps,
    role_del_resps,
)
from app.core.security.auth import get_current_user
from app.db.dao.base_dao import UserDAO
from app.db.models import User, Role, UserRole
from app.db.schemas.user import (
    SUserInfoRole,
    CheckEmailModel,
    CheckIDModel,
    CheckPhoneModel,
    SRoleInfo,
    RoleModel,
)
from app.db.sessions import SessionDep, TransactionSessionDep
from app.utils.logger import logger

admin_router = APIRouter()


@admin_router.get("s/", responses=users_get_resps)
async def get_users(
    db: AsyncSession = SessionDep,
    adm_data: User = Security(get_current_user, scopes=["ADMIN", "SYSADMIN"]),
) -> List[SUserInfoRole]:
    """
    ## Endpoint запроса списка всех пользователей системы.

    ### Описание
    - Возвращает список всех пользователей системы.
    - Этот эндпоинт доступен только для администраторов.
      Если текущий пользователь не является ADMIN, SYSADMIN, доступ будет запрещен.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """
    all_user = await UserDAO.find_all(db=db, filters=None)
    all_user = [SUserInfoRole.model_validate(user_data) for user_data in all_user]

    return all_user


@admin_router.get("/id/{address}")
async def get_user_id_by_email(address: str, db: AsyncSession = SessionDep):
    """
    ## Endpoint запроса данных пользователя системы по email.

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
    email = CheckEmailModel(email=address)
    check_user = await UserDAO.find_one_or_none(db=db, filters=email)
    if check_user is None:
        logger.remove()
        raise UserNotFoundException
    user = SUserInfoRole.model_validate(check_user)
    return user.id


@admin_router.get("/{id}", responses=user_get_resps)
async def get_user_by_id(
    db: AsyncSession = SessionDep,
    id: CheckIDModel = Depends(),
    user_data: User = Security(get_current_user, scopes=["ADMIN", "SYSADMIN"]),
) -> SUserInfoRole:
    """
    ## Endpoint запроса данных пользователя системы.

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
    check_user = await UserDAO.find_one_or_none(db=db, filters=id)
    if check_user is None:
        logger.remove()
        raise UserNotFoundException
    user = SUserInfoRole.model_validate(check_user)
    return user


@admin_router.delete("/{id}")
async def delete_user_by_id(
    db: AsyncSession = TransactionSessionDep,
    id: CheckIDModel = Depends(),
    user_data: User = Security(get_current_user, scopes=["ADMIN", "SYSADMIN"]),
) -> JSONResponse:
    """
    ## Endpoint запроса данных пользователя системы.

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
    check_user = await UserDAO.find_one_or_none(db=db, filters=id)
    if check_user is None:
        logger.remove()
        raise UserNotFoundException
    await UserDAO.delete(db=db, filters=id)
    return JSONResponse(
        status_code=200, content={"message": f"Пользователь с {id} успешно удален!"}
    )


@admin_router.post("/{id}/email/verify", responses=email_verify_resps)
async def send_verify_email(
    response: Response,
    db: AsyncSession = SessionDep,
    id: CheckIDModel = Depends(),
    user_data: User = Security(get_current_user, scopes=["ADMIN", "SYSADMIN"]),
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

    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    check_user = await UserDAO.find_one_or_none(db=db, filters=id)
    if check_user is None:
        logger.remove()
        raise UserNotFoundException

    result = await send_verify_email_to_user(db=db, email=check_user.email)

    response.headers["X-Success-Code"] = result.get("code", "2003")
    return JSONResponse(
        status_code=200, content={"status": "success", "message": result["message"]}
    )


@admin_router.get("/email/{address}", responses=user_get_resps)
async def get_email(
    address: str,
    db: AsyncSession = SessionDep,
    user_data: User = Security(get_current_user, scopes=["ADMIN", "SYSADMIN"]),
) -> SUserInfoRole:
    """
    ## Endpoint запроса данных пользователя системы по email.

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
    email = CheckEmailModel(email=address)
    check_user = await UserDAO.find_one_or_none(db=db, filters=email)
    if check_user is None:
        logger.remove()
        raise UserNotFoundException
    user = SUserInfoRole.model_validate(check_user)
    return user


@admin_router.get("/phone/{number}", responses=user_get_resps)
async def get_email(
    number: str,
    db: AsyncSession = SessionDep,
    user_data: User = Security(get_current_user, scopes=["ADMIN", "SYSADMIN"]),
) -> SUserInfoRole:
    """
    ## Endpoint запроса данных пользователя системы.

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
    phone = CheckPhoneModel(phone_number=number)
    check_user = await UserDAO.find_one_or_none(db=db, filters=phone)
    if check_user is None:
        logger.remove()
        raise UserNotFoundException
    user = SUserInfoRole.model_validate(check_user)
    return user


@admin_router.get("/{id}/role", responses=role_get_resps)
async def get_user_roles(
    user_data: User = Security(get_current_user, scopes=["ADMIN", "SYSADMIN"]),
    id: CheckIDModel = Depends(),
    db: AsyncSession = SessionDep,
) -> SRoleInfo:
    """
    ## Endpoint информации о всех доступных ролях для пользователя

    ### Описание
    - Возвращает роли пользователя системы в виде списка.
    - Этот эндпоинт доступен только для администраторов.
      Если текущий пользователь не является ADMIN, SYSADMIN, доступ будет запрещен.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """
    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    check_user = await UserDAO.find_one_or_none(db=db, filters=id)
    if check_user is None:
        logger.remove()
        raise UserNotFoundException
    roles = SRoleInfo.model_validate(check_user)
    return roles


@admin_router.post("/{id}/role", responses=role_post_resps)
async def post_user_role(
    user_data: User = Security(get_current_user, scopes=["ADMIN", "SYSADMIN"]),
    id: CheckIDModel = Depends(),
    db: AsyncSession = TransactionSessionDep,
    schema_role: RoleModel = Depends(),
) -> SUserInfoRole:
    """
    ## Endpoint добавляет роль для пользователя системы.

    ### Описание
    - Возвращает данные пользователя системы.
    - Этот эндпоинт доступен только для администраторов.
      Если текущий пользователь не является ADMIN, SYSADMIN, доступ будет запрещен.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """
    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    check_user = await UserDAO.find_one_or_none_by_id(db=db, data_id=id.id)
    if check_user is None:
        logger.remove()
        raise UserNotFoundException
    if schema_role.role in check_user.roles:
        logger.remove()
        raise RoleAlreadyAssignedException
    stmt = (
        select(Role)
        .options(selectinload(Role.users).joinedload(UserRole.user))
        .where(Role.name == schema_role.role)
    )
    role = await db.scalar(stmt)
    # Проверяем, что пользователя еще нет в ассоциации для роли
    if any(assoc.user_id == check_user.id for assoc in role.users):
        logger.remove()
        raise RoleAlreadyAssignedException

    # Добавляем связь между role и user
    check_user.roles_assoc.append(UserRole(role=role))  # И к пользователю
    await db.flush()
    # Валидация и возврат результата
    user = SUserInfoRole.model_validate(check_user)
    return user


@admin_router.delete("/{id}/role", responses=role_del_resps)
async def delete_user_role(
    user_data: User = Security(get_current_user, scopes=["ADMIN", "SYSADMIN"]),
    id: CheckIDModel = Depends(),
    db: AsyncSession = TransactionSessionDep,
    schema_role: RoleModel = Depends(),
) -> SUserInfoRole:
    """
    ## Endpoint удаляет роль для пользователя системы.

    ### Описание
    - Возвращает данные пользователя системы.
    - Этот эндпоинт доступен только для администраторов.
      Если текущий пользователь не является ADMIN, SYSADMIN, доступ будет запрещен.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """
    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    check_user = await UserDAO.find_one_or_none_by_id(db=db, data_id=id.id)
    if check_user is None:
        logger.remove()
        raise UserNotFoundException
    if schema_role.role not in check_user.roles:
        logger.remove()
        raise RoleNotAssignedException
    try:
        del_role = await db.execute(
            delete(UserRole).where(
                UserRole.user_id == check_user.id,
                UserRole.role_name == schema_role.role,
            )
        )
        await db.flush()
        await db.refresh(check_user)
        # Валидация и возврат результата
        user = SUserInfoRole.model_validate(check_user)
        return user
    except SQLAlchemyError as e:
        logger.error(f"Ошибка у user: {check_user.id}, {name_model} - delete_role: {e}")
        logger.remove()
        raise DeleteErrorException


@admin_router.put("/{id}/ban_on", responses=role_post_resps)
async def ban_on_user(
    user_data: User = Security(get_current_user, scopes=["ADMIN", "SYSADMIN"]),
    id: CheckIDModel = Depends(),
    db: AsyncSession = TransactionSessionDep,
    ban_time: CheckTimeBan = Depends(),
) -> SUserInfoRole:
    """
    ## Endpoint позволяет блокировать пользователя.

    ### Описание
    - Перманентная блокировка на сто лет.
    - Приложение автоматически снимает блокировку по назначенному времени.
    - Возвращает данные пользователя системы.
    - Этот эндпоинт доступен только для администраторов.
      Если текущий пользователь не является ADMIN, SYSADMIN, доступ будет запрещен.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """
    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    check_user = await UserDAO.find_one_or_none_by_id(db=db, data_id=id.id)
    if check_user is None:
        logger.remove()
        raise UserNotFoundException
    check_user.is_banned = True
    ban = BanTimeEnum(ban_time.period)
    check_user.ban_until = datetime.now(timezone.utc) + ban.duration
    await db.flush()
    await db.refresh(check_user)
    user = SUserInfoRole.model_validate(check_user)
    return user


@admin_router.put("/{id}/ban_off", responses=role_post_resps)
async def ban_off_user(
    user_data: User = Security(get_current_user, scopes=["ADMIN", "SYSADMIN"]),
    id: CheckIDModel = Depends(),
    db: AsyncSession = TransactionSessionDep,
) -> SUserInfoRole:
    """
    ## Endpoint позволяет разблокировать пользователя.

    ### Описание
    - Отключает бан и очищает время блокировки.
    - Возвращает данные пользователя системы.
    - Этот эндпоинт доступен только для администраторов.
      Если текущий пользователь не является ADMIN, SYSADMIN, доступ будет запрещен.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """
    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    check_user = await UserDAO.find_one_or_none_by_id(db=db, data_id=id.id)
    if check_user is None:
        logger.remove()
        raise UserNotFoundException
    check_user.is_banned = False
    check_user.ban_until = None
    await db.flush()
    await db.refresh(check_user)
    user = SUserInfoRole.model_validate(check_user)
    return user
