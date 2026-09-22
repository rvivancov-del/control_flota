"""Conexión a PostgreSQL para fleet-core-service: motor SQLAlchemy fijado al
esquema "fleet" y la dependencia de sesión que usan los routers."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

POSTGRES_USER = os.getenv("POSTGRES_USER", "flota")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "changeme_local_only")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "flota_db")
POSTGRES_SCHEMA = os.getenv("POSTGRES_SCHEMA", "fleet")

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# search_path fija el esquema "fleet" como destino por defecto de las
# consultas de este servicio, sin tocar los esquemas de los otros servicios.
# timezone=UTC hace determinista qué día es una fecha y hora (los filtros por rango de fechas cuentan
# días UTC, ver app/core/dates.py) y no depende de cómo esté configurado el servidor.
CONNECTION_OPTIONS = f"-csearch_path={POSTGRES_SCHEMA} -ctimezone=UTC"
engine = create_engine(DATABASE_URL, connect_args={"options": CONNECTION_OPTIONS}, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Metadata SIN esquema explícito a propósito: junto con el search_path fijado
# arriba y sin include_schemas=True en Alembic (ver migrations/env.py), esto
# hace que Alembic compare de forma consistente en ambos lados (reflejado y
# declarado) contra el esquema por defecto de la conexión — evitando que
# proponga borrar las propias tablas por una discrepancia de normalización.
Base = declarative_base()


def get_db():
    """Dependencia de FastAPI: entrega una sesión por request y la cierra al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
