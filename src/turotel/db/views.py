"""Queries over the migration-defined views. Every query filters `run_id` explicitly.

Views take no parameters and there is no hidden "active run": callers pass `run_id`, and the
training / export / graph / embedding views are read only for a run that is a frozen,
validated Jev run (`require_frozen_jev_run`).
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from turotel.db.models import AnnotationRun

_MASKED_VIEWS = {"v_train_export", "v_silver_val_export", "v_graph_train", "v_labels_masked"}
_REFERENCE_VIEWS = {"v_gold_dev_eval", "v_gold_test_eval", "v_external_eval"}
_TAXONOMY_TABLES = {"main_categories", "subcategories", "departments", "cause_factors", "actions"}


class RunNotUsableError(RuntimeError):
    pass


def require_frozen_jev_run(session: Session, run_id: int) -> AnnotationRun:
    """Training, export, graph and embedding data come only from one frozen + validated Jev run."""
    run = session.get(AnnotationRun, run_id)
    if run is None:
        raise RunNotUsableError(f"run {run_id} does not exist")
    if run.kind != "jev" or not run.is_frozen or run.validated_at is None:
        raise RunNotUsableError(
            f"run {run_id} must be kind=jev, is_frozen and validated "
            f"(kind={run.kind}, is_frozen={run.is_frozen}, validated_at={run.validated_at})"
        )
    return run


def require_human_run(session: Session, run_id: int) -> AnnotationRun:
    """Gold / external reference comes only from a human run."""
    run = session.get(AnnotationRun, run_id)
    if run is None or run.kind != "human":
        raise RunNotUsableError(f"run {run_id} is not a human run")
    return run


def read_masked_view(session: Session, view: str, run_id: int) -> Sequence[Any]:
    """Rows of a masked view for a frozen, validated Jev run."""
    if view not in _MASKED_VIEWS:
        raise ValueError(f"not a masked view: {view}")
    require_frozen_jev_run(session, run_id)
    # `view` is checked against a fixed allow-list above.
    return session.execute(text(f"SELECT * FROM {view} WHERE run_id = :run_id"), {"run_id": run_id}).mappings().all()


def read_reference_view(session: Session, view: str, run_id: int) -> Sequence[Any]:
    """Rows of a gold / external reference view for a human run."""
    if view not in _REFERENCE_VIEWS:
        raise ValueError(f"not a reference view: {view}")
    require_human_run(session, run_id)
    return session.execute(text(f"SELECT * FROM {view} WHERE run_id = :run_id"), {"run_id": run_id}).mappings().all()


def resolve_merged_id(session: Session, table: str, id_: str) -> str:
    """Follow the `merged_into` chain of a taxonomy id to its current identity."""
    if table not in _TAXONOMY_TABLES:
        raise ValueError(f"not a taxonomy table: {table}")
    seen = {id_}
    while True:
        # `table` is checked against a fixed allow-list above.
        merged = session.execute(text(f"SELECT merged_into FROM {table} WHERE id = :id"), {"id": id_}).scalar_one()
        if merged is None:
            return id_
        if merged in seen:
            raise RuntimeError(f"merged_into cycle in {table} at {merged}")
        seen.add(merged)
        id_ = merged
