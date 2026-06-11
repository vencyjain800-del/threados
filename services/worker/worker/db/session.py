"""
Synchronous SQLAlchemy engine and session for the worker.

Uses the owner role (threados_migrate) which has rolbypassrls=True.
All writes MUST include an explicit brand_id — tenant isolation is enforced
at the application layer, not by RLS, for worker operations.

Why owner role?  The backfill job opens hundreds of short transactions (one
per page).  Calling set_config('app.current_brand', ..., true) in every
transaction would require the app role (threados_app) and complicate the
session lifecycle.  The owner role is appropriate for a trusted server
process that always writes with explicit brand_id.
"""
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from worker.config import settings

# Engine is created at module load time — no actual DB connection is made until
# a query is executed, so this is safe to import in tests.
_engine = create_engine(
    settings.database_migrate_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

_SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


@contextmanager
def worker_session() -> Generator[Session, None, None]:
    """Open a synchronous DB session.

    Callers are responsible for calling ``session.commit()`` explicitly.
    On exception the session is rolled back automatically.

    Usage::

        with worker_session() as db:
            db.execute(...)
            db.commit()
    """
    session = _SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
