"""Evaluation core: hand-computed metrics on a tiny example, seeded bootstrap, and the database round trip."""

import math

import numpy as np
import pytest
from sqlalchemy import text

from turotel.data.taxonomy import load_taxonomy
from turotel.db.models import Review
from turotel.evaluation import compare_labels, evaluate_labels, evaluate_recommendations
from turotel.evaluation.bootstrap import bootstrap_intervals, paired_bootstrap
from turotel.evaluation.loading import EvaluationDataError, build_frame
from turotel.evaluation.metrics import EvalFrame, RecQueries, compute_metrics, quadratic_weighted_kappa

NM, POS, NEG, NEU = 0, 1, 2, 3


def small_frame() -> EvalFrame:
    """4 reviews x 3 subcategories (A, B in main M1; C in main M2); every expected value below is by hand."""
    ref = np.array([[NEG, NM, POS], [NM, POS, NM], [NEG, NEG, NM], [NM, NM, NEU]], dtype=np.int8)
    pred = np.array([[NEG, POS, POS], [NM, POS, NEU], [POS, NEG, NM], [NM, NM, NM]], dtype=np.int8)
    ref_dept = np.full((4, 3), -1, dtype=np.int16)
    pred_dept = np.full((4, 3), -1, dtype=np.int16)
    ref_dept[0, 0], ref_dept[2, 0], ref_dept[2, 1] = 0, 0, 1  # X, X, Y
    pred_dept[0, 0], pred_dept[2, 1] = 0, 0  # X, X
    ref_sev = np.zeros((4, 3), dtype=np.int8)
    pred_sev = np.zeros((4, 3), dtype=np.int8)
    ref_sev[0, 0], ref_sev[2, 0], ref_sev[2, 1] = 2, 3, 4
    pred_sev[0, 0], pred_sev[2, 1] = 3, 4
    return EvalFrame(
        reviews=["r0", "r1", "r2", "r3"], subcategories=["A", "B", "C"], mains=["M1", "M2"],
        main_of=np.array([0, 0, 1]), departments=["X", "Y"], ref_status=ref, pred_status=pred,
        ref_dept=ref_dept, pred_dept=pred_dept, ref_sev=ref_sev, pred_sev=pred_sev,
    )


def value(values, metric, scope):
    return values[(metric, scope)][0]


def test_hand_computed_metrics():
    v = compute_metrics(small_frame(), min_support=1)
    # topic: A tp2; B tp2 fp1; C tp1 fp1 fn1
    assert value(v, "topic_f1", "subcategory:A") == pytest.approx(1.0)
    assert value(v, "topic_f1", "subcategory:B") == pytest.approx(0.8)
    assert value(v, "topic_f1", "subcategory:C") == pytest.approx(0.5)
    assert value(v, "topic_f1_micro", "subcategory") == pytest.approx(10 / 13)
    assert value(v, "topic_f1_macro", "subcategory") == pytest.approx((1 + 0.8 + 0.5) / 3)
    # topic at main category level (a review is positive when any subcategory is)
    assert value(v, "topic_f1_micro", "main_category") == pytest.approx(0.8)
    assert value(v, "topic_f1_macro", "main_category") == pytest.approx(0.75)
    # complaint: A tp1 fn1; B tp1; C has no support at all
    assert value(v, "complaint_f1", "subcategory:A") == pytest.approx(2 / 3)
    assert value(v, "complaint_f1", "subcategory:B") == pytest.approx(1.0)
    assert math.isnan(value(v, "complaint_f1", "subcategory:C"))
    assert value(v, "complaint_f1_micro", "subcategory") == pytest.approx(0.8)
    assert value(v, "complaint_f1_macro", "subcategory") == pytest.approx((2 / 3 + 1) / 2)
    # sentiment on the 6 mentioned cells: positive 0.8, negative 0.8, neutral 0
    assert value(v, "sentiment_f1", "class:positive") == pytest.approx(0.8)
    assert value(v, "sentiment_f1", "class:negative") == pytest.approx(0.8)
    assert value(v, "sentiment_f1", "class:neutral") == pytest.approx(0.0)
    assert value(v, "sentiment_f1_macro", "subcategory") == pytest.approx(0.8 * 2 / 3)
    # department on the 2 cells with a department on both sides: X/X right, Y->X wrong
    assert value(v, "department_f1", "department:X") == pytest.approx(2 / 3)
    assert value(v, "department_f1", "department:Y") == pytest.approx(0.0)
    assert value(v, "department_f1_macro", "complaint") == pytest.approx(1 / 3)
    assert v[("department_f1_macro", "complaint")][1] == 2
    # severity on the same 2 cells: |2-3| and |4-4|
    assert value(v, "severity_mae", "complaint") == pytest.approx(0.5)
    assert value(v, "severity_qwk", "complaint") == pytest.approx(2 / 3)


