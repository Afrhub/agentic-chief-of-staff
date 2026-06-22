from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from pgvector.sqlalchemy import Vector
import os
from schema import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/chief_of_staff"
)

engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables and pgvector extension."""
    is_pg = engine.dialect.name == "postgresql"
    if is_pg:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")

    Base.metadata.create_all(bind=engine)

    # create_all() never ALTERs an existing table, so columns added after the
    # founders table already shipped need a one-shot migration. ponytail:
    # ADD COLUMN IF NOT EXISTS instead of standing up Alembic for two columns;
    # switch to Alembic if migrations start piling up.
    if is_pg:
        with engine.begin() as conn:
            conn.exec_driver_sql("ALTER TABLE founders ADD COLUMN IF NOT EXISTS password_hash VARCHAR")
            conn.exec_driver_sql("ALTER TABLE founders ADD COLUMN IF NOT EXISTS session_token VARCHAR")
            conn.exec_driver_sql("ALTER TABLE founders ADD COLUMN IF NOT EXISTS pack VARCHAR")
            conn.exec_driver_sql("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS deferred_until TIMESTAMP")
            conn.exec_driver_sql("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS options JSON")
    print("✓ Database initialized")


def get_db() -> Session:
    """Dependency for FastAPI to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
