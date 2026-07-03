# ai-erp-print

Мінімальний Telegram-бот на aiogram 3.x.

## Швидкий старт

### 1. Налаштування змінних середовища

```bash
cp .env.example .env
```

Відкрий `.env` і встав свій токен від [@BotFather](https://t.me/BotFather):

```
BOT_TOKEN=your_bot_token_here
```

### Запуск локально

```bash
pip install -r requirements.txt
python app/main.py
```

### Запуск через Docker

```bash
docker compose up --build
```

Зупинити:

```bash
docker compose down
```

## Команди бота

| Команда | Дія |
|---|---|
| `/start` | Привітання |
