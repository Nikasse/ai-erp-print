"""Одноразовий інструмент вимірювання токенів промпту.

Порівнює два підходи до формування промпту для аналізу операцій:
- сирі операції (старий підхід, до рефакторингу app/prompts.py)
- backend-зведення (новий підхід, build_summary + build_prompt)

Не є частиною API, запускається вручну: python check_tokens.py
"""

import asyncio

from anthropic import Anthropic
from sqlalchemy import select

from app.db import async_session
from app.llm import MODEL
from app.models import Category, Transaction
from app.prompts import SYSTEM_STRONG, build_prompt, build_summary


def build_raw_prompt(rows) -> str:
    """Старий підхід: сирі операції рядок за рядком, без зведення на бекенді."""
    lines = [
        f"{row.created_at} | {row.type.value if row.type else '-'} | {row.amount} | "
        f"{row.category or '-'} | {row.description or '-'}"
        for row in rows
    ]
    return (
        "Ось список останніх фінансових операцій у форматі "
        "\"дата | тип | сума | категорія | опис\":\n"
        + "\n".join(lines)
        + "\n\nПроаналізуй ці операції."
    )


async def fetch_rows():
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
        return result.all()


async def main() -> None:
    rows = await fetch_rows()
    if not rows:
        print("У базі немає операцій для вимірювання.")
        return

    variants = {
        "Сирі операції (старий підхід)": build_raw_prompt(rows),
        "Зведення (новий підхід)": build_prompt(build_summary(rows)),
    }

    client = Anthropic()

    results = {}
    for name, prompt in variants.items():
        response = client.messages.count_tokens(
            model=MODEL,
            system=SYSTEM_STRONG,
            messages=[{"role": "user", "content": prompt}],
        )
        results[name] = response.input_tokens

    baseline_name = "Сирі операції (старий підхід)"
    baseline = results[baseline_name]

    print(f"Операцій у вибірці: {len(rows)}\n")
    print(f"{'Варіант':<35}{'Input tokens':>15}{'Різниця, %':>15}")
    for name, tokens in results.items():
        diff_pct = 0.0 if tokens == baseline else (tokens - baseline) / baseline * 100
        print(f"{name:<35}{tokens:>15}{diff_pct:>14.1f}%")

    # Реальний виклик аналізу зі зведенням — щоб отримати output-токени.
    # ask() з app/llm.py повертає лише текст відповіді, без response.usage,
    # тому тут окремий прямий виклик client.messages.create().
    print("\nРеальний виклик аналізу (зведення)...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_STRONG,
        messages=[{"role": "user", "content": variants["Зведення (новий підхід)"]}],
    )

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    print(f"\n{'Input tokens':<20}{input_tokens:>10}")
    print(f"{'Output tokens':<20}{output_tokens:>10}")
    print(f"{'Разом токенів':<20}{input_tokens + output_tokens:>10}")


if __name__ == "__main__":
    asyncio.run(main())
