"""LangGraph-агент з пам'яттю та tools для відповідей на питання про фінанси.

Обгортає read-only функції з app/tools.py у LangChain tools і будує
react-агента через langgraph.prebuilt.create_react_agent з MemorySaver
як checkpointer (short-term memory за thread_id).

Використовується в app/api.py через POST /api/ai/chat (функція chat()).
"""

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from app.tools import get_category_totals, get_top_expenses, get_transactions_summary

MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = (
    "Ти — фінансовий помічник, який відповідає користувачу на питання про "
    "його доходи та витрати.\n\n"
    "Суворі правила:\n"
    "- Спирайся ТІЛЬКИ на дані, отримані через доступні tools. Не вигадуй "
    "суми, категорії чи операції, яких tools не повернули.\n"
    "- Для будь-якого питання про суми, категорії, витрати чи баланс "
    "спочатку виклич відповідний tool — не відповідай з памʼяті чи здогадок.\n"
    "- Якщо tool повернув порожній або дуже обмежений результат — прямо "
    "скажи, що даних замало для впевненого висновку, а не додумуй.\n"
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


async def chat(message: str, thread_id: str) -> str:
    """Відповідає на повідомлення користувача, зберігаючи контекст за thread_id."""
    agent = _get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config=config,
    )

    final_message = result["messages"][-1]
    return final_message.content
