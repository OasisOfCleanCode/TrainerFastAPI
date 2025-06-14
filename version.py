# deploy/version.py

import os


def get_app_version():
    # Определение пути к файлу version.txt в корне проекта
    version_file = os.path.join(os.path.dirname(__file__), "version.txt")

    # Чтение текущей версии из файла
    try:
        with open(version_file, "r") as file:
            version = file.read().strip()
            print(f"Current version: {version}")
            return version

    except FileNotFoundError:
        print(f"Version file not found. Returning default version '0.0.1'.")
        return "0.0.1"
