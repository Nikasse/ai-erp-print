# AGENTS.md

Контекст проєкту для AI-асистента. Читати **перед** будь-якою зміною коду.

## 1. Що це за проєкт

`ai-erp-print` — навчальний AI-SaaS обліку фінансів (курс Web Academy).

| Блок | Технологія |
|---|---|
| Backend | FastAPI + Uvicorn (`app/`) |
| Frontend | React 19 + Vite (`admin/`) |
| База | Neon Postgres (SQLAlchemy 2.0 async + asyncpg) |
| AI | Anthropic API + LangGraph (`app/agent.py`, `app/llm.py`) |
| Telegram-бот | aiogram 3.x (`app/main.py`) |
| Деплой | Render, Docker |
| Домен | `home-base.pp.ua` (техадреса: `ai-erp-print.onrender.com`) |

Документація: [docs/deploy.md](docs/deploy.md), [docs/domain.md](docs/domain.md),
[docs/security.md](docs/security.md), [docs/database.md](docs/database.md).

## 2. Архітектура і межі

Ланцюг запиту:
```
Браузер → React (admin/) → /api/* → FastAPI → SQLAlchemy → Neon
                                        └→ Anthropic API
```

**Чотири межі, які не порушувати:**

1. **React ходить у базу ТІЛЬКИ через backend API.** Ніколи напряму в Neon,
   ніколи з `DATABASE_URL` у фронтенді. Фронтенд використовує відносні URL
   (`/api/...`); локально їх проксує Vite (`admin/vite.config.js`).

2. **Production entry point — `app/render_app.py`, НЕ `app/api.py`.**
   `render_app.py` імпортує `app` з `api.py` і додає монтування статики
   (`/assets`) + SPA fallback. Якщо запустити на Render `app.api:app` —
   API працює, але адмінка не віддається: `/` повертає 404, статики немає.

3. **`app/main.py` — це Telegram-бот, окремий процес.** Не HTTP-сервіс.
   Роутів не має, порту не відкриває. Не додавати в нього FastAPI-код і не
   змішувати з API.

4. **Два Dockerfile:**
   - `Dockerfile` — образ **бота** (`CMD python -m app.main`), сервіс `bot`
     у `docker-compose.yml`.
   - `Dockerfile.render` — **production для Render**: multi-stage
     (Node збирає `admin/` → `/app/static`, Python ставить backend),
     `CMD uvicorn app.render_app:app`.

   Якщо переплутати і зібрати на Render `./Dockerfile` — образ підніметься,
   але HTTP-порту не відкриє, і Render завалить deploy по health check
   timeout ([docs/deploy.md](docs/deploy.md), розділ 6).

## 3. Головний принцип роботи з AI-діями

```
AI пропонує → людина підтверджує → backend виконує
```

- Модель **ніколи** не пише в базу напряму.
- Prepare-tools (`prepare_create_transaction`, `prepare_change_category`)
  нічого не змінюють — вони лише формують payload.
- Запис іде через таблицю `pending_actions` і лише після
  `POST /api/ai/actions/{action_id}/confirm`.
- Backend **перевалідовує** payload заново на confirm — не довіряє тому, що
  його вже перевірив prepare-tool.
- Захист від подвійного виконання: `status == "pending"`; повторний confirm
  того самого `action_id` дає `409`.

Це правило не порушувати. Не додавати AI-інструментів, які пишуть у базу
без підтвердження людиною.

## 4. Секрети

Змінні з `.env.example`:

| Змінна | Для чого |
|---|---|
| `BOT_TOKEN` | Telegram-бот |
| `DATABASE_URL` | Neon Postgres |
| `ANTHROPIC_API_KEY` | Anthropic API |

Плюс на Render: `APP_ENV=production` (вимикає CORS, бо той самий origin).

Правила:
- `.env` **ніколи** в Git (у `.gitignore`, виключений у `.dockerignore`).
- У Git тільки `.env.example` — шаблон без значень.
- Секрети не в коді, не в логах, не в текстах помилок. Аудит AI-дій
  (`_log_action_audit` в `app/api.py`) логує тільки метадані.
- На Render секрети живуть лише в Environment Variables панелі.
- Якщо секрет засвітився (чат, скріншот, комміт) — **перевипустити**, а не
  просто видалити згадку: `BOT_TOKEN` через @BotFather,
  `DATABASE_URL` через Neon → Roles → Reset password.

## 5. API-контракти

`app/api.py`:

| Метод | Шлях | Повертає |
|---|---|---|
| GET | `/health` | `{"status":"ok","env":...}` — без звернення до бази |
| GET | `/api/transactions` | список операцій |
| POST | `/api/transactions` | створена операція |
| DELETE | `/api/transactions/{transaction_id}` | `{"deleted": id}` |
| GET | `/api/summary` | `total_income`, `total_expense`, `balance` |
| POST | `/api/ai/analyze-transactions` | `summary`, `top_expense_categories`, `risks`, `advice` |
| POST | `/api/ai/chat` | `answer`, `thread_id`, `pending_action` |
| POST | `/api/ai/actions/{action_id}/confirm` | `action_id`, `status`, `transaction_id` |
| POST | `/api/ai/actions/{action_id}/cancel` | `action_id`, `status` |

`app/render_app.py`: `GET /{full_path:path}` — SPA fallback (лише `GET`),
`/api/*` і `/health` навмисно виключені.

Правила:
- **Не змінювати шляхи, методи й формат відповіді без явного прохання** —
  на них зав'язана адмінка.
- **Не створювати другий спосіб зробити те саме.** Перед новим роутом
  перевірити, чи потрібного немає в таблиці вище.
- Catch-all роут має реєструватись **після** `/api/*` — інакше він
  перехоплює API і віддає `index.html` замість JSON.

## 6. Команди запуску

**API + адмінка локально** (backend першим):

```bash
docker compose build api
docker compose up -d --force-recreate api
```
```bash
cd admin
npm install   # тільки перший раз
npm run dev
```
Адмінка: `http://localhost:5173`, API: `http://localhost:8000`.

**Telegram-бот локально:**
```bash
docker compose up --build bot
```

**Перевірка `/health`:**
```bash
curl http://localhost:8000/health
```
Очікувано: `{"status":"ok","env":"development"}`

Локально ще перевіряти (див. [docs/deploy.md](docs/deploy.md), розділ 7):
`GET /` віддає `index.html`, `GET /api/summary` — дані з бази,
`GET /api/неіснуючий` — **404 JSON**, а не HTML.

**Production:** `curl https://home-base.pp.ua/health` → `{"status":"ok","env":"production"}`

## 7. Правила перед завершенням задачі

- Працювати в **окремій гілці**, не в `main`.
- Показувати **`git diff`**, а не переказ змін словами.
- **Не** запускати `git add` / `git commit` / `git push` без прохання.
- **Не** запускати `docker` / `npm` без прохання.
- Перед завершенням запустити і **показати результат**:
  ```bash
  python scripts/preflight.py
  ```

## 8. Чого не робити ніколи

- Хардкодити секрети в код, тести, логи чи документацію.
- Змінювати `app/db.py`, `app/agent.py`, `app/action_tools.py` без явного
  прохання — це ядро підключення до бази і AI-агента.
- Додавати залежності в `requirements.txt` або `admin/package.json` без
  узгодження.
- Чіпати `.env` — ні читати значення в чат, ні редагувати, ні комітити.
