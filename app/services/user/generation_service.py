# app/services/user/generation_service.py

import random

from sqlalchemy import select, literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.utils.logger import logger


async def generate_username() -> str:
    """
    Генерирует псевдослучайное имя пользователя.

    - Использует случайное прилагательное, животное и двузначное число.
    - Не обращается к базе данных.
    - Имя может быть неуникальным — уникальность должна проверяться отдельно, если необходимо.
    - Логирует сгенерированное имя.

    :return: Строка — сгенерированное имя пользователя (например, "happyfox42").
    """
    adjectives = ["cool", "fast", "cuted", "bright", "wild", "crazy", "funny", "happy", "smart", "brave"]
    animals = ["dog", "cat", "wolf", "fox", "bear", "lion", "tiger", "bird", "shark", "panda"]
    adjective = random.choice(adjectives)
    animal = random.choice(animals)
    number = random.randint(10, 99)
    username = f"{adjective}{animal}{number}"
    logger.info(f"Сгенерировано имя пользователя: {username}")
    return username


async def generate_unique_user_id(db: AsyncSession) -> int:
    """
    Генерирует уникальный `user_id`, которого ещё нет в таблице пользователей.

    - Псевдослучайно генерирует число от 1 до 999999.
    - Проверяет уникальность через SQL-запрос к таблице `User`.
    - Повторяет попытку, пока не найдёт свободный ID.
    - Логирует успешную или неудачную попытку.

    :param db: Асинхронная сессия базы данных.
    :return: Уникальный числовой ID пользователя.
    """
    while True:
            user_id = random.randint(1, 999999)

            # Создаем запрос для проверки существования user_id
            query = select(User.id).where(User.id == literal(user_id))
            result = await db.execute(query)
            existing_user = result.fetchone()

            if not existing_user:
                logger.info(f"Сгенерирован уникальный ID пользователя: {user_id}")
                return user_id
            logger.info(f"ID {user_id} уже существует. Попытка генерации нового.")
