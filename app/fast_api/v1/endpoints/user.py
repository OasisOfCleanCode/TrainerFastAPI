# app/api/v1/endpoints/user.py

import re 
from datetime import timedelta, datetime, timezone
from typing import List, TypeVar

from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt  
from loguru import logger
from pydantic import BaseModel
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi import APIRouter, Response, Depends, Request, Security, Path
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.base import BeaHeaUserAPI
from app.core.config import TOKEN_ACCESS_SECRET_KEY, ALGORITHM
from app.db.dao.base_dao import BaseDAO
from app.db.dao.user import UsersDAO, AuthDAO
from app.db.models.associations import UserRole
from app.db.models.base_sql import BaseSQL

from app.core.exceptions import *
from app.core.responses import *
from app.db.models.enums import BanTimeEnum, TokenTypeEnum
from app.db.models.user import (
    User,
    Profile,
    Role,
    Token,
    EmailVerificationToken,
    ChangeEmailVerificationToken,
    ResetPasswordToken,
)
from app.db.schemas.user import (
    ProfileModel,
    CheckIDModel,
    RoleModel,
    CheckTimeBan,
    SUserRefreshPassword,
    SUserRegister,
    EmailModel,
    SUserAddDB,
    PhoneModel,
    CheckTokenModel,
    ResetPasswordSchema,
)
from app.db.sessions import SessionDep, TransactionSessionDep

DAO = TypeVar("DAO", bound=BaseDAO)
PYDANTIC = TypeVar("PYDANTIC", bound=BaseModel)
SQL = TypeVar("SQL", bound=BaseSQL)


class ProfileAPI(BeaHeaUserAPI):

    def __init__(self):
        super().__init__()
        # Установка маршрутов и тегов
        self.prefix = f"/me/profile"
        self.tags = ["Profile"]
        self.router = APIRouter(prefix=self.prefix, tags=self.tags)

    async def setup_routes(self):
        await self.get_profile()
        await self.put_profile()

    async def get_profile(self):
        @self.router.get("", responses=profile_get_resps)
        async def get_profile(
            db: AsyncSession = SessionDep,
            user_data: User = Security(self.get_current_user, scopes=["USER"]),
        ) -> ProfileInfo:
            """
            ## Endpoint запроса данных профиля пользователя системы.

            ### Описание
            - Возвращает данные профиля пользователя сделавшего запрос.
            - Endpoint доступен для всех авторизовавшихся пользователей.

            ### Требования
            - Этот эндпоинт не требует передачи данных в теле запроса.
            - Пользователь должен быть авторизован (наличие токена в cookie-файле).
            """

            if user_data is None:
                logger.remove()
                raise UserNotFoundException
            profile_dict = user_data.profile.to_dict_one_lap()
            profile_dict["user_id"] = user_data.id
            profile = ProfileInfo(**profile_dict)
            return profile

    async def put_profile(self):
        @self.router.put("", responses=profile_put_resps)
        async def put_profile(
            schema: ProfileModel,
            db: AsyncSession = TransactionSessionDep,
            user_data: User = Security(self.get_current_user, scopes=["USER"]),
        ) -> ProfileInfo:
            """
            ## Endpoint обновления профиля пользователя системы.

            ### Описание
            - Endpoint обновляет профиль пользователя
            - Endpoint доступен для всех авторизовавшихся пользователей.
            - Возвращает данные пользователя сделавшего запрос.

            ### Требования
            - Этот эндпоинт не требует передачи данных в теле запроса.
            - Пользователь должен быть авторизован (наличие токена в cookie-файле).
            """

            if user_data is None:
                logger.remove()
                raise UserNotFoundException

            # Явно загружаем пользователя в текущую сессию
            user = await db.get(User, user_data.id)
            if not user:
                logger.remove()
                raise UserNotFoundException

            profile_dict = schema.model_dump(exclude_none=True)

            try:
                if user.profile is None:
                    new_profile = Profile(**profile_dict)
                    db.add(new_profile)
                    await db.flush()
                    user.profile_id = new_profile.id
                    # Явно добавляем пользователя в сессию для обновления
                    db.add(user)
                else:
                    for key, value in profile_dict.items():
                        setattr(user.profile, key, value)

                await db.commit()  # Фиксируем изменения
                await db.refresh(user)  # Теперь refresh будет работать

                profile_dict = user.profile.to_dict_one_lap()
                profile_dict["user_id"] = user.id
                return ProfileInfo(**profile_dict)

            except SQLAlchemyError as e:
                await db.rollback()
                logger.error(
                    f"Ошибка при обновлении профиля пользователя {user.id}: {e}"
                )
                raise UpdateException


