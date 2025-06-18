# app/services/user/role_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.enums import RoleEnum
from app.db.models.user import Role
from app.db.sessions import async_connect_db
import bcrypt

bcrypt.__about__ = bcrypt




@async_connect_db(commit=True)
async def check_roles_in_db(db: AsyncSession):

    """
    Проверяет, чтобы в базе данных существовали все роли, описанные в `RoleEnum`,
    и автоматически синхронизирует таблицу `roles`.

    - Получает текущий список ролей из таблицы `Role`.
    - Сравнивает его с перечислением `RoleEnum`.
    - Добавляет недостающие роли.
    - Удаляет лишние роли, не входящие в `RoleEnum`.
    - Все изменения автоматически сохраняются в базу через декоратор `@async_connect_db(commit=True)`.

    :param db: Асинхронная сессия базы данных.
    :return: None
    """
    # Получаем все существующие роли из базы данных
    result = await db.execute(select(Role.name))
    existing_roles = {role.name for role in result.scalars().all()}

    # Все возможные роли из RoleEnum
    required_roles = {role for role in RoleEnum}

    # Определяем роли, которые нужно добавить
    roles_to_add = required_roles - existing_roles
    roles_to_remove = existing_roles - required_roles

    # Добавляем недостающие роли
    for role_name in roles_to_add:
        new_role = Role(name=role_name)
        db.add(new_role)

    # Удаляем лишние роли
    for role_name in roles_to_remove:
        role_del = await db.execute(select(Role).filter(Role.name == role_name))
        await db.delete(role_del)

    await db.commit()