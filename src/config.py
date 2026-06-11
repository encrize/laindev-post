"""Конфигурация: всё читается из переменных окружения (GitHub Secrets).
Локально можно положить значения в .env и экспортировать их перед запуском.
"""
import os

# --- Telegram ---
# Бот, который ПУБЛИКУЕТ в канал (должен быть админом канала).
CHANNEL_BOT_TOKEN = os.environ.get("CHANNEL_BOT_TOKEN", "")
# ID или @username канала, например "@my_gaming_news" или "-1001234567890".
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")

# Отдельный СЕРВИСНЫЙ бот: шлёт отчёты в ЛС и принимает команды по запросу.
SERVICE_BOT_TOKEN = os.environ.get("SERVICE_BOT_TOKEN", "")
# Твой личный chat_id (куда слать отчёты). Числовая строка.
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")

# --- Бесплатный ИИ ---
# Gemini API (основной). Бесплатный ключ: https://aistudio.google.com/app/apikey
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# OpenRouter (резерв). Бесплатные модели: https://openrouter.ai/keys
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"
)

# --- Поведение ---
POSTS_PER_DAY = int(os.environ.get("POSTS_PER_DAY", "6"))      # ровно 6 постов в день
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "24"))   # окно сбора новостей
MAX_CANDIDATES = int(os.environ.get("MAX_CANDIDATES", "60"))   # сколько новостей отдаём ИИ
