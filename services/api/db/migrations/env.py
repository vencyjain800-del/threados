from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from app.db.base import Base
import app.models  # noqa: F401 — ensure all models are registered

# Import settings so that .env is loaded via pydantic-settings.
# os.environ.get() cannot be used here because pydantic-settings reads .env
# into the Settings object, not into os.environ.
from app.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Use the migrate URL (table-owner role) so the migration can CREATE/ALTER tables.
config.set_main_option("sqlalchemy.url", settings.database_migrate_url)


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Alembic is a CLI tool — it does not need an async engine.
    # Using the synchronous psycopg driver (postgresql+psycopg://) avoids the
    # ProactorEventLoop incompatibility on Windows and works identically on all
    # platforms. The application runtime uses async; migrations do not need to.
    connectable = create_engine(
        settings.database_migrate_url,
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
