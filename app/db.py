import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()


class Base(DeclarativeBase):
    pass


def _build_async_url() -> tuple[str, dict]:
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        raise RuntimeError("DATABASE_URL is not set. Add it to .env")

    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query))

    # asyncpg's connect() doesn't accept psycopg2-style "sslmode"/"channel_binding"
    # query params (used by Neon and similar hosted Postgres) — translate them
    # into connect_args instead of passing them through in the URL.
    connect_args = {}
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode and sslmode != "disable":
        connect_args["ssl"] = True

    url = urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), parts.fragment))
    return url, connect_args


_ASYNC_DATABASE_URL, _CONNECT_ARGS = _build_async_url()

engine = create_async_engine(_ASYNC_DATABASE_URL, connect_args=_CONNECT_ARGS, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_models() -> None:
    from app import models  # noqa: F401 — registers tables on Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
