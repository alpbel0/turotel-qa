"""Neo4j constraints, on the separate test Neo4j (port 7688) only."""

import pytest
from neo4j.exceptions import ConstraintError

from turotel.recommend.graph_schema import UNIQUE_KEYS, apply_constraints, constraint_name


@pytest.fixture
def clean_graph(neo4j_driver):
    """Empty test graph with no constraints (the driver fixture already guards the 7688 target)."""

    def wipe():
        with neo4j_driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
            for row in session.run("SHOW CONSTRAINTS YIELD name").data():
                session.run(f"DROP CONSTRAINT `{row['name']}`").consume()

    wipe()
    yield neo4j_driver
    wipe()


def _constraints(driver):
    with driver.session() as session:
        return {r["name"]: r for r in session.run("SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties").data()}


def test_constraints_are_created_on_an_empty_graph(clean_graph):
    apply_constraints(clean_graph)
    found = _constraints(clean_graph)
    assert set(found) == {constraint_name(label, prop) for label, prop in UNIQUE_KEYS}
    for label, prop in UNIQUE_KEYS:
        row = found[constraint_name(label, prop)]
        assert row["type"] == "UNIQUENESS" and row["labelsOrTypes"] == [label] and row["properties"] == [prop]


def test_second_run_changes_nothing(clean_graph):
    apply_constraints(clean_graph)
    before = _constraints(clean_graph)
    apply_constraints(clean_graph)
    assert _constraints(clean_graph) == before


@pytest.mark.parametrize("label,prop", UNIQUE_KEYS)
def test_duplicate_id_is_rejected(clean_graph, label, prop):
    apply_constraints(clean_graph)
    with clean_graph.session() as session:
        session.run(f"CREATE (:{label} {{{prop}: 'x1'}})").consume()
        with pytest.raises(ConstraintError):
            session.run(f"CREATE (:{label} {{{prop}: 'x1'}})").consume()
        session.run(f"CREATE (:{label} {{{prop}: 'x2'}})").consume()  # a different id is fine
