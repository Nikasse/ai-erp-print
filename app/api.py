from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, select

from app.db import async_session
from app.models import Category, Transaction, TransactionType

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8000)
