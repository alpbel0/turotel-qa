"""Post-load validation of an annotation run (docs/VERI_KATMANI.md section 3, `validate_run`).

Cross-row rules are checked here, not by triggers. Export, graph and embedding jobs read only validated runs.

Rules (a violation carries the rule name and the row key):
- R1_complaint_label: a complaint's label is `negative`; every `negative` label has exactly one complaint.
- R2_label_set: `done` review has a label for every subcategory valid in the run's schema version; `skip` has none;
  labels never exist for a review without a `review_annotations` row.
- R3_severity_status (human/jev): severity 1 => cause/action `out_of_scope`; severity >= 2 => cause in
  {selected, insufficient_evidence} and action in {recommended, not_needed, insufficient_evidence}.
- R4_action_count (human/jev): `recommended` => 1..max actions (jev 1, human 3); other statuses => 0.
- R5_kind_nulls: human/jev status fields are never NULL; model rows have no cause/action fields and no actions.
- R6_taxonomy_ids: taxonomy ids are valid in the run's schema version.
- R6_duplicate_group: a duplicate group never spans two splits.

Command (development database):

    uv run python -m turotel.validation RUN_ID
"""

import sys
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session

MAX_ACTIONS = {"jev": 1, "human": 3}
CAUSE_STATUSES_SEV2 = ("selected", "insufficient_evidence")
ACTION_STATUSES_SEV2 = ("recommended", "not_needed", "insufficient_evidence")


@dataclass(frozen=True)
class Violation:
    rule: str
    key: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule} [{self.key}]: {self.detail}"


@dataclass
class ValidationReport:
    run_id: int
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def rules(self) -> set[str]:
        return {v.rule for v in self.violations}

    def __str__(self) -> str:
        if self.ok:
            return f"run {self.run_id}: valid"
        lines = [f"run {self.run_id}: {len(self.violations)} violation(s)"]
        lines += [f"  {v}" for v in self.violations]
        return "\n".join(lines)


def _literals(values: tuple[str, ...]) -> str:
    """SQL list of constant enum names (module constants only, never user input)."""
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def _valid_in(alias: str) -> str:
    return f"{alias}.introduced_in <= :v AND ({alias}.retired_in IS NULL OR :v < {alias}.retired_in)"


def _rows(session: Session, sql: str, **params):
    return session.execute(text(sql), params).all()


def _r1_complaint_label(session: Session, run_id: int) -> list[Violation]:
    out = [
        Violation("R1_complaint_label", f"complaint:{cid}", f"complaint on a {status} label ({rev}/{sub})")
        for cid, rev, sub, status in _rows(
            session,
            "SELECT c.complaint_id, c.review_id, c.subcategory_id, l.status FROM complaints c "
            "JOIN aspect_labels l USING (run_id, review_id, subcategory_id) "
            "WHERE c.run_id = :r AND l.status <> 'negative' ORDER BY 1",
            r=run_id,
        )
    ]
    out += [
        Violation("R1_complaint_label", f"label:{rev}/{sub}", "negative label without a complaint")
        for rev, sub in _rows(
            session,
            "SELECT l.review_id, l.subcategory_id FROM aspect_labels l WHERE l.run_id = :r AND l.status = 'negative' "
            "AND NOT EXISTS (SELECT 1 FROM complaints c WHERE c.run_id = l.run_id AND c.review_id = l.review_id "
            "AND c.subcategory_id = l.subcategory_id) ORDER BY 1, 2",
            r=run_id,
        )
    ]
    return out


