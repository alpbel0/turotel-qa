"""Metric definitions (docs/PROJE_PLANI.md section 5.5 and 5.6). Pure numpy, no database.

Every metric takes per-review weights `w` so the same code serves the point estimate (all ones) and each
bootstrap resample (counts of how often a review was drawn).

Definitions
- Topic detection: a (review, subcategory) cell is positive when the label is not `not_mentioned`.
  Complaint detection: positive when the label is `negative`. Micro F1 pools the counts of all classes; macro F1
  averages the per-class F1 of classes whose reference support is at least `min_support` (5). Per-class results
  are always reported with their support in `n`.
- Sentiment: macro F1 over positive / negative / neutral on cells the reference marks as mentioned. A prediction
  of `not_mentioned` on such a cell is an error (a miss for the reference class).
- Department macro F1 and severity MAE / quadratic weighted kappa: only cells that hold a complaint in BOTH the
  reference and the prediction, so they measure department / severity quality alone; missed or spurious
  complaints are already counted by complaint detection.
- Main category level: topic and complaint detection recomputed per main category, where a review is positive
  when any of its subcategories is.
- Recommendation: MRR, Hit@1, Hit@3 and coverage per eligible query; a silent query stays in the denominator
  with score 0.

`n` of a result row: reviews for aggregate detection metrics, the reference support for per-class rows, the
number of compared cells for department / severity.
"""

import math
from dataclasses import dataclass

import numpy as np

MIN_SUPPORT = 5
NOT_MENTIONED, POSITIVE, NEGATIVE, NEUTRAL = 0, 1, 2, 3
STATUS_CODES = {"not_mentioned": NOT_MENTIONED, "positive": POSITIVE, "negative": NEGATIVE, "neutral": NEUTRAL}
SENTIMENT_NAMES = {POSITIVE: "positive", NEGATIVE: "negative", NEUTRAL: "neutral"}
SEVERITY_LEVELS = 4

Key = tuple[str, str]  # (metric, scope)
Values = dict[Key, tuple[float, int]]  # key -> (value, n)


@dataclass
class EvalFrame:
    """Reference and prediction side by side, one row per review and one column per subcategory.

    `*_status` hold STATUS_CODES, `*_dept` an index into `departments` (-1 = no complaint / no department) and
    `*_sev` the severity 1..4 (0 = no complaint).
    """

    reviews: list[str]
    subcategories: list[str]
    mains: list[str]
    main_of: np.ndarray  # (S,) index into `mains`
    departments: list[str]
    ref_status: np.ndarray
    pred_status: np.ndarray
    ref_dept: np.ndarray
    pred_dept: np.ndarray
    ref_sev: np.ndarray
    pred_sev: np.ndarray

    @property
    def n_reviews(self) -> int:
        return len(self.reviews)


def f1(tp: float, fp: float, fn: float) -> float:
    denominator = 2 * tp + fp + fn
    return 2 * tp / denominator if denominator > 0 else math.nan


def quadratic_weighted_kappa(ref: np.ndarray, pred: np.ndarray, w: np.ndarray, levels: int = SEVERITY_LEVELS) -> float:
    """Cohen's kappa with quadratic weights; `ref`/`pred` are 1..levels, `w` the row weights."""
    observed = np.zeros((levels, levels))
    np.add.at(observed, (ref - 1, pred - 1), w)
    total = observed.sum()
    if total == 0:
        return math.nan
    expected = np.outer(observed.sum(1), observed.sum(0)) / total
    idx = np.arange(levels)
    weights = (idx[:, None] - idx[None, :]) ** 2 / (levels - 1) ** 2
    denominator = (weights * expected).sum()
    if denominator == 0:
        return math.nan
    return 1.0 - (weights * observed).sum() / denominator


def _class_counts(ref_b: np.ndarray, pred_b: np.ndarray, w: np.ndarray):
    weight = w[:, None]
    tp = (weight * (ref_b & pred_b)).sum(0)
    fp = (weight * (~ref_b & pred_b)).sum(0)
    fn = (weight * (ref_b & ~pred_b)).sum(0)
    return tp, fp, fn


def _add_f1_family(
    out: Values,
    metric: str,
    aggregate_scope: str,
    class_prefix: str,
    class_names: list[str],
    ref_b: np.ndarray,
    pred_b: np.ndarray,
    w: np.ndarray,
    min_support: int,
    with_micro: bool = True,
    n_aggregate: int | None = None,
) -> None:
    """`metric` F1 per class column plus macro (and micro) over the classes with enough reference support."""
    tp, fp, fn = _class_counts(ref_b, pred_b, w)
    support = ref_b.sum(0)
    per_class = [f1(tp[i], fp[i], fn[i]) for i in range(len(class_names))]
    for i, name in enumerate(class_names):
        out[(metric, f"{class_prefix}:{name}")] = (per_class[i], int(support[i]))
    n = int(w.sum()) if n_aggregate is None else n_aggregate
    if with_micro:
        out[(f"{metric}_micro", aggregate_scope)] = (f1(tp.sum(), fp.sum(), fn.sum()), n)
    eligible = [per_class[i] for i in range(len(class_names)) if support[i] >= min_support]
    eligible = [v for v in eligible if not math.isnan(v)]
    out[(f"{metric}_macro", aggregate_scope)] = (float(np.mean(eligible)) if eligible else math.nan, n)


