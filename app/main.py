import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

from app.db import init_models

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()


@dp.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(f"Привіт, {message.from_user.first_name}! Я готовий до роботи.")

@dp.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer("Доступні команди:\n/start — почати роботу\n/help — список команд")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_models()
    logging.info("Бот успішно запущено")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

