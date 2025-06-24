FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y curl gcc libpq-dev && \
    curl -Ls https://astral.sh/uv/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml version.txt ./
COPY app/ ./app/

RUN ~/.cargo/bin/uv pip install .  # или если нужно: `uv pip install -e .`

COPY . .

CMD ["gunicorn", "run:app", "-c", "/app/gunicorn.conf.py"]