"""LangGraph-агент з пам'яттю та tools для відповідей на питання про фінанси
та підготовки контрольованих AI-дій.

Обгортає read-only функції з app/tools.py та prepare-функції з
app/action_tools.py у LangChain tools і будує react-агента через
langgraph.prebuilt.create_react_agent з MemorySaver як checkpointer
(short-term memory за thread_id). Prepare-tools лише формують чернетку
дії — жодного запису в базу тут не відбувається.

Використовується в app/api.py через POST /api/ai/chat (функція chat()).
"""

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from app.action_tools import prepare_change_category, prepare_create_transaction
from app.tools import get_category_totals, get_top_expenses, get_transactions_summary

MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = (
    "Ти — фінансовий помічник, який відповідає користувачу на питання про "
    "його доходи та витрати і допомагає готувати зміни в цих даних.\n\n"
    "Суворі правила для питань про дані:\n"
    "- Спирайся ТІЛЬКИ на дані, отримані через доступні read-only tools "
    "(get_transactions_summary, get_category_totals, get_top_expenses). Не "
    "вигадуй суми, категорії чи операції, яких tools не повернули.\n"
    "- Для будь-якого питання про суми, категорії, витрати чи баланс "
    "спочатку виклич відповідний tool — не відповідай з памʼяті чи здогадок.\n"
    "- Якщо tool повернув порожній або дуже обмежений результат — прямо "
    "скажи, що даних замало для впевненого висновку, а не додумуй.\n\n"
    "Суворі правила для прохань змінити дані (наприклад, «додай витрату», "
    "«запиши дохід», «зміни категорію операції»):\n"
    "- Виклич рівно ОДИН РАЗ відповідний tool: prepare_create_transaction "
    "для нової операції або prepare_change_category для зміни категорії. "
    "Ці tools нічого не записують у базу — вони лише готують чернетку дії.\n"
    "- Ніколи не викликай prepare-tool повторно в межах одного запиту "
    "користувача.\n"
    "- Ти НЕ знаєш поточної дати. Якщо користувач сказав «сьогодні» або "
    "взагалі не згадав дату — НЕ питай дату і НЕ передавай параметр date у "
    "prepare_create_transaction, просто виклич tool без нього: backend сам "
    "підставить поточну дату сервера. Параметр date передавай лише якщо "
    "користувач явно назвав конкретний день.\n"
    "- Після виклику prepare-tool у тексті відповіді прямо скажи, що дію "
    "ПІДГОТОВЛЕНО (не виконано, не збережено) і що потрібне підтвердження "
    "користувача, перш ніж її буде застосовано. ЗАВЖДИ виведи склад "
    "чернетки списком: Тип, Сума, Категорія, Дата, Опис (якщо опису нема — "
    "напиши «без опису»). Далі — окремий рядок про те, що потрібно "
    "натиснути кнопку «Підтвердити».\n"
    "- НІКОЛИ не стверджуй, що операція вже збережена, застосована чи "
    "внесена в базу — це неправда, доки користувач її не підтвердив.\n"
    "- Не вигадуй і не згадуй жодний ідентифікатор дії (action_id) — його "
    "створює backend, а не ти.\n"
    "- Категорію бери БУКВАЛЬНО зі слів користувача і не перепитуй: сказав "
    "«еда» — категорія «еда», сказав «таксі» — категорія «таксі», сказав "
    "«кава» — категорія «кава». Не пропонуй альтернативні формулювання.\n"
    "- Опис — необов'язкове поле. Не пиши, що він обов'язковий. Якщо "
    "користувач не назвав опис — готуй чернетку без опису. Якщо питаєш про "
    "опис — одне коротке речення, без інших уточнень у тому ж повідомленні.\n\n"
    "Підтвердження дії НЕ буває текстовим:\n"
    "- Слова «ок», «так», «давай», «добре» та подібні НЕ виконують дію. "
    "Ніколи не пиши, що операцію внесено, збережено чи створено. На таке "
    "текстове підтвердження відповідай, що чернетку вже підготовлено і "
    "потрібно натиснути кнопку «Підтвердити». Повторно prepare-tool не "
    "викликай.\n\n"
    "- Відповідай виключно українською мовою."
)

_agent = None


def _log_tool_call(name: str, **params: object) -> None:
    # Логуємо лише назву tool і параметри виклику — жодних секретів
    # і жодного повного результату виклику.
    print(f"[agent] tool call: {name}({', '.join(f'{k}={v!r}' for k, v in params.items())})")


async def _logged_get_transactions_summary(period: str) -> dict:
    _log_tool_call("get_transactions_summary", period=period)
    return await get_transactions_summary(period)


async def _logged_get_category_totals(period: str) -> dict:
    _log_tool_call("get_category_totals", period=period)
    return await get_category_totals(period)


async def _logged_get_top_expenses(period: str, limit: int = 5) -> list:
    _log_tool_call("get_top_expenses", period=period, limit=limit)
    return await get_top_expenses(period, limit)


def _build_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            coroutine=_logged_get_transactions_summary,
            name="get_transactions_summary",
            description=get_transactions_summary.__doc__,
        ),
        StructuredTool.from_function(
            coroutine=_logged_get_category_totals,
            name="get_category_totals",
            description=get_category_totals.__doc__,
        ),
        StructuredTool.from_function(
            coroutine=_logged_get_top_expenses,
            name="get_top_expenses",
            description=get_top_expenses.__doc__,
        ),
        StructuredTool.from_function(
            func=prepare_create_transaction,
            name="prepare_create_transaction",
            description=prepare_create_transaction.__doc__,
        ),
        StructuredTool.from_function(
            func=prepare_change_category,
            name="prepare_change_category",
            description=prepare_change_category.__doc__,
        ),
    ]


def _get_agent():
    global _agent
    if _agent is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to .env")

        model = ChatAnthropic(model=MODEL, api_key=api_key)
        checkpointer = MemorySaver()
        _agent = create_react_agent(
            model=model,
            tools=_build_tools(),
            prompt=SYSTEM_PROMPT,
            checkpointer=checkpointer,
        )
    return _agent


async def chat(message: str, thread_id: str) -> tuple[str, list]:
    """Відповідає на повідомлення користувача, зберігаючи контекст за thread_id.

    Повертає (answer, messages), де messages — повна історія повідомлень
    графа за цей виклик, потрібна викликачу для пошуку ToolMessage від
    prepare-tools (сам агент тут нічого в базу не пише)."""
    agent = _get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config=config,
    )

    final_message = result["messages"][-1]
    return final_message.content, result["messages"]
