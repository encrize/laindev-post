"""Публикация постов в канал и отправка отчётов сервисным ботом.
Используем parse_mode=HTML: надёжнее, чем MarkdownV2 (меньше проблем с экранированием).
"""
import html

import requests

from . import config

TELEGRAM_API = "https://api.telegram.org/bot"


def _api(token, method):
    # Итоговый URL вида: https://api.telegram.org/bot<TOKEN>/<method>
    return TELEGRAM_API + token + "/" + method


_ALLOWED_TAGS = ("b", "i", "u", "s")  # теги, которые разрешаем ИИ использовать в body


def _sanitize(text):
    """Экранируем спецсимволы, но возвращаем разрешённые теги форматирования."""
    escaped = html.escape(text or "")
    for tag in _ALLOWED_TAGS:
        escaped = escaped.replace("&lt;" + tag + "&gt;", "<" + tag + ">")
        escaped = escaped.replace("&lt;/" + tag + "&gt;", "</" + tag + ">")
    return escaped


def _format_caption(post):
    title = _sanitize(post["title"])
    body = _sanitize(post["body"])
    parts = ["<b>" + title + "</b>", "", body]

    tags = post.get("tags") or []
    if tags:
        rendered = " ".join("#" + html.escape(t.replace(" ", "_")) for t in tags)
        parts += ["", rendered]

    link = html.escape(post["link"])
    source = html.escape(post["source"])
    parts += ["", '\U0001F517 <a href="' + link + '">Источник: ' + source + "</a>"]
    return "\n".join(parts)


def _post(token, method, payload):
    r = requests.post(_api(token, method), json=payload, timeout=60)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError("Telegram " + method + " error: " + str(data))
    return data["result"]


def publish_post(post):
    """Публикует один пост в канал. Картинка обязательна, если она найдена.
    Если caption длиннее лимита Telegram (1024) — шлём фото, затем полный текст.
    """
    caption = _format_caption(post)
    image = post.get("image")

    # 1) Идеальный случай: фото + подпись в одном сообщении
    if image and len(caption) <= 1024:
        try:
            return _post(config.CHANNEL_BOT_TOKEN, "sendPhoto", {
                "chat_id": config.CHANNEL_ID,
                "photo": image,
                "caption": caption,
                "parse_mode": "HTML",
            })
        except RuntimeError:
            pass  # картинка не принялась — уходим в текстовый вариант ниже

    # 2) Картинка есть, но текст длинный: сначала фото с коротким заголовком
    if image:
        try:
            _post(config.CHANNEL_BOT_TOKEN, "sendPhoto", {
                "chat_id": config.CHANNEL_ID,
                "photo": image,
                "caption": "<b>" + _sanitize(post["title"]) + "</b>",
                "parse_mode": "HTML",
            })
        except RuntimeError:
            pass

    # 3) Полный текст отдельным сообщением (надёжный fallback)
    return _post(config.CHANNEL_BOT_TOKEN, "sendMessage", {
        "chat_id": config.CHANNEL_ID,
        "text": caption,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })


def send_report(text):
    """Отчёт/уведомление тебе в ЛС через сервисный бот."""
    if not config.SERVICE_BOT_TOKEN or not config.ADMIN_CHAT_ID:
        return
    _post(config.SERVICE_BOT_TOKEN, "sendMessage", {
        "chat_id": config.ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })


def get_updates(offset, poll_timeout=0):
    """Получаем обновления сервисного бота (для команд по запросу).
    poll_timeout>0 включает длинный поллинг: Telegram сам держит соединение
    до poll_timeout секунд и отвечает сразу, как только приходит сообщение."""
    r = requests.get(
        _api(config.SERVICE_BOT_TOKEN, "getUpdates"),
        params={"offset": offset + 1, "timeout": poll_timeout, "allowed_updates": '["message"]'},
        timeout=poll_timeout + 20,
    )
    return r.json().get("result", [])
