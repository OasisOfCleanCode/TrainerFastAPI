# services/celery/tasks.py

from services.celery.init_app import celery_app


@celery_app.task
def test():
    print("✅ Anwill Back USER: 🐰 Celery - test task выполнена")
