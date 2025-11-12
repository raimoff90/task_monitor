import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from backend.models import Base

# Абсолютный путь к корню проекта (где находится run.py)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

print(f"✅ sys.path configured, BASE_DIR={BASE_DIR}")

# Путь к БД
DATABASE_URL = "sqlite:///./data.db"

# Alembic Config object
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные ORM моделей
target_metadata = Base.metadata


# --- Игнорирование служебных таблиц и лишних сравнений ---
def include_object(object, name, type_, reflected, compare_to):
    # Не трогаем служебную таблицу SQLite
    if type_ == "table" and name == "sqlite_sequence":
        return False
    return True


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=False,
        compare_nullable=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        {"sqlalchemy.url": DATABASE_URL},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=False,
            compare_nullable=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()