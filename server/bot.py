"""Бот: кнопка запуска игры, инвайт-ссылка и топ упряжек."""
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from aiogram.utils.markdown import hbold

from . import config
from .storage import Storage

log = logging.getLogger(__name__)
router = Router(name="husky")


def play_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🐺 В путь", web_app=WebAppInfo(url=config.WEBAPP_URL))]]
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        f"{hbold('Хаски: Зов Севера')}\n\n"
        "Собирай упряжку, объединяй хаски и уходи от лавины на Север.\n"
        "Прогресс хранится на сервере — играй с любого устройства.",
        reply_markup=play_kb(),
    )


@router.message(Command("play"))
async def play(message: Message) -> None:
    await message.answer("Жми кнопку — упряжка ждёт.", reply_markup=play_kb())


@router.message(Command("top"))
async def top(message: Message, db: Storage) -> None:
    rows = await db.top(10)
    if not rows:
        await message.answer("Пока никто не ушёл дальше первой стоянки.", reply_markup=play_kb())
        return
    lines = []
    for i, r in enumerate(rows, 1):
        who = r["username"] and f"@{r['username']}" or (r["name"] or f"id{r['user_id']}")
        lines.append(f"{i}. {who} — этап {r['best_stage']}, порода ур. {r['max_ever']}")
    rank = await db.rank(message.from_user.id)
    tail = f"\n\nТы на {rank} месте." if rank else ""
    await message.answer(f"{hbold('Лучшие каюры')}\n\n" + "\n".join(lines) + tail, reply_markup=play_kb())


@router.message(F.web_app_data)
async def from_webapp(message: Message) -> None:
    # Игра пока ничего не присылает через sendData, но хэндлер пригодится для событий.
    log.info("web_app_data от %s: %s", message.from_user.id, message.web_app_data.data[:200])


def build(storage: Storage) -> tuple[Bot, Dispatcher]:
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # storage= у Dispatcher занят FSM-хранилищем, свою базу кладём в workflow data
    dp = Dispatcher()
    dp["db"] = storage
    dp.include_router(router)
    return bot, dp
