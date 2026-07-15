# Безпека — робота з секретами

## Правило
Секрети не живуть у коді. Секрети живуть у .env.

## Секрети проєкту
- BOT_TOKEN — доступ до Telegram-бота
- DATABASE_URL — доступ до бази Neon

## Захист
- .env — реальні секрети, у .gitignore, у Git НЕ потрапляє
- .env.example — шаблон без значень, у Git є
- .gitignore — не пускає .env у Git

## Якщо секрет витік
Перевипустити ключ: BOT_TOKEN через @BotFather, DATABASE_URL через Neon.