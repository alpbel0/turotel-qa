"""Constraints and view behaviour of the migration-defined schema, on the test database."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from turotel.db.testing import run_migrations
from turotel.db.views import RunNotUsableError, read_masked_view, read_reference_view, resolve_merged_id


def _seed(session):
    for stmt in [
        "INSERT INTO schema_versions VALUES (1, now(), 'v1')",
        "INSERT INTO main_categories VALUES ('m', 'M', NULL, 1, NULL, NULL)",
        "INSERT INTO subcategories VALUES ('s1','m','S1',NULL,1,NULL,NULL), ('s2','m','S2',NULL,1,NULL,NULL)",
        "INSERT INTO departments VALUES ('d', 'D', NULL, 1, NULL, NULL)",
        "INSERT INTO cause_factors VALUES ('c', 'g', 'C', NULL, 1, NULL, NULL)",
        "INSERT INTO actions VALUES ('a', 'A', NULL, 1, NULL, NULL)",
        "INSERT INTO reviews (review_id, source, text, word_len, split) VALUES "
        "('r1','humir','bir iki uc',3,'train'), ('r2','humir','dort',1,'train')",
    ]:
        session.execute(text(stmt))
    return session.execute(
        text("INSERT INTO annotation_runs (kind, annotator_or_model, schema_version) VALUES ('jev','jev',1) RETURNING run_id")
    ).scalar_one()


def _label(session, run_id, review, sub, status, conf):
    session.execute(
        text("INSERT INTO aspect_labels VALUES (:r, :rv, :s, :st, :c)"),
        {"r": run_id, "rv": review, "s": sub, "st": status, "c": conf},
    )


def _complaint(session, run_id, review, sub, severity, cause_status=None, cause=None):
    session.execute(
        text(
            "INSERT INTO complaints (run_id, review_id, subcategory_id, severity, department_id, cause_status,"
            " cause_factor_id, cause_conf, action_status, action_conf) VALUES (:r, :rv, :s, :sev, 'd', :cs, :c, 0.8,"
            " 'recommended', 0.8)"
        ),
        {"r": run_id, "rv": review, "s": sub, "sev": severity, "cs": cause_status, "c": cause},
    )


def test_migrations_are_idempotent(test_engine):
    run_migrations(test_engine.url.render_as_string(hide_password=False))  # second run changes nothing
    with test_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 1


def test_severity_1_with_cause_is_rejected(db_session):
    run_id = _seed(db_session)
    _label(db_session, run_id, "r1", "s1", "negative", 0.9)
    with pytest.raises(IntegrityError, match="ck_complaints_severity1_no_cause"):
        _complaint(db_session, run_id, "r1", "s1", 1, "selected", "c")


def test_selected_requires_factor_and_vice_versa(db_session):
    run_id = _seed(db_session)
    _label(db_session, run_id, "r1", "s1", "negative", 0.9)
    with pytest.raises(IntegrityError, match="ck_complaints_cause_selected_iff_factor"):
        _complaint(db_session, run_id, "r1", "s1", 2, "selected", None)


def test_severity_out_of_range_is_rejected(db_session):
    run_id = _seed(db_session)
    _label(db_session, run_id, "r1", "s1", "negative", 0.9)
    with pytest.raises(IntegrityError, match="ck_complaints_severity_range"):
        _complaint(db_session, run_id, "r1", "s1", 5)


def test_complaint_needs_an_aspect_label(db_session):
    run_id = _seed(db_session)
    with pytest.raises(IntegrityError, match="fk_complaints_aspect_label"):
        _complaint(db_session, run_id, "r1", "s2", 2)


def test_real_and_mabsa_reviews_cannot_be_publishable(db_session):
    _seed(db_session)
    with pytest.raises(IntegrityError, match="ck_reviews_external_not_publishable"):
        db_session.execute(
            text("INSERT INTO reviews (review_id, source, text, word_len, publishable) VALUES ('x','real','t',1,true)")
        )


def test_masked_view_drops_low_confidence_label_and_its_complaint(db_session):
    run_id = _seed(db_session)
    _label(db_session, run_id, "r1", "s1", "negative", 0.4)  # below threshold
    _label(db_session, run_id, "r1", "s2", "negative", 0.9)
    _label(db_session, run_id, "r2", "s1", "positive", 0.9)
    _complaint(db_session, run_id, "r1", "s1", 2, "selected", "c")
    _complaint(db_session, run_id, "r1", "s2", 2, "selected", "c")
    db_session.execute(text("INSERT INTO complaint_actions SELECT complaint_id, 'a' FROM complaints"))
    db_session.execute(text(f"INSERT INTO confidence_thresholds (run_id, family, threshold) VALUES ({run_id}, 'aspect', 0.5)"))

    rows = {
        (r["review_id"], r["subcategory_id"]): r
        for r in db_session.execute(text("SELECT * FROM v_labels_masked WHERE run_id = :r"), {"r": run_id}).mappings()
    }
    assert rows[("r1", "s1")]["status"] is None and rows[("r1", "s1")]["complaint_id"] is None
    assert rows[("r1", "s2")]["status"] == "negative" and rows[("r1", "s2")]["action_ids"] == ["a"]
    assert rows[("r2", "s1")]["status"] == "positive"

    graph = db_session.execute(text("SELECT subcategory_id FROM v_graph_train WHERE run_id = :r"), {"r": run_id}).all()
    assert [g[0] for g in graph] == ["s2"]


def test_no_threshold_or_null_confidence_means_no_mask(db_session):
    run_id = _seed(db_session)
    _label(db_session, run_id, "r1", "s1", "negative", None)
    status = db_session.execute(text("SELECT status FROM v_labels_masked WHERE run_id = :r"), {"r": run_id}).scalar_one()
    assert status == "negative"


def test_view_queries_require_a_usable_run(db_session):
    run_id = _seed(db_session)  # a Jev run that is neither frozen nor validated
    with pytest.raises(RunNotUsableError):
        read_masked_view(db_session, "v_train_export", run_id)
    with pytest.raises(RunNotUsableError):
        read_reference_view(db_session, "v_gold_dev_eval", run_id)  # not a human run
    db_session.execute(text(f"UPDATE annotation_runs SET is_frozen = true, validated_at = now() WHERE run_id = {run_id}"))
    assert len(read_masked_view(db_session, "v_train_export", run_id)) == 0


def test_resolve_merged_id_follows_the_chain(db_session):
    _seed(db_session)
    db_session.execute(text("INSERT INTO subcategories VALUES ('old','m','Old',NULL,1,NULL,'s1')"))
    assert resolve_merged_id(db_session, "subcategories", "old") == "s1"
    assert resolve_merged_id(db_session, "subcategories", "s2") == "s2"
