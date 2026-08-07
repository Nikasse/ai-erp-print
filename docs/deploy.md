# Деплой ai-erp-print на Render

## 1. Архітектура

Один Render Web Service, runtime Docker, збирається з `Dockerfile.render`.

Ланцюг: GitHub → Render build → Docker image → container →
FastAPI (`app.render_app`) → Neon Postgres.

FastAPI віддає і `/api/*`, і зібрану статику React з `/app/static`.
Фронтенд (`admin/`) використовує відносні URL (`/api/...`), тому браузер
завжди звертається на той самий origin, що й віддав сторінку — CORS у
production не потрібен (`app/api.py` вимикає `allow_origins`, коли
`APP_ENV=production`, див. розділ 4).

Neon — зовнішня хмарна база, від Render інфраструктурно не залежить: живе
й спить (free tier) незалежно від стану Render-сервісу.

Окремо в репозиторії лишається базовий `Dockerfile` — це образ
Telegram-бота (`app/main.py`, сервіс `bot` у `docker-compose.yml`), на
Render він не використовується і деплою не стосується.

## 2. Збірка (Dockerfile.render)

Multi-stage збірка, дві стадії:

**Стадія 1 — `node:20-alpine` (`build`)**
```dockerfile
FROM node:20-alpine AS build
WORKDIR /admin
COPY admin/package*.json ./
RUN npm ci
COPY admin/ ./
RUN npm run build
```
Ставить залежності адмінки, копіює вихідний код `admin/` і збирає
production-бандл — Vite кладе його в `/admin/dist`.

