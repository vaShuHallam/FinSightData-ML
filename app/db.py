from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app import config
from app.models import Base

_connect_args = {"check_same_thread": False} if config.IS_SQLITE else {}

engine = create_engine(
    config.DATABASE_URL,
    echo=config.SQL_ECHO,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args,
)


# SQLite does NOT enforce foreign key constraints by default — every
# ForeignKey() in models.py is otherwise silently decorative, not enforced.
# This must run on every new connection (SQLite pragmas are per-connection,
# not persistent), which is why it's wired to the "connect" event rather
# than called once after create_engine().
if config.IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session() -> Iterator[Session]:
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
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    Base.metadata.drop_all(bind=engine)