"""Настройки читаются из окружения (см. .env.example)."""
import hashlib
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


BOT_TOKEN = _env("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Задай BOT_TOKEN в окружении (см. server/.env.example)")
# Публичный https-адрес мини-приложения, его же отдаём кнопкой в боте.
WEBAPP_URL = _env("WEBAPP_URL") or "http://localhost:8080/"
HOST = _env("HOST", "0.0.0.0")
PORT = int(_env("PORT", "8080"))
DB_PATH = Path(_env("DB_PATH") or (BASE_DIR / "husky.db"))
# Файл игры: раздаём его сами, чтобы хватило одного процесса.
GAME_FILE = Path(_env("GAME_FILE") or (ROOT_DIR / "Хаски_ Зов Севера (1).html"))
# initData старше этого срока не принимаем (секунды).
AUTH_TTL = int(_env("AUTH_TTL", "86400"))
# Сейв больше этого размера считаем мусором (байты).
MAX_SAVE_BYTES = int(_env("MAX_SAVE_BYTES", "20000"))
# Не чаще одной записи сейва в эти секунды на игрока.
SAVE_COOLDOWN = float(_env("SAVE_COOLDOWN", "3"))

# ---- webhook ----
# Публичный https-origin, на который Telegram будет присылать апдейты,
# например https://husky.example.com. Пусто -> бот работает на long polling.
WEBHOOK_BASE = _env("WEBHOOK_BASE").rstrip("/")
# Путь внутри приложения. Держим его неугадываемым: в него входит хэш токена.
WEBHOOK_PATH = _env("WEBHOOK_PATH") or "/tg/" + hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]
# Telegram вернёт его в заголовке X-Telegram-Bot-Api-Secret-Token, проверяем каждый запрос.
WEBHOOK_SECRET = _env("WEBHOOK_SECRET") or hashlib.sha256(("secret:" + BOT_TOKEN).encode()).hexdigest()[:48]
USE_WEBHOOK = bool(WEBHOOK_BASE)


def webhook_url() -> str:
    return WEBHOOK_BASE + WEBHOOK_PATH