class AdminAPI(BeaHeaUserAPI):

    def __init__(self):
        super().__init__()
        # Установка маршрутов и тегов
        self.prefix = f"/user"
        self.tags = ["Admin Panel"]
        self.router = APIRouter(prefix=self.prefix, tags=self.tags)

    async def setup_routes(self):

        await self.get_user_by_id()
        await self.get_user_by_email()
        await self.get_user_by_phone_number()
        await self.get_users()
        await self.get_user_roles()
        await self.post_user_role()
        await self.delete_user_role()
        await self.ban_on_user()
        await self.ban_off_user()

    async def get_user_by_id(self):
        @self.router.get("/{id}", responses=user_get_resps)
        async def get_user_by_id(
            db: AsyncSession = SessionDep,
            id: CheckIDModel = Depends(),
            user_data: User = Security(
                self.get_current_user, scopes=["ADMIN", "SYSADMIN"]
            ),
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
            check_user = await UsersDAO.find_one_or_none(db=db, filters=id)
            if check_user is None:
                logger.remove()
                raise UserNotFoundException
            user = SUserInfoRole.model_validate(check_user)
            return user

    async def get_user_by_email(self):
        @self.router.get("/email/{address}", responses=user_get_resps)
        async def get_email(
            db: AsyncSession = SessionDep,
            address: CheckEmailModel = Depends(),
            user_data: User = Security(
                self.get_current_user, scopes=["ADMIN", "SYSADMIN"]
            ),
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
            check_user = await UsersDAO.find_one_or_none(db=db, filters=address)
            if check_user is None:
                logger.remove()
                raise UserNotFoundException
            user = SUserInfoRole.model_validate(check_user)
            return user

    async def get_user_by_phone_number(self):
        @self.router.get("/phone/{number}", responses=user_get_resps)
        async def get_email(
            db: AsyncSession = SessionDep,
            number: CheckPhoneModel = Depends(),
            user_data: User = Security(
                self.get_current_user, scopes=["ADMIN", "SYSADMIN"]
            ),
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
            check_user = await UsersDAO.find_one_or_none(db=db, filters=number)
            if check_user is None:
                logger.remove()
                raise UserNotFoundException
            user = SUserInfoRole.model_validate(check_user)
            return user

    async def get_users(self):
        @self.router.get("/all", responses=users_get_resps)
        async def get_users(
            db: AsyncSession = SessionDep,
            adm_data: User = Security(
                self.get_current_user, scopes=["ADMIN", "SYSADMIN"]
            ),
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
            all_user = await UsersDAO.find_all(db=db, filters=None)
            all_user = [
                SUserInfoRole.model_validate(user_data) for user_data in all_user
            ]

            return all_user

    async def get_user_roles(self):
        @self.router.get("/{id}/role", responses=role_get_resps)
        async def get_user_roles(
            user_data: User = Security(
                self.get_current_user, scopes=["ADMIN", "SYSADMIN"]
            ),
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
            check_user = await UsersDAO.find_one_or_none(db=db, filters=id)
            if check_user is None:
                logger.remove()
                raise UserNotFoundException
            roles = SRoleInfo.model_validate(check_user)
            return roles

    async def post_user_role(self):
        @self.router.post("/{id}/role", responses=role_post_resps)
        async def post_user_role(
            user_data: User = Security(
                self.get_current_user, scopes=["ADMIN", "SYSADMIN"]
            ),
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
            check_user = await UsersDAO.find_one_or_none_by_id(db=db, data_id=id.id)
            if check_user is None:
                logger.remove()
                raise UserNotFoundException
            if schema_role.role in check_user.roles:
                logger.remove()
                raise RoleAlreadyAssignedException
            stmt = (
                select(Role)
                .options(selectinload(Role.users_assoc).joinedload(UserRole.user))
                .where(Role.name == schema_role.role)
            )
            role = await db.scalar(stmt)
            # Проверяем, что пользователя еще нет в ассоциации для роли
            if any(assoc.user_id == check_user.id for assoc in role.users_assoc):
                logger.remove()
                raise RoleAlreadyAssignedException

            # Добавляем связь между role и user
            check_user.roles_assoc.append(UserRole(role=role))  # И к пользователю
            await db.flush()
            # Валидация и возврат результата
            user = SUserInfoRole.model_validate(check_user)
            return user

    async def delete_user_role(self):
        @self.router.delete("/{id}/role", responses=role_del_resps)
        async def delete_user_role(
            user_data: User = Security(
                self.get_current_user, scopes=["ADMIN", "SYSADMIN"]
            ),
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
            check_user = await UsersDAO.find_one_or_none_by_id(db=db, data_id=id.id)
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
                logger.error(
                    f"Ошибка у user: {check_user.id}, {self.name_model} - delete_role: {e}"
                )
                logger.remove()
                raise DeleteException

    async def ban_on_user(self):
        @self.router.put("/{id}/ban_on", responses=role_post_resps)
        async def ban_on_user(
            user_data: User = Security(
                self.get_current_user, scopes=["ADMIN", "SYSADMIN"]
            ),
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
            check_user = await UsersDAO.find_one_or_none_by_id(db=db, data_id=id.id)
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

    async def ban_off_user(self):
        @self.router.put("/{id}/ban_off", responses=role_post_resps)
        async def ban_off_user(
            user_data: User = Security(
                self.get_current_user, scopes=["ADMIN", "SYSADMIN"]
            ),
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
            check_user = await UsersDAO.find_one_or_none_by_id(db=db, data_id=id.id)
            if check_user is None:
                logger.remove()
                raise UserNotFoundException
            check_user.is_banned = False
            check_user.ban_until = None
            await db.flush()
            await db.refresh(check_user)
            user = SUserInfoRole.model_validate(check_user)
            return user


class UserAPI(BeaHeaUserAPI):

    def __init__(self):
        super().__init__()
        # Установка маршрутов и тегов
        self.prefix = f"/me"
        self.tags = ["Me"]
        self.router = APIRouter(prefix=self.prefix, tags=self.tags)

    async def setup_routes(self):
        await self.get_me()
        await self.get_roles()
        await self.get_email()
        await self.post_email()
        await self.put_email()
        await self.delete_email()
        await self.send_verify_email()
        await self.get_phone_number()
        await self.post_phone_number()
        await self.put_phone_number()
        await self.delete_phone_number()
        await self.put_password()

    async def get_me(self):
        @self.router.get("", responses=user_get_resps)
        async def get_me(
            db: AsyncSession = SessionDep,
            user_data: User = Security(self.get_current_user, scopes=["USER"]),
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

    async def get_roles(self):
        @self.router.get("/role", responses=role_get_resps)
        async def get_roles(
            user_data: User = Security(
                self.get_current_user, scopes=["DEVELOPER", "ADMIN", "SYSADMIN"]
            ),
            db: AsyncSession = SessionDep,
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

    async def get_email(self):
        @self.router.get("/email", responses=email_phone_resps)
        async def get_email(
            db: AsyncSession = SessionDep,
            user_data: User = Security(self.get_current_user, scopes=["USER"]),
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

    async def post_email(self):
        @self.router.post("/email", responses=user_get_resps)
        async def post_email(
            email: CheckEmailModel,
            db: AsyncSession = TransactionSessionDep,
            user_data: User = Security(self.get_current_user, scopes=["USER"]),
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
            check_email = (
                await db.execute(select(User).where(User.email == email.email))
            ).scalar_one_or_none()
            if check_email:
                logger.remove()
                raise EmailAlreadyExistsException
            if user_data.email:
                logger.remove()
                raise PhoneAlreadyExistsException
            user_data.email = email.email
            await db.flush()
            user = SUserInfoRole.model_validate(user_data)
            return user

    async def put_email(self):
        @self.router.put("/email", responses=user_get_resps)
        async def put_email(
            email: CheckEmailModel,
            db: AsyncSession = TransactionSessionDep,
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
            check_email = (
                await db.execute(select(User).where(User.email == email.email))
            ).scalar_one_or_none()
            if check_email:
                logger.remove()
                raise EmailAlreadyExistsException
            try:
                verify = await self.send_change_verify_email_to_user(
                    db=db, email=user_data.email, new_email=email.email
                )
                return verify
            except SQLAlchemyError as e:
                logger.error(f"Ошибка при обновлении email: {e}")
                raise UpdateException

    async def delete_email(self):
        @self.router.delete("/email", responses=user_get_resps)
        async def delete_email(
            db: AsyncSession = TransactionSessionDep,
            user_data: User = Security(
                self.get_current_user, scopes=["DEVELOPER", "ADMIN", "SYSADMIN"]
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

    async def send_verify_email(self):
        @self.router.post("/email/verify", responses=email_verify_resps)
        async def send_verify_email(
            response: Response,
            user_data: User = Security(self.get_current_user, scopes=["USER"]),
            db: AsyncSession = TransactionSessionDep,
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

            verify = await self.send_verify_email_to_user(db=db, email=user_data.email)
            return verify

    async def get_phone_number(self):
        @self.router.get("/phone", responses=email_phone_resps)
        async def get_email(
            db: AsyncSession = SessionDep,
            user_data: User = Security(self.get_current_user, scopes=["USER"]),
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

    async def post_phone_number(self):
        @self.router.post("/phone", responses=user_get_resps)
        async def post_phone_number(
            phone_number: CheckPhoneModel,
            db: AsyncSession = TransactionSessionDep,
            user_data: User = Security(self.get_current_user, scopes=["USER"]),
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

    async def put_phone_number(self):
        @self.router.put("/phone", responses=user_get_resps)
        async def put_phone_number(
            phone_number: CheckPhoneModel,
            db: AsyncSession = TransactionSessionDep,
            user_data: User = Security(self.get_current_user, scopes=["USER"]),
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

    async def delete_phone_number(self):
        @self.router.delete("/phone", responses=user_get_resps)
        async def put_phone_number(
            db: AsyncSession = TransactionSessionDep,
            user_data: User = Security(
                self.get_current_user, scopes=["DEVELOPER", "ADMIN", "SYSADMIN"]
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

    async def put_password(self):
        @self.router.put("/password", responses=user_get_resps)
        async def put_password(
            schema: SUserRefreshPassword,
            db: AsyncSession = TransactionSessionDep,
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
            pass_verify = await AuthDAO.verify_password(
                schema.password, user_data.password
            )
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


class AuthAPI(BeaHeaUserAPI):

    def __init__(self):
        super().__init__()
        # Установка маршрутов и тегов
        self.tags = ["Auth"]
        self.router = APIRouter(tags=self.tags)

    async def setup_routes(self):
        await self.register()
        await self.login()
        await self.logout()
        await self.refresh()

    async def register(self):
        @self.router.post(
            "/register",
            responses=register_resps,
            # Описание для Swagger/OpenAPI документации:
            summary="Регистрация нового пользователя",
            response_description="Успешная регистрация. Возвращает access token и устанавливает cookies.",
        )
        async def register_user(
            request: Request,
            user_data: SUserRegister,
            db: AsyncSession = TransactionSessionDep,
            csrf_validation: None = Depends(self.validate_csrf_token),
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
                user_email = await UsersDAO.find_one_or_none(
                    db=db, filters=EmailModel(email=user_data.email)
                )

            if user_data.phone_number:
                phone_mess = f"телефоном {user_data.phone_number}"
                user_phone = await UsersDAO.find_one_or_none(
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
            new_user = await UsersDAO.add(db=db, values=SUserAddDB(**user_data_dict))
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
                    .options(selectinload(Role.users_assoc).joinedload(UserRole.user))
                    .where(Role.name == r_scope)
                )
                roles = await db.scalars(stmt)
                for role in roles:
                    role.users_assoc.append(UserRole(user=new_user))
            user = await UsersDAO.find_one_or_none_by_id_with_tokens(
                db=db, data_id=new_user.id
            )
            access_token, refresh_token = (
                await AuthDAO.creating_recording_all_token_to_user(
                    db=db, user=user, token_scopes=scopes_rights
                )
            )
            response = await self.response_access_refresh_token(
                access_token, refresh_token
            )
            if user_data.email:
                await self.send_verify_email_to_user(email=user_data.email, db=db)

            logger.info(f"Пользователь {new_user.id}" f" успешно зарегистрирован.")
            return response

    async def login(self):
        @self.router.post(
            "/login",
            responses=login_resps,
            # Описание для Swagger/OpenAPI документации:
            summary="Аутентификация пользователя",
            response_description="Успешная аутентификация. Возвращает access token и устанавливает cookies.",
        )
        async def login_user(
            form_data: OAuth2PasswordRequestForm = Depends(),
            db: AsyncSession = TransactionSessionDep,
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
                user = await AuthDAO.authenticate_user(
                    db=db, email=user_model.email, password=password
                )
                if user is None:
                    logger.remove()
                    raise EmailOrPasswordInvalidException
            elif re.match(r"^\+\d{5,15}$", username):  # Если это телефон
                user_model = PhoneModel(phone_number=username)
                user = await AuthDAO.authenticate_user(
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
            token_scopes_stmt = select(UserRole.role_name).where(
                UserRole.user_id == user.id
            )

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

            access_token, refresh_token = (
                await AuthDAO.creating_recording_all_token_to_user(
                    db=db, user=user, token_scopes=token_scopes
                )
            )
            response = await self.response_access_refresh_token(
                access_token, refresh_token
            )
            await db.commit()
            logger.info(
                f"Пользователь {user.id}"
                f" успешно вошел в систему. Доступы: {list(token_scopes)}"
            )
            return response

    async def logout(self):
        @self.router.post("/logout", responses=logout_resps)
        async def logout_user(
            response: Response,
            user_data: User = Security(self.get_current_user, scopes=["USER"]),
            db: AsyncSession = TransactionSessionDep,
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
            user_data.access_token_assoc.ban = True
            user_data.refresh_token_assoc.ban = True
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

    async def refresh(self):
        @self.router.put("/refresh", responses=login_resps)
        async def refresh(request: Request, db: AsyncSession = TransactionSessionDep):
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
                        refresh_token, TOKEN_ACCESS_SECRET_KEY, algorithms=[ALGORITHM]
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

                user = await UsersDAO.find_one_or_none_by_id_with_tokens(
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

                access_token = await AuthDAO.creating_recording_access_token_to_user(
                    db=db, user=user, token_scopes=token_scopes
                )

                response = await self.response_access_refresh_token(access_token)

                logger.info(
                    f"Пользователь {user.id}"
                    f" успешно обновил refresh token. Доступы: {list(token_scopes)}"
                )
                return response

            except JWTError:
                raise CredentialsValidationException


class SecurityAPI(AuthAPI):
    def __init__(self):
        super().__init__()
        # Установка маршрутов и тегов
        self.tags = ["Security"]
        self.router = APIRouter(tags=self.tags)

    async def setup_routes(self):
        await self.check_email()
        await self.check_phone()
        await self.get_roles()
        await self.send_reset_password()

    async def send_reset_password(self):
        @self.router.post("/password/reset", responses=password_reset_resps)
        async def send_reset_password(
            response: Response,
            email: CheckEmailModel,
            db: AsyncSession = TransactionSessionDep,
        ):
            """
            ## Endpoint запроса на сброс пароля.

            ### Описание
            - Генерирует токен и с помощью его формирует ссылку для страницы сброса пароля.
            - Отправляет ссылку на email пользователя.
            - Пользователь переходит по ссылке и вводит новый пароль.
            - Проходит проверка токена и далее смена пароля
            - Возвращает сообщение о статусе операции.

            ### Требования
            - Этот эндпоинт требует передачи email адреса в теле запроса.
            - Пользователь не должен быть авторизован.
            """

            verify = await self.send_reset_password_to_user(db=db, email=email.email)
            return verify

    async def check_email(self):
        @self.router.get("/email", responses=check_email_resps)
        async def check_email(
            data: CheckEmailModel = Depends(), db: AsyncSession = SessionDep
        ):
            """
            ## Endpoint проверки существования email в базе данных.
            ### Описание
            Этот эндпоинт доступен для всех.

            ### Требования
            - Этот эндпоинт не требует передачи данных в теле запроса.
            - Пользователь не должен быть авторизован.
            """
            logger.info(f"Проверка email: {data.email}")

            try:
                exists = await UsersDAO.find_one_or_none(db=db, filters=data)
                if exists:
                    logger.info(f"Email {data.email} существует в базе.")
                    return JSONResponse(
                        status_code=200,
                        content={
                            "status": "success",
                            "message": "Email exists",
                            "data": {"exists": True},
                        },
                    )
                else:
                    logger.info(f"Email {data.email} не найден.")
                    return JSONResponse(
                        status_code=200,
                        content={
                            "status": "success",
                            "message": "Email not found",
                            "data": {"exists": False},
                        },
                    )
            except Exception as e:
                logger.error(f"Ошибка при проверке email: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": "Database error",
                        "error": str(e),
                    },
                )

    async def check_phone(self):
        @self.router.get("/phone", responses=check_phone_resps)
        async def check_phone(
            data: CheckPhoneModel = Depends(), db: AsyncSession = SessionDep
        ):
            """
            ## Endpoint проверки существования номера телефона в базе данных.
            ### Описание
            Этот эндпоинт доступен для всех.

            ### Требования
            - Этот эндпоинт не требует передачи данных в теле запроса.
            - Пользователь не должен быть авторизован.
            """
            logger.info(f"Проверка номера телефона: {data.phone_number}")

            try:
                exists = await UsersDAO.find_one_or_none(db=db, filters=data)

                if exists:
                    logger.info(
                        f"Номер телефона {data.phone_number} существует в базе."
                    )
                    return JSONResponse(
                        status_code=200,
                        content={
                            "status": "success",
                            "message": "Phone number exists",
                            "data": {"exists": True},
                        },
                    )
                else:
                    logger.info(f"Номер телефона {data.phone_number} не найден.")
                    return JSONResponse(
                        status_code=200,
                        content={
                            "status": "success",
                            "message": "Phone number not found",
                            "data": {"exists": False},
                        },
                    )
            except Exception as e:
                logger.error(f"Ошибка при проверке email: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": "Database error",
                        "error": str(e),
                    },
                )

    async def get_roles(self):
        @self.router.get("/roles", responses=role_get_resps)
        async def get_roles(
            db: AsyncSession = SessionDep,
            user_data: User = Security(
                self.get_current_user, scopes=["ADMIN", "SYSADMIN"]
            ),
        ):
            """
            ## Endpoint извлекает все роли доступные в системе.
            ### Описание
            Возвращает роли пользователя системы в виде списка.
            Этот эндпоинт доступен только для администраторов.
            Если текущий пользователь не является ADMIN, SYSADMIN, доступ будет запрещен.

            ### Требования
            - Этот эндпоинт не требует передачи данных в теле запроса.
            - Пользователь должен быть авторизован (наличие токена в cookie-файле).
            """
            result = await db.execute(select(Role.name))
            roles = result.scalars().all()
            roles = [role.name for role in roles]
            roles = SRoleInfo(roles=roles)
            return roles


class BackgroundAPI(AuthAPI):
    def __init__(self):
        super().__init__()
        # Установка маршрутов и тегов
        self.tags = ["Background"]
        self.router = APIRouter(tags=self.tags)

    async def setup_routes(self):
        await self.verify_email()
        await self.verify_email_for_change_email()
        await self.applying_new_password()

    async def verify_email(self):
        @self.router.get("/email/verify/{token}", response_class=HTMLResponse)
        async def verify_email(
            token: str = Path(), db: AsyncSession = TransactionSessionDep
        ):
            """
            ## Endpoint верификации email адреса.

            ### Описание
            - Ручной способ верификации по токену.
            - Возвращает сообщение о статусе операции.
            - Endpoint доступен для всех.

            ### Требования
            - Этот эндпоинт требует передачи данных в строке запроса.
            - Пользователь не должен быть авторизован.
            """
            verify_token = CheckTokenModel(token=token)
            token_data = await db.execute(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.token == verify_token.token
                )
            )
            token_data = token_data.scalar_one_or_none()
            if not token_data:
                return TokenNotFoundException
            if datetime.now(timezone.utc) > token_data.expires_at or token_data.ban:
                return TokenExpiredException
            email_schema = CheckEmailModel(email=token_data.email)
            check_user = await UsersDAO.find_one_or_none(db=db, filters=email_schema)
            if not check_user:
                return UserNotFoundException
            token_data.ban = True
            check_user.is_email_confirmed = True
            await db.flush()
            return JSONResponse(
                status_code=200,
                content={"message": "Email Successfully confirmed"},
                headers={"X-Success-Code": "2032"},
            )

    async def verify_email_for_change_email(self):
        @self.router.get("/email/change/verify/{token}")
        async def verify_email_for_change_email(
            token: str = Path(), db: AsyncSession = TransactionSessionDep
        ):
            """
            ## Endpoint верификации нового email адреса.

            ### Описание
            - Ручной способ верификации нового email адреса по токену.
            - Возвращает сообщение о статусе операции и меняет email при удаче.
            - Endpoint доступен для всех.

            ### Требования
            - Этот эндпоинт требует передачи данных в строке запроса.
            - Пользователь не должен быть авторизован.
            """
            verify_token = CheckTokenModel(token=token)
            token_data = await db.execute(
                select(ChangeEmailVerificationToken).where(
                    ChangeEmailVerificationToken.token == verify_token.token
                )
            )
            token_data = token_data.scalar_one_or_none()
            if not token_data:
                return TokenNotFoundException
            if datetime.now(timezone.utc) > token_data.expires_at or token_data.ban:
                return TokenExpiredException
            email_schema = CheckEmailModel(email=token_data.email)
            check_user = await UsersDAO.find_one_or_none(db=db, filters=email_schema)
            if not check_user:
                return UserNotFoundException
            try:

                token_data.ban = True

                check_user.email = token_data.new_email
                check_user.is_email_confirmed = True
                await db.flush()
            except SQLAlchemyError as e:
                logger.error(f"Ошибка при обновлении email: {e}")
                raise UpdateException
            user = SUserInfoRole.model_validate(check_user)
            answer = user.model_dump(exclude_none=True)
            return JSONResponse(
                status_code=200, content=answer, headers={"X-Success-Code": "2032"}
            )

    async def applying_new_password(self):
        @self.router.post("/password/apply")
        async def applying_new_password(
            form_data: ResetPasswordSchema = Depends(ResetPasswordSchema.as_form),
            db: AsyncSession = TransactionSessionDep,
        ) -> JSONResponse:
            """
            ## Endpoint сброса пароля.

            ### Описание
            - Ручной способ сброса пароля. На него с фронта приходят данные для обновления пароля после перехода по ссылке, которую пользователе получил по email.
            - Возвращает сообщение о статусе операции.
            - Endpoint доступен для всех.

            ### Требования
            - Этот эндпоинт требует передачи данных в теле запроса в виде **form_data (application/x-www-form-urlecoded**).
            - Пользователь не должен быть авторизован.
            """

            verify_token = CheckTokenModel(token=form_data.token)
            token_data = await db.execute(
                select(ResetPasswordToken).where(
                    ResetPasswordToken.token == verify_token.token
                )
            )
            token_data = token_data.scalar_one_or_none()
            if not token_data:
                return TokenNotFoundException
            if datetime.now(timezone.utc) > token_data.expires_at or token_data.ban:
                return TokenExpiredException
            email_schema = CheckEmailModel(email=token_data.email)
            check_user = await UsersDAO.find_one_or_none(db=db, filters=email_schema)
            if not check_user:
                return UserNotFoundException
            check_user.password = form_data.password
            await db.flush()
            return JSONResponse(
                status_code=200,
                content={"message": "The password is successfully updated"},
                headers={"X-Success-Code": "2033"},
            )
