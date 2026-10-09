"""Evaluation entry points: score a prediction run against a human reference run and store `eval_results`.

    rows = evaluate_labels(session, reference_run_id=1, prediction_run_id=7, split="gold_dev", eval_mode="end_to_end")
    session.commit()

Undefined values (NaN, e.g. a class without support) are neither returned nor stored. The caller commits.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from turotel.db.models import EvalResult
from turotel.evaluation.bootstrap import DEFAULT_BOOTSTRAP, bootstrap_intervals, paired_bootstrap
from turotel.evaluation.loading import load_frame, load_rec_queries
from turotel.evaluation.metrics import MIN_SUPPORT, Values, compute_metrics

EvalMode = Literal["oracle", "end_to_end"]
DEFAULT_SEED = 42


@dataclass(frozen=True)
class ResultRow:
    metric: str
    scope: str
    value: float
    n: int
    ci_low: float | None = None
    ci_high: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)  # merged into this row's `config` (e.g. a p-value)


def _rows(values: Values, intervals: dict) -> list[ResultRow]:
    rows = []
    for (metric, scope), (value, n) in sorted(values.items()):
        if math.isnan(value):
            continue
        interval = intervals.get((metric, scope))
        rows.append(ResultRow(metric, scope, value, n, interval.low if interval else None,
                              interval.high if interval else None))
    return rows


def store_results(
    session: Session,
    rows: list[ResultRow],
    *,
    prediction_run_id: int | None,
    reference_run_id: int,
    eval_mode: EvalMode,
    split: str,
    config: dict[str, Any],
) -> None:
    session.add_all(
        EvalResult(
            prediction_run_id=prediction_run_id,
            reference_run_id=reference_run_id,
            eval_mode=eval_mode,
            config={**config, **row.extra},
            split=split,
            metric=row.metric,
            scope=row.scope,
            value=row.value,
            ci_low=row.ci_low,
            ci_high=row.ci_high,
            n=row.n,
        )
        for row in rows
    )
    session.flush()


def _config(split: str, n_boot: int, seed: int, **more: Any) -> dict[str, Any]:
    return {"split": split, "n_boot": n_boot, "seed": seed, "ci": "percentile 95%", "unit": "review", **more}


def evaluate_labels(
    session: Session,
    reference_run_id: int,
    prediction_run_id: int,
    split: str,
    eval_mode: EvalMode,
    *,
    n_boot: int = DEFAULT_BOOTSTRAP,
    seed: int = DEFAULT_SEED,
    masked: bool = False,
    min_support: int = MIN_SUPPORT,
    store: bool = True,
) -> list[ResultRow]:
    """Topic / sentiment / complaint / department / severity metrics with bootstrap intervals.

    `masked=True` scores the prediction through `v_labels_masked` (confidence thresholds applied).
    """
    frame = load_frame(session, reference_run_id, prediction_run_id, split, masked)
    values = compute_metrics(frame, min_support=min_support)
    intervals = bootstrap_intervals(
        lambda w: compute_metrics(frame, w, min_support), frame.n_reviews, n_boot, seed
    )
    rows = _rows(values, intervals)
    if store:
        store_results(session, rows, prediction_run_id=prediction_run_id, reference_run_id=reference_run_id,
                      eval_mode=eval_mode, split=split,
                      config=_config(split, n_boot, seed, masked=masked, min_support=min_support))
    return rows


def compare_labels(
    session: Session,
    reference_run_id: int,
    run_a: int,
    run_b: int,
    split: str,
    eval_mode: EvalMode,
    *,
    n_boot: int = DEFAULT_BOOTSTRAP,
    seed: int = DEFAULT_SEED,
    masked: bool = False,
    min_support: int = MIN_SUPPORT,
    store: bool = True,
) -> list[ResultRow]:
    """Paired bootstrap of `run_a - run_b` for every metric; stored as `<metric>_diff` under `run_a`."""
    frame_a = load_frame(session, reference_run_id, run_a, split, masked)
    frame_b = load_frame(session, reference_run_id, run_b, split, masked)
    results = paired_bootstrap(
        lambda w: compute_metrics(frame_a, w, min_support),
        lambda w: compute_metrics(frame_b, w, min_support),
        frame_a.n_reviews, n_boot, seed,
    )
    counts = compute_metrics(frame_a, min_support=min_support)
    rows = [
        ResultRow(f"{metric}_diff", scope, r.difference, counts[(metric, scope)][1], r.low, r.high,
                  {"p_value": r.p_value, "compared_with_run": run_b})
        for (metric, scope), r in sorted(results.items())
    ]
    if store:
        store_results(session, rows, prediction_run_id=run_a, reference_run_id=reference_run_id,
                      eval_mode=eval_mode, split=split,
                      config=_config(split, n_boot, seed, masked=masked, min_support=min_support, paired=True))
    return rows


def evaluate_recommendations(
    session: Session,
    reference_run_id: int,
    split: str,
    graph_run_id: int,
    prediction_run_id: int | None = None,
    config_filter: dict[str, Any] | None = None,
    *,
    n_boot: int = DEFAULT_BOOTSTRAP,
    seed: int = DEFAULT_SEED,
    store: bool = True,
) -> list[ResultRow]:
    """MRR, Hit@1, Hit@3 and coverage of stored recommendations against the reference actions.

    `prediction_run_id=None` scores oracle recommendations (queries are reference complaints); a run id scores
    end-to-end recommendations. `config_filter` selects one configuration (threshold, ablation) of the
    `recommendations.config` JSON.
    """
    queries = load_rec_queries(session, reference_run_id, split, graph_run_id, prediction_run_id, config_filter)
    values = queries.metrics()
    intervals = bootstrap_intervals(queries.metrics, queries.n_reviews, n_boot, seed)
    rows = _rows(values, intervals)
    if store:
        eval_mode: EvalMode = "oracle" if prediction_run_id is None else "end_to_end"
        store_results(session, rows, prediction_run_id=prediction_run_id, reference_run_id=reference_run_id,
                      eval_mode=eval_mode, split=split,
                      config=_config(split, n_boot, seed, graph_run_id=graph_run_id,
                                     recommendation_config=config_filter or {}))
    return rows
