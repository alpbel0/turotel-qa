"""Extension, ENUMs and all tables (docs/VERI_KATMANI.md section 3).

Revision ID: 0001
Revises:
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Statements are separated by a blank line.
UP = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE review_source AS ENUM ('humir', 'real', 'mabsa');

CREATE TYPE humir_class AS ENUM ('positive', 'negative');

CREATE TYPE review_split AS ENUM (
    'train', 'silver_val', 'gold_dev', 'gold_test', 'gold_reserve', 'external_real', 'external_mabsa'
);

CREATE TYPE run_kind AS ENUM ('human', 'jev', 'model');

CREATE TYPE annotation_status AS ENUM ('done', 'skip', 'needs_review');

CREATE TYPE sentiment AS ENUM ('not_mentioned', 'positive', 'negative', 'neutral');

CREATE TYPE cause_status AS ENUM ('selected', 'insufficient_evidence', 'out_of_scope');

CREATE TYPE action_status AS ENUM ('recommended', 'not_needed', 'insufficient_evidence', 'out_of_scope');

CREATE TYPE threshold_family AS ENUM ('aspect', 'department', 'severity', 'cause', 'action');

CREATE TYPE jev_target_type AS ENUM ('review', 'complaint');

CREATE TYPE eval_mode AS ENUM ('oracle', 'end_to_end');

CREATE TYPE model_task AS ENUM ('A', 'B');

-- ---------------------------------------------------------------- taxonomy

CREATE TABLE schema_versions (
    version   integer PRIMARY KEY,
    frozen_at timestamptz,
    note      text
);

CREATE TABLE main_categories (
    id            text PRIMARY KEY,
    name          text NOT NULL,
    definition    text,
    introduced_in integer NOT NULL REFERENCES schema_versions (version),
    retired_in    integer REFERENCES schema_versions (version),
    merged_into   text REFERENCES main_categories (id)
);

CREATE TABLE subcategories (
    id               text PRIMARY KEY,
    main_category_id text NOT NULL REFERENCES main_categories (id),
    name             text NOT NULL,
    definition       text,
    introduced_in    integer NOT NULL REFERENCES schema_versions (version),
    retired_in       integer REFERENCES schema_versions (version),
    merged_into      text REFERENCES subcategories (id)
);

CREATE TABLE departments (
    id            text PRIMARY KEY,
    name          text NOT NULL,
    definition    text,
    introduced_in integer NOT NULL REFERENCES schema_versions (version),
    retired_in    integer REFERENCES schema_versions (version),
    merged_into   text REFERENCES departments (id)
);

CREATE TABLE cause_factors (
    id            text PRIMARY KEY,
    factor_group  text NOT NULL,
    name          text NOT NULL,
    definition    text,
    introduced_in integer NOT NULL REFERENCES schema_versions (version),
    retired_in    integer REFERENCES schema_versions (version),
    merged_into   text REFERENCES cause_factors (id)
);

CREATE TABLE actions (
    id            text PRIMARY KEY,
    name          text NOT NULL,
    definition    text,
    introduced_in integer NOT NULL REFERENCES schema_versions (version),
    retired_in    integer REFERENCES schema_versions (version),
    merged_into   text REFERENCES actions (id)
);

CREATE TABLE subcategory_departments (
    subcategory_id text NOT NULL REFERENCES subcategories (id),
    department_id  text NOT NULL REFERENCES departments (id),
    introduced_in  integer NOT NULL REFERENCES schema_versions (version),
    retired_in     integer REFERENCES schema_versions (version),
    PRIMARY KEY (subcategory_id, department_id)
);

CREATE TABLE cause_actions (
    cause_factor_id text NOT NULL REFERENCES cause_factors (id),
    action_id       text NOT NULL REFERENCES actions (id),
    introduced_in   integer NOT NULL REFERENCES schema_versions (version),
    retired_in      integer REFERENCES schema_versions (version),
    PRIMARY KEY (cause_factor_id, action_id)
);

-- -------------------------------------------------------------------- data

CREATE TABLE reviews (
    review_id          text PRIMARY KEY,
    source             review_source NOT NULL,
    text               text NOT NULL,
    humir_class        humir_class,
    word_len           integer NOT NULL CHECK (word_len >= 0),
    duplicate_group_id text,
    split              review_split,
    split_assigned_at  timestamptz,
    publishable        boolean NOT NULL DEFAULT false,
    CONSTRAINT ck_reviews_external_not_publishable
        CHECK (source NOT IN ('real', 'mabsa') OR publishable = false)
);

CREATE INDEX ix_reviews_split ON reviews (split);

CREATE INDEX ix_reviews_duplicate_group ON reviews (duplicate_group_id);

CREATE TABLE split_snapshot (
    snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at  timestamptz NOT NULL DEFAULT now(),
    scope       text NOT NULL DEFAULT 'source=humir',
    sha256      text NOT NULL,
    counts      jsonb NOT NULL
);

CREATE TABLE mabsa_sentences (
    review_id     text PRIMARY KEY REFERENCES reviews (review_id),
    orig_split    text NOT NULL,
    raw_labels    jsonb NOT NULL,
    mapped_labels jsonb
);

-- ------------------------------------------------- models / exports (early)

CREATE TABLE annotation_runs (
    run_id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind               run_kind NOT NULL,
    annotator_or_model text NOT NULL,
    model_id           bigint,
    schema_version     integer NOT NULL REFERENCES schema_versions (version),
    prompt_version     text,
    is_frozen          boolean NOT NULL DEFAULT false,
    validated_at       timestamptz,
    params             jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE export_manifests (
    manifest_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    view_name      text NOT NULL,
    run_id         bigint NOT NULL REFERENCES annotation_runs (run_id),
    schema_version integer NOT NULL REFERENCES schema_versions (version),
    splits         jsonb NOT NULL,
    row_count      integer NOT NULL CHECK (row_count >= 0),
    sha256         text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE models (
    model_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task              model_task NOT NULL,
    base_encoder      text NOT NULL,
    train_size        integer NOT NULL,
    hyperparams       jsonb NOT NULL DEFAULT '{}'::jsonb,
    artifact_path     text,
    train_manifest_id bigint REFERENCES export_manifests (manifest_id)
);

ALTER TABLE annotation_runs
    ADD CONSTRAINT fk_annotation_runs_model FOREIGN KEY (model_id) REFERENCES models (model_id);

-- ------------------------------------------------------------------ labels

CREATE TABLE review_annotations (
    run_id       bigint NOT NULL REFERENCES annotation_runs (run_id),
    review_id    text NOT NULL REFERENCES reviews (review_id),
    status       annotation_status NOT NULL,
    duration_sec double precision,
    note         text,
    PRIMARY KEY (run_id, review_id)
);

CREATE TABLE aspect_labels (
    run_id         bigint NOT NULL REFERENCES annotation_runs (run_id),
    review_id      text NOT NULL REFERENCES reviews (review_id),
    subcategory_id text NOT NULL REFERENCES subcategories (id),
    status         sentiment NOT NULL,
    confidence     double precision CHECK (confidence BETWEEN 0 AND 1),
    PRIMARY KEY (run_id, review_id, subcategory_id)
);

CREATE INDEX ix_aspect_labels_review ON aspect_labels (review_id);

CREATE TABLE complaints (
    complaint_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          bigint NOT NULL,
    review_id       text NOT NULL,
    subcategory_id  text NOT NULL,
    department_id   text REFERENCES departments (id),
    department_conf double precision CHECK (department_conf BETWEEN 0 AND 1),
    severity        smallint NOT NULL,
    severity_conf   double precision CHECK (severity_conf BETWEEN 0 AND 1),
    cause_status    cause_status,
    cause_factor_id text REFERENCES cause_factors (id),
    cause_conf      double precision CHECK (cause_conf BETWEEN 0 AND 1),
    action_status   action_status,
    action_conf     double precision CHECK (action_conf BETWEEN 0 AND 1),
    CONSTRAINT fk_complaints_aspect_label FOREIGN KEY (run_id, review_id, subcategory_id)
        REFERENCES aspect_labels (run_id, review_id, subcategory_id),
    CONSTRAINT uq_complaints_label UNIQUE (run_id, review_id, subcategory_id),
    CONSTRAINT ck_complaints_severity_range CHECK (severity BETWEEN 1 AND 4),
    CONSTRAINT ck_complaints_severity1_no_cause CHECK (severity <> 1 OR cause_factor_id IS NULL),
    CONSTRAINT ck_complaints_cause_selected_iff_factor
        CHECK ((cause_status IS NOT DISTINCT FROM 'selected') = (cause_factor_id IS NOT NULL))
);

CREATE TABLE complaint_actions (
    complaint_id bigint NOT NULL REFERENCES complaints (complaint_id) ON DELETE CASCADE,
    action_id    text NOT NULL REFERENCES actions (id),
    PRIMARY KEY (complaint_id, action_id)
);

CREATE TABLE confidence_thresholds (
    run_id    bigint NOT NULL REFERENCES annotation_runs (run_id),
    family    threshold_family NOT NULL,
    threshold double precision NOT NULL CHECK (threshold BETWEEN 0 AND 1),
    chosen_on timestamptz NOT NULL DEFAULT now(),
    note      text,
    PRIMARY KEY (run_id, family)
);

-- ------------------------------------------------------------- Jev cache

CREATE TABLE jev_calls (
    call_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_hash   text NOT NULL UNIQUE,
    call_type      smallint NOT NULL CHECK (call_type IN (1, 2)),
    target_type    jev_target_type NOT NULL,
    review_id      text REFERENCES reviews (review_id),
    subcategory_id text REFERENCES subcategories (id),
    request        jsonb NOT NULL,
    response       jsonb NOT NULL,
    jev_version    text NOT NULL,
    latency_ms     integer,
    cost           numeric,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- ----------------------------------------------- embeddings / recommend

CREATE TABLE complaint_embeddings (
    complaint_id  bigint NOT NULL REFERENCES complaints (complaint_id) ON DELETE CASCADE,
    model_name    text NOT NULL,
    input_variant text NOT NULL,
    embedding     vector NOT NULL,
    PRIMARY KEY (complaint_id, model_name, input_variant)
);

CREATE TABLE recommendations (
    rec_id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    query_complaint_id bigint NOT NULL REFERENCES complaints (complaint_id),
    prediction_run_id  bigint REFERENCES annotation_runs (run_id),
    graph_run_id       bigint NOT NULL REFERENCES annotation_runs (run_id),
    config             jsonb NOT NULL DEFAULT '{}'::jsonb,
    rank               integer NOT NULL CHECK (rank >= 1),
    cause_factor_id    text REFERENCES cause_factors (id),
    action_id          text REFERENCES actions (id),
    support            integer NOT NULL CHECK (support >= 0),
    backoff_level      text NOT NULL,
    score              double precision,
    neighbor_ids       bigint[] NOT NULL DEFAULT '{}'
);

-- ----------------------------------------------------------------- results

CREATE TABLE eval_results (
    eval_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prediction_run_id bigint REFERENCES annotation_runs (run_id),
    reference_run_id  bigint NOT NULL REFERENCES annotation_runs (run_id),
    eval_mode         eval_mode NOT NULL,
    config            jsonb NOT NULL DEFAULT '{}'::jsonb,
    split             review_split NOT NULL,
    metric            text NOT NULL,
    scope             text NOT NULL,
    value             double precision NOT NULL,
    ci_low            double precision,
    ci_high           double precision,
    n                 integer NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- --------------------------------------------------------------- synthetic

CREATE TABLE kpi_daily (
    scenario text NOT NULL,
    seed     integer NOT NULL,
    day      integer NOT NULL,
    variable text NOT NULL,
    value    double precision NOT NULL,
    PRIMARY KEY (scenario, seed, day, variable)
);

CREATE TABLE causal_true_edges (
    scenario text NOT NULL,
    source   text NOT NULL,
    target   text NOT NULL,
    lag      integer NOT NULL,
    coef     double precision NOT NULL,
    PRIMARY KEY (scenario, source, target, lag)
);

CREATE TABLE causal_edges (
    scenario text NOT NULL,
    seed     integer NOT NULL,
    method   text NOT NULL CHECK (method IN ('pcmci_parcorr', 'pcmci_cmiknn', 'xcorr')),
    source   text NOT NULL,
    target   text NOT NULL,
    lag      integer NOT NULL,
    strength double precision NOT NULL,
    p_value  double precision,
    PRIMARY KEY (scenario, seed, method, source, target, lag)
);

CREATE TABLE forecasts (
    seed       integer NOT NULL,
    target     text NOT NULL,
    origin_day integer NOT NULL,
    horizon    integer NOT NULL,
    q10        double precision,
    q50        double precision,
    q90        double precision,
    actual     double precision,
    method     text NOT NULL,
    PRIMARY KEY (seed, target, origin_day, horizon, method)
);

CREATE TABLE anomaly_events (
    event_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    seed      integer NOT NULL,
    target    text NOT NULL,
    type      text NOT NULL,
    start_day integer NOT NULL,
    end_day   integer NOT NULL CHECK (end_day >= start_day)
);

CREATE TABLE anomaly_alerts (
    seed   integer NOT NULL,
    target text NOT NULL,
    day    integer NOT NULL,
    method text NOT NULL,
    PRIMARY KEY (seed, target, day, method)
)
"""

