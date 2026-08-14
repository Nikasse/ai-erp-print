# PROJECT.md

Зведений стан проєкту `ai-erp-print`. Відповідає на питання «що це і в
якому воно стані». Інструкція «як запустити» — у [README.md](README.md),
цей файл її не дублює.

## 1. Шапка

Навчальний AI-SaaS обліку фінансів. Курс Web Academy, vibe coding.

| | |
|---|---|
| Репозиторій | публічний, `Nikasse/ai-erp-print` |
| Продакшн | https://home-base.pp.ua (власний домен) |
| Технічна адреса | https://ai-erp-print.onrender.com |
| Оновлено | 14 серпня 2026 |
| Статус курсу | завершено, 15 уроків |

## 2. Наскрізна ідея курсу

Бекенд — єдина точка, де приймаються рішення про дані. Одна межа,
п'ять рівнів, кожен додавав ще одне обмеження на те, що можна робити
в обхід backend:

| Урок | Межа |
|---|---|
| 7 | React не читає базу напряму, тільки через `/api/*` |
| 8 | React не пише в базу, тільки через `/api/*` |
| 9 | React не викликає LLM, тільки через backend |
| 11 | LLM тільки читає (read-only tools) |
| 12 | LLM пропонує → людина підтверджує → backend виконує |

## 3. Головний принцип роботи AI

```
AI пропонує → людина підтверджує → backend виконує
```

Модель не пише в базу напряму, тільки через `pending_actions` —
детально в [AGENTS.md](AGENTS.md), розділ 3.

## 4. Архітектура

```
Браузер → home-base.pp.ua → Render → FastAPI (app.render_app) → Neon Postgres
                                          └→ Anthropic API
```

Telegram-бот (`app/main.py`) — окремий процес, на Render не деплоїться,
запускається локально через `docker compose`.

Одна база, два інтерфейси: Telegram — для вводу (`/expense`), веб-адмінка —
для перегляду й керування (створення, видалення, AI-аналіз, AI-чат).

## 5. Стек

| Шар | Технологія |
|---|---|
| Backend | FastAPI + Uvicorn |
| Frontend | React 19 + Vite |
| База | Neon Postgres (SQLAlchemy 2.0 async + asyncpg) |
| AI | Anthropic API + LangGraph (`app/agent.py`, `app/llm.py`) |
| Telegram-бот | aiogram 3.x (`app/main.py`) |
| Деплой | Render, Docker |
| CI | GitHub Actions |
| Домен | NIC.UA, зона `.pp.ua` |

## 6. Структура репозиторію

```
app/                    — backend: API, бот, база, AI-агент
admin/                  — React-адмінка (Vite)
docs/                   — документація (deploy, domain, maintenance, database, security, architecture)
scripts/                — preflight.py
.github/workflows/      — CI (preflight.yml)
```

Два Dockerfile, різне призначення:

| Файл | Що збирає | Де використовується |
|---|---|---|
| `Dockerfile` | образ **Telegram-бота** (`CMD python -m app.main`) | сервіс `bot` у `docker-compose.yml`, локально |
| `Dockerfile.render` | **production-образ** (backend + зібраний фронтенд) | Render |

**Production entry point — `app/render_app.py`, не `app/api.py`.**
`render_app.py` імпортує `app` з `api.py` і додає монтування статики та
SPA fallback. Запуск на Render `app.api:app` дав би робочий API, але без
адмінки — `/` повертав би 404.

## 7. База даних

Таблиці: `users`, `categories`, `transactions`, `pending_actions`
(`app/models.py`).

Схема створюється через `Base.metadata.create_all()` у `init_models()`
(`app/db.py`). Міграційного інструменту немає: `create_all` лише додає
відсутні таблиці, не змінює й не видаляє наявні — зміна структури
робиться і відкочується руками ([docs/maintenance.md](docs/maintenance.md),
розділ 10).

## 8. API

`app/api.py`:

| Метод | Шлях | Призначення |
|---|---|---|
| GET | `/health` | liveness-перевірка, без звернення до бази |
| GET | `/api/transactions` | список операцій |
| POST | `/api/transactions` | створити операцію |
| DELETE | `/api/transactions/{transaction_id}` | видалити операцію |
| GET | `/api/summary` | `total_income`, `total_expense`, `balance` |
| POST | `/api/ai/analyze-transactions` | AI-аналіз операцій (structured JSON) |
| POST | `/api/ai/chat` | AI-чат, повертає `pending_action` за потреби |
| POST | `/api/ai/actions/{action_id}/confirm` | підтвердити AI-дію, ідемпотентно |
| POST | `/api/ai/actions/{action_id}/cancel` | скасувати AI-дію |

`app/render_app.py`: `GET /{full_path:path}` — SPA fallback (лише `GET`,
`/api/*` і `/health` виключені).

## 9. Змінні оточення

