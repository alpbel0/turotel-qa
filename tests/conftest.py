"""Shared fixtures. Everything here targets the test environment only (TEST_* settings)."""

from collections.abc import Iterator

import pytest
from neo4j import Driver, GraphDatabase
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from turotel.config import TestSettings, load_test_settings
from turotel.db.testing import assert_test_neo4j_uri, assert_test_settings, ensure_test_database, make_test_engine


@pytest.fixture(scope="session")
def test_settings() -> TestSettings:
    settings = load_test_settings()
    assert_test_settings(settings)
    return settings


@pytest.fixture(scope="session")
def test_engine(test_settings: TestSettings) -> Iterator[Engine]:
    ensure_test_database(test_settings)
    engine = make_test_engine(test_settings)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    """Session whose work is rolled back after each test (commits become savepoint releases)."""
    connection = test_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture(scope="session")
def neo4j_driver(test_settings: TestSettings) -> Iterator[Driver]:
    assert_test_neo4j_uri(test_settings.neo4j_uri)
    driver = GraphDatabase.driver(test_settings.neo4j_uri, auth=(test_settings.neo4j_user, test_settings.neo4j_password))
    driver.verify_connectivity()
    yield driver
    driver.close()
