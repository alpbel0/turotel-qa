"""Review-level bootstrap: confidence intervals and a paired difference test.

The resampling unit is the review (cells of one review are not independent). A resample is a weight vector
(how often each review was drawn), so `metrics_fn(w)` is the same function that gives the point estimate with
all-ones weights. Randomness comes only from the seed: the same seed gives the same interval.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from turotel.evaluation.metrics import Key, Values

MetricsFn = Callable[[np.ndarray], Values]

DEFAULT_BOOTSTRAP = 1000
DEFAULT_ALPHA = 0.05


@dataclass(frozen=True)
class Interval:
    low: float
    high: float


@dataclass(frozen=True)
class PairedResult:
    difference: float  # a - b on the full data
    low: float
    high: float
    p_value: float  # two-sided, share of resamples on the other side of zero, doubled


def _weights(n_units: int, n_boot: int, seed: int):
    rng = np.random.default_rng(seed)
    for _ in range(n_boot):
        yield np.bincount(rng.integers(0, n_units, n_units), minlength=n_units)


def _interval(samples: list[float], alpha: float) -> Interval | None:
    finite = [v for v in samples if not math.isnan(v)]
    if len(finite) < max(2, len(samples) // 2):
        return None  # undefined in most resamples (e.g. a class absent)
    low, high = np.percentile(finite, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return Interval(float(low), float(high))


def bootstrap_intervals(
    metrics_fn: MetricsFn,
    n_units: int,
    n_boot: int = DEFAULT_BOOTSTRAP,
    seed: int = 42,
    alpha: float = DEFAULT_ALPHA,
) -> dict[Key, Interval | None]:
    """Percentile interval of every metric `metrics_fn` returns."""
    samples: dict[Key, list[float]] = {}
    for w in _weights(n_units, n_boot, seed):
        for key, (value, _n) in metrics_fn(w).items():
            samples.setdefault(key, []).append(value)
    return {key: _interval(values, alpha) for key, values in samples.items()}


def paired_bootstrap(
    metrics_a: MetricsFn,
    metrics_b: MetricsFn,
    n_units: int,
    n_boot: int = DEFAULT_BOOTSTRAP,
    seed: int = 42,
    alpha: float = DEFAULT_ALPHA,
) -> dict[Key, PairedResult]:
    """Paired difference a - b per metric: both runs are scored on the same resampled reviews."""
    point_a, point_b = metrics_a(np.ones(n_units)), metrics_b(np.ones(n_units))
    keys = [k for k in point_a if k in point_b]
    diffs: dict[Key, list[float]] = {k: [] for k in keys}
    for w in _weights(n_units, n_boot, seed):
        sample_a, sample_b = metrics_a(w), metrics_b(w)
        for key in keys:
            diffs[key].append(sample_a[key][0] - sample_b[key][0])
    results = {}
    for key in keys:
        observed = point_a[key][0] - point_b[key][0]
        finite = [d for d in diffs[key] if not math.isnan(d)]
        interval = _interval(diffs[key], alpha)
        if math.isnan(observed) or interval is None:
            continue
        below = sum(d <= 0 for d in finite) / len(finite)
        above = sum(d >= 0 for d in finite) / len(finite)
        results[key] = PairedResult(observed, interval.low, interval.high, min(1.0, 2 * min(below, above)))
    return results
