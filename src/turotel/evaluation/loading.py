"""Read reference and prediction runs from the database and shape them for the metric code.

Reference rows come only from the gold / external views through `read_reference_view` (human run, `status=done`
reviews). Taxonomy ids are resolved along `merged_into` chains so runs written under different schema versions
compare on the same ids.
"""

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from turotel.db.views import read_reference_view
from turotel.evaluation.metrics import STATUS_CODES, EvalFrame, RecQueries

REFERENCE_VIEWS = {
    "gold_dev": "v_gold_dev_eval",
    "gold_test": "v_gold_test_eval",  # opened only by the final-test script (Task 8.2)
    "external_real": "v_external_eval",
}


class EvaluationDataError(ValueError):
    """The runs cannot be compared (empty reference, ids outside the reference schema, ...)."""


def taxonomy_resolver(session: Session, table: str) -> dict[str, str]:
    """id -> id after following `merged_into` to the end of the chain."""
    assert table in {"subcategories", "main_categories", "departments", "actions"}
    merged = dict(session.execute(text(f"SELECT id, merged_into FROM {table}")).all())  # table is allow-listed
    resolved: dict[str, str] = {}
    for start in merged:
        current, seen = start, {start}
        while merged.get(current) is not None and merged[current] not in seen:
            current = merged[current]
            seen.add(current)
        resolved[start] = current
    return resolved


def read_reference_rows(session: Session, reference_run_id: int, split: str) -> list[Mapping[str, Any]]:
    if split not in REFERENCE_VIEWS:
        raise EvaluationDataError(f"no reference view for split {split!r}; use one of {sorted(REFERENCE_VIEWS)}")
    rows = [r for r in read_reference_view(session, REFERENCE_VIEWS[split], reference_run_id) if r["split"] == split]
    if not rows:
        raise EvaluationDataError(f"reference run {reference_run_id} has no done reviews in split {split!r}")
    return rows


def read_prediction_rows(session: Session, prediction_run_id: int, masked: bool) -> list[Mapping[str, Any]]:
    """Label rows of a prediction run. `masked=True` reads `v_labels_masked`: a masked label counts as not mentioned."""
    if masked:
        sql = (
            "SELECT review_id, subcategory_id, status::text AS status, department_id, severity "
            "FROM v_labels_masked WHERE run_id = :r AND status IS NOT NULL"
        )
    else:
        sql = (
            "SELECT al.review_id, al.subcategory_id, al.status::text AS status, c.department_id, c.severity "
            "FROM aspect_labels al LEFT JOIN complaints c ON c.run_id = al.run_id AND c.review_id = al.review_id "
            "AND c.subcategory_id = al.subcategory_id WHERE al.run_id = :r"
        )
    if session_run_missing(session, prediction_run_id):
        raise EvaluationDataError(f"prediction run {prediction_run_id} does not exist")
    return session.execute(text(sql), {"r": prediction_run_id}).mappings().all()


def session_run_missing(session: Session, run_id: int) -> bool:
    return session.execute(text("SELECT 1 FROM annotation_runs WHERE run_id = :r"), {"r": run_id}).first() is None


