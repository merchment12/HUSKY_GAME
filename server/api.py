"""HTTP-API мини-приложения: загрузка/сохранение прогресса и топ игроков.

Авторизация у каждого запроса одна — initData из Telegram.WebApp, поэтому
отдельных сессий и куки нет.
"""
import json
import logging
import time

from aiohttp import web

from . import config
from .storage import Storage
from .tg_auth import AuthError, parse_init_data

log = logging.getLogger(__name__)
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Max-Age": "86400",
}


def _json(data: dict, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, headers=CORS, dumps=lambda o: json.dumps(o, ensure_ascii=False))


async def _auth(request: web.Request) -> tuple[dict, dict]:
    """Разбирает тело запроса и проверяет подпись. Возвращает (body, user)."""
    if request.content_length and request.content_length > config.MAX_SAVE_BYTES + 8192:
        raise web.HTTPRequestEntityTooLarge(max_size=config.MAX_SAVE_BYTES, actual_size=request.content_length)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        raise web.HTTPBadRequest(text="bad json", headers=CORS)
    if not isinstance(body, dict):
        raise web.HTTPBadRequest(text="bad json", headers=CORS)
    try:
        data = parse_init_data(body.get("initData", ""), config.BOT_TOKEN, config.AUTH_TTL)
    except AuthError as e:
        raise web.HTTPUnauthorized(text=str(e), headers=CORS)
    return body, data["user"]


async def preflight(request: web.Request) -> web.Response:
    return web.Response(status=204, headers=CORS)


async def load(request: web.Request) -> web.Response:
    _, user = await _auth(request)
    rec = await request.app["storage"].load(user["id"])
    return _json({"save": rec["save"] if rec else None, "serverTime": int(time.time() * 1000)})


async def save(request: web.Request) -> web.Response:
    body, user = await _auth(request)
    payload = body.get("save")
    if not isinstance(payload, dict) or not isinstance(payload.get("cells"), list):
        raise web.HTTPBadRequest(text="bad save", headers=CORS)

    cooldown: dict[int, float] = request.app["cooldown"]
    now = time.monotonic()
    last = cooldown.get(user["id"], 0.0)
    if now - last < config.SAVE_COOLDOWN:
        return _json({"status": "throttled"}, status=429)
    cooldown[user["id"]] = now

    status, server_save = await request.app["storage"].store(user["id"], user, payload)
    if status == "stale":
        return _json({"status": "stale", "save": server_save["save"]})
    return _json({"status": "ok"})


async def top(request: web.Request) -> web.Response:
    _, user = await _auth(request)
    storage: Storage = request.app["storage"]
    return _json({"top": await storage.top(20), "rank": await storage.rank(user["id"])})


async def game(request: web.Request) -> web.Response:
    path = config.GAME_FILE
    if not path.is_file():
        raise web.HTTPNotFound(text=f"не нашёл файл игры: {path}")
    return web.FileResponse(path, headers={"Cache-Control": "no-cache", "Content-Type": "text/html; charset=utf-8"})


def setup_routes(app: web.Application) -> None:
    app.router.add_get("/", game)
    app.router.add_post("/api/load", load)
    app.router.add_post("/api/save", save)
    app.router.add_post("/api/top", top)
    for route in ("/api/load", "/api/save", "/api/top"):
        app.router.add_options(route, preflight)


def create_app(storage: Storage) -> web.Application:
    app = web.Application(client_max_size=config.MAX_SAVE_BYTES + 8192)
    app["storage"] = storage
    app["cooldown"] = {}
    setup_routes(app)
    return app
