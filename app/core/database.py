"""Database engine / session management (SQLAlchemy 2.0, sync)."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_url = settings.resolved_database_url
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}

engine = create_engine(
    _url,
    echo=settings.debug and settings.environment == "development" and False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Dev convenience only — production uses Alembic."""
    from app.models.base import Base  # noqa: WPS433  (import here to register models)
    import app.models  # noqa: F401  (ensure every model module is imported)

    Base.metadata.create_all(bind=engine)
