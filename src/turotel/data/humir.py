"""HUMIR hotel reviews: parse, de-duplicate, group near-duplicates, load into `reviews`.

Method (also in README):
- Only `Type == "Hotel Review"` rows of the `;`-separated, UTF-8-BOM CSV are used.
- Exact duplicates (identical raw text after trimming) collapse to the row with the lowest
  ReviewId. Short reviews (< 5 words) are kept.
- Near-duplicates: texts are normalised (Turkish-aware lowercase, punctuation removed) and compared by the
  Jaccard similarity of their word 3-gram shingles. Pairs with similarity >= NEAR_DUP_THRESHOLD are joined
  (connected components) and share a `duplicate_group_id`. Texts with fewer than MIN_WORDS_FOR_NEAR words
  are only grouped when their normalised text is identical.
- `duplicate_group_id` is set only for groups with two or more reviews; NULL means "no duplicate", so a
  review without a group is its own unit for splitting.

Run against the development database (after `alembic upgrade head`):

    uv run python -m turotel.data.humir
"""

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from turotel.config import PROJECT_ROOT
from turotel.db.models import Review

HUMIR_CSV = PROJECT_ROOT / "data" / "raw" / "humir" / "HUMIRSentimentDatasets.csv"
HOTEL_TYPE = "Hotel Review"
SHINGLE_SIZE = 3
NEAR_DUP_THRESHOLD = 0.4  # pairs >= 0.4 were all real duplicates on inspection; boilerplate matches start below 0.3
MIN_WORDS_FOR_NEAR = 8
MAX_POSTING = 200  # shingles shared by more documents than this are too generic to propose candidates
SHORT_REVIEW_WORDS = 5

_WS = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class RawReview:
    review_id: str  # "humir-<ReviewId>"
    text: str
    humir_class: str  # "positive" | "negative"
    word_len: int


def clean_text(text: str) -> str:
    return _WS.sub(" ", text).strip()


def normalize(text: str) -> str:
    """Turkish-aware lowercase, punctuation removed, whitespace collapsed (for similarity only)."""
    lowered = text.replace("İ", "i").replace("I", "ı").lower()
    return _WS.sub(" ", _NON_WORD.sub(" ", lowered)).strip()


def read_hotel_rows(path: Path = HUMIR_CSV) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle, delimiter=";") if row["Type"] == HOTEL_TYPE]


def dedupe_exact(rows: list[dict[str, str]]) -> tuple[list[RawReview], dict[str, int]]:
    """Collapse exact duplicates; returns the kept reviews and counters for the load report."""
    ordered = sorted(rows, key=lambda r: int(r["ReviewId"]))
    kept: dict[str, RawReview] = {}
    classes: dict[str, set[str]] = defaultdict(set)
    for row in ordered:
        key = row["Content"].strip()
        classes[key].add(row["Class"])
        if key and key not in kept:
            text = clean_text(key)
            kept[key] = RawReview(
                review_id=f"humir-{row['ReviewId']}",
                text=text,
                humir_class=row["Class"].lower(),
                word_len=len(text.split()),
            )
    stats = {
        "rows": len(rows),
        "unique_texts": len(kept),
        "exact_duplicate_rows_removed": len(rows) - len(kept),
        "duplicate_texts_with_conflicting_class": sum(1 for t, c in classes.items() if len(c) > 1),
    }
    return list(kept.values()), stats


def _shingles(norm: str) -> set[int]:
    words = norm.split()
    return {hash(tuple(words[i : i + SHINGLE_SIZE])) for i in range(len(words) - SHINGLE_SIZE + 1)}


def similar_pairs(texts: list[str], threshold: float = NEAR_DUP_THRESHOLD) -> list[tuple[int, int, float]]:
    """All (i, j, jaccard) with i < j whose normalised texts are near-duplicates."""
    norms = [normalize(t) for t in texts]
    pairs: dict[tuple[int, int], float] = {}

    by_norm: dict[str, list[int]] = defaultdict(list)
    for i, norm in enumerate(norms):
        by_norm[norm].append(i)
    for members in by_norm.values():
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                pairs[(members[a], members[b])] = 1.0

    long_ids = [i for i, n in enumerate(norms) if len(n.split()) >= MIN_WORDS_FOR_NEAR]
    shingles = {i: _shingles(norms[i]) for i in long_ids}
    postings: dict[int, list[int]] = defaultdict(list)
    for i in long_ids:
        for s in shingles[i]:
            postings[s].append(i)
    for i in long_ids:
        overlap: Counter[int] = Counter()
        for s in shingles[i]:
            posting = postings[s]
            if len(posting) <= MAX_POSTING:
                overlap.update(j for j in posting if j > i)
        for j, shared in overlap.items():
            union = len(shingles[i]) + len(shingles[j]) - shared
            score = shared / union
            if score >= threshold:
                pairs[(i, j)] = max(pairs.get((i, j), 0.0), score)
    return [(i, j, s) for (i, j), s in sorted(pairs.items())]


def assign_duplicate_groups(reviews: list[RawReview], threshold: float = NEAR_DUP_THRESHOLD) -> dict[str, str]:
    """review_id -> duplicate_group_id for every review that belongs to a group of two or more."""
    parent = list(range(len(reviews)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j, _ in similar_pairs([r.text for r in reviews], threshold):
        parent[find(i)] = find(j)
    members: dict[int, list[int]] = defaultdict(list)
    for i in range(len(reviews)):
        members[find(i)].append(i)
    groups: dict[str, str] = {}
    for ids in members.values():
        if len(ids) > 1:
            group_id = "dup-" + min(reviews[i].review_id for i in ids)
            groups.update({reviews[i].review_id: group_id for i in ids})
    return groups


def load_humir(session: Session, path: Path = HUMIR_CSV) -> dict[str, int]:
    """Insert missing HUMIR reviews; existing rows are never touched. The caller commits."""
    reviews, stats = dedupe_exact(read_hotel_rows(path))
    groups = assign_duplicate_groups(reviews)
    rows = [
        {
            "review_id": r.review_id,
            "source": "humir",
            "text": r.text,
            "humir_class": r.humir_class,
            "word_len": r.word_len,
            "duplicate_group_id": groups.get(r.review_id),
        }
        for r in reviews
    ]
    inserted = 0
    for start in range(0, len(rows), 2000):
        stmt = (
            insert(Review)
            .values(rows[start : start + 2000])
            .on_conflict_do_nothing(index_elements=["review_id"])
            .returning(Review.review_id)
        )
        inserted += len(session.execute(stmt).all())
    return {
        **stats,
        "near_duplicate_groups": len(set(groups.values())),
        "reviews_in_groups": len(groups),
        "inserted": inserted,
    }


def main() -> int:
    from turotel.db.session import make_session_factory

    with make_session_factory()() as session:
        report = load_humir(session)
        session.commit()
    for key, value in report.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
