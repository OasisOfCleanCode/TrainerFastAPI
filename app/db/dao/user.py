# app/db/dao/user.py
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, raiseload
from sqlalchemy import select

from app.core.exceptions import EmailAlreadyExistsException, PhoneAlreadyExistsException
from app.db.dao.base_dao import BaseDAO
from app.db.models.user import User, Token
from app.db.sessions import TransactionSessionDep, SessionDep
from app.utils.logger import logger

if TYPE_CHECKING:
    from app.db.schemas.user import TokenBase, CheckEmailModel

import bcrypt

bcrypt.__about__ = bcrypt


class UserDAO(BaseDAO):
    model: User

    @classmethod
    async def get_refresh_token(cls, values: TokenBase, db: AsyncSession = SessionDep):
        """
        Получает refresh-токен по заданным параметрам.

        - Ищет токен в таблице Token по полям из модели TokenBase (например: user_id, token, type_token).
        - Возвращает объект токена или None.
        - Используется при проверке валидности refresh-токенов.

        :param db: Асинхронная сессия базы данных.
        :param values: Модель TokenBase с параметрами для фильтрации.
        :return: Объект Token или None.
        """
        values_dict = values.model_dump(exclude_unset=True)
        token = values_dict.get("token")

        logger.info(f"Поиск токена : {token}")
        try:
            query = select(Token).filter_by(**values_dict)
            result = await db.execute(query)
            record = result.scalar_one_or_none()
            if record:
                logger.info(f"Токен {token} найден.")
            else:
                logger.info(f"Токен {token} не найден.")
            return record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске токена {token}: {e}")
            raise

    @classmethod
    async def find_one_user_or_none_by_id(
        cls, data_id: int, db: AsyncSession = SessionDep
    ) -> User:
        """
        Возвращает одного пользователя по ID или None, если пользователь не найден.

        - Загружает связанные роли пользователя.
        - Не подгружает токены.

        :param data_id: Идентификатор пользователя.
        :param db: Асинхронная сессия базы данных.
        :return: Объект User или None.
        """
        logger.info(f"Поиск пользователя с ID: {data_id}")
        try:
            query = select(User).filter_by(id=data_id).options(selectinload(User.roles))
            result = await db.execute(query)
            record = result.scalars().first()
            if record:
                logger.info(f"Запись с ID {data_id} найдена.")
            else:
                logger.info(f"Запись с ID {data_id} не найдена.")
            return record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске записи с ID {data_id}: {e}")
            raise

    @classmethod
    async def find_one_user_or_none(
        cls, filters: BaseModel, db: AsyncSession = SessionDep
    ) -> User:
        """
        Возвращает одного пользователя по фильтру (например, email или phone) или None.

        - Фильтры передаются через Pydantic-модель.
        - Загружает связанные роли.

        :param db: Асинхронная сессия базы данных.
        :param filters: Модель с полями фильтрации.
        :return: Объект User или None.
        """
        logger.info("# Найти одну запись по фильтрам. (UsersDAO.find_one_or_none)")
        filter_dict = filters.model_dump()
        logger.info(f"Поиск одной записи пользователя по фильтрам: {filter_dict}")
        try:
            query = (
                select(User).filter_by(**filter_dict).options(selectinload(User.roles))
            )
            result = await db.execute(query)
            record = result.scalars().first()
            if record:
                logger.info(f"Запись найдена по фильтрам: {filter_dict}")
            else:
                logger.info(f"Запись не найдена по фильтрам: {filter_dict}")
            return record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске записи по фильтрам {filter_dict}: {e}")
            raise

    @classmethod
    async def find_one_user_or_none_by_id_with_tokens(
        cls, data_id: int, db: AsyncSession = SessionDep
    ) -> User:
        """
        Возвращает одного пользователя по ID вместе с ролями и токенами.

        - Используется при проверке access/refresh токенов и аутентификации.
        - Загружает связанные роли и список токенов пользователя.

        :param data_id: Идентификатор пользователя.
        :param db: Асинхронная сессия базы данных.
        :return: Объект User или None.
        """
        logger.info(f"Поиск пользователя с ID: {data_id}")
        try:
            query = (
                select(User)
                .filter_by(id=data_id)
                .options(
                    selectinload(User.roles),
                    selectinload(User.tokens),
                )
            )
            result = await db.execute(query)
            record = result.scalars().first()
            if record:
                logger.info(f"Запись с ID {data_id} найдена.")
            else:
                logger.info(f"Запись с ID {data_id} не найдена.")
            return record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске записи с ID {data_id}: {e}")
            raise

    @classmethod
    async def find_one_user_or_none_with_tokens(
        cls, filters: BaseModel, db: AsyncSession = SessionDep
    ) -> User:
        """
        Возвращает одного пользователя по фильтрам с предзагрузкой токенов и ролей.

        - Используется в логике логина, обновления токена и админ-интерфейсах.
        - Запрещает подгрузку других связей (`raiseload('*')`).
        - Позволяет загрузить только необходимую информацию.

        :param db: Асинхронная сессия базы данных.
        :param filters: Pydantic-модель с фильтрами (email, phone и т.д.).
        :return: Объект User или None.
        """
        logger.info(
            "# Найти одну запись по фильтрам. (UsersDAO.find_one_or_none_with_tokens)"
        )
        filter_dict = filters.model_dump()
        logger.info(f"Поиск одной записи пользователя по фильтрам: {filter_dict}")
        try:
            query = (
                select(User)
                .filter_by(**filter_dict)
                .options(
                    selectinload(User.roles),
                    selectinload(User.tokens),
                    raiseload(
                        "*"
                    ),  # Запрещает случайную ленивую загрузку других связей
                )
            )
            result = await db.execute(query)
            record = result.scalars().first()
            if record:
                logger.info(f"Запись найдена по фильтрам: {filter_dict}")
            else:
                logger.info(f"Запись не найдена по фильтрам: {filter_dict}")
            return record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске записи по фильтрам {filter_dict}: {e}")
            raise

    @classmethod
    async def find_all_user(cls, filters: BaseModel, db: AsyncSession = SessionDep):
        """
        Возвращает список всех пользователей, соответствующих фильтрам.

        - Если фильтры не заданы, возвращает всех пользователей.
        - Загружает связанные роли.
        - Используется для админки, вывода списка пользователей и служебных задач.

        :param db: Асинхронная сессия базы данных.
        :param filters: Модель с фильтрами или None.
        :return: Список пользователей (list[User]).
        """
        if filters:
            filter_dict = filters.model_dump(exclude_unset=True)
        else:
            filter_dict = {}
        logger.info(f"Поиск всех записей пользователя по фильтрам: {filter_dict}")
        try:
            query = (
                select(User).filter_by(**filter_dict).options(selectinload(User.roles))
            )
            result = await db.execute(query)
            records = result.scalars().all()

            logger.info(f"Найдено {len(records)} записей.")
            return records
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при поиске всех записей по фильтрам {filter_dict}: {e}"
            )
            raise

    @classmethod
    async def check_email_to_user(
        cls, user: User, email: CheckEmailModel, db: AsyncSession
    ):
        check_email = (
            await db.execute(select(User).where(User.email == email.email))
        ).scalar_one_or_none()
        return check_email

    @classmethod
    async def post_email_to_user(
        cls,
        user: User,
        email: CheckEmailModel,
        db: AsyncSession = TransactionSessionDep,
    ):
        check_email = cls.check_email_to_user(user, email, db)
        if check_email:
            logger.remove()
            raise EmailAlreadyExistsException
        if user.email:
            logger.remove()
            raise PhoneAlreadyExistsException
        user.email = email.email
        await db.flush()
        return user
