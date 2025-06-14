"""
📘 generate_config_doc.py

Скрипт для автоматической генерации документации по конфигурации проекта на основе классов Pydantic `BaseSettings`.

📦 Что делает:
- Находит все конфигурационные классы (наследники BaseSettings) в `app/core/config.py`.
- Формирует Markdown-документацию (`descriptions/config_settings.md`) со списком всех переменных, их типов и значений по умолчанию.
- Генерирует шаблон `.env.example` с понятными placeholder'ами (your_...) и комментариями по группам настроек.

🧠 Зачем нужен:
- Упрощает поддержку .env и структуры настроек.
- Ускоряет онбординг новых разработчиков.
- Может быть частью CI, генерации Swagger-доков и пр.

🚀 Как использовать:
```bash
python scripts/generate_config_doc.py
```

📂 Файлы:
- Markdown: `descriptions/config_settings.md`
- Пример .env: `.env.example`

📌 P.S. Это не магия. Это забота.
"""

import importlib.util
import sys
from inspect import getmembers, isclass
from pathlib import Path
from pydantic_core import PydanticUndefined

# Пути
BASE_PATH = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_PATH / "app" / "core" / "config.py"
OUTPUT_DIR = BASE_PATH / "descriptions"
OUTPUT_FILE_CONFIG = OUTPUT_DIR / "config_settings.md"
OUTPUT_FILE_ENV = BASE_PATH / ".env.example"
OUTPUT_DIR.mkdir(exist_ok=True)

# Загрузка config.py
spec = importlib.util.spec_from_file_location("config", CONFIG_PATH)
config = importlib.util.module_from_spec(spec)
sys.modules["config"] = config
spec.loader.exec_module(config)

# Markdown-документация
def generate_config_doc() -> str:
    output = ["# 📦 Документация настроек конфигурации\n"]

    for name, cls in getmembers(config):
        if isclass(cls) and issubclass(cls, config.Settings) and cls is not config.Settings:
            section = [f"## 🔹 {name}"]
            try:
                for field, field_info in cls.model_fields.items():
                    field_type = getattr(field_info.annotation, '__name__', str(field_info.annotation))
                    if field_info.default is PydanticUndefined:
                        default = "(required)"
                    else:
                        default = field_info.default
                    section.append(f"- **{field}**: `{field_type}` = `{default}`")
            except Exception as e:
                section.append(f"- ⚠️ Ошибка: {e}")
            output.append("\n".join(section) + "\n")

    return "\n".join(output)

# .env.example
def generate_env_example() -> str:
    output = ["# 🔧 .env.example — сгенерирован автоматически\n"]

    for name, cls in getmembers(config):
        if isclass(cls) and issubclass(cls, config.Settings) and cls is not config.Settings:
            output.append(f"# ▶️ {name}")
            try:
                for field, field_info in cls.model_fields.items():
                    env_name = field.upper()
                    if field_info.default is PydanticUndefined:
                        placeholder = f"your_{field.lower()}"
                    else:
                        placeholder = field_info.default
                    output.append(f"{env_name}={placeholder}")
            except Exception as e:
                output.append(f"# ⚠️ Ошибка: {e}")
            output.append("")  # пустая строка между блоками

    return "\n".join(output)

# Вступление
intro_md = f"""# 📘 Конфигурация проекта: автогенерация

Этот файл создан автоматически скриптом `generate_config_doc.py`.

## 📍 Где находится
- Конфиг: `app/core/config.py`
- .env: `{BASE_PATH / ".env.example"}`
- Документация: `descriptions/config_settings.md`

## 🔍 Как пользоваться конфигами

Все настройки импортируются через ленивые обёртки, например:

```python
from app.core.config import get_db_settings

db_url = get_db_settings().async_tapi_pstgr_url
```

## 🛠 Список настроек:
"""

# Генерация и сохранение
OUTPUT_FILE_CONFIG.write_text(intro_md + "\n" + generate_config_doc(), encoding="utf-8")
OUTPUT_FILE_ENV.write_text(generate_env_example(), encoding="utf-8")
print(f"✅ Документация: {OUTPUT_FILE_CONFIG}")
print(f"✅ Пример .env: {OUTPUT_FILE_ENV}")
