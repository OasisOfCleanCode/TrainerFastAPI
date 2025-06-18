# app/services/auth/authentication_service.py

from datetime import datetime, timezone, timedelta

from app.db.dao.user import UserDAO
from app.db.models import User
from app.utils.logger import logger

from passlib.context import CryptContext

from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi.responses import JSONResponse

from app.core.exceptions import RefreshPasswordInvalidException
from app.db.schemas.user import PhoneModel, EmailModel
from app.db.sessions import SessionDep


import bcrypt

bcrypt.__about__ = bcrypt


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет соответствие введённого пароля и хэша пароля из базы данных.

    - Использует bcrypt через passlib для сравнения паролей.
    - Не сохраняет ничего в базу.
    - Логирует успешную или неудачную попытку верификации пароля.

    :param plain_password: Пароль, введённый пользователем.
    :param hashed_password: Хэшированный пароль, хранящийся в БД.
    :return: True, если пароли совпадают, иначе False.
    """
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    is_valid = pwd_context.verify(plain_password, hashed_password)
    if is_valid:
        logger.info("Пароль успешно верифицирован")
    else:
        logger.warning("Ошибка верификации пароля")
    return is_valid


async def authenticate_user(
    db: SessionDep, password: str, email: EmailStr = None, phone: PhoneModel = None
):
    """
    Аутентифицирует пользователя по email или телефону и паролю.

    - Ищет пользователя в базе с его токенами.
    - Проверяет пароль через `verify_password`.
    - Если пароль не совпадает — выбрасывает исключение.
    - Ничего не сохраняет в базу.

    :param password: Пароль, введённый пользователем.
    :param email: Email пользователя (опционально).
    :param phone: Телефон пользователя (опционально).
    :param db: Асинхронная сессия базы данных.
    :return: Объект пользователя или None, если не найден.
    """
    user = None
    if email:
        user = await UserDAO.find_one_user_or_none_with_tokens(
            filters=EmailModel(email=email)
        )
    elif phone:
        user = await UserDAO.find_one_user_or_none_with_tokens(filters=PhoneModel)
    if user:
        is_verified = await verify_password(
            plain_password=password, hashed_password=user.password
        )
        if is_verified is False:
            logger.remove()
            raise RefreshPasswordInvalidException
    return user


async def handle_failed_login(user: User, db: AsyncSession):
    """
    Обрабатывает неудачную попытку входа пользователя.

    - Увеличивает счётчик `failed_attempts`.
    - Если попыток становится ≥ 10:
        - Устанавливает `is_banned = True`
        - Устанавливает `ban_until` на 10 минут вперёд
        - Логирует бан
        - Сохраняет изменения в БД
        - Возвращает JSONResponse 403 с описанием блокировки
    - В противном случае просто сохраняет `failed_attempts`.

    :param user: Объект пользователя.
    :param db: Асинхронная сессия базы данных.
    :return: None или JSONResponse 403, если пользователь заблокирован.
    """
    # Проверяем, забанен ли пользователь
    if user.is_banned:
        return None

    # Увеличиваем количество неудачных попыток
    user.failed_attempts += 1

    # Если количество неудачных попыток достигло 10, блокируем пользователя
    if user.failed_attempts >= 10:
        user.is_banned = True
        user.ban_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        await db.commit()

        ban_until_str = user.ban_until.strftime("%Y-%m-%d %H:%M:%S %Z")
        logger.warning(
            f"Пользователь {user.email} заблокирован на 10 минут до {ban_until_str}."
        )

        return JSONResponse(
            status_code=403,
            content={
                "status": "error",
                "message": f"User {user.email} is banned for 10 minutes due to too many "
                f"failed login attempts. Blocked until: {ban_until_str}",
                "error_code": 1006,
            },
        )

    await db.commit()  # Сохраняем изменения после увеличения попыток
    return None


async def check_user_ban(user: User, db: AsyncSession):
    """
    Проверяет, забанен ли пользователь, и снимает бан, если срок блокировки истёк.

    - Если `is_banned = False`, возвращает None.
    - Если бан истёк:
        - Обнуляет `is_banned`, `failed_attempts`, `ban_until`
        - Сохраняет изменения в БД
        - Возвращает None
    - Если бан активен:
        - Возвращает строку с оставшимся временем блокировки

    :param user: Объект пользователя.
    :param db: Асинхронная сессия базы данных.
    :return: None, если пользователь не забанен, или строка вида "N minute(s)", если бан активен.
    """
    if not user.is_banned:
        return None

    # Приводим оба времени к UTC для точности и логируем для отладки
    ban_until_utc = user.ban_until.replace(
        tzinfo=timezone.utc
    )  # Принудительно устанавливаем UTC для ban_until
    current_time_utc = datetime.now(timezone.utc)

    # Проверяем, истёк ли бан
    if current_time_utc >= ban_until_utc:
        # Бан истёк, снимаем блокировку
        user.is_banned = False
        user.failed_attempts = 0
        user.ban_until = None
        await db.commit()
        logger.info(f"Бан пользователя {user.email} снят, так как время бана истекло.")
        return None

    # Вычисляем оставшееся время
    remaining_ban_time = ban_until_utc - current_time_utc
    remaining_seconds = int(remaining_ban_time.total_seconds())
    remaining_minutes, _ = divmod(remaining_seconds, 60)

    # Формируем строку с оставшимся временем
    remaining_time_str = f"{remaining_minutes} minute(s)"

    logger.warning(
        f"Пользователь {user.email} забанен. Оставшееся время бана: {remaining_time_str}."
    )
    return remaining_time_str


async def remove_bans(db: AsyncSession):
    """
    Снимает бан со всех пользователей, у которых истёк срок блокировки.

    - Ищет всех пользователей, у которых:
        - `is_banned = True`
        - `ban_until` <= текущее UTC-время
    - Обнуляет у них `is_banned`, `failed_attempts`, `ban_until`.
    - Сохраняет изменения в базу.
    - Логирует результат.

    :param db: Асинхронная сессия базы данных.
    :return: Список разблокированных пользователей.
    """
    now = datetime.now(timezone.utc)
    query = select(User).where(and_(User.is_banned, User.ban_until <= now))
    result = await db.execute(query)
    users_to_unban = result.scalars().all()

    for user in users_to_unban:
        user.is_banned = False
        user.failed_attempts = 0
        user.ban_until = None

    await db.commit()
    for user in users_to_unban:
        logger.info(f"Пользователь {user.email} успешно разблокирован.")

    return users_to_unban