def _r2_label_set(session: Session, run_id: int, version: int) -> list[Violation]:
    out = [
        Violation("R2_label_set", f"review:{rev}", f"done review misses {len(subs)} subcategory label(s): {', '.join(subs)}")
        for rev, subs in _rows(
            session,
            "SELECT ra.review_id, array_agg(s.id ORDER BY s.id) FROM review_annotations ra "
            f"CROSS JOIN subcategories s WHERE ra.run_id = :r AND ra.status = 'done' AND {_valid_in('s')} "
            "AND NOT EXISTS (SELECT 1 FROM aspect_labels l WHERE l.run_id = ra.run_id AND l.review_id = ra.review_id "
            "AND l.subcategory_id = s.id) GROUP BY ra.review_id ORDER BY 1",
            r=run_id,
            v=version,
        )
    ]
    out += [
        Violation("R2_label_set", f"review:{rev}", f"skipped review has {n} label(s)")
        for rev, n in _rows(
            session,
            "SELECT ra.review_id, count(*) FROM review_annotations ra JOIN aspect_labels l USING (run_id, review_id) "
            "WHERE ra.run_id = :r AND ra.status = 'skip' GROUP BY ra.review_id ORDER BY 1",
            r=run_id,
        )
    ]
    out += [
        Violation("R2_label_set", f"review:{rev}", f"{n} label(s) but no review_annotations row")
        for rev, n in _rows(
            session,
            "SELECT l.review_id, count(*) FROM aspect_labels l WHERE l.run_id = :r AND NOT EXISTS "
            "(SELECT 1 FROM review_annotations ra WHERE ra.run_id = l.run_id AND ra.review_id = l.review_id) "
            "GROUP BY l.review_id ORDER BY 1",
            r=run_id,
        )
    ]
    return out


def _r3_severity_status(session: Session, run_id: int) -> list[Violation]:
    rows = _rows(
        session,
        "SELECT complaint_id, severity, cause_status::text, action_status::text FROM complaints "
        "WHERE run_id = :r AND ((severity = 1 AND (cause_status IS DISTINCT FROM 'out_of_scope' "
        "OR action_status IS DISTINCT FROM 'out_of_scope')) "
        f"OR (severity >= 2 AND (cause_status IS NULL OR cause_status::text NOT IN {_literals(CAUSE_STATUSES_SEV2)} "
        f"OR action_status IS NULL OR action_status::text NOT IN {_literals(ACTION_STATUSES_SEV2)}))) ORDER BY 1",
        r=run_id,
    )
    return [
        Violation("R3_severity_status", f"complaint:{cid}", f"severity {sev} with cause={cs}, action={act}")
        for cid, sev, cs, act in rows
    ]


def _r4_action_count(session: Session, run_id: int, kind: str) -> list[Violation]:
    if kind not in MAX_ACTIONS:
        return []
    limit = MAX_ACTIONS[kind]
    rows = _rows(
        session,
        "SELECT c.complaint_id, c.action_status::text, count(a.action_id) FROM complaints c "
        "LEFT JOIN complaint_actions a USING (complaint_id) WHERE c.run_id = :r GROUP BY 1, 2 ORDER BY 1",
        r=run_id,
    )
    out = []
    for cid, status, n in rows:
        if status == "recommended" and not 1 <= n <= limit:
            out.append(Violation("R4_action_count", f"complaint:{cid}", f"recommended with {n} action(s), expected 1..{limit}"))
        elif status != "recommended" and n:
            out.append(Violation("R4_action_count", f"complaint:{cid}", f"action_status={status} but {n} action(s)"))
    return out


def _r5_kind_nulls(session: Session, run_id: int, kind: str) -> list[Violation]:
    if kind in MAX_ACTIONS:
        return [
            Violation("R5_kind_nulls", f"complaint:{cid}", f"{kind} row with NULL cause_status/action_status")
            for (cid,) in _rows(
                session,
                "SELECT complaint_id FROM complaints WHERE run_id = :r "
                "AND (cause_status IS NULL OR action_status IS NULL) ORDER BY 1",
                r=run_id,
            )
        ]
    return [
        Violation("R5_kind_nulls", f"complaint:{cid}", "model row has cause/action fields or actions")
        for (cid,) in _rows(
            session,
            "SELECT c.complaint_id FROM complaints c WHERE c.run_id = :r AND (c.cause_status IS NOT NULL "
            "OR c.cause_factor_id IS NOT NULL OR c.cause_conf IS NOT NULL OR c.action_status IS NOT NULL "
            "OR c.action_conf IS NOT NULL OR EXISTS (SELECT 1 FROM complaint_actions a "
            "WHERE a.complaint_id = c.complaint_id)) ORDER BY 1",
            r=run_id,
        )
    ]