def _group_any(matrix: np.ndarray, group_of: np.ndarray, n_groups: int) -> np.ndarray:
    return np.stack([matrix[:, group_of == g].any(axis=1) for g in range(n_groups)], axis=1)


def compute_metrics(frame: EvalFrame, w: np.ndarray | None = None, min_support: int = MIN_SUPPORT) -> Values:
    """Every label metric of `frame` under review weights `w` (default: all ones)."""
    w = np.ones(frame.n_reviews) if w is None else w.astype(float)
    out: Values = {}
    ref, pred = frame.ref_status, frame.pred_status

    for metric, positive in (("topic_f1", lambda s: s != NOT_MENTIONED), ("complaint_f1", lambda s: s == NEGATIVE)):
        _add_f1_family(out, metric, "subcategory", "subcategory", frame.subcategories,
                       positive(ref), positive(pred), w, min_support)
        _add_f1_family(out, metric, "main_category", "main_category", frame.mains,
                       _group_any(positive(ref), frame.main_of, len(frame.mains)),
                       _group_any(positive(pred), frame.main_of, len(frame.mains)), w, min_support)

    # Sentiment: only cells the reference marks as mentioned; classes are the three polarities.
    mentioned = ref != NOT_MENTIONED
    weight = w[:, None]
    sentiment_f1: list[float] = []
    for code, name in SENTIMENT_NAMES.items():
        is_ref, is_pred = mentioned & (ref == code), mentioned & (pred == code)
        tp = float((weight * (is_ref & is_pred)).sum())
        fp = float((weight * (is_pred & ~is_ref)).sum())
        fn = float((weight * (is_ref & ~is_pred)).sum())
        value, support = f1(tp, fp, fn), int(is_ref.sum())
        out[("sentiment_f1", f"class:{name}")] = (value, support)
        if support >= min_support and not math.isnan(value):
            sentiment_f1.append(value)
    out[("sentiment_f1_macro", "subcategory")] = (
        float(np.mean(sentiment_f1)) if sentiment_f1 else math.nan,
        int((weight * mentioned).sum()),
    )

    # Department: cells with a department on both sides.
    both_dept = (frame.ref_dept >= 0) & (frame.pred_dept >= 0)
    n_dept = int((w[:, None] * both_dept).sum())
    if frame.departments:
        dept_ref = np.stack([both_dept & (frame.ref_dept == d) for d in range(len(frame.departments))], axis=2)
        dept_pred = np.stack([both_dept & (frame.pred_dept == d) for d in range(len(frame.departments))], axis=2)
        # classes as columns: collapse the review/subcategory axes, weighting rows by w
        tp = (w[:, None, None] * (dept_ref & dept_pred)).sum((0, 1))
        fp = (w[:, None, None] * (~dept_ref & dept_pred)).sum((0, 1))
        fn = (w[:, None, None] * (dept_ref & ~dept_pred)).sum((0, 1))
        support = dept_ref.sum((0, 1))
        values = [f1(tp[d], fp[d], fn[d]) for d in range(len(frame.departments))]
        for d, name in enumerate(frame.departments):
            out[("department_f1", f"department:{name}")] = (values[d], int(support[d]))
        eligible = [v for d, v in enumerate(values) if support[d] >= min_support and not math.isnan(v)]
        out[("department_f1_macro", "complaint")] = (float(np.mean(eligible)) if eligible else math.nan, n_dept)

    # Severity: cells with a severity on both sides.
    both_sev = (frame.ref_sev > 0) & (frame.pred_sev > 0)
    rows = np.nonzero(both_sev)
    row_w = w[rows[0]]
    n_sev = int(row_w.sum())
    if n_sev > 0:
        err = np.abs(frame.ref_sev[rows] - frame.pred_sev[rows])
        out[("severity_mae", "complaint")] = (float((row_w * err).sum() / row_w.sum()), n_sev)
    else:
        out[("severity_mae", "complaint")] = (math.nan, 0)
    out[("severity_qwk", "complaint")] = (
        quadratic_weighted_kappa(frame.ref_sev[rows].astype(int), frame.pred_sev[rows].astype(int), row_w)
        if n_sev > 0
        else math.nan,
        n_sev,
    )
    return out


@dataclass
class RecQueries:
    """Recommendation outcome per eligible query (a reference complaint that carries reference actions).

    `ranks[i]` is the 1-based rank of the first correct action (0 = none correct), `answered[i]` whether the
    system returned any recommendation, `review_idx[i]` the index into `n_reviews` bootstrap units.
    """

    n_reviews: int
    review_idx: np.ndarray
    ranks: np.ndarray
    answered: np.ndarray

    def metrics(self, w: np.ndarray | None = None) -> Values:
        w = np.ones(self.n_reviews) if w is None else w.astype(float)
        weight = w[self.review_idx]
        total = weight.sum()
        n = int(total)
        if total == 0:
            nan = (math.nan, 0)
            return {(m, "all"): nan for m in ("mrr", "hit_at_1", "hit_at_3", "coverage")}
        correct = self.ranks > 0
        reciprocal = np.where(correct, 1.0 / np.maximum(self.ranks, 1), 0.0)
        return {
            ("mrr", "all"): (float((weight * reciprocal).sum() / total), n),
            ("hit_at_1", "all"): (float((weight * (correct & (self.ranks <= 1))).sum() / total), n),
            ("hit_at_3", "all"): (float((weight * (correct & (self.ranks <= 3))).sum() / total), n),
            ("coverage", "all"): (float((weight * self.answered).sum() / total), n),
        }
