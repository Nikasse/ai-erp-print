import asyncio

from sqlalchemy import text

from app.db import engine


async def check_db() -> bool:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    print("Database connection OK")
    return True


if __name__ == "__main__":
    asyncio.run(check_db())
