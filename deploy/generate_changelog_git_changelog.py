# deploy/generate_changelog_git_changelog.py

import subprocess
import sys
from pathlib import Path


def generate_changelog(output_path="CHANGELOG.md"):
    result = subprocess.run(
        ["git-changelog", "--output", output_path, "--template", "angular"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Ошибка генерации CHANGELOG:", result.stderr)
        sys.exit(1)
    print(f"✅ CHANGELOG сгенерирован в {output_path}")


def extract_latest_changes(md_path="CHANGELOG.md", limit=10):
    changes = []
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()
    inside_block = False
    for line in lines:
        if line.startswith("## "):  # новый релиз
            if inside_block:
                break
            inside_block = True
            changes.append(line)
        elif inside_block and line.strip():
            changes.append(line)
    return "\n".join(changes[:limit])


def main():
    generate_changelog()
    latest = extract_latest_changes()
    print("--- Последние изменения ---")
    print(latest)

    lines = latest.splitlines()
    version_line = next((line for line in lines if line.startswith("### ")), "")
    content_lines = [line for line in lines[1:] if line.strip()]
    content = "\n".join(content_lines)

    with open(".version_env", "w", encoding="utf-8") as f:
        f.write(f"LAST_CHANGES_HEADER={version_line.strip()}\n")
        f.write(f"LAST_CHANGES_CONTENT={content.strip().replace(chr(10), '%0A')}")


if __name__ == "__main__":
    main()
