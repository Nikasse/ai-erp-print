# База даних

Postgres (Neon, регіон Frankfurt). Підключення — SQLAlchemy 2.0 async + asyncpg.

## Таблиці
- users — Telegram-користувачі (telegram_id унікальний)
- categories — категорії витрат
- transactions — сума, опис, дата; зв'язки на users і categories

Схема — див. dbdiagram.
