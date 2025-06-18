from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, HTMLResponse

info_router = APIRouter()

EXCLUDED_FILES = {
    "__init__.py",
    "__pycache__",
    ".env",
    ".dockerignore",
    ".gitignore",
    "venv",
    ".venv",
    "env",
    ".git",
    "node_modules",
    "web_app.egg-info",
    "TrainerAPI.egg-info",
    "build",
    "node_modules",
    "logs"
}
EXCLUDED_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".db", ".log"}


def is_valid_file(path: Path) -> bool:
    """Проверяет, нужно ли показывать файл или директорию"""
    # Исключаем любые части пути, которые явно указаны
    if any(part in EXCLUDED_FILES for part in path.parts):
        return False

    # Исключаем по расширению (только для файлов)
    if path.is_file() and path.suffix in EXCLUDED_EXTENSIONS:
        return False

    # Исключаем скрытые директории и файлы (но не корень проекта!)
    if any(part.startswith(".") and part != BASE_PATH.name for part in path.parts):
        return False

    return True


def get_file_icon(ext: str, name: str) -> str:
    if name.lower() == "readme.md":
        return "📘"
    if ext in {".py"}:
        return "🐍"
    if ext in {".js"}:
        return "🟨"
    if ext in {".css"}:
        return "🎨"
    if ext in {".html", ".htm", ".jinja"}:
        return "🧩"
    if ext in {".sh", ".ps1"}:
        return "🖥️"
    if ext in {".json", ".yaml", ".yml", ".toml"}:
        return "🧾"
    if ext in {".md"}:
        return "📘"
    if ext in {".txt"}:
        return "📄"
    if ext in {".log"}:
        return "📜"
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif"}:
        return "🖼️"
    if ext in {".pdf"}:
        return "📕"
    if ext in {".zip", ".tar", ".gz"}:
        return "🗜️"
    if ext in {".sql"}:
        return "🗄️"
    return "📄"

@info_router.get("/health")
async def health():
    """
    **Проверка работоспособности сервиса**

    ```
    Endpoint: GET /health
    Response: {"status": "ok"}
    Status Codes:
      - 200: Сервис работает нормально
    ```

    Простейший эндпоинт для проверки доступности сервиса.
    Всегда возвращает HTTP 200 с JSON-объектом {"status": "ok"}.
    """
    return {"status": "ok"}


@info_router.get("/source/{path:path}", response_class=FileResponse)
async def get_source_file(path: str):
    """
    **Получение содержимого файла из проекта с поддержкой вложенных путей**

    ```
    Endpoint: GET /source/{path}

    Parameters:
      - path (str): Относительный путь к файлу от корня проекта. Поддерживает вложенные пути.
                   Примеры:
                   - "README.md" - файл в корне проекта
                   - "src/main.py" - файл в поддиректории
                   - "docs/api/v1/spec.yaml" - глубоко вложенный файл

    Response Types:
      - PlainTextResponse: Для текстовых файлов (.py, .md, .txt, .html, .css, .js, .json)
                          с Content-Type: text/plain
      - FileResponse: Для всех остальных типов файлов (бинарные файлы, изображения и т.д.)

    Status Codes:
      - 200: Успешный запрос
      - 400: Запрошенный путь не является файлом (например, это директория)
      - 403: Доступ к файлу запрещен (скрытые/системные файлы)
      - 404: Файл не найден

    Security:
      - Запрещен доступ к файлам, начинающимся с точки (скрытые файлы)
      - Запрещен доступ к системным директориям (.git, __pycache__ и т.д.)
      - Запрещен доступ к файлам с определенными расширениями (.pyc, .pyd и т.д.)

    Examples:
      1. Получение README.md из корня проекта:
         GET /source/README.md

      2. Получение файла из поддиректории src:
         GET /source/src/main.py

      3. Получение конфигурационного файла из глубокой вложенности:
         GET /source/configs/production/database.yaml

      4. Получение изображения (вернется как бинарный файл):
         GET /source/static/images/logo.png
    ```

    Возвращает содержимое файла проекта с учетом следующих правил:
    1. Для текстовых файлов возвращает содержимое непосредственно в теле ответа
    2. Для бинарных файлов возвращает файл для скачивания
    3. Поддерживает любую глубину вложенности директорий
    4. Путь всегда указывается относительно корня проекта
    5. Чувствителен к регистру в именах файлов на UNIX-системах

    """
    full_path = BASE_PATH / path

    # Проверки безопасности
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Requested path is not a file")
    if not is_valid_file(full_path):
        raise HTTPException(status_code=403, detail="Access to this file is restricted")

    # Для текстовых файлов возвращаем как текст
    if full_path.suffix in {".py", ".md", ".txt", ".html", ".css", ".js", ".json"}:
        return PlainTextResponse(
            content=full_path.read_text(encoding="utf-8"), media_type="text/plain"
        )

    return FileResponse(full_path)


