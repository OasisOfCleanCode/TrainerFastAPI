#!/usr/bin/env bash

# 1️⃣ Установим базовые утилиты
python -m pip install --upgrade pip setuptools pip-tools

# 2️⃣ Сгенерируем requirements.txt
pip-compile --strip-extras --output-file=requirements.txt requirements.in

# 3️⃣ Установим зависимости
pip-sync requirements.txt
