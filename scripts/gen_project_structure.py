# app/utils/gen_project_structure.py

import os

from app.utils.logger import logger


def get_readable_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024


def generate_folder_structure(path, exclusions, output_file):
    structure = ["Mode            Length Hierarchy\n",
                 "----            ------ ---------\n"]

    path = str(path)

    for root, dirs, files in os.walk(path):
        # Удаляем исключенные папки из обхода
        dirs[:] = [d for d in dirs if d not in exclusions]

        level = root.replace(path, "").count(os.sep)
        indent = " " * 4 * level

        # Вычисляем размер файлов в текущей директории
        dir_size = sum(os.path.getsize(os.path.join(root, file)) for file in files)
        structure.append(
            f"d----       {get_readable_size(dir_size):>10} {indent}{os.path.basename(root)}\n"
        )

        sub_indent = " " * 4 * (level + 1)
        for file in files:
            file_path = os.path.join(root, file)
            file_size = get_readable_size(os.path.getsize(file_path))
            structure.append(f"-a---       {file_size:>10} {sub_indent}├── {file}\n")

    # Записываем структуру в файл
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("".join(structure))
    logger.info(f"Дерево проекта обновлено в {output_file}")


if __name__ == "__main__":
    base_path = Path(__file__).resolve().parent.parent
    exclusions = [
        ".venv",
        ".git",
        ".idea",
        "__pycache__",
        ".github",
        "photos",
        "logs",
        "web_app.egg-info",
        "node_modules",
        ".mypy_cache",
        "build",
    ]
    output_file = BASE_PATH / "descriptions" / "project_structure.txt"
    generate_folder_structure(base_path, exclusions, output_file)
