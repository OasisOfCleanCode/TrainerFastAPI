from redis.asyncio import Redis
from app.core.config import get_redis_settings
from utils.logger import logger

redis_ban = Redis.from_url(
    get_redis_settings().tapi_redis_ban_list_url,
    decode_responses=True,
    encoding="utf-8",
)


def _make_key(prefix: str, user_id: int, obj_id: str) -> str:
    return f"{prefix}:{user_id}:{obj_id}"


DEFAULT_EXPIRE_SECONDS = 1800


async def ban_token(
    prefix: str, user_id: int, obj_id: str, expire: int = DEFAULT_EXPIRE_SECONDS
):
    key = _make_key(prefix, user_id, obj_id)
    await redis_ban.set(key, "banned", ex=expire)
    logger.info(
        f"~~~⛔️ JWT ДОБАВЛЕН В БАН | type={prefix} | user_id={user_id} | obj_id={obj_id} | key={key}~~~"
    )


async def is_token_banned(prefix: str, user_id: int, obj_id: str) -> bool:
    key = _make_key(prefix, user_id, obj_id)
    exists = await redis_ban.exists(key)
    if exists:
        logger.info(
            f"~~~✅ КЭШ НАЙДЕН | type={prefix} | user_id={user_id} | obj_id={obj_id} | key={key}~~~"
        )
    return bool(exists)


async def remove_banned_token(prefix: str, user_id: int, obj_id: str):
    key = _make_key(prefix, user_id, obj_id)
    result = await redis_ban.delete(key)
    if result:
        logger.info(
            f"~~~❎ JWT УДАЛЁН ИЗ БАНА | type={prefix} | user_id={user_id} | obj_id={obj_id} | key={key}~~~"
        )
    else:
        logger.info(
            f"~~~⚠️ JWT НЕ НАЙДЕН ПРИ УДАЛЕНИИ | type={prefix} | user_id={user_id} | obj_id={obj_id} | key={key}~~~"
        )
