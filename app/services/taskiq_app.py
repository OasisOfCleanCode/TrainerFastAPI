# app/services/taskiq_app.py

from taskiq import TaskiqScheduler, ZeroMQBroker

broker = ZeroMQBroker("0.0.0.0", 5777)
scheduler = TaskiqScheduler(broker=broker)  # type: ignore