def build_frame(
    reference_rows: Sequence[Mapping[str, Any]],
    prediction_rows: Iterable[Mapping[str, Any]],
    main_of_subcategory: Mapping[str, str],
    resolve_sub: Mapping[str, str],
    resolve_main: Mapping[str, str],
    resolve_dept: Mapping[str, str],
) -> EvalFrame:
    """Align both sides on the reference's reviews and subcategories. Absent prediction cells are `not_mentioned`."""
    prediction_rows = list(prediction_rows)
    reviews = sorted({r["review_id"] for r in reference_rows})
    subs = sorted({resolve_sub.get(r["subcategory_id"], r["subcategory_id"]) for r in reference_rows})
    mains = sorted({resolve_main.get(main_of_subcategory[s], main_of_subcategory[s]) for s in subs})
    review_idx = {r: i for i, r in enumerate(reviews)}
    sub_idx = {s: i for i, s in enumerate(subs)}

    def dept_of(row) -> str | None:
        d = row["department_id"]
        return None if d is None else resolve_dept.get(d, d)

    departments = sorted(
        {d for rows in (reference_rows, prediction_rows) for r in rows if (d := dept_of(r)) is not None}
    )
    dept_idx = {d: i for i, d in enumerate(departments)}
    shape = (len(reviews), len(subs))

    def fill(rows, require_known_sub: bool):
        status = np.zeros(shape, dtype=np.int8)
        dept = np.full(shape, -1, dtype=np.int16)
        sev = np.zeros(shape, dtype=np.int8)
        seen: set[tuple[int, int]] = set()
        for row in rows:
            if row["review_id"] not in review_idx:
                continue  # prediction on a review outside the reference
            sub = resolve_sub.get(row["subcategory_id"], row["subcategory_id"])
            if sub not in sub_idx:
                if require_known_sub:
                    raise EvaluationDataError(f"prediction labels subcategory {sub!r} unknown to the reference")
                continue
            cell = (review_idx[row["review_id"]], sub_idx[sub])
            if cell in seen:
                raise EvaluationDataError(f"two labels map onto {row['review_id']}/{sub} after merging subcategories")
            seen.add(cell)
            status[cell] = STATUS_CODES[row["status"]]
            if (d := dept_of(row)) is not None:
                dept[cell] = dept_idx[d]
            if row["severity"] is not None:
                sev[cell] = row["severity"]
        return status, dept, sev

    ref_status, ref_dept, ref_sev = fill(reference_rows, require_known_sub=False)
    pred_status, pred_dept, pred_sev = fill(prediction_rows, require_known_sub=True)
    main_pos = {m: i for i, m in enumerate(mains)}
    main_of = np.array([main_pos[resolve_main.get(main_of_subcategory[s], main_of_subcategory[s])] for s in subs])
    return EvalFrame(reviews, subs, mains, main_of, departments, ref_status, pred_status, ref_dept, pred_dept,
                     ref_sev, pred_sev)


def load_frame(
    session: Session, reference_run_id: int, prediction_run_id: int, split: str, masked: bool = False
) -> EvalFrame:
    reference_rows = read_reference_rows(session, reference_run_id, split)
    prediction_rows = read_prediction_rows(session, prediction_run_id, masked)
    main_of = dict(session.execute(text("SELECT id, main_category_id FROM subcategories")).all())
    return build_frame(
        reference_rows,
        prediction_rows,
        main_of,
        taxonomy_resolver(session, "subcategories"),
        taxonomy_resolver(session, "main_categories"),
        taxonomy_resolver(session, "departments"),
    )


def load_rec_queries(
    session: Session,
    reference_run_id: int,
    split: str,
    graph_run_id: int,
    prediction_run_id: int | None = None,
    config_filter: Mapping[str, Any] | None = None,
) -> RecQueries:
    """One query per reference complaint that has reference actions; unanswered queries stay in with score 0.

    Recommendations are matched to a query by (review, subcategory), so oracle queries (reference complaints) and
    end-to-end queries (predicted complaints) are scored against the same reference.
    """
    reference_rows = read_reference_rows(session, reference_run_id, split)
    resolve_sub = taxonomy_resolver(session, "subcategories")
    resolve_action = taxonomy_resolver(session, "actions")
    reviews = sorted({r["review_id"] for r in reference_rows})
    review_idx = {r: i for i, r in enumerate(reviews)}

    gold: dict[tuple[str, str], set[str]] = {}
    for r in reference_rows:
        if r["complaint_id"] is not None and r["action_status"] == "recommended" and r["action_ids"]:
            key = (r["review_id"], resolve_sub.get(r["subcategory_id"], r["subcategory_id"]))
            gold[key] = {resolve_action.get(a, a) for a in r["action_ids"]}

    answers: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    recs = session.execute(
        text(
            "SELECT qc.review_id, qc.subcategory_id, rec.rank, rec.action_id FROM recommendations rec "
            "JOIN complaints qc ON qc.complaint_id = rec.query_complaint_id "
            "WHERE rec.graph_run_id = :g AND rec.prediction_run_id IS NOT DISTINCT FROM :p "
            "AND rec.config @> CAST(:cfg AS jsonb) AND rec.action_id IS NOT NULL"
        ),
        {"g": graph_run_id, "p": prediction_run_id, "cfg": json.dumps(dict(config_filter or {}))},
    ).all()
    for review_id, sub, rank, action in recs:
        answers[(review_id, resolve_sub.get(sub, sub))].append((rank, resolve_action.get(action, action)))

    queries = sorted(gold)
    ranks = np.zeros(len(queries), dtype=np.int64)
    answered = np.zeros(len(queries), dtype=bool)
    for i, key in enumerate(queries):
        given = sorted(answers.get(key, []))
        answered[i] = bool(given)
        ranks[i] = next((rank for rank, action in given if action in gold[key]), 0)
    return RecQueries(len(reviews), np.array([review_idx[k[0]] for k in queries], dtype=np.int64), ranks, answered)
