#!/bin/bash
set -e

echo "🔧 Установка uv..."
curl -Ls https://astral.sh/uv/install.sh | sh

echo "✅ uv установлен"

export PATH="$HOME/.cargo/bin:$PATH"

echo "📦 Создание виртуального окружения..."
uv venv

echo "📥 Установка зависимостей..."
uv pip install .

echo "🚀 Готово. Активируй окружение: source .venv/bin/activate"
