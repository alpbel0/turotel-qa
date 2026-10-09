"""SQLAlchemy mappings of the tables created by the Alembic migrations (docs/VERI_KATMANI.md section 3).

Mapping only: never call `Base.metadata.create_all`; migrations are the single DDL source.
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _enum(name: str, *values: str) -> PgEnum:
    return PgEnum(*values, name=name, create_type=False)


REVIEW_SOURCE = _enum("review_source", "humir", "real", "mabsa")
HUMIR_CLASS = _enum("humir_class", "positive", "negative")
REVIEW_SPLIT = _enum(
    "review_split", "train", "silver_val", "gold_dev", "gold_test", "gold_reserve", "external_real", "external_mabsa"
)
RUN_KIND = _enum("run_kind", "human", "jev", "model")
ANNOTATION_STATUS = _enum("annotation_status", "done", "skip", "needs_review")
SENTIMENT = _enum("sentiment", "not_mentioned", "positive", "negative", "neutral")
CAUSE_STATUS = _enum("cause_status", "selected", "insufficient_evidence", "out_of_scope")
ACTION_STATUS = _enum("action_status", "recommended", "not_needed", "insufficient_evidence", "out_of_scope")
THRESHOLD_FAMILY = _enum("threshold_family", "aspect", "department", "severity", "cause", "action")
JEV_TARGET_TYPE = _enum("jev_target_type", "review", "complaint")
EVAL_MODE = _enum("eval_mode", "oracle", "end_to_end")
MODEL_TASK = _enum("model_task", "A", "B")


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- taxonomy


class SchemaVersion(Base):
    __tablename__ = "schema_versions"
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)


class _TaxonomyMixin:
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    definition: Mapped[str | None] = mapped_column(Text)
    introduced_in: Mapped[int] = mapped_column(ForeignKey("schema_versions.version"))
    retired_in: Mapped[int | None] = mapped_column(ForeignKey("schema_versions.version"))


class MainCategory(_TaxonomyMixin, Base):
    __tablename__ = "main_categories"
    merged_into: Mapped[str | None] = mapped_column(ForeignKey("main_categories.id"))


class Subcategory(_TaxonomyMixin, Base):
    __tablename__ = "subcategories"
    main_category_id: Mapped[str] = mapped_column(ForeignKey("main_categories.id"))
    merged_into: Mapped[str | None] = mapped_column(ForeignKey("subcategories.id"))


class Department(_TaxonomyMixin, Base):
    __tablename__ = "departments"
    merged_into: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))


class CauseFactor(_TaxonomyMixin, Base):
    __tablename__ = "cause_factors"
    factor_group: Mapped[str] = mapped_column(Text)
    merged_into: Mapped[str | None] = mapped_column(ForeignKey("cause_factors.id"))


class Action(_TaxonomyMixin, Base):
    __tablename__ = "actions"
    merged_into: Mapped[str | None] = mapped_column(ForeignKey("actions.id"))


class SubcategoryDepartment(Base):
    __tablename__ = "subcategory_departments"
    subcategory_id: Mapped[str] = mapped_column(ForeignKey("subcategories.id"), primary_key=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), primary_key=True)
    introduced_in: Mapped[int] = mapped_column(ForeignKey("schema_versions.version"))
    retired_in: Mapped[int | None] = mapped_column(ForeignKey("schema_versions.version"))


class CauseAction(Base):
    __tablename__ = "cause_actions"
    cause_factor_id: Mapped[str] = mapped_column(ForeignKey("cause_factors.id"), primary_key=True)
    action_id: Mapped[str] = mapped_column(ForeignKey("actions.id"), primary_key=True)
    introduced_in: Mapped[int] = mapped_column(ForeignKey("schema_versions.version"))
    retired_in: Mapped[int | None] = mapped_column(ForeignKey("schema_versions.version"))


# -------------------------------------------------------------------- data


class Review(Base):
    __tablename__ = "reviews"
    review_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(REVIEW_SOURCE)
    text: Mapped[str] = mapped_column(Text)
    humir_class: Mapped[str | None] = mapped_column(HUMIR_CLASS)
    word_len: Mapped[int] = mapped_column(Integer)
    duplicate_group_id: Mapped[str | None] = mapped_column(Text)
    split: Mapped[str | None] = mapped_column(REVIEW_SPLIT)
    split_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publishable: Mapped[bool] = mapped_column(Boolean, default=False)
    hotel_type: Mapped[str | None] = mapped_column(Text)
    stars_given: Mapped[int | None] = mapped_column(SmallInteger)


class SplitSnapshot(Base):
    __tablename__ = "split_snapshot"
    snapshot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    scope: Mapped[str] = mapped_column(Text, server_default="source=humir")
    sha256: Mapped[str] = mapped_column(Text)
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB)


class MabsaSentence(Base):
    __tablename__ = "mabsa_sentences"
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.review_id"), primary_key=True)
    orig_split: Mapped[str] = mapped_column(Text)
    raw_labels: Mapped[Any] = mapped_column(JSONB)
    mapped_labels: Mapped[Any | None] = mapped_column(JSONB)


# ------------------------------------------------------------------ labels


class AnnotationRun(Base):
    __tablename__ = "annotation_runs"
    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(RUN_KIND)
    annotator_or_model: Mapped[str] = mapped_column(Text)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("models.model_id", use_alter=True))
    schema_version: Mapped[int] = mapped_column(ForeignKey("schema_versions.version"))
    prompt_version: Mapped[str | None] = mapped_column(Text)
    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewAnnotation(Base):
    __tablename__ = "review_annotations"
    run_id: Mapped[int] = mapped_column(ForeignKey("annotation_runs.run_id"), primary_key=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.review_id"), primary_key=True)
    status: Mapped[str] = mapped_column(ANNOTATION_STATUS)
    duration_sec: Mapped[float | None] = mapped_column(Double)
    note: Mapped[str | None] = mapped_column(Text)


class AspectLabel(Base):
    __tablename__ = "aspect_labels"
    run_id: Mapped[int] = mapped_column(ForeignKey("annotation_runs.run_id"), primary_key=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.review_id"), primary_key=True)
    subcategory_id: Mapped[str] = mapped_column(ForeignKey("subcategories.id"), primary_key=True)
    status: Mapped[str] = mapped_column(SENTIMENT)
    confidence: Mapped[float | None] = mapped_column(Double)


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "review_id", "subcategory_id"],
            ["aspect_labels.run_id", "aspect_labels.review_id", "aspect_labels.subcategory_id"],
        ),
    )
    complaint_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInteger)
    review_id: Mapped[str] = mapped_column(Text)
    subcategory_id: Mapped[str] = mapped_column(Text)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))
    department_conf: Mapped[float | None] = mapped_column(Double)
    severity: Mapped[int] = mapped_column(SmallInteger)
    severity_conf: Mapped[float | None] = mapped_column(Double)
    cause_status: Mapped[str | None] = mapped_column(CAUSE_STATUS)
    cause_factor_id: Mapped[str | None] = mapped_column(ForeignKey("cause_factors.id"))
    cause_conf: Mapped[float | None] = mapped_column(Double)
    action_status: Mapped[str | None] = mapped_column(ACTION_STATUS)
    action_conf: Mapped[float | None] = mapped_column(Double)


class ComplaintAction(Base):
    __tablename__ = "complaint_actions"
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.complaint_id"), primary_key=True)
    action_id: Mapped[str] = mapped_column(ForeignKey("actions.id"), primary_key=True)


class ConfidenceThreshold(Base):
    __tablename__ = "confidence_thresholds"
    run_id: Mapped[int] = mapped_column(ForeignKey("annotation_runs.run_id"), primary_key=True)
    family: Mapped[str] = mapped_column(THRESHOLD_FAMILY, primary_key=True)
    threshold: Mapped[float] = mapped_column(Double)
    chosen_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str | None] = mapped_column(Text)


# ------------------------------------------------------------- Jev cache


class JevCall(Base):
    __tablename__ = "jev_calls"
    call_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_hash: Mapped[str] = mapped_column(Text, unique=True)
    call_type: Mapped[int] = mapped_column(SmallInteger)
    target_type: Mapped[str] = mapped_column(JEV_TARGET_TYPE)
    review_id: Mapped[str | None] = mapped_column(ForeignKey("reviews.review_id"))
    subcategory_id: Mapped[str | None] = mapped_column(ForeignKey("subcategories.id"))
    request: Mapped[Any] = mapped_column(JSONB)
    response: Mapped[Any] = mapped_column(JSONB)
    jev_version: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[float | None] = mapped_column(Double)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ----------------------------------------------- embeddings / recommend


class ComplaintEmbedding(Base):
    __tablename__ = "complaint_embeddings"
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.complaint_id"), primary_key=True)
    model_name: Mapped[str] = mapped_column(Text, primary_key=True)
    input_variant: Mapped[str] = mapped_column(Text, primary_key=True)
    embedding: Mapped[Any] = mapped_column(Vector())


class Recommendation(Base):
    __tablename__ = "recommendations"
    rec_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query_complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.complaint_id"))
    prediction_run_id: Mapped[int | None] = mapped_column(ForeignKey("annotation_runs.run_id"))
    graph_run_id: Mapped[int] = mapped_column(ForeignKey("annotation_runs.run_id"))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    rank: Mapped[int] = mapped_column(Integer)
    cause_factor_id: Mapped[str | None] = mapped_column(ForeignKey("cause_factors.id"))
    action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"))
    support: Mapped[int] = mapped_column(Integer)
    backoff_level: Mapped[str] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Double)
    neighbor_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list)


# ----------------------------------------------------------- models / results


class ExportManifest(Base):
    __tablename__ = "export_manifests"
    manifest_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    view_name: Mapped[str] = mapped_column(Text)
    run_id: Mapped[int] = mapped_column(ForeignKey("annotation_runs.run_id"))
    schema_version: Mapped[int] = mapped_column(ForeignKey("schema_versions.version"))
    splits: Mapped[Any] = mapped_column(JSONB)
    row_count: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Model(Base):
    __tablename__ = "models"
    model_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task: Mapped[str] = mapped_column(MODEL_TASK)
    base_encoder: Mapped[str] = mapped_column(Text)
    train_size: Mapped[int] = mapped_column(Integer)
    hyperparams: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    artifact_path: Mapped[str | None] = mapped_column(Text)
    train_manifest_id: Mapped[int | None] = mapped_column(ForeignKey("export_manifests.manifest_id"))


class EvalResult(Base):
    __tablename__ = "eval_results"
    eval_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    prediction_run_id: Mapped[int | None] = mapped_column(ForeignKey("annotation_runs.run_id"))
    reference_run_id: Mapped[int] = mapped_column(ForeignKey("annotation_runs.run_id"))
    eval_mode: Mapped[str] = mapped_column(EVAL_MODE)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    split: Mapped[str] = mapped_column(REVIEW_SPLIT)
    metric: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text)
    value: Mapped[float] = mapped_column(Double)
    ci_low: Mapped[float | None] = mapped_column(Double)
    ci_high: Mapped[float | None] = mapped_column(Double)
    n: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------- synthetic


class KpiDaily(Base):
    __tablename__ = "kpi_daily"
    scenario: Mapped[str] = mapped_column(Text, primary_key=True)
    seed: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[int] = mapped_column(Integer, primary_key=True)
    variable: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[float] = mapped_column(Double)


class CausalTrueEdge(Base):
    __tablename__ = "causal_true_edges"
    scenario: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, primary_key=True)
    target: Mapped[str] = mapped_column(Text, primary_key=True)
    lag: Mapped[int] = mapped_column(Integer, primary_key=True)
    coef: Mapped[float] = mapped_column(Double)


class CausalEdge(Base):
    __tablename__ = "causal_edges"
    scenario: Mapped[str] = mapped_column(Text, primary_key=True)
    seed: Mapped[int] = mapped_column(Integer, primary_key=True)
    method: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, primary_key=True)
    target: Mapped[str] = mapped_column(Text, primary_key=True)
    lag: Mapped[int] = mapped_column(Integer, primary_key=True)
    strength: Mapped[float] = mapped_column(Double)
    p_value: Mapped[float | None] = mapped_column(Double)


class Forecast(Base):
    __tablename__ = "forecasts"
    seed: Mapped[int] = mapped_column(Integer, primary_key=True)
    target: Mapped[str] = mapped_column(Text, primary_key=True)
    origin_day: Mapped[int] = mapped_column(Integer, primary_key=True)
    horizon: Mapped[int] = mapped_column(Integer, primary_key=True)
    method: Mapped[str] = mapped_column(Text, primary_key=True)
    q10: Mapped[float | None] = mapped_column(Double)
    q50: Mapped[float | None] = mapped_column(Double)
    q90: Mapped[float | None] = mapped_column(Double)
    actual: Mapped[float | None] = mapped_column(Double)


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"
    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    seed: Mapped[int] = mapped_column(Integer)
    target: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    start_day: Mapped[int] = mapped_column(Integer)
    end_day: Mapped[int] = mapped_column(Integer)


class AnomalyAlert(Base):
    __tablename__ = "anomaly_alerts"
    seed: Mapped[int] = mapped_column(Integer, primary_key=True)
    target: Mapped[str] = mapped_column(Text, primary_key=True)
    day: Mapped[int] = mapped_column(Integer, primary_key=True)
    method: Mapped[str] = mapped_column(Text, primary_key=True)
