"""validate_run: a valid run passes; one deliberately broken run per rule is rejected with that rule's name."""

import pytest
from sqlalchemy import text

from turotel import validation as v
from turotel.data.taxonomy import load_taxonomy
from turotel.db.models import Review


def _one(session, sql, **params):
    return session.execute(text(sql), params).scalar_one()


def _ids(session, table):
    return [r[0] for r in session.execute(text(f"SELECT id FROM {table} ORDER BY id"))]


class RunBuilder:
    """Builds a small valid run: r1 done (1 severity-1 and 1 severity-3 complaint), r2 skip, r3 done, nothing negative."""

    def __init__(self, session, kind="jev"):
        self.s = session
        load_taxonomy(session)
        self.subs = _ids(session, "subcategories")
        self.dep = _ids(session, "departments")[0]
        self.cause = _ids(session, "cause_factors")[0]
        self.action = _ids(session, "actions")[0]
        session.add_all(
            Review(review_id=f"r{i}", source="humir", text=f"t{i}", word_len=1, humir_class="negative", split="train")
            for i in (1, 2, 3)
        )
        session.flush()
        self.run_id = _one(
            session,
            "INSERT INTO annotation_runs (kind, annotator_or_model, schema_version) "
            "VALUES (CAST(:k AS run_kind), 'test', 1) RETURNING run_id",
            k=kind,
        )
        self.kind = kind
        self.annotation("r1", "done")
        self.annotation("r2", "skip")
        self.annotation("r3", "done")
        for review in ("r1", "r3"):
            for sub in self.subs:
                self.label(review, sub, "not_mentioned")
        self.set_label("r1", self.subs[0], "negative")
        self.set_label("r1", self.subs[1], "negative")
        low = "out_of_scope" if kind != "model" else None
        self.c_low = self.complaint("r1", self.subs[0], severity=1, cause_status=low, action_status=low)
        if kind == "model":
            self.c_high = self.complaint("r1", self.subs[1], severity=3)
        else:
            self.c_high = self.complaint(
                "r1", self.subs[1], severity=3, cause_status="selected", cause_factor_id=self.cause,
                action_status="recommended",
            )
            self.s.execute(
                text("INSERT INTO complaint_actions VALUES (:c, :a)"), {"c": self.c_high, "a": self.action}
            )

    def annotation(self, review, status):
        self.s.execute(
            text("INSERT INTO review_annotations (run_id, review_id, status) VALUES (:r, :v, CAST(:s AS annotation_status))"),
            {"r": self.run_id, "v": review, "s": status},
        )

    def label(self, review, sub, status):
        self.s.execute(
            text("INSERT INTO aspect_labels (run_id, review_id, subcategory_id, status) "
                 "VALUES (:r, :v, :u, CAST(:s AS sentiment))"),
            {"r": self.run_id, "v": review, "u": sub, "s": status},
        )

    def set_label(self, review, sub, status):
        self.s.execute(
            text("UPDATE aspect_labels SET status = CAST(:s AS sentiment) "
                 "WHERE run_id = :r AND review_id = :v AND subcategory_id = :u"),
            {"r": self.run_id, "v": review, "u": sub, "s": status},
        )

    def complaint(self, review, sub, severity, cause_status=None, cause_factor_id=None, action_status=None):
        return _one(
            self.s,
            "INSERT INTO complaints (run_id, review_id, subcategory_id, department_id, severity, cause_status, "
            "cause_factor_id, action_status) VALUES (:r, :v, :u, :d, :sev, CAST(:cs AS cause_status), :cf, "
            "CAST(:as_ AS action_status)) RETURNING complaint_id",
            r=self.run_id, v=review, u=sub, d=self.dep, sev=severity, cs=cause_status, cf=cause_factor_id,
            as_=action_status,
        )

    def exec(self, sql, **params):
        self.s.execute(text(sql), {"r": self.run_id, **params})

    def violations(self):
        return v.validate_run(self.s, self.run_id)


@pytest.fixture
def run(db_session):
    return RunBuilder(db_session)


