"""Taxonomy v1 data consistency (no database) and the idempotent loader (test database)."""

from sqlalchemy import text

from turotel.data import taxonomy as t


def _ids(rows):
    return [r[0] for r in rows]


def test_counts():
    assert len(t.MAIN_CATEGORIES) == 9
    assert len(t.SUBCATEGORIES) == 29
    assert len(t.DEPARTMENTS) == 11
    assert len(t.CAUSE_FACTORS) == 13
    assert len(t.ACTIONS) == 13


def test_ids_unique():
    for rows in (t.MAIN_CATEGORIES, t.SUBCATEGORIES, t.DEPARTMENTS, t.CAUSE_FACTORS, t.ACTIONS):
        assert len(set(_ids(rows))) == len(rows)


def test_every_subcategory_has_a_main_category():
    mains = set(_ids(t.MAIN_CATEGORIES))
    assert all(main in mains for _, main, _, _ in t.SUBCATEGORIES)
    assert {main for _, main, _, _ in t.SUBCATEGORIES} == mains


def test_mappings_reference_known_ids():
    subs, deps = set(_ids(t.SUBCATEGORIES)), set(_ids(t.DEPARTMENTS))
    assert set(t.SUBCATEGORY_DEPARTMENTS) == subs
    assert all(1 <= len(v) <= 3 and len(set(v)) == len(v) for v in t.SUBCATEGORY_DEPARTMENTS.values())
    assert all(d in deps for v in t.SUBCATEGORY_DEPARTMENTS.values() for d in v)
    causes, actions = set(_ids(t.CAUSE_FACTORS)), set(_ids(t.ACTIONS))
    assert set(t.ACTION_CAUSES) == actions
    assert all(c in causes for v in t.ACTION_CAUSES.values() for c in v)
    # every cause factor leads to at least one action
    assert {c for v in t.ACTION_CAUSES.values() for c in v} == causes


def _count(session, table):
    return session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_load_and_rerun_is_noop(db_session):
    first = t.load_taxonomy(db_session)
    assert first.changed
    expected = {"main_categories": 9, "subcategories": 29, "departments": 11, "cause_factors": 13, "actions": 13}
    for table, n in expected.items():
        assert _count(db_session, table) == n
    assert _count(db_session, "schema_versions") == 1
    assert _count(db_session, "subcategory_departments") == sum(len(v) for v in t.SUBCATEGORY_DEPARTMENTS.values())
    assert _count(db_session, "cause_actions") == sum(len(v) for v in t.ACTION_CAUSES.values())
    assert db_session.execute(text("SELECT count(*) FROM actions WHERE introduced_in <> 1")).scalar_one() == 0

    second = t.load_taxonomy(db_session)
    assert not second.changed
    assert _count(db_session, "subcategories") == 29
