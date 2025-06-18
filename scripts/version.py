# deploy/version.py

import sys
from core.config import BASE_PATH
from app.utils.logger import logger



version_file = BASE_PATH / "version.txt"

def get_update_version():
    new_version = sys.argv[1]

    with open(version_file, "w") as file:
        file.write(new_version)

    logger.info(f"Version updated to: {new_version}")


def get_app_version():
    # Определение пути к файлу version.txt в корне проекта

    # Чтение текущей версии из файла
    try:
        with open(version_file, "r") as file:
            version = file.read().strip()
            print(f"Current version: {version}")
            return version

    except FileNotFoundError:
        print(f"Version file not found. Returning default version '0.0.1'.")
        return "0.0.1"
