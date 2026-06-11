"""Простое файловое состояние (JSON). Файлы коммитятся обратно в репозиторий
шагом GitHub Actions — так состояние переживает запуски.
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
POSTED_FILE = os.path.join(DATA_DIR, "posted.json")
QUEUE_FILE = os.path.join(DATA_DIR, "queue.json")
OFFSET_FILE = os.path.join(DATA_DIR, "offset.json")


def _load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _save(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_posted():
    return set(_load(POSTED_FILE, []))


def save_posted(links):
    _save(POSTED_FILE, sorted(links))


def load_queue():
    return _load(QUEUE_FILE, [])


def save_queue(queue):
    _save(QUEUE_FILE, queue)


def load_offset():
    return int(_load(OFFSET_FILE, {"offset": 0}).get("offset", 0))


def save_offset(offset):
    _save(OFFSET_FILE, {"offset": int(offset)})
