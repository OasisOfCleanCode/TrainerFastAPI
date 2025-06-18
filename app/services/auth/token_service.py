# app/services/auth/token_service.py


from datetime import datetime, timezone, timedelta
from typing import Tuple, Annotated
from app.utils.logger import logger

from jose import jwt

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import update

from app.core.config import get_api_tokens
from app.core.exceptions import TokenGenerationException
from app.db.models.enums import TokenTypeEnum
from app.db.models.user import User, Token
from app.db.schemas.user import TokenBase


async def creating_recording_access_token_to_user(
    db: AsyncSession, user: User, token_scopes: list
) -> str:
    """
    Создаёт и возвращает access token для пользователя.

    - Удаляет старые access токены не сохраняет — логика сохранения не реализована в этой функции.
    - Генерирует новый JWT access token.
    - Возвращает токен как строку.

    :param db: Асинхронная сессия базы данных.
    :param user: Объект пользователя.
    :param token_scopes: Список scopes для токена.
    :return: Строка access токена.
    """
    if not isinstance(token_scopes, list):
        token_scopes = list(token_scopes)

    access_token = creating_recording_token_to_user(
        db=db, user=user, token_scopes=token_scopes, type_token=TokenTypeEnum.ACCESS
    )

    return access_token.token


async def creating_recording_all_token_to_user(
    db: AsyncSession, user: User, token_scopes: list
) -> Annotated[Tuple[str, str], "access_token, refresh_token"]:
    """
    Создаёт и возвращает новую пару access + refresh токенов для пользователя.

    - Помечает все существующие токены пользователя как заблокированные (`ban=True`).
    - Генерирует новые access и refresh токены.
    - Сохраняет refresh токен в `user.tokens` (access — нет).
    - Логирует каждое действие.

    :param db: Асинхронная сессия базы данных.
    :param user: Объект пользователя.
    :param token_scopes: Список scopes для токенов.
    :return: Кортеж (access_token: str, refresh_token: str).
    """
    if not isinstance(token_scopes, list):
        token_scopes = list(token_scopes)

    token_stmt = await db.execute(
        update(Token).where(Token.user_id == user.id).values(ban=True)
    )

    await db.flush()
    logger.info(f"Старые токены удалены (user_id: {user.id})")

    access_token = creating_recording_token_to_user(
        db=db, user=user, token_scopes=token_scopes, type_token=TokenTypeEnum.ACCESS
    )
    if not access_token:
        logger.error(f"Ошибка при генерации access_token (user_id: {user.id})")
        raise TokenGenerationException
    logger.info(f"Новый access_token создан (user_id: {user.id})")

    refresh_token = creating_recording_token_to_user(
        db=db, user=user, token_scopes=token_scopes, type_token=TokenTypeEnum.REFRESH
    )
    if not refresh_token:
        logger.error(f"Ошибка при генерации refresh_token (user_id: {user.id})")
        raise TokenGenerationException
    logger.info(f"Новый refresh_token создан (user_id: {user.id})")

    try:
        user.tokens.append(Token(**refresh_token.model_dump()))
        await db.flush()
        logger.info(f"Токены успешно записаны! (user_id: {user.id})")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка при записи access_token, refresh_token (user_id: {user.id})"
        )
    return access_token.token, refresh_token.token


def creating_recording_token_to_user(
    db: AsyncSession,
    user: User,
    token_scopes: list,
    type_token: TokenTypeEnum = TokenTypeEnum.ACCESS,
) -> TokenBase:
    """
    Генерирует токен определённого типа (access или refresh) и возвращает его как Pydantic-модель TokenBase.

    - Вызывает `create_token` для генерации JWT.
    - Не сохраняет токен в базу данных.
    - Возвращает объект TokenBase (user_id, token, expires_at, type_token).

    :param db: Асинхронная сессия базы данных.
    :param user: Объект пользователя.
    :param token_scopes: Список scopes.
    :param type_token: Тип токена (ACCESS или REFRESH).
    :return: Объект TokenBase с данными токена.
    """

    token, expire_token = create_token(data={"sub": str(user.id)}, scopes=token_scopes)
    schema_token = TokenBase(
        user_id=user.id, token=token, expires_at=expire_token, type_token=type_token
    )
    return schema_token


def create_token(
    data: dict, scopes: list[str], type_token: TokenTypeEnum = TokenTypeEnum.ACCESS
) -> str:
    """
    Генерирует JWT токен с заданными данными, scopes и сроком действия.

    - Использует разные секреты и время жизни для access и refresh токенов.
    - Добавляет в payload: sub, scopes, exp.
    - Кодирует JWT с алгоритмом из настроек.
    - Не сохраняет токен в базу данных.

    :param data: Словарь с полезной нагрузкой (например, sub: user_id).
    :param scopes: Список разрешений (scopes), добавляемых в payload.
    :param type_token: Тип токена (по умолчанию — access).
    :return: Кортеж (JWT: str, истекает: datetime).
    """
    if type_token == TokenTypeEnum.ACCESS:
        type_secret_key = get_api_tokens().TAPI_TOKEN_ACCESS_SECRET_KEY
        expires_delta = timedelta(minutes=15)
    else:
        type_secret_key = get_api_tokens().TAPI_TOKEN_REFRESH_SECRET_KEY
        expires_delta = timedelta(days=7)

    to_encode = data.copy()
    to_encode.update({"scopes": scopes})
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})

    encode_jwt = jwt.encode(
        claims=to_encode, key=type_secret_key, algorithm=get_api_tokens().ALGORITHM
    )

    return encode_jwt, expire
