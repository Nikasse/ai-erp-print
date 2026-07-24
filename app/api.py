import json
import re
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session
from app.llm import ask
from app.models import Category, Transaction, TransactionType, User
from app.prompts import SYSTEM_STRONG, build_prompt, build_summary

# Transactions/categories created through the API aren't tied to a Telegram
# user, so they're attributed to a single shared system user instead of
# requiring auth. -1 is outside the range of real Telegram user ids.
API_USER_TELEGRAM_ID = -1
API_USER_USERNAME = "api"

app = FastAPI(title="ai-erp-print API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TransactionOut(BaseModel):
    id: int
    amount: float
    description: str | None
    category: str | None
    type: TransactionType | None
    created_at: datetime


class SummaryOut(BaseModel):
    total_income: float
    total_expense: float
    balance: float


class TransactionIn(BaseModel):
    amount: float
    type: str
    category: str
    description: str | None = None


class AnalysisOut(BaseModel):
    summary: str
    top_expense_categories: list[str]
    risks: list[str]
    advice: list[str]


async def _get_or_create_api_user(session: AsyncSession) -> User:
    result = await session.execute(select(User).where(User.telegram_id == API_USER_TELEGRAM_ID))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=API_USER_TELEGRAM_ID, username=API_USER_USERNAME)
        session.add(user)
        await session.flush()
    return user


@app.get("/api/transactions", response_model=list[TransactionOut])
async def get_transactions() -> list[TransactionOut]:
    async with async_session() as session:
        result = await session.execute(
            select(
                Transaction.id,
                Transaction.amount,
                Transaction.description,
                Category.name.label("category"),
                Category.type.label("type"),
                Transaction.created_at,
            )
            .outerjoin(Category, Transaction.category_id == Category.id)
            .order_by(Transaction.created_at.desc())
        )
        rows = result.all()

    return [
        TransactionOut(
            id=row.id,
            amount=float(row.amount),
            description=row.description,
            category=row.category,
            type=row.type,
            created_at=row.created_at,
        )
        for row in rows
    ]


@app.get("/api/summary", response_model=SummaryOut)
async def get_summary() -> SummaryOut:
    async with async_session() as session:
        result = await session.execute(
            select(Category.type, func.sum(Transaction.amount))
            .join(Category, Transaction.category_id == Category.id)
            .group_by(Category.type)
        )
        sums = {row[0]: float(row[1]) for row in result.all()}

    total_income = sums.get(TransactionType.income, 0.0)
    total_expense = sums.get(TransactionType.expense, 0.0)
    return SummaryOut(
        total_income=total_income,
        total_expense=total_expense,
        balance=total_income - total_expense,
    )


@app.post("/api/transactions", response_model=TransactionOut)
async def create_transaction(payload: TransactionIn) -> TransactionOut:
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="amount має бути більше 0")

    if payload.type not in (TransactionType.income.value, TransactionType.expense.value):
        raise HTTPException(status_code=400, detail="type має бути 'income' або 'expense'")

    category_name = payload.category.strip()
    if not category_name:
        raise HTTPException(status_code=400, detail="category не може бути порожньою")

    tx_type = TransactionType(payload.type)

    async with async_session() as session:
        user = await _get_or_create_api_user(session)

        result = await session.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.name == category_name,
                Category.type == tx_type,
            )
        )
        category = result.scalar_one_or_none()
        if category is None:
            category = Category(user_id=user.id, name=category_name, type=tx_type)
            session.add(category)
            await session.flush()

        transaction = Transaction(
            user_id=user.id,
            category_id=category.id,
            amount=payload.amount,
            description=payload.description,
        )
        session.add(transaction)
        await session.flush()
        await session.commit()

        return TransactionOut(
            id=transaction.id,
            amount=float(transaction.amount),
            description=transaction.description,
            category=category.name,
            type=category.type,
            created_at=transaction.created_at,
        )


@app.delete("/api/transactions/{transaction_id}")
async def delete_transaction(transaction_id: int) -> dict:
    async with async_session() as session:
        transaction = await session.get(Transaction, transaction_id)
        if transaction is None:
            raise HTTPException(status_code=404, detail="Операцію не знайдено")

        await session.delete(transaction)
        await session.commit()

    return {"deleted": transaction_id}


@app.post("/api/ai/analyze-transactions", response_model=AnalysisOut)
async def analyze_transactions() -> AnalysisOut:
    async with async_session() as session:
        result = await session.execute(
            select(
                Transaction.created_at,
                Transaction.amount,
                Transaction.description,
                Category.name.label("category"),
                Category.type.label("type"),
            )
            .outerjoin(Category, Transaction.category_id == Category.id)
            .order_by(Transaction.created_at.desc())
            .limit(100)
        )
        rows = result.all()

    if not rows:
        raise HTTPException(status_code=400, detail="У базі немає операцій для аналізу")

    prompt = build_prompt(build_summary(rows))

    try:
        raw_response = await ask(prompt, system=SYSTEM_STRONG)
    except Exception:
        raise HTTPException(status_code=502, detail="LLM недоступний")

    if not raw_response:
        raise HTTPException(status_code=502, detail="LLM недоступний")

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_response.strip(), flags=re.IGNORECASE)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="LLM повернув не-JSON")

    try:
        return AnalysisOut(**data)
    except ValidationError:
        raise HTTPException(status_code=502, detail="LLM повернув невірну структуру відповіді")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8000)
