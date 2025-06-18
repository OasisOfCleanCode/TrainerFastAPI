# app/core/config.py

"""
📦 Конфигурация проекта: зачем и как всё устроено

✅ Почему используется `pydantic_settings.BaseSettings`?
---------------------------------------------------------
- Все переменные окружения строго типизированы и валидируются.
- .env-файл подключается автоматически (через Config).
- Удобно работать с разными окружениями: dev, prod, test.
- Ошибки конфигурации ловятся сразу при старте проекта.

✅ Зачем нужны lazy-обёртки с `@lru_cache`?
------------------------------------------
- Настройки и .env загружаются один раз — никакой лишней работы.
- Нет глобальных переменных — вызов в любом месте через `get_*_settings()`.
- Устойчиво к циклическим импортам.
- Легко протестировать или подменить конфиг.

📚 Где какой конфиг и зачем он нужен?
--------------------------------------

🔹 `AppMetaSettings`
    - Общие параметры приложения.
    - `APP_MODE`, `VERSION_TAG`.

🔹 `UrlSetting`
    - Базовый домен, CORS-источники.
    - `DOMAIN_URL`, `CORS_ALLOWED_ORIGINS`.

🔹 `ApiTokens`
    - Секреты для JWT-токенов.
    - `TAPI_TOKEN_ACCESS_SECRET_KEY`, `TAPI_TOKEN_REFRESH_SECRET_KEY`.

🔹 `TelegramBotSetting`
    - Токен и чат ID телеграм-бота.
    - `TELEGRAM_TOKEN_FOR_SEND_TELEBOT`, `CHAT_ID_FOR_SEND`.

🔹 `PstgrDataBaseSettings`
    - Настройки PostgreSQL.
    - `USER`, `PASS`, `HOST`, `PORT`, `DB_NAME` + `sync/async URL`.

🔹 `RabbitMqSetting`
    - Настройки подключения к RabbitMQ (Celery и др.).
    - `USER`, `PASS`, `HOST`, `PORT` + `amqp://...`.

🔹 `RedisMqSetting`
    - Настройки Redis (TaskIQ, кэш, списки банов).
    - `PASSWORD`, `HOST`, `PORT`, `INDEX` + `redis://...`.

🧠 Использование (в любом месте проекта):
-----------------------------------------
    from app.core.config import get_db_settings
    db = get_db_settings().async_tapi_pstgr_url
"""


from enum import Enum
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Загрузка .env
BASE_PATH = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_PATH / ".env")


class ModeEnum(str, Enum):
    development = "development"
    production = "production"
    testing = "testing"


class Settings(BaseSettings):
    class Config:
        env_file = BASE_PATH / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class AppMetaSettings(Settings):
    APP_MODE: ModeEnum = ModeEnum.development
    VERSION_TAG: str = "v1.0.0"


class UrlSetting(Settings):
    DOMAIN_URL: str
    CORS_ALLOWED_ORIGINS: list[str] = []


class TelegramBotSetting(Settings):
    TELEGRAM_TOKEN_FOR_SEND_TELEBOT: str
    CHAT_ID_FOR_SEND: int


class ApiTokens(Settings):
    TAPI_TOKEN_ACCESS_SECRET_KEY: str
    TAPI_TOKEN_REFRESH_SECRET_KEY: str
    ALGORITHM: str = "HS256"


class PstgrDataBaseSettings(Settings):
    TAPI_PSTGR_USER: str
    TAPI_PSTGR_PASS: str
    TAPI_PSTGR_NAME: str
    TAPI_PSTGR_HOST: str
    TAPI_PSTGR_PORT: str

    @property
    def async_tapi_pstgr_url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.TAPI_PSTGR_USER}:"
            f"{self.TAPI_PSTGR_PASS}@"
            f"{self.TAPI_PSTGR_HOST}:"
            f"{self.TAPI_PSTGR_PORT}/"
            f"{self.TAPI_PSTGR_NAME}"
        )

    @property
    def sync_tapi_pstgr_url(self) -> str:
        return (
            f"postgresql://"
            f"{self.TAPI_PSTGR_USER}:"
            f"{self.TAPI_PSTGR_PASS}@"
            f"{self.TAPI_PSTGR_HOST}:"
            f"{self.TAPI_PSTGR_PORT}/"
            f"{self.TAPI_PSTGR_NAME}"
        )


class RabbitMqSetting(Settings):
    TAPI_RABBITMQ_USER: str
    TAPI_RABBITMQ_PASS: str
    TAPI_RABBITMQ_HOST: str
    TAPI_RABBITMQ_PORT: str

    @property
    def tapi_rabbitmq_broker_url(self) -> str:
        return (
            f"amqp://"
            f"{self.TAPI_RABBITMQ_USER}:"
            f"{self.TAPI_RABBITMQ_PASS}@"
            f"{self.TAPI_RABBITMQ_HOST}:"
            f"{self.TAPI_RABBITMQ_PORT}/"
        )


class RedisMqSetting(Settings):
    TAPI_REDIS_HOST: str
    TAPI_REDIS_PORT: str
    TAPI_REDIS_PASS: str
    TAPI_REDIS_BAN_LIST_INDEX: int = 0
    TAPI_REDIS_BROKER_INDEX: int = 1

    @property
    def tapi_redis_ban_list_url(self) -> str:
        return (
            f"redis://:"
            f"{self.TAPI_REDIS_PASS}@"
            f"{self.TAPI_REDIS_HOST}:"
            f"{self.TAPI_REDIS_PORT}/"
            f"{self.TAPI_REDIS_BAN_LIST_INDEX}"
        )

    @property
    def tapi_redis_broker_url(self) -> str:
        return (
            f"redis://:"
            f"{self.TAPI_REDIS_PASS}@"
            f"{self.TAPI_REDIS_HOST}:"
            f"{self.TAPI_REDIS_PORT}/"
            f"{self.TAPI_REDIS_BROKER_INDEX}"
        )


class MailSenderConfig(Settings):
    TAPI_MAIL_USERNAME: str
    TAPI_MAIL_PASSWORD: str
    TAPI_MAIL_SERVER: str
    TAPI_MAIL_PORT: int


class UrlsToServices(Settings):
    BASE_URL: str = "https://occ.dev/"
    BASE_USER_URL: str = "https://id.occ.dev/"
    BASE_USER_API_URL: str = "https://id.api.occ.dev/"


# =======================
# ✅ Lazy-access обёртки
# =======================


@lru_cache()
def get_app_settings() -> AppMetaSettings:
    return AppMetaSettings()


@lru_cache()
def get_url_settings() -> UrlSetting:
    return UrlSetting()


@lru_cache()
def get_api_tokens() -> ApiTokens:
    return ApiTokens()


@lru_cache()
def get_db_settings() -> PstgrDataBaseSettings:
    return PstgrDataBaseSettings()


@lru_cache()
def get_rabbitmq_settings() -> RabbitMqSetting:
    return RabbitMqSetting()


@lru_cache()
def get_redis_settings() -> RedisMqSetting:
    return RedisMqSetting()


@lru_cache()
def get_telegram_settings() -> TelegramBotSetting:
    return TelegramBotSetting()


@lru_cache()
def get_mail_sender_config() -> MailSenderConfig:
    return MailSenderConfig()


@lru_cache()
def get_urls_to_services() -> UrlsToServices:
    return UrlsToServices()
