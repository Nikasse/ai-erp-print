import os

from anthropic import AsyncAnthropic

MODEL = "claude-haiku-4-5"

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to .env")
        _client = AsyncAnthropic(api_key=api_key)
    return _client


async def ask(prompt: str, system: str | None = None) -> str:
    client = _get_client()
    kwargs = {"system": system} if system else {}
    response = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    return next((block.text for block in response.content if block.type == "text"), "")


if __name__ == "__main__":
    import asyncio

    async def _test() -> None:
        result = await ask("Скажи одним реченням українською, що ти працюєш.")
        print("Відповідь LLM:", result)

    asyncio.run(_test())
