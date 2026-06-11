"""Простое файловое состояние (JSON). Файлы коммитятся обратно в репозиторий
шагом GitHub Actions — так состояние переживает запуски.
"""
import json
import os
import re
from urllib.parse import urlsplit

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


def normalize_link(url):
    """Нормализуем ссылку: убираем схему, www, query и хвостовой слэш —
    чтобы один и тот же материал не считался разным из-за мелочей в URL."""
    if not url:
        return ""
    s = urlsplit(url.strip())
    if s.scheme or s.netloc:
        host = (s.hostname or "").lower()
        path = s.path
    else:
        host = ""
        path = url.strip().lower()
    if host.startswith("www."):
        host = host[4:]
    path = path.rstrip("/")
    return (host + path) if host else path


def title_key(title):
    """Ключ по заголовку — ловит один и тот же сюжет из разных источников."""
    t = (title or "").lower()
    t = re.sub(r"[^0-9a-zа-яё]+", " ", t)
    return " ".join(t.split())


def post_keys(item):
    """Набор ключей дедупликации (по ссылке и по заголовку)."""
    keys = []
    lk = normalize_link(item.get("link", ""))
    if lk:
        keys.append("l:" + lk)
    tk = title_key(item.get("title", ""))
    if tk:
        keys.append("t:" + tk)
    return keys


def is_posted(item, posted):
    """True, если новость уже публиковалась (по любому из ключей)."""
    return any(k in posted for k in post_keys(item))


def load_posted():
    """Множество ключей уже опубликованного. Старый формат
    (сырые ссылки) мигрируем на лету в нормализованные ключи."""
    raw = _load(POSTED_FILE, [])
    out = set()
    for entry in raw:
        if not isinstance(entry, str):
            continue
        if entry.startswith("l:") or entry.startswith("t:"):
            out.add(entry)
        else:
            lk = normalize_link(entry)
            if lk:
                out.add("l:" + lk)
    return out


def save_posted(keys):
    _save(POSTED_FILE, sorted(keys))


def load_queue():
    return _load(QUEUE_FILE, [])


def save_queue(queue):
    _save(QUEUE_FILE, queue)


def load_offset():
    return int(_load(OFFSET_FILE, {"offset": 0}).get("offset", 0))


def save_offset(offset):
    _save(OFFSET_FILE, {"offset": int(offset)})
