# app/utils/logger.py

from loguru import logger as _logger
import sys
from pathlib import Path
from datetime import datetime
import platform
import os

from app.core.config import BASE_PATH


BASE_LOGS_PATH = os.path.join(BASE_PATH, "logs")
Path(BASE_LOGS_PATH).mkdir(parents=True, exist_ok=True)


def setup_logger():
    _logger.remove()

    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )

    _logger.add(
        sys.stdout,
        format=console_format,
        level="DEBUG",
        colorize=True,
        backtrace=True,
        diagnose=True,
        filter=lambda r: r["level"].no >= _logger.level("INFO").no
    )

    _logger.add(
        os.path.join(BASE_LOGS_PATH, "debug.log"),
        format=file_format,
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        compression="zip"
    )

    _logger.add(
        os.path.join(BASE_LOGS_PATH, "info.log"),
        format=file_format,
        level="INFO",
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )

    _logger.add(
        os.path.join(BASE_LOGS_PATH, "error.log"),
        format=file_format,
        level="ERROR",
        rotation="10 MB",
        retention="60 days",
        compression="zip"
    )

    # Стартовая рамка
    system_info = f"System: {platform.system()} {platform.release()}"
    python_info = f"Python: {platform.python_version()}"
    time_info = f"Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    title = "FASTAPI APP INITIALIZATION"

    lines = [title, system_info, python_info, time_info]
    content_width = max(len(line) for line in lines)
    total_width = content_width + 4  # padding for ║ + spaces

    def format_line(content: str) -> str:
        return f"║ {content.ljust(content_width)} ║"

    _logger.info("")
    _logger.info("╔" + "═" * (total_width - 2) + "╗")
    _logger.info(format_line(title.center(content_width)))
    _logger.info("╠" + "═" * (total_width - 2) + "╣")
    _logger.info(format_line(system_info))
    _logger.info(format_line(python_info))
    _logger.info(format_line(time_info))
    _logger.info("╚" + "═" * (total_width - 2) + "╝")
    _logger.info("")

    return _logger


logger = setup_logger()
