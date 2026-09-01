from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import get_settings

settings = get_settings()
legacy_engine = create_async_engine(settings.legacy_database_url, pool_pre_ping=True)
legacy_session_factory = async_sessionmaker(legacy_engine, expire_on_commit=False)


async def get_legacy_session() -> AsyncIterator[AsyncSession]:
    async with legacy_session_factory() as session:
        yield session


async def close_legacy_database() -> None:
    await legacy_engine.dispose()
