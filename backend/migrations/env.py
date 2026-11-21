"""Environnement Alembic de Dari : migrations du kit (branche auth_kit) + celles de Dari (branche dari).

    alembic upgrade heads                      # applique les deux branches
    alembic revision --autogenerate --head dari@head -m "message"
    alembic check                              # échoue si les modèles ont changé sans migration

URL de la base : -x database_url=... ou variable DATABASE_URL (ou fichier .env).
sslmode PostgreSQL : DATABASE_SSLMODE (défaut "require", "disable" pour le Postgres de Docker Compose).
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

import app.models  # noqa: F401  (enregistre les tables de Dari dans la metadata)
from auth_kit.db import create_engine_from_url
from auth_kit.models import Base

config = context.config
if config.config_file_name is not None:
    # Ne pas désactiver les loggers déjà créés (application, tests)
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    url = context.get_x_argument(as_dictionary=True).get("database_url")
    if not url:
        try:
            from dotenv import load_dotenv
            load_dotenv(".env")
        except ImportError:
            pass
        url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("URL de base manquante : -x database_url=... ou variable DATABASE_URL")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(), target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"}, render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine_from_url(
        _database_url(), sslmode=os.environ.get("DATABASE_SSLMODE", "require"), poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True, compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
