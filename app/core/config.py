# app/config.py
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv

from pydantic_settings import BaseSettings

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent


class ModeEnum(str, Enum):
    development = "development"
    production = "production"
    testing = "testing"


class Settings(BaseSettings):
    class Config:
        env_file = BASE_DIR / '.env'
        env_file_encoding = "utf-8"


class AppMetaSettings(Settings):
    APP_MODE: ModeEnum = ModeEnum.development
    VERSION_TAG: str = "v1.0.0"


class UrlSetting(Settings):
    DOMAIN_URL: str
    CORS_ALLOWED_ORIGINS: list[str] = [
    ]


class TelegramBotSetting(Settings):
    TELEGRAM_TOKEN_FOR_SEND_TELEBOT: str
    CHAT_ID_FOR_SEND: int




class ApiTokens(Settings):
    TFA_TOKEN_ACCESS_SECRET_KEY: str
    TFA_TOKEN_REFRESH_SECRET_KEY: str
    ALGORITHM: str = "HS256"


class DataBaseSettings(Settings):

    TAPI_PSTGR_USER: str
    TAPI_PSTGR_PASS: str
    TAPI_PSTGR_NAME: str
    TAPI_PSTGR_HOST: str
    TAPI_PSTGR_PORT: str

    TAPI_RABBITMQ_USER: str
    TAPI_RABBITMQ_PASS: str
    TAPI_RABBITMQ_HOST: str
    TAPI_RABBITMQ_PORT: str

    TAPI_REDIS_HOST: str
    TAPI_REDIS_PORT: str
    TAPI_REDIS_PASSWORD: str
    TAPI_REDIS_BAN_LIST_INDEX: str
    TAPI_REDIS_USER_INDEX: str

    @property
    def async_tapi_pstgr_url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.TAPI_PSTGR_USER}:"
            f"{self.TAPI_PSTGR_PASS}@"
            f"{self.TAPI_PSTGR_NAME}:"
            f"{self.TAPI_PSTGR_HOST}/"
            f"{self.TAPI_PSTGR_PORT}"
        )

    @property
    def sync_tapi_pstgr_url(self) -> str:
        return (
            f"postgresql://"
            f"{self.TAPI_PSTGR_USER}:"
            f"{self.TAPI_PSTGR_PASS}@"
            f"{self.TAPI_PSTGR_NAME}:"
            f"{self.TAPI_PSTGR_HOST}/"
            f"{self.TAPI_PSTGR_PORT}"
        )



app_meta_settings = AppMetaSettings()
url_setting = UrlSetting()
api_tokens_setting = ApiTokens()
db_settings = DataBaseSettings()
