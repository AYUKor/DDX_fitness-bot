import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
from keyboards import role_keyboard, trainer_menu, client_menu
from handlers import trainer, client
from scheduler import setup_scheduler

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

common = Router()


@common.message(CommandStart())
async def cmd_start(message: Message):
    chat_id = message.from_user.id

    # Trainer already registered?
    t = await db.get_trainer(chat_id)
    if t and t["registered"]:
        await message.answer(
            f"👋 С возвращением, {t['full_name'].split()[0]}!",
            reply_markup=trainer_menu()
        )
        return

    # Client already registered?
    c = await db.get_client(chat_id)
    if c and c["registered"]:
        await message.answer(
            f"👋 С возвращением, {c['full_name'].split()[0]}!",
            reply_markup=client_menu()
        )
        return

    # New user
    await message.answer(
        "🏋️ <b>Фитнес-бот</b>\n\n"
        "Добро пожаловать! Кто вы?",
        parse_mode="HTML",
        reply_markup=role_keyboard()
    )


@common.message(Command("menu"))
async def cmd_menu(message: Message):
    chat_id = message.from_user.id
    t = await db.get_trainer(chat_id)
    if t and t["registered"]:
        await message.answer("Главное меню:", reply_markup=trainer_menu())
        return
    c = await db.get_client(chat_id)
    if c and c["registered"]:
        await message.answer("Главное меню:", reply_markup=client_menu())
        return
    await message.answer("Сначала пройдите регистрацию через /start")


@common.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ <b>Справка</b>\n\n"
        "/start — начать / вернуться в меню\n"
        "/menu — показать меню\n\n"
        "<b>Тренер</b> — регистрируется с секретным кодом, добавляет слоты, подтверждает записи\n\n"
        "<b>Клиент</b> — выбирает тренера, записывается на время, "
        "получает напоминания в 7:00 и за час до тренировки",
        parse_mode="HTML"
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в .env!")

    await db.init_db()
    logger.info("Database ready")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(common)
    dp.include_router(trainer.router)
    dp.include_router(client.router)

    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started")

    logger.info("Starting polling…")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
