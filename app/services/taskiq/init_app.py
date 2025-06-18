# services/taskiq.py

from taskiq_redis import ListQueueBroker

from config import REDIS_HOST, REDIS_PORT, REDIS_TASKIQ_INDEX


taskiq_redis_broker = ListQueueBroker(
    f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_TASKIQ_INDEX}"
)
