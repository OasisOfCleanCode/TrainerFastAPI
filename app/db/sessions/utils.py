# app/database/utils.py
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker

from ._session import DatabaseSessionManager
from ...core.config import PSTGR_URL, PSTGR_URL_SYNC

# Создание асинхронного и синхронного движков
async_engine = create_async_engine(PSTGR_URL)
async_session_maker = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# sync_engine = create_engine(PSTGR_URL_SYNC, pool_pre_ping=True)
# sync_session_maker = sessionmaker(bind=sync_engine)

# Создаём менеджер сессий
async_session_manager = DatabaseSessionManager(async_session_maker)
# sync_session_manager = DatabaseSessionManager(sync_session_maker)

# Декораторы
async_connect_db = async_session_manager.async_connection
# sync_connect_db = sync_session_manager.sync_connection

# FastAPI зависимости
SessionDep = async_session_manager.async_session_dependency
TransactionSessionDep = async_session_manager.async_transaction_session_dependency
# SessionDepSync = sync_session_manager.sync_session_dependency
# TransactionSessionDepSync = sync_session_manager.sync_transaction_session_dependency
