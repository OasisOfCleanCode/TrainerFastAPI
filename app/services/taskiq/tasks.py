# services/taskiq/tasks.py

from services.taskiq.init_app import taskiq_broker


@taskiq_broker.task
async def test_task():
    print("✅ Anwill Back USER: 🧠 TaskIQ - test task выполнена")
