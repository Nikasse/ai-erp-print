

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

## Перевірка (як доводимо, що межа тримається)
Запит «додай витрату 450 на таксі» → приходить pending_action зі status=pending,
але GET /api/transactions нової витрати НЕ показує.
Запит «скільки я витратив» → pending_action: null, працюють read-only tools.