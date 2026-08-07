import json
import logging
import os
import re
from datetime import date as date_cls
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import chat as agent_chat
from app.db import async_session
from app.llm import ask
from app.models import Category, PendingAction, Transaction, TransactionType, User
from app.prompts import SYSTEM_STRONG, build_prompt, build_summary

# Prepare-tools, чий останній виклик у result["messages"] перетворюється
# на запис у pending_actions (сам виклик tool нічого в базу не пише).
_PREPARE_TOOL_NAMES = {"prepare_create_transaction", "prepare_change_category"}

_KNOWN_ACTION_TYPES = {"create_transaction", "change_category"}

_action_logger = logging.getLogger("ai_actions")

# Transactions/categories created through the API aren't tied to a Telegram
# user, so they're attributed to a single shared system user instead of
# requiring auth. -1 is outside the range of real Telegram user ids.
API_USER_TELEGRAM_ID = -1
API_USER_USERNAME = "api"

app = FastAPI(title="ai-erp-print API")

# У production фронтенд віддається тим самим сервісом (той самий origin),
# тому CORS не потрібен. Локально Vite проксує /api, але dev-режим без
# проксі теж має працювати — звідси localhost:5173.
APP_ENV = os.getenv("APP_ENV", "development")
_ALLOWED_ORIGINS = [] if APP_ENV == "production" else ["http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Liveness-перевірка для Render.

    Навмисно НЕ звертається до бази: Neon на free tier засинає, і перший
    запит після сну падає. Якщо health check це зачепить — Render вирішить,
    що сервіс не піднявся, і завалить робочий deploy.
    """
    return {"status": "ok", "env": APP_ENV}


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


class ChatIn(BaseModel):
    message: str
    thread_id: str | None = None


class PendingActionOut(BaseModel):
    action_id: str
    action_type: str
    payload: dict
    status: str


class ChatOut(BaseModel):
    answer: str
    thread_id: str
    pending_action: PendingActionOut | None = None


class ActionConfirmOut(BaseModel):
    action_id: str
    status: str
    transaction_id: int


class ActionCancelOut(BaseModel):
    action_id: str
    status: str


async def _get_or_create_api_user(session: AsyncSession) -> User:
    result = await session.execute(select(User).where(User.telegram_id == API_USER_TELEGRAM_ID))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=API_USER_TELEGRAM_ID, username=API_USER_USERNAME)
        session.add(user)
        await session.flush()
    return user


def _log_action_audit(
    action_id: str,
    thread_id: str,
    action_type: str,
    status: str,
    *,
    result: int | None = None,
    error: str | None = None,
) -> None:
    # Тільки метадані дії — жодного payload цілком і жодних секретів (ключі,
    # DATABASE_URL, BOT_TOKEN, .env сюди не потрапляють).
    _action_logger.info(
        "action_id=%s thread_id=%s action_type=%s status=%s result=%s error=%s",
        action_id,
        thread_id,
        action_type,
        status,
        result,
        error,
    )


async def _get_own_pending_action(session: AsyncSession, action_id: str, user: User) -> PendingAction:
    action = await session.get(PendingAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Дію не знайдено")
    if action.user_id != user.id:
        raise HTTPException(status_code=403, detail="Дія належить іншому користувачу")
    if action.status != "pending":
        raise HTTPException(status_code=409, detail=f"Дія вже має статус '{action.status}'")
    return action


def _validate_create_transaction_payload(payload: dict) -> str | None:
    """Повертає текст помилки або None. Не довіряє тому, що payload уже
    пройшов валідацію в prepare-tool — перевіряє все заново."""
    tx_type = payload.get("type")
    if tx_type not in (TransactionType.income.value, TransactionType.expense.value):
        return "type має бути 'income' або 'expense'"

    amount = payload.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        return "amount має бути числом більше 0"

    category = payload.get("category")
    if not isinstance(category, str) or not category.strip():
        return "category не може бути порожньою"

    date_value = payload.get("date")
    if not isinstance(date_value, str):
        return "date має бути рядком"
    try:
        date_cls.fromisoformat(date_value)
    except ValueError:
        return "date має бути у форматі YYYY-MM-DD"

    return None


async def _validate_change_category_payload(
    session: AsyncSession, user_id: int, payload: dict
) -> tuple[str | None, Transaction | None, TransactionType | None]:
    """Повертає (error, transaction, current_type). error є None лише якщо
    transaction_id існує, належить цьому user_id, і new_category непорожня."""
    transaction_id = payload.get("transaction_id")
    if not isinstance(transaction_id, int) or isinstance(transaction_id, bool):
        return "transaction_id має бути цілим числом", None, None

    new_category = payload.get("new_category")
    if not isinstance(new_category, str) or not new_category.strip():
        return "new_category не може бути порожньою", None, None

    transaction = await session.get(Transaction, transaction_id)
    if transaction is None or transaction.user_id != user_id:
        return "transaction_id не знайдено для цього користувача", None, None

    result = await session.execute(select(Category.type).where(Category.id == transaction.category_id))
    current_type = result.scalar_one_or_none()
    if current_type is None:
        return "У операції немає категорії — тип визначити неможливо", None, None

    return None, transaction, current_type


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


@app.post("/api/ai/chat", response_model=ChatOut)
async def chat_with_agent(payload: ChatIn) -> ChatOut:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message не може бути порожнім")

    thread_id = payload.thread_id or str(uuid4())

    try:
        answer, messages = await agent_chat(message, thread_id)
    except Exception:
        raise HTTPException(status_code=502, detail="AI-помічник недоступний")

    pending_action = None
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and msg.name in _PREPARE_TOOL_NAMES:
            parsed = json.loads(msg.content)
            async with async_session() as session:
                user = await _get_or_create_api_user(session)
                action = PendingAction(
                    action_id=str(uuid4()),
                    user_id=user.id,
                    thread_id=thread_id,
                    action_type=parsed["action_type"],
                    payload=parsed["payload"],
                    status="pending",
                )
                session.add(action)
                await session.commit()

                pending_action = PendingActionOut(
                    action_id=action.action_id,
                    action_type=action.action_type,
                    payload=action.payload,
                    status=action.status,
                )
            break

    return ChatOut(answer=answer, thread_id=thread_id, pending_action=pending_action)


@app.post("/api/ai/actions/{action_id}/confirm", response_model=ActionConfirmOut)
async def confirm_action(action_id: str) -> ActionConfirmOut:
    """Виконує підготовлену AI-дію рівно один раз.

    Захист від повторного виконання — перевірка status == "pending" у
    _get_own_pending_action: як тільки статус змінюється на "confirmed",
    "cancelled" чи "failed", повторний confirm того самого action_id
    завжди впаде з 409, а не виконає дію ще раз.

    Для create_transaction: payload.date валідується (має парситись як
    дата), але НЕ записується в Transaction — у моделі Transaction немає
    окремого поля дати, є лише created_at через server_default, тож
    транзакція отримує поточний час створення, а не дату з payload.
    """
    async with async_session() as session:
        user = await _get_or_create_api_user(session)
        action = await _get_own_pending_action(session, action_id, user)

        transaction: Transaction | None = None
        current_type: TransactionType | None = None

        if action.action_type == "create_transaction":
            error = _validate_create_transaction_payload(action.payload)
        elif action.action_type == "change_category":
            error, transaction, current_type = await _validate_change_category_payload(
                session, user.id, action.payload
            )
        else:
            error = f"Невідомий тип дії: {action.action_type}"

        if error:
            action.status = "failed"
            await session.commit()
            _log_action_audit(action_id, action.thread_id, action.action_type, "failed", error=error)
            raise HTTPException(status_code=422, detail=error)

        if action.action_type == "create_transaction":
            payload = action.payload
            tx_type = TransactionType(payload["type"])
            category_name = payload["category"].strip()

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

            new_transaction = Transaction(
                user_id=user.id,
                category_id=category.id,
                amount=payload["amount"],
                description=payload.get("description"),
            )
            session.add(new_transaction)
            await session.flush()
            transaction_id = new_transaction.id
        else:
            new_category_name = action.payload["new_category"].strip()

            result = await session.execute(
                select(Category).where(
                    Category.user_id == user.id,
                    Category.name == new_category_name,
                    Category.type == current_type,
                )
            )
            category = result.scalar_one_or_none()
            if category is None:
                category = Category(user_id=user.id, name=new_category_name, type=current_type)
                session.add(category)
                await session.flush()

            transaction.category_id = category.id
            transaction_id = transaction.id

        action.status = "confirmed"
        action.confirmed_at = datetime.now(timezone.utc)
        await session.commit()

        _log_action_audit(action_id, action.thread_id, action.action_type, "confirmed", result=transaction_id)

        return ActionConfirmOut(action_id=action.action_id, status=action.status, transaction_id=transaction_id)


@app.post("/api/ai/actions/{action_id}/cancel", response_model=ActionCancelOut)
async def cancel_action(action_id: str) -> ActionCancelOut:
    """Скасовує підготовлену AI-дію, не чіпаючи таблицю transactions.

    Захист від подвійної дії — та сама перевірка status == "pending" у
    _get_own_pending_action, що й у confirm: скасувати можна лише дію, яка
    ще не була ні підтверджена, ні скасована раніше.
    """
    async with async_session() as session:
        user = await _get_or_create_api_user(session)
        action = await _get_own_pending_action(session, action_id, user)

        action.status = "cancelled"
        action.confirmed_at = datetime.now(timezone.utc)
        await session.commit()

        _log_action_audit(action_id, action.thread_id, action.action_type, "cancelled")

        return ActionCancelOut(action_id=action.action_id, status=action.status)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8000)