def _validated_at(session, run_id):
    return _one(session, "SELECT validated_at FROM annotation_runs WHERE run_id = :r", r=run_id)


@pytest.mark.parametrize("kind", ["jev", "human", "model"])
def test_valid_run_gets_validated_at(db_session, kind):
    builder = RunBuilder(db_session, kind)
    assert _validated_at(db_session, builder.run_id) is None
    report = builder.violations()
    assert report.ok, str(report)
    assert _validated_at(db_session, builder.run_id) is not None


def test_unknown_run(db_session):
    with pytest.raises(ValueError):
        v.validate_run(db_session, 999999)


def test_failure_clears_earlier_validated_at(db_session, run):
    assert run.violations().ok
    run.exec("UPDATE aspect_labels SET status = 'positive' WHERE run_id = :r AND review_id = 'r1' "
             "AND subcategory_id = :u", u=run.subs[0])
    assert not run.violations().ok
    assert _validated_at(db_session, run.run_id) is None


def test_clear_validation(db_session, run):
    assert run.violations().ok
    v.clear_validation(db_session, run.run_id)
    assert _validated_at(db_session, run.run_id) is None
    with pytest.raises(ValueError):
        v.clear_validation(db_session, 999999)


def test_report_names_rule_and_row(run):
    run.exec("DELETE FROM complaint_actions")
    report = run.violations()
    assert [str(x) for x in report.violations] == [
        f"R4_action_count [complaint:{run.c_high}]: recommended with 0 action(s), expected 1..1"
    ]


# ------------------------------------------------------------------ R1


def test_r1_complaint_on_non_negative_label(run):
    run.set_label("r1", run.subs[0], "positive")
    assert "R1_complaint_label" in run.violations().rules()


def test_r1_negative_label_without_complaint(run):
    run.set_label("r3", run.subs[2], "negative")
    report = run.violations()
    assert report.rules() == {"R1_complaint_label"}
    assert report.violations[0].key == f"label:r3/{run.subs[2]}"


# ------------------------------------------------------------------ R2


def test_r2_done_review_missing_labels(run):
    run.exec("DELETE FROM aspect_labels WHERE run_id = :r AND review_id = 'r3' AND subcategory_id = :u", u=run.subs[5])
    report = run.violations()
    assert report.rules() == {"R2_label_set"}
    assert run.subs[5] in report.violations[0].detail


def test_r2_skip_review_with_labels(run):
    run.label("r2", run.subs[0], "not_mentioned")
    assert run.violations().rules() == {"R2_label_set"}


def test_r2_labels_without_review_annotation(run):
    run.exec("DELETE FROM review_annotations WHERE run_id = :r AND review_id = 'r3'")
    assert run.violations().rules() == {"R2_label_set"}


def test_r2_does_not_require_labels_retired_in_the_schema_version(db_session, run):
    # Subcategory retired before the run's version: not part of the required set, and R6 rejects labels on it.
    db_session.execute(text("INSERT INTO schema_versions (version, note) VALUES (2, 'retire one')"))
    db_session.execute(text("UPDATE subcategories SET retired_in = 2 WHERE id = :u"), {"u": run.subs[7]})
    db_session.execute(text("UPDATE annotation_runs SET schema_version = 2 WHERE run_id = :r"), {"r": run.run_id})
    report = run.violations()
    assert report.rules() == {"R6_taxonomy_ids"}


# ------------------------------------------------------------------ R3


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE complaints SET cause_status = 'insufficient_evidence' WHERE complaint_id = :c",  # severity 1 low
        "UPDATE complaints SET action_status = 'not_needed' WHERE complaint_id = :c",
    ],
)
def test_r3_severity_1_must_be_out_of_scope(run, sql):
    run.exec(sql, c=run.c_low)
    assert "R3_severity_status" in run.violations().rules()


def test_r3_severity_2_cannot_be_out_of_scope(run):
    run.exec("UPDATE complaints SET severity = 2, action_status = 'out_of_scope' WHERE complaint_id = :c", c=run.c_high)
    assert "R3_severity_status" in run.violations().rules()


