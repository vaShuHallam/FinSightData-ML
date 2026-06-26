"""
FinSight AI — database engine and session management.

One connection string drives everything: set DATABASE_URL to a sqlite:// URL
locally or a postgresql:// URL in production and the same code works against
both (see app/config.py).
"""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import config
from app.models import Base

# SQLite needs check_same_thread=False so the connection can be shared across
# Streamlit's worker threads. Postgres ignores connect_args here.
_connect_args = {"check_same_thread": False} if config.IS_SQLITE else {}

engine = create_engine(
    config.DATABASE_URL,
    echo=config.SQL_ECHO,
    future=True,
    pool_pre_ping=True,  # transparently recycle dropped Postgres connections
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session() -> Iterator[Session]:
    """
    Provide a transactional session scope.

        with get_session() as session:
            session.add(obj)
            # commit happens automatically on clean exit; rollback on error
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables that don't yet exist. Safe to call repeatedly."""
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Drop all tables. Destructive — intended for dev/test resets only."""
    Base.metadata.drop_all(bind=engine)