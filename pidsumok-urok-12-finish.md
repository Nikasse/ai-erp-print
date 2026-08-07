# Підсумок: Урок 12 завершено

*Дата: 1 серпня 2026. Проєкт: `ai-erp-print` (публічний, навчальний, Web Academy).*

## СТАН
Урок 12 закрито повністю. PR #15 змержено в `main`, всі 10 пунктів ДЗ виконано.
Додатково: колонка «№» у таблиці операцій з `id` транзакції з бази
(не порядковий номер рядка — щоб збігалося з «Операція №NN» у підсумку моделі).

## ПРИНЦИП
`AI пропонує → людина підтверджує → backend виконує.`
Модель ніколи не змінює базу напряму.

## ЩО ПОБУДОВАНО
- `pending_actions` (app/models.py) — таблиця чернеток дій
- `app/action_tools.py` — два prepare-tools, повертають `json.dumps(dict)`,
  жодного запису в базу
- `app/agent.py` — prepare-tools через `StructuredTool.from_function`,
  `chat()` повертає `(answer, messages)`
- `POST /api/ai/chat` — шукає ОСТАННІЙ ToolMessage від prepare-tools,
  створює PendingAction зі `status=pending`
- `POST /api/ai/actions/{id}/confirm` — 404 → 403 → 409 → валідація payload
  заново → виконання → `confirmed`
- `POST /api/ai/actions/{id}/cancel` — ті самі перевірки, `cancelled`,
  transactions не чіпається
- audit log через `logging` (logger `ai_actions`), без payload і секретів
- React-картка «Запропонована дія» з кнопками Підтвердити / Скасувати

## МЕЖІ МОДЕЛІ
- `action_id` генерує backend (`uuid4()`)
- дату підставляє backend (`date.today()`)
- опис необов'язковий
- підтвердження НЕ буває текстовим — тільки кнопка

## ТЕХНІЧНИЙ БОРГ
- `date` з payload валідується, але не записується — у моделі `Transaction`
  нема окремого поля дати, тільки `created_at` через `server_default`
- `init_models()` з `app/db.py` не викликається на старті `app/api.py`
- нема захисту від одночасного подвійного confirm (перевірки статусу
  достатньо для навчального проєкту)

## УРОКИ ПРОЦЕСУ
- **Правки SYSTEM_PROMPT не діють без перезапуску backend.** Кілька ітерацій
  правок було зроблено даремно — тестувався старий промпт.
- **Спершу перевіряй базову поведінку моделі БЕЗ додаткових правил.**
  Заборонні формулювання («не питай опис») дали зворотний ефект.
- **`git checkout <file>` стирає всі незакомічені правки цього файлу**,
  зокрема ті, що зробив Claude Code.
- Перед комітом React-змін — `git status` цілком: Claude Code часто чіпає
  і `App.jsx`, і `index.css`.

## КОМАНДИ ЗАПУСКУ
Backend (порт 8000):

```
docker run --rm --name erp-backend -p 8000:8000 --env-file ~/ai-erp-print/.env -v ~/ai-erp-print:/app -w /app python:3.12-slim bash -c "pip install -q -r requirements.txt && python -m app.api"
```

Зупинка: `docker stop erp-backend`

Vite (порт 5173): `cd ~/ai-erp-print/admin && npm run dev`

## НАСТУПНИЙ КРОК
Здати посилання на репозиторій Архипу через платформу Web Academy:
https://github.com/Nikasse/ai-erp-print

## ПОТОЧНА РОБОТА (7 серпня)
- гілка `deploy/render` — підготовка до деплою на Render
- `app/api.py`: CORS переведено на APP_ENV-залежні origins, додано `/health` endpoint
- `admin`: абсолютні URL замінюються на відносні (`vite.config.js`, `App.jsx`)
- стан: у процесі, не змержено
</content>
