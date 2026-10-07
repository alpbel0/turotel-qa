"""Single place for all settings; every value comes from the environment / `.env`."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _get(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required setting {name}; copy .env.example to .env")
    return value


@dataclass(frozen=True)
class Settings:
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    postgres_db: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    jev_api_key: str
    jev_base_url: str

    @property
    def postgres_url(self) -> str:
        return self._pg_url(self.postgres_db)

    def _pg_url(self, db: str) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{db}"
        )


@dataclass(frozen=True)
class TestSettings:
    """Test environment addresses. Separate keys (TEST_*): tests never read the development ones."""

    __test__ = False  # not a pytest class

    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_admin_db: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def load_settings(env_file: Path | None = None) -> Settings:
    """Read `.env` (if present) and return the settings; secrets stay out of the repo."""
    load_dotenv(env_file or PROJECT_ROOT / ".env")
    return Settings(
        postgres_host=_get("POSTGRES_HOST", "127.0.0.1"),
        postgres_port=int(_get("POSTGRES_PORT", "5432")),
        postgres_user=_get("POSTGRES_USER"),
        postgres_password=_get("POSTGRES_PASSWORD"),
        postgres_db=_get("POSTGRES_DB"),
        neo4j_uri=_get("NEO4J_URI", "bolt://127.0.0.1:7687"),
        neo4j_user=_get("NEO4J_USER"),
        neo4j_password=_get("NEO4J_PASSWORD"),
        jev_api_key=_get("JEV_API_KEY", ""),
        jev_base_url=_get("JEV_BASE_URL", ""),
    )


def load_test_settings(env_file: Path | None = None) -> TestSettings:
    """Read only the TEST_* keys; development addresses are never consulted."""
    load_dotenv(env_file or PROJECT_ROOT / ".env")
    return TestSettings(
        postgres_host=_get("TEST_POSTGRES_HOST", "127.0.0.1"),
        postgres_port=int(_get("TEST_POSTGRES_PORT", "5432")),
        postgres_user=_get("TEST_POSTGRES_USER"),
        postgres_password=_get("TEST_POSTGRES_PASSWORD"),
        postgres_db=_get("TEST_POSTGRES_DB", "turotel_test"),
        postgres_admin_db=_get("TEST_POSTGRES_ADMIN_DB", "postgres"),
        neo4j_uri=_get("TEST_NEO4J_URI", "bolt://127.0.0.1:7688"),
        neo4j_user=_get("TEST_NEO4J_USER", "neo4j"),
        neo4j_password=_get("TEST_NEO4J_PASSWORD"),
    )
