"""Точка входа: один процесс держит и бота, и HTTP-API мини-приложения.

    python -m server.main

Если задан WEBHOOK_BASE — бот работает на webhook (Telegram сам стучится
в наше же aiohttp-приложение), иначе на long polling. Для продакшена
за nginx нужен webhook, для локальной отладки хватает polling.
"""
import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from . import config
from .api import create_app
from .bot import build
from .storage import Storage

log = logging.getLogger("husky")


async def on_startup(bot: Bot) -> None:
    await bot.set_webhook(
        config.webhook_url(),
        secret_token=config.WEBHOOK_SECRET,
        drop_pending_updates=False,
        allowed_updates=["message", "callback_query"],
    )
    info = await bot.get_webhook_info()
    log.info("webhook: %s (в очереди %s)", info.url, info.pending_update_count)


async def on_shutdown(bot: Bot) -> None:
    # Снимаем webhook, чтобы Telegram не копил апдейты в очередь на время рестарта.
    with contextlib.suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=False)


def attach_bot(app: web.Application, bot: Bot, dp: Dispatcher, storage: Storage) -> None:
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=config.WEBHOOK_SECRET, db=storage).register(
        app, path=config.WEBHOOK_PATH
    )
    setup_application(app, dp, bot=bot, db=storage)


async def run_polling(bot: Bot, dp: Dispatcher, storage: Storage) -> None:
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, db=storage, allowed_updates=dp.resolve_used_update_types())


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    storage = Storage(config.DB_PATH)
    await storage.open()
    bot, dp = build(storage)
    app = create_app(storage)

    if config.USE_WEBHOOK:
        attach_bot(app, bot, dp, storage)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, config.HOST, config.PORT).start()
    log.info("API на http://%s:%s, игра на %s", config.HOST, config.PORT, config.WEBAPP_URL)

    try:
        if config.USE_WEBHOOK:
            log.info("режим webhook, путь %s", config.WEBHOOK_PATH)
            await asyncio.Event().wait()   # апдейты приходят в aiohttp, просто не выходим
        else:
            log.info("режим long polling")
            await run_polling(bot, dp, storage)
    finally:
        await runner.cleanup()
        await storage.close()
        await bot.session.close()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(main())