# Reverse dependency order.
DOWN_TABLES = [
    "anomaly_alerts", "anomaly_events", "forecasts", "causal_edges", "causal_true_edges", "kpi_daily",
    "eval_results", "recommendations", "complaint_embeddings", "jev_calls", "confidence_thresholds",
    "complaint_actions", "complaints", "aspect_labels", "review_annotations", "models",
    "export_manifests", "annotation_runs", "mabsa_sentences", "split_snapshot", "reviews",
    "cause_actions", "subcategory_departments", "actions", "cause_factors", "departments",
    "subcategories", "main_categories", "schema_versions",
]
DOWN_TYPES = [
    "model_task", "eval_mode", "jev_target_type", "threshold_family", "action_status", "cause_status",
    "sentiment", "annotation_status", "run_kind", "review_split", "humir_class", "review_source",
]


def upgrade() -> None:
    for statement in UP.split(";\n\n"):
        statement = statement.strip().rstrip(";")
        if statement:
            op.execute(statement)


def downgrade() -> None:
    op.execute("ALTER TABLE annotation_runs DROP CONSTRAINT fk_annotation_runs_model")
    for table in DOWN_TABLES:
        op.execute(f"DROP TABLE {table}")
    for enum_type in DOWN_TYPES:
        op.execute(f"DROP TYPE {enum_type}")
    op.execute("DROP EXTENSION IF EXISTS vector")
