

Навчальний фінансовий продукт (курс Web Academy, вайбкодинг).
Telegram-бот записує витрати в базу, web-адмінка показує їх у браузері.

## Що це вміє

- **Telegram-бот** — приймає команди й записує витрати в базу.
- **Backend API (FastAPI)** — читає операції з бази й віддає JSON.
- **React-адмінка** — показує фінансову картину: картки та таблицю операцій.

## Команди бота

| Команда | Що робить |
|---|---|
| `/start` | Привітання, перевірка, що бот працює |
| `/help` | Список доступних команд |
| `/expense <сума> <опис>` | Записує витрату в базу |

Приклад: `/expense 250 обід` → збереже витрату 250 з описом «обід»
(категорія за замовчуванням — «Витрати», тип — `expense`).

Якщо сума не число — бот підкаже правильний формат.

## API endpoints

| Метод | Шлях | Повертає |
|---|---|---|
| GET | `/api/transactions` | Список операцій (id, amount, description, category, type, created_at) |
| GET | `/api/summary` | Підсумок: `total_income`, `total_expense`, `balance` |

## Стек

- **Бот:** aiogram 3.x
- **База:** Neon Postgres (SQLAlchemy 2.0 async + asyncpg)
- **Backend:** FastAPI + Uvicorn
- **Frontend:** React + Vite
- **Секрети:** `.env` (не потрапляє в git)

## Як запустити

> Через Python 3.14 локально backend/бот запускаються в Docker
> (у контейнері Python 3.12).

### 1. Backend API (порт 8000)

\```bash
docker run --rm -p 8000:8000 --env-file .env \
  -v "$PWD":/app -w /app python:3.12-slim \
  bash -c "pip install -q -r requirements.txt && python -m app.api"
\```

Перевірка: `curl http://localhost:8000/api/summary`

### 2. Адмінка (порт 5173)

\```bash
cd admin
npm install   # тільки перший раз
npm run dev
\```

Відкрити: `http://localhost:5173`

> Адмінка читає дані **тільки через backend API**, ніколи не звертається
> до бази напряму. Тому backend має бути запущений першим.

## Структура

\```
app/          — бот (main.py) + API (api.py) + моделі, підключення до бази
admin/        — React-адмінка (Vite)
docs/         — документація (напр. e2e-test.md)
.env          — секрети (у .gitignore)
.env.example  — шаблон без секретів
\```

## Безпека

- `DATABASE_URL`, `BOT_TOKEN` та інші секрети живуть у `.env`.
- `.env` у `.gitignore` — у git не потрапляє.
- У git комітяться тільки `.env.example` (шаблон) і код.

## Debug / Troubleshooting

Запуск бота:

\```bash
docker compose up --build
\```

Зупинка: `Ctrl+C`

Часті проблеми:
- Docker не запущений (`docker.sock: no such file`) → відкрити Docker Desktop
- `logging.info` не виводить → перевірити `logging.basicConfig(level=logging.INFO)`
- локальний запуск падає на Python 3.14 → запускати через Docker

Детальніше про помилки — див. `DEBUG.md`
EOF