def test_support_and_min_support_rule():
    v = compute_metrics(small_frame())  # default min_support 5: no class qualifies for a macro average
    assert math.isnan(value(v, "topic_f1_macro", "subcategory"))
    assert v[("topic_f1", "subcategory:A")][1] == 2  # per-class rows always carry their support
    assert value(v, "topic_f1_micro", "subcategory") == pytest.approx(10 / 13)  # micro keeps every class


def test_quadratic_weighted_kappa_known_values():
    ones = np.ones(5)
    assert quadratic_weighted_kappa(np.array([1, 2, 3, 4, 2]), np.array([1, 2, 3, 4, 2]), ones) == pytest.approx(1.0)
    # one off-by-one disagreement in 4 rows, checked against sklearn.metrics.cohen_kappa_score(weights="quadratic")
    ref, pred = np.array([1, 2, 3, 4]), np.array([1, 2, 4, 4])
    assert quadratic_weighted_kappa(ref, pred, np.ones(4)) == pytest.approx(0.9166666667)


def test_recommendation_metrics():
    # 4 queries (one per review): correct at rank 1, correct at rank 3, answered but wrong, silent
    queries = RecQueries(4, np.array([0, 1, 2, 3]), np.array([1, 3, 0, 0]), np.array([True, True, True, False]))
    v = queries.metrics()
    assert value(v, "mrr", "all") == pytest.approx((1 + 1 / 3) / 4)
    assert value(v, "hit_at_1", "all") == pytest.approx(0.25)
    assert value(v, "hit_at_3", "all") == pytest.approx(0.5)
    assert value(v, "coverage", "all") == pytest.approx(0.75)
    assert v[("mrr", "all")][1] == 4


def test_bootstrap_is_reproducible_and_brackets_the_estimate():
    frame = small_frame()
    fn = lambda w: compute_metrics(frame, w, min_support=1)  # noqa: E731
    first = bootstrap_intervals(fn, frame.n_reviews, n_boot=200, seed=7)
    again = bootstrap_intervals(fn, frame.n_reviews, n_boot=200, seed=7)
    other = bootstrap_intervals(fn, frame.n_reviews, n_boot=200, seed=8)
    assert first == again
    assert first != other
    interval = first[("topic_f1_micro", "subcategory")]
    assert interval.low <= 10 / 13 <= interval.high


def test_paired_bootstrap_identical_runs_have_zero_difference():
    frame = small_frame()
    fn = lambda w: compute_metrics(frame, w, min_support=1)  # noqa: E731
    result = paired_bootstrap(fn, fn, frame.n_reviews, n_boot=100, seed=1)[("topic_f1_micro", "subcategory")]
    assert (result.difference, result.low, result.high, result.p_value) == (0.0, 0.0, 0.0, 1.0)


def test_paired_bootstrap_detects_a_clear_difference():
    frame = small_frame()
    perfect = EvalFrame(**{**frame.__dict__, "pred_status": frame.ref_status.copy()})
    result = paired_bootstrap(
        lambda w: compute_metrics(perfect, w, min_support=1),
        lambda w: compute_metrics(frame, w, min_support=1),
        frame.n_reviews, n_boot=300, seed=3,
    )[("topic_f1_micro", "subcategory")]
    assert result.difference == pytest.approx(1 - 10 / 13)
    assert result.low >= 0


