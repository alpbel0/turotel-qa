"""Evaluation core: label and recommendation metrics, review-level bootstrap, `eval_results` storage."""

from turotel.evaluation.core import ResultRow, compare_labels, evaluate_labels, evaluate_recommendations

__all__ = ["ResultRow", "compare_labels", "evaluate_labels", "evaluate_recommendations"]
