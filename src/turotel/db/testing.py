"""Idempotent test database setup and the guards that keep tests away from development data.

One command (starts the test Neo4j, sets up the test database, runs pytest):

    uv run python -m turotel.db.testing [pytest args]
"""

import subprocess
import sys
from urllib.parse import urlparse

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import Engine, create_engine, text

from turotel.config import PROJECT_ROOT, TestSettings, load_test_settings

TEST_NEO4J_PORT = 7688
_LOCAL_HOSTS = {"127.0.0.1", "localhost"}


class UnsafeTestTargetError(RuntimeError):
    """A test tried to touch something that is not a test database."""


def assert_test_postgres_db(name: str) -> None:
    if not name.endswith("_test"):
        raise UnsafeTestTargetError(f"refusing to use Postgres database {name!r}: name must end with '_test'")


def assert_test_neo4j_uri(uri: str) -> None:
    parsed = urlparse(uri)
    if parsed.port != TEST_NEO4J_PORT or parsed.hostname not in _LOCAL_HOSTS:
        raise UnsafeTestTargetError(
            f"refusing to use Neo4j at {uri!r}: tests may only use 127.0.0.1:{TEST_NEO4J_PORT}"
        )


def assert_test_settings(settings: TestSettings) -> None:
    assert_test_postgres_db(settings.postgres_db)
    assert_test_neo4j_uri(settings.neo4j_uri)


def run_migrations(url: str) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["url"] = url
    command.upgrade(config, "head")


def ensure_test_database(settings: TestSettings) -> None:
    """Create the test database if missing (outside a transaction), then `alembic upgrade head`."""
    assert_test_postgres_db(settings.postgres_db)
    with psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_admin_db,
        autocommit=True,
        connect_timeout=5,
    ) as admin:
        exists = admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.postgres_db,)).fetchone()
        if not exists:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.postgres_db)))
    run_migrations(settings.postgres_url)


def make_test_engine(settings: TestSettings) -> Engine:
    """Engine for the test database; verifies the actual database name after connecting."""
    assert_test_postgres_db(settings.postgres_db)
    engine = create_engine(settings.postgres_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        actual = connection.execute(text("SELECT current_database()")).scalar_one()
    try:
        assert_test_postgres_db(actual)
    except UnsafeTestTargetError:
        engine.dispose()
        raise
    return engine


def main() -> int:
    settings = load_test_settings()
    assert_test_settings(settings)
    subprocess.run(
        ["docker", "compose", "--profile", "test", "up", "-d", "--wait", "postgres", "neo4j-test"],
        cwd=PROJECT_ROOT,
        check=True,
    )
    ensure_test_database(settings)
    return subprocess.call([sys.executable, "-m", "pytest", *sys.argv[1:]], cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
