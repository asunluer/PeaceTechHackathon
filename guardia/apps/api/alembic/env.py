"""Alembic environment using the same database configuration as the API."""

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.infrastructure.database import database_url
from app.infrastructure.models import Base

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(get_settings()).render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(get_settings()), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
