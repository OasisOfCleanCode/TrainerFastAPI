# services/celery/init_app.py

from celery import Celery


celery_app = Celery(
    "services.celery.init_app",
    broker=f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}",
    backend=f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CELERY_INDEX}",
    include=["services.celery.tasks"],
    broker_connection_retry_on_startup=True,
)
