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
    TELEGRAM_TOKEN: str
    CHAT_ID: int

    TFA_TOKEN_ACCESS_SECRET_KEY: str
    TFA_TOKEN_REFRESH_SECRET_KEY: str
    ALGORITHM: str = "HS256"

    # PostgreSQL credentials
    CATALOG_PSTGR_USER: str
    CATALOG_PSTGR_PASS: str
    CATALOG_PSTGR_HOST: str
    CATALOG_PSTGR_PORT: str
    CATALOG_PSTGR_NAME: str

    RABBITMQ_USER: str
    RABBITMQ_PASS: str
    RABBITMQ_HOST: str
    RABBITMQ_PORT: str

    REDIS_HOST: str
    REDIS_PORT: str
    REDIS_PASSWORD: str = os.environ.get("REDIS_PASSWORD")
    REDIS_BAN_LIST_INDEX: str
    REDIS_USER_INDEX: str

    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_PORT: str
    MAIL_SERVER: str

    DOMAIN_URL: str

    CORS_ALLOWED_ORIGINS: list[str] = [
    ]

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

    class Config:
        env_file = BASE_DIR / '.env'
        env_file_encoding = "utf-8"

settings = Settings()