"""Prepare-функції для контрольованих AI-дій.

Кожна функція лише формує структурований payload для чернетки дії —
жодного session.add, жодного commit, жодного запису в базу. AI готує
дію, користувач підтверджує, а виконує вже backend (окремим кроком,
не тут).
"""

import json
from datetime import date as date_cls


def prepare_create_transaction(
    type: str, amount: float, category: str, description: str, date: str | None = None
) -> str:
    """Готує чернетку створення транзакції. Нічого не пише в базу.

    Параметр date передавай лише якщо користувач назвав конкретний день
    (наприклад "15 січня" чи "2026-01-15"). Якщо користувач сказав
    "сьогодні" або взагалі не згадав дату — НЕ передавай date, backend
    сам підставить поточну дату сервера."""
    if not date:
        date = date_cls.today().isoformat()
    return json.dumps({
        "action_type": "create_transaction",
        "payload": {
            "type": type,
            "amount": amount,
            "category": category,
            "date": date,
            "description": description,
        },
    })


def prepare_change_category(transaction_id: int, new_category: str) -> str:
    """Готує чернетку зміни категорії транзакції. Нічого не пише в базу."""
    return json.dumps({
        "action_type": "change_category",
        "payload": {
            "transaction_id": transaction_id,
            "new_category": new_category,
        },
    })
