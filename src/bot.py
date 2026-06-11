"""Обработка команд «по запросу» через сервисный бот (long polling).
Запускается отдельным workflow по расписанию (например, раз в 30 минут)
и реагирует ТОЛЬКО на сообщения владельца (ADMIN_CHAT_ID).

Команды:
  /post   — опубликовать одну новость прямо сейчас
  /batch  — собрать и опубликовать всю пачку
  /status — длина очереди
"""
from . import config, state
from .telegram import get_updates, send_report


def poll_once():
    if not config.SERVICE_BOT_TOKEN:
        return

    offset = state.load_offset()
    updates = get_updates(offset)
    last = offset

    # Импортируем здесь, чтобы избежать циклического импорта
    from .main import curate, publish_all, publish_one

    for upd in updates:
        last = max(last, upd["update_id"])
        msg = upd.get("message") or {}
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = (msg.get("text") or "").strip().lower()

        if chat_id != str(config.ADMIN_CHAT_ID):
            continue  # игнорируем всех, кроме владельца

        if text.startswith("/post"):
            send_report("\U0001F680 Команда /post принята — публикую новость…")
            if not state.load_queue():
                curate()
            publish_one()
        elif text.startswith("/batch"):
            send_report("\U0001F680 Команда /batch принята — публикую пачку…")
            publish_all()
        elif text.startswith("/status"):
            send_report(f"\U0001F4CA В очереди: {len(state.load_queue())} постов.")
        elif text.startswith("/start") or text.startswith("/help"):
            send_report(
                "Доступные команды:\n"
                "/post — опубликовать одну новость сейчас\n"
                "/batch — собрать и опубликовать пачку\n"
                "/status — длина очереди"
            )

    state.save_offset(last)
