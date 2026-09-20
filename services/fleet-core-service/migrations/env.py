from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.core.database import Base, DATABASE_URL, POSTGRES_SCHEMA
from app.models import Vehicle, Driver, Trip, Expense, MaintenanceRecord  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    # alembic_version es la propia tabla de control de Alembic: nunca debe
    # compararse contra el metadata de los modelos.
    if type_ == "table" and name == "alembic_version":
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        version_table_schema=POSTGRES_SCHEMA,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # NOTA: deliberadamente NO se usa include_schemas=True. Con él,
        # Alembic reflexiona TODOS los esquemas visibles en la misma
        # instancia de PostgreSQL (auth, fleet, reporting) y normaliza el
        # esquema "por defecto" (el de search_path) a None solo del lado
        # reflejado, mientras que nuestro metadata declara schema=POSTGRES_SCHEMA
        # explícito del lado del modelo — el mismatch resultante hace que
        # autogenerate proponga borrar las tablas propias. Sin
        # include_schemas, Alembic solo inspecciona el esquema por defecto
        # de la conexión (fijado aquí vía search_path), que es exactamente
        # el esquema de este servicio, sin ambigüedad.
        connection.execute(text(f"SET search_path TO {POSTGRES_SCHEMA}"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=POSTGRES_SCHEMA,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
