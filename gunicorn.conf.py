# gunicorn.conf.py

import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
bind = "0.0.0.0:8666"
timeout = 120
keepalive = 5
accesslog = "-"  # stdout
errorlog = "-"  # stdout
forwarded_allow_ips = "*"
graceful_timeout = 30  # время на завершение воркеров
limit_request_line = 8190  # защита от больших заголовков
limit_request_fields = 100
limit_request_field_size = 8190
