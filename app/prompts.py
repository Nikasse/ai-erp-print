from app.models import TransactionType

# Слабкий системний промпт — не використовується в продакшені,
# лишається як приклад "поганого" промпту для порівняння.
SYSTEM_WEAK = "Ти фінансовий аналітик. Проаналізуй фінанси."

SYSTEM_STRONG = (
    "Ти досвідчений фінансовий аналітик, який готує короткий звіт для власника "
    "особистого чи невеликого бізнес-бюджету.\n\n"
    "Суворі правила:\n"
    "- Спирайся ТІЛЬКИ на дані, передані нижче у зведенні. Не вигадуй суми, "
    "категорії, дати чи операції, яких там немає.\n"
    "- Якщо операцій замало для впевнених висновків (наприклад, дуже мало "
    "операцій або короткий період) — прямо скажи про це у summary, а не "
    "додумуй.\n"
    "- Відповідай виключно українською мовою.\n"
    "- Відповідь має бути строго валідним JSON без markdown-обгортки "
    "(без ```), без жодного тексту до чи після JSON.\n\n"
    "Формат JSON:\n"
    '{"summary": string, "top_expense_categories": [string], '
    '"risks": [string], "advice": [string]}'
)

# Той самий SYSTEM_STRONG, але з жорсткими обмеженнями на довжину
# відповіді — для порівняння вартості output-токенів. SYSTEM_STRONG
# лишається робочим промптом, цей використовується окремо.
SYSTEM_STRONG_COMPACT = (
    "Ти досвідчений фінансовий аналітик, який готує короткий звіт для власника "
    "особистого чи невеликого бізнес-бюджету.\n\n"
    "Суворі правила:\n"
    "- Спирайся ТІЛЬКИ на дані, передані нижче у зведенні. Не вигадуй суми, "
    "категорії, дати чи операції, яких там немає.\n"
    "- Якщо операцій замало для впевнених висновків (наприклад, дуже мало "
    "операцій або короткий період) — прямо скажи про це у summary, а не "
    "додумуй.\n"
    "- Відповідай виключно українською мовою.\n"
    "- Відповідь має бути строго валідним JSON без markdown-обгортки "
    "(без ```), без жодного тексту до чи після JSON.\n\n"
    "Жорсткі обмеження на довжину відповіді:\n"
    "- summary: максимум 2 речення.\n"
    "- top_expense_categories: максимум 3 позиції.\n"
    "- risks: максимум 3 пункти, кожен — одне коротке речення.\n"
    "- advice: максимум 3 пункти, кожен — одне коротке речення.\n"
    "- Жодної води, тільки суть.\n\n"
    "Формат JSON:\n"
    '{"summary": string, "top_expense_categories": [string], '
    '"risks": [string], "advice": [string]}'
)


def build_summary(rows) -> dict:
    """Рахує backend-зведення по операціях замість передачі сирих рядків у модель."""
    total_income = 0.0
    total_expense = 0.0
    by_category: dict[str, dict[str, float]] = {}
    expenses_for_top: list[dict] = []
    uncategorized_count = 0
    dates = []

    for row in rows:
        amount = float(row.amount)
        category_name = row.category or "Без категорії"
        row_type = row.type

        if row_type is None:
            uncategorized_count += 1

        bucket = by_category.setdefault(category_name, {"income": 0.0, "expense": 0.0})

        if row_type == TransactionType.income:
            total_income += amount
            bucket["income"] += amount
        elif row_type == TransactionType.expense:
            total_expense += amount
            bucket["expense"] += amount
            expenses_for_top.append({"category": category_name, "amount": amount})

        if row.created_at:
            dates.append(row.created_at)

    top_expenses = sorted(expenses_for_top, key=lambda item: item["amount"], reverse=True)[:5]

    return {
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "balance": round(total_income - total_expense, 2),
        "operations_count": len(rows),
        "by_category": {
            name: {"income": round(sums["income"], 2), "expense": round(sums["expense"], 2)}
            for name, sums in by_category.items()
        },
        "top_expenses": top_expenses,
        "period": {
            "from": min(dates).isoformat() if dates else None,
            "to": max(dates).isoformat() if dates else None,
        },
        "uncategorized_count": uncategorized_count,
    }


def build_prompt(summary: dict) -> str:
    """Збирає компактний текстовий запит із зведення (без id та created_at операцій)."""
    period_from = summary["period"]["from"] or "-"
    period_to = summary["period"]["to"] or "-"

    lines = [
        f"Фінансове зведення за період {period_from} — {period_to}:",
        f"- Кількість операцій: {summary['operations_count']}",
        f"- Доходи: {summary['total_income']}",
        f"- Витрати: {summary['total_expense']}",
        f"- Баланс: {summary['balance']}",
        f"- Операцій без категорії: {summary['uncategorized_count']}",
        "",
        "Суми по категоріях (дохід / витрата):",
    ]

    if summary["by_category"]:
        for category, amounts in summary["by_category"].items():
            lines.append(f"- {category}: дохід {amounts['income']}, витрата {amounts['expense']}")
    else:
        lines.append("- немає даних")

    lines.append("")
    lines.append("Топ-5 найбільших витрат:")
    if summary["top_expenses"]:
        for item in summary["top_expenses"]:
            lines.append(f"- {item['category']}: {item['amount']}")
    else:
        lines.append("- немає витрат")

    lines.append("")
    lines.append("Проаналізуй ці дані.")

    return "\n".join(lines)
