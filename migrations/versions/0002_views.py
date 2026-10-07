"""Views: the leakage boundary (docs/VERI_KATMANI.md section 3, "View'lar").

PostgreSQL views take no parameters, so every view carries a `run_id` column; callers
filter `WHERE run_id = :run_id` and check the run's kind / is_frozen / validated_at
(see turotel.db.views). Views are defined only here.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Masks a field when its confidence is below the run's threshold for that family.
# No threshold row, or a NULL confidence (human labels) => no mask.
V_LABELS_MASKED = """
CREATE VIEW v_labels_masked AS
SELECT
    f.run_id,
    f.review_id,
    f.subcategory_id,
    CASE WHEN f.aspect_ok THEN f.status END                                      AS status,
    f.confidence,
    CASE WHEN f.aspect_ok THEN f.complaint_id END                                AS complaint_id,
    CASE WHEN f.aspect_ok AND f.department_ok THEN f.department_id END           AS department_id,
    CASE WHEN f.aspect_ok AND f.severity_ok THEN f.severity END                  AS severity,
    CASE WHEN f.aspect_ok AND f.cause_ok THEN f.cause_status END                 AS cause_status,
    CASE WHEN f.aspect_ok AND f.cause_ok THEN f.cause_factor_id END              AS cause_factor_id,
    CASE WHEN f.aspect_ok AND f.action_ok THEN f.action_status END               AS action_status,
    CASE WHEN f.aspect_ok AND f.action_ok AND f.action_status = 'recommended'
         THEN ARRAY(SELECT ca.action_id FROM complaint_actions ca
                    WHERE ca.complaint_id = f.complaint_id ORDER BY ca.action_id) END AS action_ids
FROM (
    SELECT
        al.run_id, al.review_id, al.subcategory_id, al.status, al.confidence,
        c.complaint_id, c.department_id, c.severity, c.cause_status, c.cause_factor_id, c.action_status,
        NOT (ta.threshold IS NOT NULL AND al.confidence IS NOT NULL AND al.confidence < ta.threshold)      AS aspect_ok,
        NOT (td.threshold IS NOT NULL AND c.department_conf IS NOT NULL AND c.department_conf < td.threshold) AS department_ok,
        NOT (ts.threshold IS NOT NULL AND c.severity_conf IS NOT NULL AND c.severity_conf < ts.threshold)  AS severity_ok,
        NOT (tc.threshold IS NOT NULL AND c.cause_conf IS NOT NULL AND c.cause_conf < tc.threshold)        AS cause_ok,
        NOT (tn.threshold IS NOT NULL AND c.action_conf IS NOT NULL AND c.action_conf < tn.threshold)      AS action_ok
    FROM aspect_labels al
    LEFT JOIN complaints c
           ON c.run_id = al.run_id AND c.review_id = al.review_id AND c.subcategory_id = al.subcategory_id
    LEFT JOIN confidence_thresholds ta ON ta.run_id = al.run_id AND ta.family = 'aspect'
    LEFT JOIN confidence_thresholds td ON td.run_id = al.run_id AND td.family = 'department'
    LEFT JOIN confidence_thresholds ts ON ts.run_id = al.run_id AND ts.family = 'severity'
    LEFT JOIN confidence_thresholds tc ON tc.run_id = al.run_id AND tc.family = 'cause'
    LEFT JOIN confidence_thresholds tn ON tn.run_id = al.run_id AND tn.family = 'action'
) f
"""

V_TRAIN_EXPORT = """
CREATE VIEW v_train_export AS
SELECT m.*, r.source, r.text, r.word_len, r.duplicate_group_id, r.split
FROM v_labels_masked m
JOIN reviews r ON r.review_id = m.review_id
WHERE r.split = 'train'
"""

V_SILVER_VAL_EXPORT = """
CREATE VIEW v_silver_val_export AS
SELECT m.*, r.source, r.text, r.word_len, r.duplicate_group_id, r.split
FROM v_labels_masked m
JOIN reviews r ON r.review_id = m.review_id
WHERE r.split = 'silver_val'
"""

# One row per surviving (unmasked) complaint; no review text.
V_GRAPH_TRAIN = """
CREATE VIEW v_graph_train AS
SELECT m.run_id, m.complaint_id, m.review_id, r.source, r.word_len,
       m.subcategory_id, m.department_id, m.severity,
       m.cause_status, m.cause_factor_id, m.action_status, m.action_ids
