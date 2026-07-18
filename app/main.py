import asyncio
import logging
import os
from decimal import Decimal, InvalidOperation

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message
from dotenv import load_dotenv
from sqlalchemy import select

from app.db import async_session, init_models
from app.models import Category, Transaction, TransactionType, User

DEFAULT_EXPENSE_CATEGORY = "Витрати"

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()


@dp.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(f"Привіт, {message.from_user.first_name}! Я готовий до роботи.")

@dp.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer("Доступні команди:\n/start — почати роботу\n/help — список команд")


@dp.message(Command("expense"))
async def handle_expense(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer("Формат: /expense 120 кава")
        return

    parts = command.args.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /expense 120 кава")
        return

    amount_raw, description = parts
    try:
        amount = Decimal(amount_raw)
    except InvalidOperation:
        await message.answer("Сума має бути числом. Формат: /expense 120 кава")
        return

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=message.from_user.id, username=message.from_user.username)
            session.add(user)
            await session.flush()

        result = await session.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.name == DEFAULT_EXPENSE_CATEGORY,
                Category.type == TransactionType.expense,
            )
        )
        category = result.scalar_one_or_none()
        if category is None:
            category = Category(user_id=user.id, name=DEFAULT_EXPENSE_CATEGORY, type=TransactionType.expense)
            session.add(category)
            await session.flush()

        session.add(Transaction(user_id=user.id, category_id=category.id, amount=amount, description=description))
        await session.commit()

    await message.answer(f"Витрату збережено: {amount_raw} — {description}")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_models()
    logging.info("Бот успішно запущено")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

