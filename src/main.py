"""Точка входа. Режимы:
  curate       — собрать новости, выбрать топ-N, сложить в очередь (1x в день).
  publish      — опубликовать 1 пост из очереди (вызывается по cron-слотам).
  publish_all  — собрать и сразу опубликовать всю пачку (ручной режим).
  bot          — обработать команды сервисного бота (по запросу).

Запуск: python -m src.main <режим>
"""
import argparse
import datetime as dt

from . import config, state
from .ai import select_and_write
from .fetcher import fetch_article_og_image, fetch_recent_news
from .telegram import publish_post, send_report


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _ensure_image(post):
    """Гарантируем картинку: если в RSS её не было — берём og:image со страницы."""
    if not post.get("image"):
        post["image"] = fetch_article_og_image(post["link"])
    return post


def curate():
    posted = state.load_posted()
    news = [n for n in fetch_recent_news() if n["link"] not in posted]
    if not news:
        send_report(
            f"\u26A0\uFE0F <b>Курирование {_now()}</b>\n"
            f"Свежих новостей за {config.LOOKBACK_HOURS}ч не найдено."
        )
        return

    posts = select_and_write(news, config.POSTS_PER_DAY)
    for p in posts:
        _ensure_image(p)
    state.save_queue(posts)

    lines = [
        f"\U0001F5C2 <b>Очередь на день готова ({_now()})</b>",
        f"Отобрано постов: {len(posts)}",
        "",
    ]
    for i, p in enumerate(posts, 1):
        lines.append(f"{i}. <b>{p['title']}</b>\n   \U0001F4A1 {p['reason']}")
    send_report("\n".join(lines))


def publish_one():
    queue = state.load_queue()
    if not queue:
        return
    post = queue.pop(0)
    publish_post(post)

    posted = state.load_posted()
    posted.add(post["link"])
    state.save_posted(posted)
    state.save_queue(queue)

    send_report(
        f"\u2705 <b>Опубликовано ({_now()})</b>\n\n"
        f"<b>{post['title']}</b>\n"
        f"Источник: {post['source']}\n"
        f"\U0001F517 {post['link']}\n\n"
        f"<i>Почему выбрано:</i> {post['reason']}\n"
        f"Осталось в очереди: {len(queue)}"
    )


def publish_all():
    """Курируем заново и публикуем всю пачку (для ручного запуска по запросу)."""
    curate()
    queue = state.load_queue()
    total = len(queue)
    posted = state.load_posted()
    ok = 0
    for post in queue:
        try:
            publish_post(post)
            posted.add(post["link"])
            ok += 1
        except Exception as e:  # noqa: BLE001
            send_report(f"\u274C Ошибка публикации «{post['title']}»: {e}")
    state.save_posted(posted)
    state.save_queue([])
    send_report(
        f"\U0001F4E6 <b>Пакет завершён ({_now()})</b>\nОпубликовано: {ok} из {total}."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=["curate", "publish", "publish_all", "bot", "bot_loop"],
    )
    args = parser.parse_args()

    if args.mode == "curate":
        curate()
    elif args.mode == "publish":
        publish_one()
    elif args.mode == "publish_all":
        publish_all()
    elif args.mode == "bot":
        from .bot import poll_once
        poll_once()
    elif args.mode == "bot_loop":
        import os
        from .bot import run_loop
        # Бюджет чуть меньше лимита одного запуска Actions (6ч).
        minutes = int(os.environ.get("LOOP_MINUTES", "340"))
        run_loop(minutes * 60)


if __name__ == "__main__":
    main()
