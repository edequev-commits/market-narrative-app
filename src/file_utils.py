import json
import os


def ensure_folder(path: str):
    if not path:
        return
    os.makedirs(path, exist_ok=True)


def save_json(data, filepath: str):
    folder = os.path.dirname(filepath)
    ensure_folder(folder)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_text(text: str, filepath: str):
    folder = os.path.dirname(filepath)
    ensure_folder(folder)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)