FROM v_labels_masked m
JOIN reviews r ON r.review_id = m.review_id
WHERE r.split = 'train' AND m.complaint_id IS NOT NULL
"""


def _gold_view(name: str, split: str) -> str:
    """Reference = human run, status=done, rows of one split. Raw (unresolved) taxonomy ids."""
    return f"""
CREATE VIEW {name} AS
SELECT ar.run_id, ar.schema_version, r.review_id, r.split,
       al.subcategory_id, al.status,
       c.complaint_id, c.department_id, c.severity,
       c.cause_status, c.cause_factor_id, c.action_status,
       ARRAY(SELECT ca.action_id FROM complaint_actions ca
             WHERE ca.complaint_id = c.complaint_id ORDER BY ca.action_id) AS action_ids
FROM annotation_runs ar
JOIN review_annotations ra ON ra.run_id = ar.run_id AND ra.status = 'done'
JOIN reviews r ON r.review_id = ra.review_id AND r.split = '{split}'
JOIN aspect_labels al ON al.run_id = ra.run_id AND al.review_id = ra.review_id
LEFT JOIN complaints c
       ON c.run_id = al.run_id AND c.review_id = al.review_id AND c.subcategory_id = al.subcategory_id
WHERE ar.kind = 'human'
"""


# external_real: human reference like the gold views. external_mabsa: reference is the mapped
# M-ABSA labels (mapped_labels), there is no human run (run_id NULL).
V_EXTERNAL_EVAL = """
CREATE VIEW v_external_eval AS
SELECT ar.run_id, ar.schema_version, r.review_id, r.split,
       al.subcategory_id, al.status,
       c.complaint_id, c.department_id, c.severity,
       c.cause_status, c.cause_factor_id, c.action_status,
       ARRAY(SELECT ca.action_id FROM complaint_actions ca
             WHERE ca.complaint_id = c.complaint_id ORDER BY ca.action_id) AS action_ids,
       NULL::jsonb AS mapped_labels
FROM annotation_runs ar
JOIN review_annotations ra ON ra.run_id = ar.run_id AND ra.status = 'done'
JOIN reviews r ON r.review_id = ra.review_id AND r.split = 'external_real'
JOIN aspect_labels al ON al.run_id = ra.run_id AND al.review_id = ra.review_id
LEFT JOIN complaints c
       ON c.run_id = al.run_id AND c.review_id = al.review_id AND c.subcategory_id = al.subcategory_id
WHERE ar.kind = 'human'
UNION ALL
SELECT NULL::bigint, NULL::integer, r.review_id, r.split,
       NULL::text, NULL::sentiment,
       NULL::bigint, NULL::text, NULL::smallint,
       NULL::cause_status, NULL::text, NULL::action_status,
       NULL::text[], ms.mapped_labels
FROM mabsa_sentences ms
JOIN reviews r ON r.review_id = ms.review_id AND r.split = 'external_mabsa'
WHERE ms.mapped_labels IS NOT NULL
"""

VIEWS = [
    ("v_labels_masked", V_LABELS_MASKED),
    ("v_train_export", V_TRAIN_EXPORT),
    ("v_silver_val_export", V_SILVER_VAL_EXPORT),
    ("v_graph_train", V_GRAPH_TRAIN),
    ("v_gold_dev_eval", _gold_view("v_gold_dev_eval", "gold_dev")),
    ("v_gold_test_eval", _gold_view("v_gold_test_eval", "gold_test")),
    ("v_external_eval", V_EXTERNAL_EVAL),
]


def upgrade() -> None:
    for _, sql in VIEWS:
        op.execute(sql.strip())


def downgrade() -> None:
    for name, _ in reversed(VIEWS):
        op.execute(f"DROP VIEW {name}")
