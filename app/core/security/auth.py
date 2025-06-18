# app/core/security/auth.py

import secrets
from datetime import datetime, timezone

from jose import jwt, JWTError, ExpiredSignatureError
from app.utils.logger import logger

from fastapi import Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    TokenExpiredException,
    InvalidJWTException,
    UserIdNotFoundException,
    ForbiddenAccessException,
    UserNotFoundException,
    TokenMismatchException,
    UserBannedException,
)
from app.db.models import User, Token
from app.db.models.enums import TokenTypeEnum
from app.db.sessions import TransactionSessionDep

from app.core.config import get_api_tokens


oauth2_scopes = {
    "USER": "Стандартный пользовательский доступ.",
    "DEVELOPER": "Доступ для разработчиков",
    "ADMIN": "Администраторский доступ с ограничениями.",
    "SYSADMIN": "Администраторский доступ без ограничений.",
    "MANAGER": "Менеджерский доступ",
    "SUPPORT": "Доступ для тех.поддержки",
    "MODERATOR": "Доступ для модераторов",
}

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/login",
    scopes=oauth2_scopes,
    scheme_name="JWT Bearer Token",  # Название схемы безопасности, которое будет видно в OpenAPI
    description="""
    OAuth2 схема аутентификации с использованием JWT токена. Эндпоинт авторизации поддерживает два типа грантов: 
    1. **`password`** - аутентификация с использованием имени пользователя (email или телефон) и пароля.
    2. **`refresh_token`** - обновление токена доступа с помощью предоставленного refresh_token.

    Для получения токенов доступа (access_token) и обновления токенов (refresh_token) используется следующая логика:
    - При `grant_type=password` генерируется новый `access_token` (сроком на 30 минут) и `refresh_token`.
    - При `grant_type=refresh_token` обновляется `access_token` и возвращается новый `refresh_token` в cookies.

    Необходимость в предоставлении токена актуальна для всех защищенных эндпоинтов.
    """,
)


async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Security(oauth2_scheme),
    session: AsyncSession = TransactionSessionDep,
) -> User:
    try:
        payload = jwt.decode(
            token,
            get_api_tokens().TAPI_TOKEN_ACCESS_SECRET_KEY,
            algorithms=[get_api_tokens().ALGORITHM],
        )
        user_id: str = payload.get("sub")
        token_scopes = payload.get("scopes", [])
        expire: str = payload.get("exp")
    except ExpiredSignatureError:
        logger.remove()
        raise TokenExpiredException  # Если refresh_token отсутствует или заблокирован
    except JWTError:
        logger.remove()
        raise InvalidJWTException

    if not user_id:
        logger.remove()
        raise UserIdNotFoundException

    rig = False
    if not security_scopes.scopes:
        rig = True
    for scope in security_scopes.scopes:
        if scope in token_scopes:
            rig = True
    if not rig:
        logger.remove()
        raise ForbiddenAccessException

    expire_time = datetime.fromtimestamp(int(expire), tz=timezone.utc)
    if not expire or expire_time < datetime.now(timezone.utc):
        logger.remove()
        raise TokenExpiredException

    user = await UsersDAO.find_one_or_none_by_id_with_tokens(
        data_id=int(user_id), db=session
    )
    if not user:
        logger.remove()
        raise UserNotFoundException

    check_access_token = (
        await session.execute(
            select(Token).where(
                Token.user_id == user.id,
                Token.token_type == TokenTypeEnum.ACCESS,
                Token.ban == False,
                Token.token == token,
            )
        )
    ).scalar_one_or_none()
    if not check_access_token:
        logger.remove()
        raise TokenMismatchException

    user.last_login_attempt = datetime.now(tz=timezone.utc)

    if user.is_banned:
        logger.remove()
        raise UserBannedException
    return user


async def response_access_refresh_token(
    access_token: str, refresh_token: str = None
) -> JSONResponse:
    response = JSONResponse(
        status_code=200,
        content={
            "access_token": access_token,
            "token_type": "bearer",
        },
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="None",
    )
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="None",
        )

    # Устанавливаем CSRF-токен в cookie (не HttpOnly, чтобы он был доступен на клиенте)
    csrf_token = secrets.token_hex(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # Доступен на фронтенде
        secure=True,
        samesite="None",
    )

    return response
