"""Database initialization and session management for PodX server."""

import os
from pathlib import Path
from typing import AsyncGenerator, Union

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from podx.server.models.database import Base

# Database path: ~/.podx/server.db
DEFAULT_DB_PATH = Path.home() / ".podx" / "server.db"


def get_database_url(db_path: Union[Path, str] = DEFAULT_DB_PATH) -> str:
    """Get SQLAlchemy database URL.

    Args:
        db_path: Path to SQLite database file or ":memory:" for in-memory DB

    Returns:
        SQLAlchemy database URL
    """
    # Handle in-memory database
    if str(db_path) == ":memory:":
        return "sqlite+aiosqlite:///:memory:"

    # Ensure directory exists for file-based DB
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # SQLite URL for async SQLAlchemy (using aiosqlite)
    return f"sqlite+aiosqlite:///{db_path}"


# Create async engine
# Environment variable PODX_DB_PATH can override default
db_path = Path(os.getenv("PODX_DB_PATH", str(DEFAULT_DB_PATH)))
DATABASE_URL = get_database_url(db_path)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    future=True,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize database tables.

    Creates all tables defined in Base metadata.
    Should be called on application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Yields:
        AsyncSession instance

    Example:
        @app.get("/jobs")
        async def list_jobs(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session_factory() as session:
        yield session
