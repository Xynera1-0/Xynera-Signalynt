from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings

settings = get_settings()

_url = settings.database_url
# SQLAlchemy async requires postgresql+asyncpg scheme
if _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+asyncpg://", 1)

# asyncpg does not accept sslmode= as a query parameter; strip it and
# convert to the ssl= connect_arg that asyncpg understands.
_ssl_arg: str | bool = False
if "sslmode=" in _url:
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    _parsed = urlparse(_url)
    _qs = parse_qs(_parsed.query, keep_blank_values=True)
    _sslmode = (_qs.pop("sslmode", [None])[0] or "").lower()
    _ssl_arg = _sslmode not in ("disable", "allow", "")
    _new_qs = urlencode({k: v[0] for k, v in _qs.items()})
    _url = urlunparse(_parsed._replace(query=_new_qs))

engine = create_async_engine(
    _url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.debug,
    connect_args={"ssl": _ssl_arg} if _ssl_arg else {},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
