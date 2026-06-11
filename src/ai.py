"""Работа с бесплатным ИИ: выбор топ-N новостей и генерация постов.
Один запрос на день -> легко укладывается в бесплатные лимиты.
Основной провайдер — Gemini, резерв — OpenRouter (перебираем несколько бесплатных моделей).
На 429/5xx делаем повторы с экспоненциальной задержкой, потом фолбэк.
"""
import json
import re
import time

import requests

from . import config

# Сколько раз повторять запрос при временных ошибках (429/5xx) до фолбэка.
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 4  # сек: 4, 8, 16...
RETRY_STATUSES = {429, 500, 502, 503, 504}

# Запасные БЕСПЛАТНЫЕ модели OpenRouter — перебираем по очереди при 429/ошибке.
# Первым идёт OPENROUTER_MODEL из Secrets, потом эти.
OPENROUTER_FALLBACK_MODELS = [
    "openrouter/free",                          # авто-роутер: сам выбирает любую доступную бесплатную модель
    "deepseek/deepseek-chat-v3-0324:free",
    "deepseek/deepseek-r1:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-235b-a22b:free",
]

# В шаблоне используем простые плейсхолдеры __N__ и __NEWS__ (без str.format),
# чтобы фигурные скобки JSON-примера не надо было экранировать.
PROMPT = """Ты — главный редактор крупного русскоязычного игрового Telegram-канала.
Ниже — список игровых новостей за последние 24 часа в формате JSON.

Задача:
1. Оцени каждую новость по хайпу, важности, актуальности и пользе для аудитории.
2. Выбери РОВНО __N__ самых топовых новостей. Не бери дубли одной темы из разных источников.
3. Для каждой выбранной новости напиши вовлекающий пост на русском языке.

Требования к посту:
- title: цепляющий заголовок до 80 символов, без хэштегов и без эмодзи в начале.
- body: 2-4 коротких абзаца ИЛИ маркированный список, живой язык, без воды, до 650 символов.
  Для выделения используй ТОЛЬКО HTML-теги Telegram: <b>жирный</b> и <i>курсив</i>.
  Списки оформляй через символ "• " и переносы строк. НЕ используй Markdown (никаких ** или __).
  Уместные эмодзи приветствуются (по делу, не перебарщивай).
- tags: 1-3 коротких тематических тега (без решётки).
- reason: 1-2 предложения для внутреннего отчёта — почему новость попала в топ.
- index: число — индекс новости из входного списка.

Верни СТРОГО валидный JSON-массив объектов без какого-либо текста вокруг.
Каждый элемент массива — объект с полями: index (число), title (строка),
body (строка), tags (массив строк), reason (строка).

Список новостей:
__NEWS__
"""


def _payload(items):
    compact = [
        {"index": i, "source": it["source"], "title": it["title"], "summary": it["summary"]}
        for i, it in enumerate(items)
    ]
    return json.dumps(compact, ensure_ascii=False)


def _build_prompt(items, n):
    return PROMPT.replace("__N__", str(n)).replace("__NEWS__", _payload(items))


def _extract_json(text):
    """Аккуратно вытаскиваем JSON-массив, даже если ИИ обернул его в код-блок."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)


def _request_with_retries(method, url, **kwargs):
    """POST/GET с повторами на временных ошибках (429/5xx).
    Учитываем заголовок Retry-After, если сервер его вернул.
    """
    last_exc = None
    for attempt in range(RETRY_ATTEMPTS):
        resp = requests.request(method, url, **kwargs)
        if resp.status_code in RETRY_STATUSES and attempt < RETRY_ATTEMPTS - 1:
            retry_after = resp.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else RETRY_BASE_DELAY * (2 ** attempt)
            except ValueError:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
            print("[ai] {} {} -> повтор через {:.0f}с (попытка {}/{})".format(
                resp.status_code, url.split("?")[0], delay, attempt + 1, RETRY_ATTEMPTS))
            time.sleep(delay)
            last_exc = requests.HTTPError("{} for {}".format(resp.status_code, url.split("?")[0]))
            continue
        resp.raise_for_status()
        return resp
    if last_exc:
        raise last_exc
    raise RuntimeError("Не удалось выполнить запрос: " + url)


def _call_gemini(prompt):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + config.GEMINI_MODEL + ":generateContent"
    )
    r = _request_with_retries(
        "POST", url,
        params={"key": config.GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
        },
        timeout=120,
    )
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_openrouter(prompt, model):
    r = _request_with_retries(
        "POST", "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": "Bearer " + config.OPENROUTER_API_KEY},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        },
        timeout=120,
    )
    return r.json()["choices"][0]["message"]["content"]


def _generate(prompt):
    """Пробуем Gemini (с повторами), при ошибке — OpenRouter (перебор бесплатных моделей)."""
    errors = []

    if config.GEMINI_API_KEY:
        try:
            return _call_gemini(prompt)
        except Exception as e:  # noqa: BLE001
            errors.append("Gemini: " + str(e))

    if config.OPENROUTER_API_KEY:
        models = []
        for m in [config.OPENROUTER_MODEL] + OPENROUTER_FALLBACK_MODELS:
            if m and m not in models:
                models.append(m)
        for m in models:
            try:
                return _call_openrouter(prompt, m)
            except Exception as e:  # noqa: BLE001
                errors.append("OpenRouter[" + m + "]: " + str(e))

    if not errors:
        raise RuntimeError(
            "Не задан ни один ИИ-ключ. Укажи GEMINI_API_KEY и/или OPENROUTER_API_KEY в Secrets."
        )
    raise RuntimeError("Все ИИ-провайдеры недоступны -> " + "; ".join(errors))


def select_and_write(items, n):
    """Возвращает список готовых постов с привязкой к исходным новостям."""
    raw = _generate(_build_prompt(items, n))
    selected = _extract_json(raw)

    posts = []
    for sel in selected:
        idx = sel.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(items):
            continue
        src = items[idx]
        posts.append({
            "title": sel.get("title") or src["title"],
            "body": sel.get("body", ""),
            "tags": sel.get("tags", []) or [],
            "reason": sel.get("reason", ""),
            "link": src["link"],
            "source": src["source"],
            "image": src["image"],
        })
    return posts[:n]
