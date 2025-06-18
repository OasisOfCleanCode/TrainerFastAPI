# app/db/dao/base_dao.py

"""
⚠️ Почему нет смысла переписывать этот DAO в функциональном стиле ради "оптимизации":

Некоторые могут подумать, что замена классов на функции улучшит производительность за счёт «меньшей нагрузки».
Однако в реальности это не даст заметного выигрыша. Вот почему:

1. 💡 Основная задержка при работе с базой — это не код Python, а САМ ЗАПРОС в БД (I/O, сети, диск и т.д.).
   Даже идеально «лёгкая» функция всё равно будет ждать ответа от PostgreSQL или другого движка.

2. 📦 Класс действительно чуть тяжелее (в памяти хранится ссылка на self/class), но это **сотые доли миллисекунды**.
   Если вы не вызываете DAO миллионы раз в секунду — вы этого не заметите.

3. 🔁 DAO-класс делает код переиспользуемым: можно хранить логику в одном месте, наследоваться и расширять.
   В функциональном стиле придётся копировать много однотипной логики — это сложнее поддерживать.

4. 🛠 Настоящая оптимизация делается не здесь:
   - Используйте `EXPLAIN ANALYZE` и индексируйте поля в БД.
   - Сокращайте число запросов (batching, prefetching).
   - Добавляйте кеширование (Redis, в памяти, selectinload).
   - Следите за количеством соединений и пулов.

5. ⚙️ Если вы упёрлись в I/O — спасёт не функционал, а железо и инфраструктура:
   - SSD/NVMe-диски (быстрый доступ к данным)
   - Больше RAM (меньше свопа)
   - Быстрая сеть (для распределённых БД)
   - Продвинутое логирование/мониторинг (tracing, метрики).

Вывод: классы в данном случае — это **не тормоз**, а **структурный инструмент**.
"""

from typing import Generic, TypeVar, List, Any

from sqlalchemy import (
    select,
    update as sqlalchemy_update,
    delete as sqlalchemy_delete,
    func,
)
from sqlalchemy.exc import SQLAlchemyError

from pydantic import BaseModel

from app.core.exceptions import ValidationException
from app.db.models import User
from app.utils.logger import logger

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.models.base_sql import IntIdSQL

SQL = TypeVar("SQL", bound=IntIdSQL)


