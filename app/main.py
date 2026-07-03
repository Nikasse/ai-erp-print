import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()


@dp.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(f"Привіт, {message.from_user.first_name}! Я готовий до роботи.")


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
