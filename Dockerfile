FROM python:3.12-slim

# Обновление системы и установка необходимых зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Установка uv
RUN curl -Ls https://astral.sh/uv/install.sh | sh && \
    ln -s ~/.cargo/bin/uv /usr/local/bin/uv

WORKDIR /app

# Копируем только pyproject.toml и версию — быстрее layer caching
COPY pyproject.toml version.txt ./

# Установка зависимостей проекта
RUN uv pip install .

# Копируем остальной код
COPY . .

EXPOSE 8666

# Команда запуска (можно поменять под нужды проекта)
CMD ["gunicorn", "run:app", "-c", "/app/gunicorn.conf.py"]
