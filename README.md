# ai-erp-print

Мінімальний Telegram-бот на aiogram 3.x.

## Швидкий старт
Бот підтримує /start і /help
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
python -m app.main
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
 | /help | Список команд |

## Debug / Troubleshooting

Запуск бота:

```bash
docker compose up --build
```

Зупинка: `Ctrl+C`

Часті проблеми:
- Docker не запущений (`docker.sock: no such file`) → відкрити Docker Desktop
- `logging.info` не виводить → перевірити `logging.basicConfig(level=logging.INFO)`
- локальний запуск падає на Python 3.14 → запускати через Docker

Детальніше про помилки — див. DEBUG.md
