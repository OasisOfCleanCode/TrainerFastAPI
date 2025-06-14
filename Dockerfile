# Dockerfile

FROM python:3.12-slim

# Системные зависимости
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала копируем только зависимости (для кеширования)
COPY requirements.in ./
COPY setup.py ./
COPY README.md ./
COPY version.py ./deploy/version.py


# Устанавливаем зависимости
RUN pip install --upgrade pip && \
    pip install --no-cache-dir pip-tools && \
    pip-compile requirements.in && \
    pip install --no-cache-dir -r requirements.txt

# Затем копируем всё остальное
COPY . .

# Устанавливаем проект как пакет
RUN pip install --no-cache-dir -e .

EXPOSE 8666

CMD ["gunicorn", "-c", "/app/alembic.ini", "/app/gunicorn.conf.py", "run:app"]