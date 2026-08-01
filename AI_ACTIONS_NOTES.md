

## Принцип
AI пропонує → користувач підтверджує → backend виконує.
Модель ніколи не змінює базу напряму.

## Архітектура (стан на зараз)
- pending_actions (app/models.py) — таблиця чернеток дій
- app/action_tools.py — два prepare-tools, повертають json.dumps(dict),
  жодного session/commit/add
- app/agent.py — prepare-tools підключені через StructuredTool.from_function
  поряд з read-only tools Уроку 11; chat() повертає (answer, messages)
- app/api.py, POST /api/ai/chat — шукає ОСТАННІЙ ToolMessage від prepare-tools,
  парсить JSON, створює PendingAction зі status=pending, повертає pending_action
- app/api.py, POST /api/ai/actions/{action_id}/confirm — перевірки по порядку:
  існує (404) → належить користувачу (403) → status == "pending" (409) →
  валідація payload заново, без довіри до збереженого JSON (422, status→failed)
  → тільки після цього створення Transaction / зміна категорії →
  status→confirmed, confirmed_at
- app/api.py, POST /api/ai/actions/{action_id}/cancel — ті самі перевірки,
  status→cancelled, таблиця transactions не чіпається
- спільний хелпер _get_own_pending_action для перевірок обох ендпоінтів
- audit log через logging (logger "ai_actions"): action_id, thread_id,
  action_type, status, результат або помилка. Без payload, ключів, .env
- React: картка "Запропонована дія" в admin/src/App.jsx, стан cardState
  (pending / loading / confirmed / cancelled / error). Кнопки disabled під час
  запиту, після відповіді зникають і замінюються підсумком — повторний клік
  неможливий структурно. Після confirm перезавантажуються таблиця й підсумки,
  після cancel — ні.

## Межі моделі (що модель НЕ робить)
- не генерує action_id — його створює backend через uuid4()
- не знає поточної дати — backend підставляє date.today()
- не пише в базу транзакцій
- не стверджує «збережено», тільки «підготовлено, потрібне підтвердження»

## Що рахує backend, а не модель
Все детерміноване: action_id, дата, status, user_id.
Правило: якщо факт можна обчислити точно — його обчислює код.

## Технічні пастки (перевірено на практиці)
- LangGraph віддає результат тулу як рядок → prepare-функції мусять повертати
  json.dumps(...), інакше json.loads падає на Python-repr з одинарними лапками
- init_models() з app/db.py НЕ викликається на старті app/api.py — нова таблиця
  pending_actions не створилась сама, довелось прогнати init_models() вручну.
  При додаванні нової моделі це треба пам'ятати.
- Модель без явної інструкції починає питати дату у користувача — лікується
  опційним параметром date + правилом у SYSTEM_PROMPT
- Правки SYSTEM_PROMPT не діють без перезапуску backend. Кілька ітерацій
  правок було зроблено даремно, бо тестувався старий промпт.
- Спершу перевіряй базову поведінку моделі БЕЗ додаткових правил у промпті.
  Заборонні формулювання ("не питай опис") дали зворотний ефект — модель
  почала наполягати. Без правил поведінка була кращою.
- git checkout <file> стирає всі незакомічені правки цього файлу, зокрема
  ті, що зробив Claude Code.

## Технічний борг
- date з payload валідується, але не записується — у моделі Transaction
  немає окремого поля дати, тільки created_at через server_default
- init_models() не викликається на старті app/api.py
- немає захисту від одночасного подвійного confirm (для навчального
  проєкту достатньо перевірки статусу)

## Перевірка (як доводимо, що межа тримається)
Запит «додай витрату 450 на таксі» → приходить pending_action зі status=pending,
але GET /api/transactions нової витрати НЕ показує.
Запит «скільки я витратив» → pending_action: null, працюють read-only tools.

## Матриця станів (перевірено вручну)
prepare → pending, база чиста
confirm з pending → транзакція створена, status=confirmed
confirm повторно → 409, другої транзакції немає
cancel з pending → cancelled, база чиста
confirm скасованої → 409
Стан pending — єдина точка входу, вихід із неї односторонній в обидва боки.