@info_router.get("/structure", response_class=PlainTextResponse)
async def get_project_structure():
    """
    **Получение древовидной структуры проекта**

    Endpoint: GET /structure
    Response: PlainTextResponse
    Format:
      📁 dir_name
          📄 file_name (size KB)
    Status Codes:
      - 200: Успешный запрос

    Возвращает текстовое представление структуры проекта в виде дерева.
    Для файлов указывается размер в килобайтах. Скрытые файлы и директории
    исключаются из вывода.
    """
    structure = [f"📁 {BASE_PATH.name}"]  # Добавляем корневую директорию

    def build_tree(directory: Path, prefix: str = ""):
        try:
            items = sorted(directory.iterdir(), key=lambda x: (x.is_dir(), x.name.lower()))
        except (PermissionError, OSError):
            return

        for item in items:
            if not is_valid_file(item):
                continue

            if item.is_dir():
                structure.append(f"{prefix}📁 {item.name}")
                build_tree(item, prefix + "    ")
            else:
                size_kb = item.stat().st_size / 1024
                icon = get_file_icon(item.suffix.lower(), item.name)
                structure.append(f"{prefix}{icon} {item.name} ({size_kb:.1f} KB)")

    build_tree(BASE_PATH)
    return "\n".join(structure)


@info_router.get("/structure/html", response_class=HTMLResponse)
async def get_clickable_structure():
    """
    **HTML-структура проекта со ссылками на файлы**

    Endpoint: GET /structure/html
    Response: HTMLResponse
    Стиль: дерево в моноширинном виде, кликабельные файлы (ссылки на /source/{path})
    """
    lines = [f"<div><strong>📁 {BASE_PATH.name}</strong></div>"]

    def build_tree(directory: Path, prefix: str = ""):
        try:
            items = sorted(directory.iterdir(), key=lambda x: (x.is_dir(), x.name.lower()))
        except (PermissionError, OSError):
            return

        for item in items:
            if not is_valid_file(item):
                continue

            rel_path = item.relative_to(BASE_PATH).as_posix()
            safe_href = f"/api/info/source/{rel_path}"

            if item.is_dir():
                lines.append(f"{prefix}📁 {item.name}<br>")
                build_tree(item, prefix + "&nbsp;&nbsp;&nbsp;&nbsp;")
            else:
                size_kb = item.stat().st_size / 1024
                icon = get_file_icon(item.suffix.lower(), item.name)
                lines.append(
                    f"{prefix}{icon} <a href='{safe_href}' target='_blank' style='color:#4fc3f7;text-decoration:none;'>{item.name}</a> "
                    f"<span style='color:gray'>({size_kb:.1f} KB)</span><br>"
                )

    build_tree(BASE_PATH)

    return f"""
    <html>
        <head>
            <title>Структура проекта</title>
            <style>
                body {{
                    background-color: #1e1e1e;
                    color: #ccc;
                    font-family: monospace;
                    padding: 20px;
                    white-space: pre-wrap;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            {''.join(lines)}
        </body>
    </html>
    """

@info_router.get("/", response_class=PlainTextResponse)
async def get_file_list():
    """
    **Получение плоского списка всех доступных файлов**

    Endpoint: GET /
    Response: PlainTextResponse
    Format:
      path/to/file1
      path/to/file2
    Status Codes:
      - 200: Успешный запрос

    Возвращает отсортированный список всех файлов проекта с относительными путями.
    Скрытые файлы и специальные директории исключаются из вывода.
    """
    file_list = []

    # Сначала обрабатываем файлы в корне
    for item in BASE_PATH.iterdir():
        if item.is_file() and is_valid_file(item):
            file_list.append(item.name)

    # Затем обрабатываем все остальные файлы рекурсивно
    for item in BASE_PATH.rglob("*"):
        if not is_valid_file(item) or not item.is_file() or item.parent == BASE_PATH:
            continue

        relative_path = item.relative_to(BASE_PATH)
        file_list.append(str(relative_path))

    return "\n".join(sorted(file_list, key=lambda x: x.lower()))


@info_router.get("/README.md", response_class=FileResponse)
async def readme():
    """
    **Получение файла README.md проекта**

    ```
    Endpoint: GET /README.md
    Response: FileResponse
    Status Codes:
      - 200: Успешный запрос
      - 404: Файл не найден
    ```

    Возвращает содержимое основного README-файла проекта.
    Если файл отсутствует, возвращает HTTP 404.
    """
    full_path = BASE_PATH / "README.md"
    return FileResponse(full_path)


@info_router.get("/logo_readme.webp", response_class=FileResponse)
async def readme_logo():
    """
    **Получение логотипа проекта**

    ```
    Endpoint: GET /logo_readme.webp
    Response: FileResponse
    Status Codes:
      - 200: Успешный запрос
      - 404: Файл не найден
    ```

    Возвращает изображение логотипа проекта в формате WEBP.
    Если файл отсутствует, возвращает HTTP 404.
    """
    full_path = BASE_PATH / "logo_readme.webp"
    return FileResponse(full_path)

