# 📘 Конфигурация проекта: автогенерация

Этот файл создан автоматически скриптом `generate_config_doc.py`.

## 📍 Где находится
- Конфиг: `app/core/config.py`
- .env: `C:\Users\dblmo\PycharmProjects\TrainerAPI\.env.example`
- Документация: `descriptions/config_settings.md`

## 🔍 Как пользоваться конфигами

Все настройки импортируются через ленивые обёртки, например:

```python
from app.core.config import get_db_settings

db_url = get_db_settings().async_tapi_pstgr_url
```

## 🛠 Список настроек:

# 📦 Документация настроек конфигурации

## 🔹 ApiTokens
- **TAPI_TOKEN_ACCESS_SECRET_KEY**: `str` = `(required)`
- **TAPI_TOKEN_REFRESH_SECRET_KEY**: `str` = `(required)`
- **ALGORITHM**: `str` = `HS256`

## 🔹 AppMetaSettings
- **APP_MODE**: `ModeEnum` = `ModeEnum.development`
- **VERSION_TAG**: `str` = `v1.0.0`

## 🔹 PstgrDataBaseSettings
- **TAPI_PSTGR_USER**: `str` = `(required)`
- **TAPI_PSTGR_PASS**: `str` = `(required)`
- **TAPI_PSTGR_NAME**: `str` = `(required)`
- **TAPI_PSTGR_HOST**: `str` = `(required)`
- **TAPI_PSTGR_PORT**: `str` = `(required)`

## 🔹 RabbitMqSetting
- **TAPI_RABBITMQ_USER**: `str` = `(required)`
- **TAPI_RABBITMQ_PASS**: `str` = `(required)`
- **TAPI_RABBITMQ_HOST**: `str` = `(required)`
- **TAPI_RABBITMQ_PORT**: `str` = `(required)`

## 🔹 RedisMqSetting
- **TAPI_REDIS_HOST**: `str` = `(required)`
- **TAPI_REDIS_PORT**: `str` = `(required)`
- **TAPI_REDIS_PASS**: `str` = `(required)`
- **TAPI_REDIS_BAN_LIST_INDEX**: `int` = `0`
- **TAPI_REDIS_BROKER_INDEX**: `int` = `1`

## 🔹 TelegramBotSetting
- **TELEGRAM_TOKEN_FOR_SEND_TELEBOT**: `str` = `(required)`
- **CHAT_ID_FOR_SEND**: `int` = `(required)`

## 🔹 UrlSetting
- **DOMAIN_URL**: `str` = `(required)`
- **CORS_ALLOWED_ORIGINS**: `list` = `[]`