class BaseDAO(Generic[SQL]):
    """
    Базовый класс DAO(Объекта доступа к данным).
    Принимает модель SQLAlchemy и данные обернутые в Pydantic.
    """

    model: type[SQL]
    name_object_model: str

    def __init_subclass__(cls, **kwargs):
        """
        Автоматически вызывается при создании подкласса.

        - Определяет имя модели (`name_object_model`) как имя класса без "DAO" в конце.
        - Используется для логирования и регистрации класса.
        - Работает только при наследовании от `BaseDAO`.
        """
        super().__init_subclass__(**kwargs)
        # Проверяем, что это прямой наследник BaseDAO, а не внутренний класс SQLAlchemy
        if issubclass(cls, BaseDAO) and cls is not BaseDAO:
            cls.name_object_model = cls.__name__[:-3].lower()
            logger.info(f"{cls.__name__} инициализирован")

    @classmethod
    async def find_one_or_none_by_id(cls, data_id: int, db: AsyncSession) -> IntIdSQL:
        """
        Найти одну запись по её ID.

        - Формирует SELECT-запрос по полю `id`.
        - Возвращает объект SQLAlchemy или None.
        - Логирует результат.

        :param data_id: Идентификатор записи.
        :param db: Сессия базы данных.
        :return: Один объект модели или None.
        """
        logger.info(f"Поиск {cls.model.__name__} с ID: {data_id}")
        try:
            query = select(cls.model).filter_by(id=data_id)
            result = await db.execute(query)
            record = result.scalar_one_or_none()
            if record:
                logger.info(f"Запись с ID {data_id} найдена.")
            else:
                logger.info(f"Запись с ID {data_id} не найдена.")
            return record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске записи с ID {data_id}: {e}")
            raise

    @classmethod
    async def find_one_or_none(cls, db: AsyncSession, filters: BaseModel):
        """
        Найти одну запись по переданным фильтрам.

        - Фильтры передаются через Pydantic-модель.
        - Использует `filter_by(**dict)` для SQL-запроса.
        - Возвращает объект или None.

        :param db: Сессия базы данных.
        :param filters: Pydantic-модель с полями фильтрации.
        :return: Один объект модели или None.
        """
        logger.info("# Найти одну запись по фильтрам. (BaseDAO.find_one_or_none)")
        filter_dict = filters.model_dump()
        logger.info(
            f"Поиск одной записи {cls.model.__name__} по фильтрам: {filter_dict}"
        )
        try:
            query = select(cls.model).filter_by(**filter_dict)
            result = await db.execute(query)
            record = result.scalar_one_or_none()
            if record:
                logger.info(f"Запись найдена по фильтрам: {filter_dict}")
            else:
                logger.info(f"Запись не найдена по фильтрам: {filter_dict}")
            return record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске записи по фильтрам {filter_dict}: {e}")
            raise

    @classmethod
    async def find_all(cls, db: AsyncSession, filters: BaseModel | None):
        """
        Получить все записи, соответствующие фильтрам.

        - Если фильтры не заданы, вернёт все записи.
        - Использует `filter_by()`.

        :param db: Сессия базы данных.
        :param filters: Модель с фильтрами или None.
        :return: Список найденных объектов.
        """
        if filters:
            filter_dict = filters.model_dump(exclude_unset=True)
        else:
            filter_dict = {}
        logger.info(
            f"Поиск всех записей {cls.model.__name__} по фильтрам: {filter_dict}"
        )
        try:
            query = select(cls.model).filter_by(**filter_dict)
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
    async def add(cls, db: AsyncSession, values: BaseModel):
        """
        Добавить одну запись в базу.

        - Принимает Pydantic-модель, мапит её в SQL-модель.
        - Выполняет `flush()` (не `commit()`).
        - Возвращает добавленный объект.

        :param db: Сессия базы данных.
        :param values: Pydantic-модель с данными.
        :return: Добавленный объект SQLAlchemy.
        """
        values_dict = values.model_dump(exclude_unset=True)
        logger.info(
            f"Добавление записи {cls.model.__name__} с параметрами: {values_dict}"
        )
        new_instance = cls.model(**values_dict)
        db.add(new_instance)
        try:
            await db.flush()
            logger.info(f"Запись {cls.model.__name__} успешно добавлена.")
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Ошибка при добавлении записи: {e}")
            raise e
        return new_instance

    @classmethod
    async def add_many(cls, db: AsyncSession, instances: List[BaseModel]):
        """
        Добавить несколько записей сразу.

        - Принимает список Pydantic-моделей.
        - Преобразует каждую в SQL-модель.
        - Выполняет `flush()`.

        :param db: Сессия базы данных.
        :param instances: Список моделей.
        :return: Список добавленных SQL-моделей.
        """
        values_list = [item.model_dump(exclude_unset=True) for item in instances]
        logger.info(
            f"Добавление нескольких записей {cls.model.__name__}. Количество: {len(values_list)}"
        )
        new_instances = [cls.model(**values) for values in values_list]
        db.add_all(new_instances)
        try:
            await db.flush()
            logger.info(f"Успешно добавлено {len(new_instances)} записей.")
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Ошибка при добавлении нескольких записей: {e}")
            raise e
        return new_instances

    @classmethod
    async def update(cls, db: AsyncSession, filters: BaseModel, values: BaseModel):
        """
        Обновить одну или несколько записей по фильтру.

        - Строит запрос через `update(...)`.
        - Работает без загрузки объектов в память.
        - Возвращает число обновлённых строк.

        :param db: Сессия.
        :param filters: Модель с фильтрами.
        :param values: Новые значения.
        :return: Количество обновлённых строк.
        """
        filter_dict = filters.model_dump(exclude_unset=True)
        values_dict = values.model_dump(exclude_unset=True)
        logger.info(
            f"Обновление записей {cls.model.__name__} по фильтру: {filter_dict} с параметрами: {values_dict}"
        )
        query = (
            sqlalchemy_update(cls.model)
            .where(*[getattr(cls.model, k) == v for k, v in filter_dict.items()])
            .values(**values_dict)
            .execution_options(synchronize_session="fetch")
        )
        try:
            result = await db.execute(query)
            await db.flush()
            logger.info(f"Обновлено {result.rowcount} записей.")
            return result.rowcount
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Ошибка при обновлении записей: {e}")
            raise e

    @classmethod
    async def delete(cls, db: AsyncSession, filters: BaseModel):
        """
        Удалить записи, соответствующие фильтру.

        - Обязательно нужен хотя бы один фильтр.
        - Использует `delete(...)`.

        :param db: Сессия.
        :param filters: Модель с условиями удаления.
        :return: Количество удалённых строк.
        """
        filter_dict = filters.model_dump(exclude_unset=True)
        logger.info(f"Удаление записей {cls.model.__name__} по фильтру: {filter_dict}")
        if not filter_dict:
            logger.error("Нужен хотя бы один фильтр для удаления.")
            raise ValidationException("Нужен хотя бы один фильтр для удаления.")

        query = sqlalchemy_delete(cls.model).filter_by(**filter_dict)
        try:
            result = await db.execute(query)
            await db.flush()
            logger.info(f"Удалено {result.rowcount} записей.")
            return result.rowcount
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Ошибка при удалении записей: {e}")
            raise e

    @classmethod
    async def count(cls, db: AsyncSession, filters: BaseModel):
        """
        Подсчитать количество записей по фильтрам.

        - Выполняет `SELECT COUNT(...)`.
        - Учитывает только строки, соответствующие фильтру.

        :param db: Сессия.
        :param filters: Модель с фильтрами.
        :return: Количество строк.
        """
        filter_dict = filters.model_dump(exclude_unset=True)
        logger.info(
            f"Подсчет количества записей {cls.model.__name__} по фильтру: {filter_dict}"
        )
        try:
            query = select(func.count(cls.model.id)).filter_by(**filter_dict)
            result = await db.execute(query)
            count = result.scalar()
            logger.info(f"Найдено {count} записей.")
            return count
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при подсчете записей: {e}")
            raise

    @classmethod
    async def paginate(
        cls,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        filters: BaseModel = None,
    ):
        """
        Получить записи с пагинацией.

        - Поддерживает фильтры и разбиение по страницам.
        - Использует `.offset().limit()`.

        :param db: Сессия.
        :param page: Номер страницы (начиная с 1).
        :param page_size: Кол-во записей на страницу.
        :param filters: Опциональные фильтры.
        :return: Список записей.
        """
        filter_dict = filters.model_dump(exclude_unset=True) if filters else {}
        logger.info(
            f"Пагинация записей {cls.model.__name__} по фильтру: {filter_dict}, страница: {page}, размер страницы: {page_size}"
        )
        try:
            query = select(cls.model).filter_by(**filter_dict)
            result = await db.execute(
                query.offset((page - 1) * page_size).limit(page_size)
            )
            records = result.scalars().all()
            logger.info(f"Найдено {len(records)} записей на странице {page}.")
            return records
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при пагинации записей: {e}")
            raise

    @classmethod
    async def find_by_ids(cls, db: AsyncSession, ids: List[int]) -> List[Any]:
        """
        Получить записи по списку ID.

        - Использует `IN` выражение.
        - Возвращает все записи, у которых id входит в список.

        :param db: Сессия.
        :param ids: Список идентификаторов.
        :return: Список объектов.
        """
        logger.info(f"Поиск записей {cls.model.__name__} по списку ID: {ids}")
        try:
            query = select(cls.model).filter(cls.model.id.in_(ids))
            result = await db.execute(query)
            records = result.scalars().all()
            logger.info(f"Найдено {len(records)} записей по списку ID.")
            return records
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске записей по списку ID: {e}")
            raise

    @classmethod
    async def upsert(
        cls, db: AsyncSession, unique_fields: List[str], values: BaseModel
    ):
        """
        Обновить запись, если она существует, иначе создать новую.

        - Поиск ведётся по `unique_fields`.
        - Если запись найдена — обновляется.
        - Иначе создаётся новая.

        :param db: Сессия.
        :param unique_fields: Список полей, по которым ищем.
        :param values: Данные для вставки/обновления.
        :return: Новый или обновлённый объект.
        """
        values_dict = values.model_dump(exclude_unset=True)
        filter_dict = {
            field: values_dict[field] for field in unique_fields if field in values_dict
        }

        logger.info(f"Upsert для {cls.model.__name__}")
        try:
            existing = await cls.find_one_or_none(
                db, BaseModel.model_construct(**filter_dict)
            )
            if existing:
                # Обновляем существующую запись
                for key, value in values_dict.items():
                    setattr(existing, key, value)
                await db.flush()
                logger.info(f"Обновлена существующая запись {cls.model.__name__}")
                return existing
            else:
                # Создаем новую запись
                new_instance = cls.model(**values_dict)
                db.add(new_instance)
                await db.flush()
                logger.info(f"Создана новая запись {cls.model.__name__}")
                return new_instance
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Ошибка при upsert: {e}")
            raise

    @classmethod
    async def bulk_update(cls, db: AsyncSession, records: List[BaseModel]) -> int:
        """
        Массовое обновление нескольких записей.

        - Обрабатывает список объектов.
        - Каждая запись должна содержать поле `id`.
        - Использует `update(...).filter_by(id=...)`.

        :param db: Сессия.
        :param records: Список моделей с id и обновляемыми полями.
        :return: Кол-во обновлённых строк.
        """
        logger.info(f"Массовое обновление записей {cls.model.__name__}")
        try:
            updated_count = 0
            for record in records:
                record_dict = record.model_dump(exclude_unset=True)
                if "id" not in record_dict:
                    continue

                update_data = {k: v for k, v in record_dict.items() if k != "id"}
                stmt = (
                    sqlalchemy_update(cls.model)
                    .filter_by(id=record_dict["id"])
                    .values(**update_data)
                )
                result = await db.execute(stmt)
                updated_count += result.rowcount

            await db.flush()
            logger.info(f"Обновлено {updated_count} записей")
            return updated_count
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Ошибка при массовом обновлении: {e}")
            raise
