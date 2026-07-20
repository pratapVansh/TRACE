from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import logger

engine = create_async_engine(
    settings.get_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def verify_database_connection() -> bool:
    """Verify PostgreSQL is reachable."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connection verified")
        return True
    except Exception as exc:
        logger.error("PostgreSQL connection failed: %s", exc)
        return False


async def close_database_connection() -> None:
    await engine.dispose()
    logger.info("PostgreSQL connection pool closed")
