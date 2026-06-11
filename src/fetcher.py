"""Парсинг RSS за последние N часов + извлечение релевантной картинки."""
import time
from datetime import datetime, timezone, timedelta

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

from . import config
from .sources import FEEDS

USER_AGENT = "Mozilla/5.0 (compatible; GamingNewsBot/1.0; +https://github.com)"


def _entry_datetime(entry):
    """Достаём дату публикации записи в виде aware datetime (UTC)."""
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            try:
                return dtparser.parse(val)
            except (ValueError, TypeError, OverflowError):
                pass
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            return datetime.fromtimestamp(time.mktime(st), tz=timezone.utc)
    return None


def _extract_image(entry):
    """Пытаемся найти картинку прямо в RSS-записи."""
    for m in entry.get("media_content", []) or []:
        if m.get("url"):
            return m["url"]
    for t in entry.get("media_thumbnail", []) or []:
        if t.get("url"):
            return t["url"]
    for enc in entry.get("enclosures", []) or []:
        if str(enc.get("type", "")).startswith("image") and enc.get("href"):
            return enc["href"]
    for link in entry.get("links", []) or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image"):
            return link.get("href")
    summary = entry.get("summary", "")
    if summary:
        img = BeautifulSoup(summary, "html.parser").find("img")
        if img and img.get("src"):
            return img["src"]
    return None


def fetch_article_og_image(url):
    """Резерв: тянем og:image / twitter:image со страницы первоисточника."""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for prop in ("og:image", "og:image:url", "twitter:image", "twitter:image:src"):
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content"):
                return tag["content"]
    except requests.RequestException:
        return None
    return None


def _clean(html_text, limit=600):
    if not html_text:
        return ""
    text = BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True)
    return text[:limit]


def fetch_recent_news():
    """Собираем и дедуплицируем новости за последние LOOKBACK_HOURS часов."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.LOOKBACK_HOURS)
    seen_links = set()
    items = []

    for source_name, feed_url in FEEDS:
        try:
            parsed = feedparser.parse(feed_url, agent=USER_AGENT)
        except Exception:
            continue  # один сбойный фид не должен ронять весь сбор

        for entry in parsed.entries:
            link = entry.get("link")
            if not link or link in seen_links:
                continue

            dt = _entry_datetime(entry)
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue  # старше окна — пропускаем

            seen_links.add(link)
            items.append({
                "source": source_name,
                "title": (entry.get("title") or "").strip(),
                "link": link,
                "summary": _clean(entry.get("summary", "")),
                "published": dt.isoformat() if dt else "",
                "image": _extract_image(entry),
            })

    items.sort(key=lambda x: x["published"], reverse=True)  # свежее — выше
    return items[: config.MAX_CANDIDATES]
