"""Сервисный бот: обработка команд «по запросу» через long polling.

Два режима:
  poll_once()  — один проход (для cron-воркфлоу, просыпается раз в N минут).
  run_loop()   — непрерывный цикл (для always-on воркфлоу).

Реагирует ТОЛЬКО на сообщения владельца (ADMIN_CHAT_ID).

Команды:
  /post   — опубликовать одну новость прямо сейчас
  /batch  — собрать и опубликовать всю пачку
  /status — длина очереди
"""
import os
import subprocess
import time

from . import config, state
from .telegram import get_updates, send_report


def _persist_state():
    """Коммитим изменения состояния обратно в репозиторий (best-effort).
    Нужно, чтобы /post и offset пережили перезапуск воркфлоу.
    Работает только внутри GitHub Actions.
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    try:
        # Надёжный коммит с обработкой гонок нескольких воркфлоу (см. scripts/commit_state.sh).
        subprocess.run(
            ["bash", "scripts/commit_state.sh", "chore: bot state [skip ci]"],
            check=False,
        )
    except Exception as e:  # noqa: BLE001
        print("[bot] не удалось сохранить состояние:", e)


def _handle_update(upd):
    """Обрабатывает одно обновление. Возвращает True, если состояние изменилось."""
    msg = upd.get("message") or {}
    chat_id = str(msg.get("chat", {}).get("id", ""))
    text = (msg.get("text") or "").strip().lower()

    if chat_id != str(config.ADMIN_CHAT_ID):
        return False  # игнорируем всех, кроме владельца

    # Импорт здесь — чтобы избежать циклического импорта.
    from .main import curate, publish_all, publish_one

    if text.startswith("/post"):
        send_report("\U0001F680 Команда /post принята — публикую новость…")
        if not state.load_queue():
            curate()
        publish_one()
        return True
    elif text.startswith("/batch"):
        send_report("\U0001F680 Команда /batch принята — публикую пачку…")
        publish_all()
        return True
    elif text.startswith("/status"):
        send_report("\U0001F4CA В очереди: " + str(len(state.load_queue())) + " постов.")
    elif text.startswith("/start") or text.startswith("/help"):
        send_report(
            "Доступные команды:\n"
            "/post — опубликовать одну новость сейчас\n"
            "/batch — собрать и опубликовать пачку\n"
            "/status — длина очереди"
        )
    return False


def _process(poll_timeout):
    """Один запрос getUpdates + обработка. Возвращает (изменилось_ли_состояние)."""
    offset = state.load_offset()
    updates = get_updates(offset, poll_timeout)
    changed = False
    last = offset
    for upd in updates:
        last = max(last, upd["update_id"])
        if _handle_update(upd):
            changed = True
    if updates:
        state.save_offset(last)
    return changed


def poll_once():
    """Один проход (режим cron). Совместимо со старым поведением."""
    if not config.SERVICE_BOT_TOKEN:
        return
    _process(poll_timeout=0)


def run_loop(max_seconds):
    """Непрерывный long-polling до исчерпания бюджета времени.
    После каждого изменения состояния — best-effort коммит в репозиторий.
    """
    if not config.SERVICE_BOT_TOKEN:
        print("[bot] SERVICE_BOT_TOKEN не задан — цикл не запущен.")
        return
    deadline = time.time() + max_seconds
    print("[bot] непрерывный режим запущен, бюджет сек:", int(max_seconds))
    while time.time() < deadline:
        try:
            if _process(poll_timeout=50):
                _persist_state()
        except Exception as e:  # noqa: BLE001
            print("[bot] ошибка цикла:", e)
            time.sleep(5)
    _persist_state()
    print("[bot] бюджет времени исчерпан — выход (воркфлоу перезапустит себя).")
