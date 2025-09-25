"""
Database session management with async SQLAlchemy.
"""
from typing import AsyncGenerator, Optional, Any
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine
)

# Handle different SQLAlchemy versions
try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
except ImportError:
    # For SQLAlchemy < 2.0, use sessionmaker with class_ parameter
    from sqlalchemy.orm import sessionmaker
    async_sessionmaker = sessionmaker  # type: Any

from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global engine and session factory
_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[Any] = None  # Can be async_sessionmaker or sessionmaker


def get_engine() -> AsyncEngine:
    """
    Get or create the database engine.
    
    Returns:
        Async database engine
    """
    global _engine
    
    if _engine is None:
        # Create engine with connection pooling
        _engine = create_async_engine(
            settings.database.database_url,
            echo=settings.database.database_echo,
            pool_size=settings.database.database_pool_size,
            max_overflow=settings.database.database_max_overflow,
            pool_timeout=settings.database.database_pool_timeout,
            pool_pre_ping=True,  # Verify connections before using
            # Use NullPool for serverless/Lambda deployments
            poolclass=NullPool if settings.app.app_env == "serverless" else None,
        )
        logger.info("Database engine created", url=settings.database.database_url.split("@")[1])
    
    return _engine


def get_session_factory() -> Any:
    """
    Get or create the async session factory.
    
    Returns:
        Async session factory
    """
    global _async_session_factory
    
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False
        )
        logger.info("Session factory created")
    
    return _async_session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.
    Dependency for FastAPI routes.
    
    Yields:
        Database session
    """
    async_session = get_session_factory()
    
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions.
    Use this for non-FastAPI code.
    
    Example:
        async with get_db_session() as session:
            result = await session.execute(query)
    
    Yields:
        Database session
    """
    async_session = get_session_factory()
    
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """
    Create all database tables.
    Use Alembic for production migrations.
    """
    from models import Base
    
    engine = get_engine()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created")


async def drop_tables() -> None:
    """
    Drop all database tables.
    WARNING: This will delete all data!
    """
    from models import Base
    
    engine = get_engine()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.warning("Database tables dropped")


async def init_database() -> None:
    """
    Initialize the database.
    Creates tables if they don't exist.
    """
    try:
        await create_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


async def close_database() -> None:
    """
    Close database connections.
    Call this on application shutdown.
    """
    global _engine, _async_session_factory
    
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database connections closed")


class DatabaseTransaction:
    """
    Context manager for database transactions with automatic rollback.
    
    Example:
        async with DatabaseTransaction() as tx:
            await tx.session.execute(query1)
            await tx.session.execute(query2)
            await tx.commit()  # Explicit commit
    """
    
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
        self._owns_session = session is None
        self._committed = False
    
    async def __aenter__(self):
        if self._owns_session:
            async_session = get_session_factory()
            self.session = async_session()
        
        await self.session.begin()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        elif not self._committed:
            await self.commit()
        
        if self._owns_session:
            await self.session.close()
    
    async def commit(self):
        """Commit the transaction"""
        if not self._committed:
            await self.session.commit()
            self._committed = True
            logger.debug("Transaction committed")
    
    async def rollback(self):
        """Rollback the transaction"""
        if not self._committed:
            await self.session.rollback()
            logger.debug("Transaction rolled back")