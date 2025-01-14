import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None


def get_schema_name():
    """Get the schema name from environment or config."""
    return os.environ.get("R2R_PROJECT_NAME", "r2r_default")


def include_object(object, name, type_, reflected, compare_to):
    """Filter objects based on schema."""
    # Include only objects in our schema
    if hasattr(object, "schema"):
        return object.schema == get_schema_name()
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    schema_name = get_schema_name()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
        version_table_schema=schema_name,
        version_table=f"{schema_name}_alembic_version",
    )

    with context.begin_transaction():
        # Ensure schema exists
        context.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    schema_name = get_schema_name()

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Ensure schema exists
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,
            version_table_schema=schema_name,
            version_table=f"{schema_name}_alembic_version",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
