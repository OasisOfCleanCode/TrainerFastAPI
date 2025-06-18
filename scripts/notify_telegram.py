# deploy/notify_telegram.py

import os
from pathlib import Path

from app.core.config import TELEGRAM_TOKEN_FOR_SEND_TELEBOT, CHAT_ID_FOR_SEND


def read_latest_changes(path=".version_env"):
    if not Path(path).exists():
        return "Изменения недоступны"
    return Path(path).read_text(encoding="utf-8").strip().replace("LAST_CHANGES=", "")


def send_message(text):
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN_FOR_SEND_TELEBOT}/sendMessage",
        data={"chat_id": CHAT_ID_FOR_SEND, "text": text, "parse_mode": "Markdown"},
    )
    print("Telegram response:", response.text)


if __name__ == "__main__":
    message = "🚀 *Новый релиз каталога*\n"
    message += read_latest_changes()
    send_message(message)
