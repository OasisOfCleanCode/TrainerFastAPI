# services/cache/product_cache.py
import json
from typing import Any

from pydantic import BaseModel
from redis.asyncio import Redis
from config import REDIS_HOST, REDIS_PORT, REDIS_CATALOG_INDEX
from utils.logger import logger

DEFAULT_EXPIRE_SECONDS = 300

redis = Redis(
    host=REDIS_HOST,
    port=int(REDIS_PORT),
    db=int(REDIS_CATALOG_INDEX),
    decode_responses=True
)


def _make_key(prefix: str, user_id: int, obj_id: str) -> str:
    return f"{prefix}:{user_id}:{obj_id}"

def serialize_for_cache(data: Any) -> dict | list[dict]:
    """
    Преобразует Pydantic модель или список моделей в сериализуемый словарь/список словарей.
    Использует mode="json" для корректной сериализации UUID, datetime и прочего.
    """
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json")
    elif isinstance(data, list):
        return [item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in data]
    elif isinstance(data, dict):
        return data
    raise TypeError("Невозможно сериализовать объект для кэша")


async def get_cached(prefix: str, user_id: int, obj_id: str):
    pass
    key = _make_key(prefix, user_id, obj_id)
    data = await redis.get(key)
    if data:
        logger.info(f"~~~✅ КЭШ НАЙДЕН | type={prefix} | user_id={user_id} | obj_id={obj_id} | key={key}~~~")
        return json.loads(data)
    logger.info(f"~~~🚫 КЭШ НЕ НАЙДЕН | type={prefix} | user_id={user_id} | obj_id={obj_id} | key={key}~~~")
    return None


async def set_cached(prefix: str, user_id: int, obj_id: str, data: dict, expire: int = DEFAULT_EXPIRE_SECONDS):
    pass
    key = _make_key(prefix, user_id, obj_id)
    await redis.set(key, json.dumps(data), ex=expire)
    logger.info(f"~~~📦 КЭШ СОХРАНЁН | type={prefix} | user_id={user_id} | obj_id={obj_id} | key={key} | TTL={expire}s~~~")


async def invalidate_cache(prefix: str, user_id: int, obj_id: str):
    pass
    key = _make_key(prefix, user_id, obj_id)
    deleted = await redis.delete(key)
    if deleted:
        logger.info(f"~~~❌ КЭШ УДАЛЁН | type={prefix} | user_id={user_id} | obj_id={obj_id} | key={key}~~~")
    else:
        logger.info(f"~~~⚠️ КЭШ НЕ НАЙДЕН ДЛЯ УДАЛЕНИЯ | type={prefix} | user_id={user_id} | obj_id={obj_id} | key={key}~~~")


async def invalidate_all_by_prefix(prefix: str, user_id: int) -> int:
    pass
    pattern = f"{prefix}:{user_id}:*"
    keys = await redis.keys(pattern)
    if keys:
        await redis.delete(*keys)
        logger.info(f"~~~❌🧹 УДАЛЕНО ВСЕ КЭШИ ПО ШАБЛОНУ | prefix={prefix} | user_id={user_id} | count={len(keys)} | pattern={pattern}~~~")
        return len(keys)
    else:
        logger.info(f"~~~ℹ️ НЕТ КЭША ДЛЯ УДАЛЕНИЯ | prefix={prefix} | user_id={user_id} | pattern={pattern}~~~")
        return 0
