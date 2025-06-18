# Базовый образ с Python 3.12
FROM python:3.12-slim


ENV PYTHONUNBUFFERED=1

# Устанавливаем системные зависимости (для psycopg2 и др.)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем pyproject.toml и version.txt для установки зависимостей
COPY pyproject.toml .
COPY version.txt .

# Обновляем pip и устанавливаем зависимости
RUN pip install --upgrade pip
RUN pip install .

# Копируем остальной код
COPY . .

# Открываем порт (по желанию)
EXPOSE 8666

# Запускаем приложение
CMD ["gunicorn", "--config", "gunicorn.conf.py", "run:app"]
