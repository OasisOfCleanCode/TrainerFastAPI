.PHONY: setup

setup:
	@echo "🔍 Определение операционной системы..."
	@if [ "$$(uname)" = "Linux" ] || [ "$$(uname)" = "Darwin" ]; then \
		echo "🐧 macOS/Linux обнаружен"; \
		chmod +x setup.sh && ./setup.sh; \
	elif [ "$$OS" = "Windows_NT" ]; then \
		if [ -f setup.cmd ]; then \
			echo "🪟 Windows CMD обнаружен"; \
			cmd //C setup.cmd; \
		else \
			echo "💥 setup.cmd не найден"; \
		fi; \
	else \
		echo "❌ ОС не поддерживается автоматически. Запусти нужный скрипт вручную."; \
	fi