**Стадія 2 — `python:3.12-slim` (фінальний образ)**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY --from=build /admin/dist ./static
```
Ставить Python-залежності, копіює backend-код `app/` і забирає готову
збірку фронтенду зі стадії `build` у `./static` — тобто `/app/static`
(бо `WORKDIR /app`). Саме цей шлях читає `STATIC_DIR` в
`app/render_app.py`.

Стадія `build` у фінальний образ не потрапляє — лишається лише
скомпільований `/admin/dist`, Node у рантаймі немає.

## 3. Команда запуску

```dockerfile
CMD ["sh", "-c", "uvicorn app.render_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

Це shell-форма (`sh -c "..."`), і це обов'язково: в exec-формі
(`CMD ["uvicorn", "app.render_app:app", "--port", "${PORT}"]`) Docker не
запускає шелл, тому `${PORT}` не розкривається — uvicorn отримає
буквальний рядок `"${PORT}"` як значення `--port`, впаде на старті, і
Render завалить health check по таймауту (порт, на який він шле запити,
ніколи не відкриється).

Render сам прокидає змінну `PORT` в контейнер (на практиці — `10000`);
`${PORT:-8000}` бере це значення, а `8000` лишається fallback-ом для
локального запуску без `PORT`. Слухаємо `0.0.0.0`, не `127.0.0.1` —
інакше Render не достукається до контейнера ззовні.

## 4. Змінні оточення на Render

У Render Dashboard → сервіс → **Environment** потрібні:

| Змінна | Значення |
|---|---|
| `DATABASE_URL` | той самий рядок, що й локально в `.env` |
| `ANTHROPIC_API_KEY` | ключ Anthropic |
| `APP_ENV` | `production` |

Формат `DATABASE_URL` — такий самий, як локально:
```
postgresql://user:password@host/dbname?sslmode=require&channel_binding=require
```
Перетворення для asyncpg (drop `sslmode`/`channel_binding` з query-рядка,
переклад у `connect_args={"ssl": True}`) робить `app/db.py` сам — на
Render нічого додатково конвертувати не треба, вставляється той самий
рядок, що й у локальному `.env`.

Секрети — **тільки** в Environment Variables панелі Render, ніколи в
Git (`.env` і так у `.gitignore`, `Dockerfile.render` його не копіює:
`.dockerignore` виключає `.env` з build-контексту).

## 5. Health check

Path у налаштуваннях Render: **`/health`**.

```json
{"status": "ok", "env": "production"}
```

Ендпоінт (`app/api.py`) навмисно **не звертається до бази**. Причина:
Neon на free tier засинає після простою, і перший запит після сну
виконується повільно й може впасти. Якби health check ходив у базу —
одне невдале пробудження Neon змусило б Render вирішити, що сервіс не
піднявся, і завалити цілком робочий deploy.

## 6. Типові помилки (з реального досвіду цього деплою)

- **`Could not parse SQLAlchemy URL from string 'postgresql+asyncpg:XXXX'`**
  → у `DATABASE_URL` на Render потрапив обрізаний рядок при вставці.
  Лікування: очистити поле повністю, вставити рядок цілком, Save Changes.

- **`"LLM недоступний"` на фронтенді при робочій базі**
  → обрізаний `ANTHROPIC_API_KEY` у Environment Variables. Ключ має
  починатися з `sk-ant-` і бути ~100+ символів. Важливо: у
  `app/api.py` виклик LLM обгорнутий у `except Exception` без
  логування (`raise HTTPException(status_code=502, detail="LLM недоступний")`),
  тому справжня причина (обрізаний ключ, відсутній ключ, збій Anthropic
  API) НЕ потрапляє в логи Render — усі ці випадки виглядають однаково.
  Діагностувати можна тільки прямою перевіркою самої змінної в
  Environment, логи тут не допоможуть.

  **Загальне правило вставки секретів на Render** (обидві помилки вище —
  наслідок часткової вставки): перед вставкою очистити поле повністю
  (⌘A, Delete), вставити значення цілком одним разом, візуально
  перевірити початок і кінець рядка, і лише тоді Save Changes.

- **Deploy успішний, але сервіс падає по health check timeout**
  → перевірити поле Dockerfile Path у налаштуваннях сервісу: має бути
  `./Dockerfile.render`, а не `./Dockerfile` (той збирає образ бота —
  жодного HTTP-порту він не відкриває, тож health check ніколи не
  пройде).

- **`"HEAD / HTTP/1.1" 405 Method Not Allowed` у логах** — це НЕ
  помилка. Catch-all роут у `app/render_app.py` зареєстрований лише на
  `GET`, а Render інколи шле `HEAD`-пінги; сам health check іде окремо
  на `GET /health` і відпрацьовує нормально.

- **Локально: `docker compose` ігнорує нові `ports` у вже створеному
  контейнері** → перестворити контейнер явно:
  ```
  docker compose up -d --force-recreate api
  ```

- **Якщо секрет засвітився** (у чаті, скріншоті, комміті) — його треба
  перевипустити, а не просто видалити зі згадки. Для Neon:
  Console → Roles → Reset password, після чого оновити і локальний
  `.env`, і Environment Variables на Render.

## 7. Локальна перевірка перед деплоєм

```
docker compose build api
docker compose up -d --force-recreate api
```

Перевірити:
- `GET /health` — повертає JSON зі `status: ok`
- `GET /` — віддає `index.html` адмінки
- `GET /api/summary` — реальні дані з бази, не HTML
- `GET /api/неіснуючий` — повертає **404 JSON**, а не HTML-сторінку

Останній пункт критичний: якщо неіснуючий `/api/...`-шлях повертає
`index.html`, значить catch-all роут з `app/render_app.py` зареєстрований
раніше за `/api/*`-роути (або їх реєстрація зламана) і перехоплює API —
такий образ на Render деплоїти не можна.

## 8. Обмеження Free tier

- Спін-даун після ~15 хв простою, холодний старт після цього — 30–60 с.
- Якщо разом з цим заснула ще й Neon (теж free tier) — перший запит
  після паузи повільний подвійно: спершу піднімається контейнер, потім
  прокидається база.
- Немає SSH-доступу, немає one-off jobs, немає persistent disk (диск
  ефемерний, зникає при кожному redeploy).
- Ресурси сервісу: 512 MB RAM, 0.1 CPU.
- Діагностика — тільки через логи в панелі Render (Logs), локального
  доступу до контейнера немає.