def test_build_frame_resolves_merged_ids_and_defaults_missing_cells():
    ref = [
        {"review_id": "r1", "subcategory_id": "old", "status": "negative", "department_id": "d", "severity": 2},
        {"review_id": "r1", "subcategory_id": "b", "status": "not_mentioned", "department_id": None, "severity": None},
    ]
    pred = [{"review_id": "r1", "subcategory_id": "new", "status": "negative", "department_id": "d", "severity": 2}]
    frame = build_frame(ref, pred, {"new": "m", "b": "m", "old": "m"}, {"old": "new"}, {}, {})
    assert frame.subcategories == ["b", "new"]
    assert frame.pred_status.tolist() == [[0, 2]]  # b was never predicted -> not_mentioned
    assert frame.ref_status.tolist() == [[0, 2]]


def test_build_frame_rejects_unknown_prediction_subcategory():
    ref = [{"review_id": "r1", "subcategory_id": "a", "status": "negative", "department_id": None, "severity": None}]
    pred = [{"review_id": "r1", "subcategory_id": "zzz", "status": "negative", "department_id": None, "severity": None}]
    with pytest.raises(EvaluationDataError):
        build_frame(ref, pred, {"a": "m", "zzz": "m"}, {}, {}, {})


# ------------------------------------------------------------ database round trip


def _scalar(session, sql, **params):
    return session.execute(text(sql), params).scalar_one()


def _make_run(session, kind, name):
    return _scalar(
        session,
        "INSERT INTO annotation_runs (kind, annotator_or_model, schema_version) "
        "VALUES (CAST(:k AS run_kind), :n, 1) RETURNING run_id",
        k=kind, n=name,
    )


def _label(session, run, review, sub, status, severity=None, dept=None, actions=()):
    session.execute(
        text("INSERT INTO aspect_labels (run_id, review_id, subcategory_id, status) "
             "VALUES (:r, :v, :u, CAST(:s AS sentiment))"),
        {"r": run, "v": review, "u": sub, "s": status},
    )
    if status != "negative":
        return None
    cid = _scalar(
        session,
        "INSERT INTO complaints (run_id, review_id, subcategory_id, department_id, severity, action_status) "
        "VALUES (:r, :v, :u, :d, :sev, CAST(:a AS action_status)) RETURNING complaint_id",
        r=run, v=review, u=sub, d=dept, sev=severity, a="recommended" if actions else "not_needed",
    )
    for action in actions:
        session.execute(text("INSERT INTO complaint_actions VALUES (:c, :a)"), {"c": cid, "a": action})
    return cid


@pytest.fixture
def world(db_session):
    """Human reference + a prediction run over 4 gold_dev reviews; the prediction misses one complaint."""
    load_taxonomy(db_session)
    subs = [r[0] for r in db_session.execute(text("SELECT id FROM subcategories ORDER BY id"))]
    depts = [r[0] for r in db_session.execute(text("SELECT id FROM departments ORDER BY id"))]
    actions = [r[0] for r in db_session.execute(text("SELECT id FROM actions ORDER BY id"))]
    db_session.add_all(
        Review(review_id=f"e{i}", source="humir", text=f"t{i}", word_len=1, humir_class="negative", split="gold_dev")
        for i in range(4)
    )
    db_session.flush()
    human, model = _make_run(db_session, "human", "h"), _make_run(db_session, "model", "m")
    for run in (human, model):
        for i in range(4):
            db_session.execute(
                text("INSERT INTO review_annotations (run_id, review_id, status) VALUES (:r, :v, 'done')"),
                {"r": run, "v": f"e{i}"},
            )
    # Cells not listed below are not_mentioned in both runs.
    reference = {("e0", 0): ("negative", 3, 0, (0,)), ("e1", 0): ("negative", 2, 1, (1,)),
                 ("e1", 1): ("positive", None, None, ()), ("e2", 2): ("negative", 4, 0, (2,)),
                 ("e3", 1): ("neutral", None, None, ())}
    predicted = {("e0", 0): ("negative", 3, 0, ()), ("e1", 0): ("negative", 3, 1, ()),
                 ("e1", 1): ("positive", None, None, ()), ("e3", 1): ("positive", None, None, ())}
    ref_ids = {}
    for run, data, store in ((human, reference, ref_ids), (model, predicted, {})):
        for i in range(4):
            for s, sub in enumerate(subs):
                status, sev, d, acts = data.get((f"e{i}", s), ("not_mentioned", None, None, ()))
                cid = _label(db_session, run, f"e{i}", sub, status, sev,
                             depts[d] if d is not None else None, [actions[a] for a in acts])
                store[(f"e{i}", s)] = cid
    return {"human": human, "model": model, "subs": subs, "actions": actions, "ref_ids": ref_ids}


