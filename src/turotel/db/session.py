"""Engine and session helpers. No DDL here: the schema comes only from Alembic migrations."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from turotel.config import load_settings


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or load_settings().postgres_url, pool_pre_ping=True)


def make_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(engine or make_engine(), expire_on_commit=False)