def test_r3_severity_2_cause_out_of_scope(run):
    run.exec("UPDATE complaints SET cause_status = 'out_of_scope', cause_factor_id = NULL WHERE complaint_id = :c",
             c=run.c_high)
    assert "R3_severity_status" in run.violations().rules()


def test_r3_not_checked_for_model_runs(db_session):
    builder = RunBuilder(db_session, "model")
    builder.exec("UPDATE complaints SET severity = 1 WHERE complaint_id = :c", c=builder.c_high)
    assert builder.violations().ok


# ------------------------------------------------------------------ R4


def test_r4_jev_recommends_exactly_one(run):
    other = _ids(run.s, "actions")[1]
    run.exec("INSERT INTO complaint_actions VALUES (:c, :a)", c=run.c_high, a=other)
    assert run.violations().rules() == {"R4_action_count"}


def test_r4_human_allows_up_to_three_but_not_four(db_session):
    builder = RunBuilder(db_session, "human")
    actions = _ids(db_session, "actions")
    for a in actions[1:3]:
        builder.exec("INSERT INTO complaint_actions VALUES (:c, :a)", c=builder.c_high, a=a)
    assert builder.violations().ok
    builder.exec("INSERT INTO complaint_actions VALUES (:c, :a)", c=builder.c_high, a=actions[3])
    assert builder.violations().rules() == {"R4_action_count"}


def test_r4_action_without_recommended(run):
    run.exec("INSERT INTO complaint_actions VALUES (:c, :a)", c=run.c_low, a=run.action)
    assert "R4_action_count" in run.violations().rules()


def test_r4_recommended_with_no_action(run):
    run.exec("DELETE FROM complaint_actions")
    assert run.violations().rules() == {"R4_action_count"}


# ------------------------------------------------------------------ R5


def test_r5_human_status_must_not_be_null(db_session):
    builder = RunBuilder(db_session, "human")
    builder.exec("UPDATE complaints SET action_status = NULL WHERE complaint_id = :c", c=builder.c_low)
    assert "R5_kind_nulls" in builder.violations().rules()


def test_r5_model_row_must_not_have_cause_or_action(db_session):
    builder = RunBuilder(db_session, "model")
    builder.exec("UPDATE complaints SET action_status = 'not_needed' WHERE complaint_id = :c", c=builder.c_high)
    assert builder.violations().rules() == {"R5_kind_nulls"}


def test_r5_model_row_must_not_have_actions(db_session):
    builder = RunBuilder(db_session, "model")
    builder.exec("INSERT INTO complaint_actions VALUES (:c, :a)", c=builder.c_high, a=builder.action)
    assert builder.violations().rules() == {"R5_kind_nulls"}


# ------------------------------------------------------------------ R6


def test_r6_department_not_valid_in_schema_version(db_session, run):
    db_session.execute(text("INSERT INTO schema_versions (version, note) VALUES (2, 'v2')"))
    db_session.execute(text("UPDATE departments SET introduced_in = 2 WHERE id = :d"), {"d": run.dep})
    report = run.violations()
    assert report.rules() == {"R6_taxonomy_ids"}
    assert "department" in report.violations[0].detail


def test_r6_cause_and_action_not_valid_in_schema_version(db_session, run):
    db_session.execute(text("INSERT INTO schema_versions (version, note) VALUES (2, 'v2')"))
    db_session.execute(text("UPDATE cause_factors SET introduced_in = 2 WHERE id = :c"), {"c": run.cause})
    db_session.execute(text("UPDATE actions SET introduced_in = 2 WHERE id = :a"), {"a": run.action})
    report = run.violations()
    assert report.rules() == {"R6_taxonomy_ids"}
    assert len(report.violations) == 2


def test_r6_duplicate_group_spans_two_splits(db_session, run):
    db_session.execute(text("UPDATE reviews SET duplicate_group_id = 'dup-1' WHERE review_id IN ('r1', 'r2')"))
    db_session.execute(text("UPDATE reviews SET split = 'silver_val' WHERE review_id = 'r2'"))
    report = run.violations()
    assert report.rules() == {"R6_duplicate_group"}
    assert report.violations[0].key == "group:dup-1"
