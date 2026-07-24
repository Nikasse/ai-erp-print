"""Одноразовий скрипт перевірки поведінки промпту на трьох сценаріях.

Дані для кожного сценарію задані вручну — до бази скрипт не звертається.
Мета: побачити, чи SYSTEM_STRONG змушує модель чесно казати
"даних замало", коли операцій дуже мало (сценарії 1 і 2), а не
вигадувати впевнені висновки.

Не є частиною API, запускається вручну: python check_scenarios.py
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.llm import ask
from app.models import TransactionType
from app.prompts import SYSTEM_STRONG, build_prompt, build_summary


@dataclass
class FakeRow:
    created_at: datetime
    amount: float
    description: str | None
    category: str | None
    type: TransactionType | None


def scenario_empty() -> list[FakeRow]:
    return []


def scenario_two_operations() -> list[FakeRow]:
    now = datetime(2026, 7, 20, 12, 0)
    return [
        FakeRow(
            created_at=now,
            amount=15000,
            description="Зарплата за липень",
            category="Зарплата",
            type=TransactionType.income,
        ),
        FakeRow(
            created_at=now + timedelta(hours=2),
            amount=350,
            description="обід",
            category="Їжа",
            type=TransactionType.expense,
        ),
    ]


def scenario_realistic() -> list[FakeRow]:
    base = datetime(2026, 7, 1, 9, 0)
    data = [
        (0, 25000, "зарплата", "Зарплата", TransactionType.income),
        (1, 850, "супермаркет", "Їжа", TransactionType.expense),
        (2, 1200, "аптека", "Здоровʼя", TransactionType.expense),
        (3, 400, "таксі", "Транспорт", TransactionType.expense),
        (4, 2500, "комунальні", "Комунальні", TransactionType.expense),
        (5, 600, "кава", "Їжа", TransactionType.expense),
        (6, 3000, "фріланс", "Підробіток", TransactionType.income),
        (7, 1800, "одяг", "Шопінг", TransactionType.expense),
        (8, 300, "автобус", "Транспорт", TransactionType.expense),
        (9, 500, "підписки", "Розваги", TransactionType.expense),
        (10, 950, "супермаркет", "Їжа", TransactionType.expense),
        (11, 200, None, None, None),
        (12, 4000, "ремонт крана", "Дім", TransactionType.expense),
        (13, 700, "бензин", "Транспорт", TransactionType.expense),
    ]
    return [
        FakeRow(
            created_at=base + timedelta(days=day),
            amount=amount,
            description=description,
            category=category,
            type=tx_type,
        )
        for day, amount, description, category, tx_type in data
    ]


SCENARIOS = [
    ("Сценарій 1: порожній список операцій", scenario_empty),
    ("Сценарій 2: дві операції", scenario_two_operations),
    ("Сценарій 3: реалістичний набір (14 операцій, різні категорії)", scenario_realistic),
]


async def run_scenario(title: str, rows: list[FakeRow]) -> None:
    print(f"\n=== {title} ===")

    summary = build_summary(rows)
    prompt = build_prompt(summary)

    response = await ask(prompt, system=SYSTEM_STRONG)
    print(response)


async def main() -> None:
    for title, build_rows in SCENARIOS:
        await run_scenario(title, build_rows())


if __name__ == "__main__":
    asyncio.run(main())
