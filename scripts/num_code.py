# app/utils/num_code.py

import os
from pathlib import Path

from app.core.config import BASE_PATH
from app.utils.logger import logger


def counting_rows():
    directory = BASE_PATH
    line_count = 0

    for f in directory.rglob('*.py'):
        if '.venv' in f.parts or not f.is_file() or not f.exists():
            # Пропускаем файлы в папке venv
            continue

        local_count = 0
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()

                if not line or line.startswith(('#', '"', "'")):
                    continue
                local_count += 1

            logger.info(f'{f} - {local_count} строк')
            line_count += local_count
        except UnicodeDecodeError:
            logger.warning(f"Ошибка декодирования файла: {f}")

    logger.info("=====================================")
    logger.info(f"Всего строк - {line_count}")
    return line_count


def update_readme(line_count):
    readme_path = Path(os.path.join(os.path.dirname(__file__), '../README.md'))
    if not readme_path.exists():
        logger.error("Файл README.md не найден.")
        return

    try:
        content = readme_path.read_text(encoding="utf-8")
        updated_content = content.replace(
            "Общее количество строк кода в проекте: {}",
            f"Общее количество строк кода в проекте: {line_count}"
        )
        readme_path.write_text(updated_content, encoding="utf-8")
        logger.info("README.md успешно обновлен.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении README.md: {e}")


if __name__ == "__main__":
    total_lines = counting_rows()
    update_readme(total_lines)