def _r6_taxonomy_ids(session: Session, run_id: int, version: int) -> list[Violation]:
    checks = [
        ("subcategory", "aspect_labels l", "l.subcategory_id", "subcategories", "l.run_id = :r",
         "l.review_id || '/' || l.subcategory_id"),
        ("department", "complaints c", "c.department_id", "departments", "c.run_id = :r", "c.complaint_id::text"),
        ("cause factor", "complaints c", "c.cause_factor_id", "cause_factors", "c.run_id = :r", "c.complaint_id::text"),
        ("action", "complaint_actions ca JOIN complaints c USING (complaint_id)", "ca.action_id", "actions",
         "c.run_id = :r", "ca.complaint_id::text || '/' || ca.action_id"),
    ]
    out = []
    for label, source, column, table, where, key in checks:
        for k, ident in _rows(
            session,
            f"SELECT {key}, {column} FROM {source} WHERE {where} AND {column} IS NOT NULL AND NOT EXISTS "
            f"(SELECT 1 FROM {table} t WHERE t.id = {column} AND {_valid_in('t')}) ORDER BY 1",
            r=run_id,
            v=version,
        ):
            prefix = "label" if label == "subcategory" else "complaint"
            out.append(Violation("R6_taxonomy_ids", f"{prefix}:{k}", f"{label} {ident!r} not valid in schema v{version}"))
    return out


def _r6_duplicate_groups(session: Session, run_id: int) -> list[Violation]:
    return [
        Violation("R6_duplicate_group", f"group:{gid}", f"duplicate group spans {n} splits")
        for gid, n in _rows(
            session,
            "SELECT duplicate_group_id, count(DISTINCT split) FROM reviews WHERE duplicate_group_id IN "
            "(SELECT DISTINCT r.duplicate_group_id FROM reviews r WHERE r.duplicate_group_id IS NOT NULL AND "
            "r.review_id IN (SELECT review_id FROM review_annotations WHERE run_id = :r UNION "
            "SELECT review_id FROM aspect_labels WHERE run_id = :r)) "
            "GROUP BY duplicate_group_id HAVING count(DISTINCT split) > 1 ORDER BY 1",
            r=run_id,
        )
    ]


def find_violations(session: Session, run_id: int) -> list[Violation]:
    run = _rows(session, "SELECT kind::text, schema_version FROM annotation_runs WHERE run_id = :r", r=run_id)
    if not run:
        raise ValueError(f"annotation run {run_id} does not exist")
    kind, version = run[0]
    return [
        *_r1_complaint_label(session, run_id),
        *_r2_label_set(session, run_id, version),
        *(_r3_severity_status(session, run_id) if kind in MAX_ACTIONS else []),
        *_r4_action_count(session, run_id, kind),
        *_r5_kind_nulls(session, run_id, kind),
        *_r6_taxonomy_ids(session, run_id, version),
        *_r6_duplicate_groups(session, run_id),
    ]


def validate_run(session: Session, run_id: int) -> ValidationReport:
    """Check every rule. A clean run gets `validated_at`; a run with violations loses any earlier one.

    The caller commits.
    """
    report = ValidationReport(run_id, find_violations(session, run_id))
    stamp = "now()" if report.ok else "NULL"
    session.execute(text(f"UPDATE annotation_runs SET validated_at = {stamp} WHERE run_id = :r"), {"r": run_id})
    return report


def clear_validation(session: Session, run_id: int) -> None:
    """Drop `validated_at` (e.g. after a confidence threshold changed); validation must run again. Caller commits."""
    result = session.execute(text("UPDATE annotation_runs SET validated_at = NULL WHERE run_id = :r"), {"r": run_id})
    if result.rowcount == 0:
        raise ValueError(f"annotation run {run_id} does not exist")


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].isdigit():
        print("usage: python -m turotel.validation RUN_ID", file=sys.stderr)
        return 2
    from turotel.db.session import make_session_factory

    with make_session_factory()() as session:
        report = validate_run(session, int(argv[0]))
        session.commit()
    print(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
