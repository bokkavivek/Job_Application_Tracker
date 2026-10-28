from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session():
    """FastAPI dependency: one DB session per request."""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create tables if they do not exist (simple alternative to migrations)."""
    import models  # noqa: F401  (registers the tables on Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
