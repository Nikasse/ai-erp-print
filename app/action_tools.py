"""Prepare-функції для контрольованих AI-дій.

Кожна функція лише формує структурований payload для чернетки дії —
жодного session.add, жодного commit, жодного запису в базу. AI готує
дію, користувач підтверджує, а виконує вже backend (окремим кроком,
не тут).
"""


def prepare_create_transaction(type: str, amount: float, category: str, date: str, description: str) -> dict:
    """Готує чернетку створення транзакції. Нічого не пише в базу."""
    return {
        "action_type": "create_transaction",
        "payload": {
            "type": type,
            "amount": amount,
            "category": category,
            "date": date,
            "description": description,
        },
    }


def prepare_change_category(transaction_id: int, new_category: str) -> dict:
    """Готує чернетку зміни категорії транзакції. Нічого не пише в базу."""
    return {
        "action_type": "change_category",
        "payload": {
            "transaction_id": transaction_id,
            "new_category": new_category,
        },
    }