def test_evaluate_labels_round_trip(db_session, world):
    rows = evaluate_labels(db_session, world["human"], world["model"], "gold_dev", "end_to_end", n_boot=50)
    by = {(r.metric, r.scope): r for r in rows}
    # topic: reference mentions 5 cells, prediction 4 of them (e2 missed), all correct
    topic = by[("topic_f1_micro", "subcategory")]
    assert topic.value == pytest.approx(2 * 4 / (2 * 4 + 0 + 1))
    assert topic.ci_low is not None and topic.ci_low <= topic.value <= topic.ci_high
    # severity compared on the two shared complaints: |3-3| and |2-3|
    assert by[("severity_mae", "complaint")].value == pytest.approx(0.5)
    assert by[("severity_mae", "complaint")].n == 2
    stored = db_session.execute(
        text("SELECT count(*), min(prediction_run_id), min(reference_run_id), min(eval_mode::text), min(split::text) "
             "FROM eval_results")
    ).one()
    assert stored == (len(rows), world["model"], world["human"], "end_to_end", "gold_dev")
    config = db_session.execute(text("SELECT config FROM eval_results LIMIT 1")).scalar_one()
    assert config["seed"] == 42 and config["n_boot"] == 50


def test_same_seed_same_interval_through_the_database(db_session, world):
    def run():
        return {(r.metric, r.scope): (r.ci_low, r.ci_high)
                for r in evaluate_labels(db_session, world["human"], world["model"], "gold_dev", "oracle",
                                         n_boot=60, seed=5, store=False)}

    assert run() == run()


def test_compare_labels_against_itself(db_session, world):
    rows = compare_labels(db_session, world["human"], world["model"], world["model"], "gold_dev", "oracle", n_boot=40)
    assert rows and all(r.value == 0 and r.extra["p_value"] == 1.0 for r in rows)
    assert all(r.metric.endswith("_diff") for r in rows)


def test_reference_must_be_a_human_run_with_done_reviews(db_session, world):
    with pytest.raises(Exception):
        evaluate_labels(db_session, world["model"], world["human"], "gold_dev", "oracle", n_boot=5)
    with pytest.raises(EvaluationDataError):
        evaluate_labels(db_session, world["human"], world["model"], "external_real", "oracle", n_boot=5)


def test_evaluate_recommendations(db_session, world):
    a = world["actions"]
    ref = world["ref_ids"]
    graph_run = world["human"]
    # oracle queries are the reference complaints e0 (action a0), e1 (a1), e2 (a2)
    def rec(complaint, rank, action, config='{"support": 5}'):
        db_session.execute(
            text("INSERT INTO recommendations (query_complaint_id, prediction_run_id, graph_run_id, config, rank, "
                 "action_id, support, backoff_level) VALUES (:c, NULL, :g, CAST(:cfg AS jsonb), :k, :a, 5, 'sub')"),
            {"c": ref[("e0", 0)] if complaint == "e0" else ref[(complaint, 0 if complaint == "e1" else 2)],
             "g": graph_run, "cfg": config, "k": rank, "a": action},
        )

    rec("e0", 1, a[0])  # correct at rank 1
    rec("e1", 1, a[5])
    rec("e1", 2, a[1])  # correct at rank 2
    rec("e2", 1, a[6])  # answered, wrong
    rec("e2", 1, a[7], config='{"support": 10}')  # other configuration: filtered out below
    rows = evaluate_recommendations(db_session, world["human"], "gold_dev", graph_run, None, {"support": 5}, n_boot=30)
    by = {(r.metric): r for r in rows}
    assert by["mrr"].value == pytest.approx((1 + 0.5 + 0) / 3)
    assert by["hit_at_1"].value == pytest.approx(1 / 3)
    assert by["hit_at_3"].value == pytest.approx(2 / 3)
    assert by["coverage"].value == pytest.approx(1.0)
    stored = db_session.execute(
        text("SELECT DISTINCT eval_mode::text, prediction_run_id FROM eval_results WHERE metric = 'mrr'")
    ).all()
    assert stored == [("oracle", None)]
