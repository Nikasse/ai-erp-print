"""Read-only функції для аналізу фінансів, призначені для виклику з LLM-tools.

Кожна функція лише читає дані через async_session (як у app/api.py) —
жодного INSERT/UPDATE/DELETE і жодного сирого SQL від моделі: усі запити
побудовані через SQLAlchemy select() із фіксованими таблицями/полями.

Підключені як LangChain tools до LangGraph-агента в app/agent.py.
"""

import calendar
import re
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.db import async_session
from app.models import Category, Transaction, TransactionType

# Розпізнавані формати periodу:
# - "YYYY-MM" (наприклад "2026-06") — конкретний рік і місяць
# - назва місяця англійською в нижньому регістрі (наприклад "june") —
#   береться поточний рік, оскільки рік у такому форматі не вказаний
# - "all" — усі операції без обмеження за датою
# Будь-що інше (включно з порожнім рядком) теж трактується як "усі
# операції" — навмисно проста і передбачувана поведінка без винятків.
_MONTH_NAMES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_YEAR_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


def _parse_period(period: str) -> tuple[datetime, datetime] | None:
    """Повертає (start, end) меж місяця включно, або None для "усіх операцій"."""
    if not period:
        return None

    normalized = period.strip().lower()

    if normalized == "all":
        return None

    match = _YEAR_MONTH_RE.match(normalized)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
    elif normalized in _MONTH_NAMES:
        # Рік не вказаний у форматі "june" — беремо поточний.
        year = datetime.now(timezone.utc).year
        month = _MONTH_NAMES[normalized]
    else:
        # Нерозпізнаний формат — за задачею беремо всі операції.
        return None

    start = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    return start, end


async def get_transactions_summary(period: str) -> dict:
    """Зведення доходів/витрат за period: total_income, total_expense,
    balance, operations_count. Тільки читання з бази."""
    date_range = _parse_period(period)

    query = select(Transaction.amount, Category.type.label("type")).outerjoin(
        Category, Transaction.category_id == Category.id
    )
    if date_range:
        start, end = date_range
        query = query.where(Transaction.created_at.between(start, end))

    async with async_session() as session:
        result = await session.execute(query)
        rows = result.all()

    total_income = 0.0
    total_expense = 0.0
    for row in rows:
        amount = float(row.amount)
        if row.type == TransactionType.income:
            total_income += amount
        elif row.type == TransactionType.expense:
            total_expense += amount

    return {
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "balance": round(total_income - total_expense, 2),
        "operations_count": len(rows),
    }


async def get_category_totals(period: str) -> dict:
    """Суми операцій по категоріях за period: {назва_категорії: сума}.
    Тільки читання з бази. Операції без категорії до результату не входять —
    їм немає за яким ім'ям групуватись."""
    date_range = _parse_period(period)

    query = (
        select(Category.name.label("category"), func.sum(Transaction.amount).label("total"))
        .join(Category, Transaction.category_id == Category.id)
        .group_by(Category.name)
    )
    if date_range:
        start, end = date_range
        query = query.where(Transaction.created_at.between(start, end))

    async with async_session() as session:
        result = await session.execute(query)
        rows = result.all()

    return {row.category: round(float(row.total), 2) for row in rows}


async def get_top_expenses(period: str, limit: int = 5) -> list[dict]:
    """Топ найбільших витрат за period: список {amount, category, description, date}.
    Тільки читання з бази."""
    date_range = _parse_period(period)

    query = (
        select(
            Transaction.amount,
            Transaction.description,
            Transaction.created_at,
            Category.name.label("category"),
        )
        .join(Category, Transaction.category_id == Category.id)
        .where(Category.type == TransactionType.expense)
    )
    if date_range:
        start, end = date_range
        query = query.where(Transaction.created_at.between(start, end))

    query = query.order_by(Transaction.amount.desc()).limit(limit)

    async with async_session() as session:
        result = await session.execute(query)
        rows = result.all()

    return [
        {
            "amount": float(row.amount),
            "category": row.category,
            "description": row.description,
            "date": row.created_at.isoformat(),
        }
        for row in rows
    ]
