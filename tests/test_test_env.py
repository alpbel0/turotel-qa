"""The test environment refuses unsafe targets and never falls back to development addresses."""

import dataclasses

import psycopg
import pytest
from sqlalchemy import text

from turotel.config import TestSettings
from turotel.db.testing import (
    UnsafeTestTargetError,
    assert_test_neo4j_uri,
    assert_test_postgres_db,
    ensure_test_database,
    make_test_engine,
)


@pytest.mark.parametrize("name", ["turotel", "turotel_dev", "turotel_test_old", "postgres", ""])
def test_postgres_name_without_test_suffix_is_refused(name):
    with pytest.raises(UnsafeTestTargetError):
        assert_test_postgres_db(name)


def test_postgres_test_suffix_is_accepted():
    assert_test_postgres_db("turotel_test")


@pytest.mark.parametrize(
    "uri",
    ["bolt://127.0.0.1:7687", "bolt://127.0.0.1:7474", "bolt://example.com:7688", "bolt://10.0.0.5:7688", "bolt://127.0.0.1"],
)
def test_neo4j_other_than_7688_local_is_refused(uri):
    with pytest.raises(UnsafeTestTargetError):
        assert_test_neo4j_uri(uri)


def test_neo4j_test_port_is_accepted():
    assert_test_neo4j_uri("bolt://127.0.0.1:7688")


def test_setup_refuses_development_database_name(test_settings: TestSettings):
    wrong = dataclasses.replace(test_settings, postgres_db="turotel")
    with pytest.raises(UnsafeTestTargetError):
        ensure_test_database(wrong)
    with pytest.raises(UnsafeTestTargetError):
        make_test_engine(wrong)


def test_wrong_postgres_address_fails_immediately(test_settings: TestSettings):
    wrong = dataclasses.replace(test_settings, postgres_port=5999)
    with pytest.raises(psycopg.OperationalError):
        ensure_test_database(wrong)


def test_engine_points_at_a_test_database(test_engine):
    with test_engine.connect() as connection:
        assert connection.execute(text("SELECT current_database()")).scalar_one().endswith("_test")


def test_test_neo4j_is_reachable(neo4j_driver):
    with neo4j_driver.session() as session:
        assert session.run("RETURN 1 AS one").single()["one"] == 1