| Змінна | Де потрібна | Призначення |
|---|---|---|
| `BOT_TOKEN` | бот (`app/main.py`) | доступ до Telegram Bot API |
| `DATABASE_URL` | бот, API | підключення до Neon Postgres |
| `ANTHROPIC_API_KEY` | API | виклики Anthropic (аналіз, чат) |
| `APP_ENV` | API на Render | `production` вимикає CORS і позначає `/health` |

Шаблон — [.env.example](.env.example). `.env` у Git не потрапляє
([docs/security.md](docs/security.md)).

## 10. Процес змін

```
гілка → preflight локально → PR → CI → merge → Render deploy → smoke test → rollback за потреби
```

`main` захищена: preflight — required status check, merge без нього
заблокований.

**Важливо:** Render **не чекає** на зелений CI — він реагує на сам push у
`main`. Від зламаного production захищає саме захист гілки, а не Actions:
push напряму в `main` в обхід PR обходить усі перевірки
([docs/maintenance.md](docs/maintenance.md), розділ 4).

## 11. Запуск

```bash
docker compose build api
docker compose up -d --force-recreate api
```
```bash
cd admin && npm install && npm run dev
```

Перевірка: `curl http://localhost:8000/health`

Повна інструкція, змінні оточення, деплой на Render — [docs/deploy.md](docs/deploy.md).

## 12. Технічний борг

- `except Exception` без логування в `app/api.py` (виклик LLM у
  `/api/ai/analyze-transactions` і `/api/ai/chat`) — ховає справжню
  причину, назовні тільки `"LLM недоступний"` / `"AI-помічник недоступний"`.
- `HEAD /` → `405` у логах Render — не помилка, catch-all роут
  зареєстрований лише на `GET`.
- Free tier Render: спін-даун після ~15 хв простою, холодний старт 30–60 с.
- NS у NIC.UA діють до 12 листопада 2026, автопродовження вимкнено —
  домен зареєстрований до серпня 2027, строки різні
  ([docs/domain.md](docs/domain.md), розділ 8).
- Міграцій немає: зміна схеми робиться і відкочується руками (розділ 7).

## 13. Що зроблено по уроках

| Урок | Що з'явилось у проєкті |
|---|---|
| 1 | Git як страховка: branch, commit, push, merge |
| 2 | Середовище: Cursor, AI-помічник, Docker, localhost, tunnel |
| 3 | Перший Telegram-бот на aiogram, hot reload, фіксація в Git |
| 4 | Логи й traceback, config окремо від коду (`.env`/`.env.example`/`.gitignore`), `logging`, detect-secrets і `.secrets.baseline`, правила промпту для виправлення помилок |
| 5 | Блоки IT-продуктів |
| 6 | Цифрова безпека: секрети в `.env`, `DATABASE_URL`, Neon Postgres, SQLAlchemy 2.0 async + asyncpg, схема бази (`users`, `categories`, `transactions`), команда `/expense`, [docs/security.md](docs/security.md), [docs/database.md](docs/database.md) |
| 7 | Від бота до SaaS: `GET /api/transactions`, `GET /api/summary`, React + Vite адмінка, картки й таблиця операцій |
| 8 | Керування даними: форма створення, `POST /api/transactions`, `DELETE /api/transactions/{id}` з confirm, фільтри all/income/expense, базова валідація |
| 9 | LLM як функція продукту: `POST /api/ai/analyze-transactions`, backend бере операції з Neon, будує prompt, отримує structured JSON, React показує картки. Відхилення від курсу: у програмі `OPENAI_API_KEY`, у проєкті — Anthropic API (`ANTHROPIC_API_KEY`) |
| 10 | Prompt під контролем: винесений в `app/prompts.py`, анатомія промпту (роль, задача, дані, обмеження, формат), structured JSON як контракт з frontend, правило «модель не вигадує дані», підрахунок токенів, сирі операції vs зведення, `AI_PROMPT_NOTES.md` |
| 11 | Від AI-кнопки до AI-чату: `POST /api/ai/chat`, `thread_id`, short-term memory через checkpointer, read-only tools (`app/tools.py`, `app/agent.py`). Межа: тільки читання, без write/delete/довільного SQL. `AI_ASSISTANT_NOTES.md` |
| 12 | Write-actions під контролем людини: `pending_actions`, prepare-tools, ідемпотентні confirm/cancel, audit log, колонка № в таблиці = id транзакції. `AI_ACTIONS_NOTES.md` |
| 13 | Деплой на Render: `Dockerfile.render` (multi-stage), `app/render_app.py` (статика + SPA fallback), `/health` без звернення до бази, [docs/deploy.md](docs/deploy.md) |
| 14 | Власний домен `home-base.pp.ua`: NIC.UA, NS `ns10-12.uadns.com`, A-запис на `216.24.57.1`, TLS-сертифікат, [docs/domain.md](docs/domain.md) |
| 15 | Процес безпечної підтримки: [AGENTS.md](AGENTS.md), `scripts/preflight.py` (5 перевірок), GitHub Actions на PR і push у `main`, branch protection з required check, [docs/maintenance.md](docs/maintenance.md) |
