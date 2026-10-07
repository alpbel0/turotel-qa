"""Neo4j constraint definitions (docs/VERI_KATMANI.md section 2).

Each node type is keyed by the immutable Postgres id. Taxonomy nodes use the property `id`;
`Review` and `Complaint` use `review_id` / `complaint_id` (as in the recommendation query).
Idempotent (`IF NOT EXISTS`); the graph rebuild script (Task 5.2) calls this first.
The graph is derived data: it is rebuilt from Postgres and never written by hand.
"""

from neo4j import Driver

# (label, unique property)
UNIQUE_KEYS: tuple[tuple[str, str], ...] = (
    ("MainCategory", "id"),
    ("Subcategory", "id"),
    ("Department", "id"),
    ("CauseFactor", "id"),
    ("Action", "id"),
    ("Review", "review_id"),
    ("Complaint", "complaint_id"),
)


def constraint_name(label: str, prop: str) -> str:
    return f"{label.lower()}_{prop}_unique"


def constraint_statements() -> list[str]:
    return [
        f"CREATE CONSTRAINT {constraint_name(label, prop)} IF NOT EXISTS "
        f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
        for label, prop in UNIQUE_KEYS
    ]


def apply_constraints(driver: Driver) -> None:
    """Create all uniqueness constraints; running it again changes nothing."""
    with driver.session() as session:
        for statement in constraint_statements():
            session.run(statement).consume()
