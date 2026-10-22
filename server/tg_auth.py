"""Проверка Telegram.WebApp.initData.

Схема из документации Bot API: секрет — HMAC-SHA256 от токена бота с ключом
"WebAppData", подпись — HMAC-SHA256 от data_check_string с этим секретом.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class AuthError(Exception):
    pass


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def parse_init_data(init_data: str, bot_token: str, ttl: int = 86400) -> dict:
    """Возвращает разобранный initData или бросает AuthError."""
    if not init_data or len(init_data) > 4096:
        raise AuthError("пустой initData")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    if len(pairs) != len(dict(pairs)):
        raise AuthError("дублирующиеся поля initData")
    data = dict(pairs)

    received = data.pop("hash", "")
    data.pop("signature", None)  # подпись Ed25519 для сторонней валидации, нам не нужна
    if not received:
        raise AuthError("нет hash")

    check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    expected = hmac.new(_secret_key(bot_token), check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthError("подпись не совпала")

    try:
        auth_date = int(data.get("auth_date", "0"))
    except ValueError:
        raise AuthError("некорректный auth_date")
    if ttl and (time.time() - auth_date) > ttl:
        raise AuthError("initData просрочен")

    try:
        user = json.loads(data.get("user") or "{}")
    except json.JSONDecodeError:
        raise AuthError("некорректный user")
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise AuthError("нет user.id")

    data["user"] = user
    return data
