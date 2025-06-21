# app/api/v1/endpoints/user.py

import re
from datetime import timedelta, datetime, timezone
from typing import List, TypeVar

from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from app.utils.logger import logger
from pydantic import BaseModel
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi import APIRouter, Response, Depends, Request, Security, Path
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.dao.base_dao import BaseDAO
from app.db.dao.user import UsersDAO, AuthDAO
from app.db.models.associations import UserRole
from app.db.models.base_sql import IntIdSQL

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
SQL = TypeVar("SQL", bound=IntIdSQL)



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
