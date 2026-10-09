"""Real (user-collected) reviews: light checks and load into `reviews` as `external_real`.

The collection protocol and personal-data scrubbing belong to the user; this module only checks that a text is
not empty, not too short and not a repeat, then inserts it. Input is a UTF-8 file: a `.csv` with a `text` column
(`;` or `,` separated; optional `hotel_type` and `stars_given` 1-5 columns are stored, other columns are ignored)
or any other extension read as one review per line.

- review_id is `real-<first 12 hex of sha256(cleaned text)>`, so re-loading the same file (or a re-ordered one)
  inserts nothing new.
- Rows are `source=real`, `split=external_real`, `publishable=false` (the database rejects `publishable=true`
  for this source) and stay outside `split_snapshot`, which only covers `source=humir`.
- Texts with fewer than MIN_WORDS words, empty texts and repeats inside the file are skipped and counted.

    uv run python -m turotel.data.real path/to/reviews.csv
"""

import csv
import hashlib
import sys
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from turotel.data.humir import clean_text, normalize
from turotel.db.models import Review

MIN_WORDS = 3
META_COLUMNS = ("text", "hotel_type", "stars_given")


def real_review_id(text: str) -> str:
    return "real-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def read_records(path: Path) -> list[dict[str, str]]:
    """One dict per input row with keys text / hotel_type / stars_given (empty string when absent)."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        if path.suffix.lower() != ".csv":
            return [{"text": line} for line in handle.read().splitlines()]
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = ";" if sample.split("\n", 1)[0].count(";") > sample.split("\n", 1)[0].count(",") else ","
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames or "text" not in reader.fieldnames:
            raise ValueError("CSV needs a 'text' column")
        return [{k: (row.get(k) or "").strip() if k != "text" else row["text"] or "" for k in META_COLUMNS} for row in reader]


def read_texts(path: Path) -> list[str]:
    return [r["text"] for r in read_records(path)]


def parse_stars(value: str) -> int | None:
    if not value:
        return None
    try:
        stars = int(float(value))
    except ValueError:
        raise ValueError(f"stars_given must be 1-5, got {value!r}") from None
    if not 1 <= stars <= 5:
        raise ValueError(f"stars_given must be 1-5, got {value!r}")
    return stars


def check_records(records: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Records with cleaned text that pass the empty / too-short / repeat checks, plus load-report counters."""
    kept: list[dict[str, str]] = []
    seen: set[str] = set()
    stats = {"rows": len(records), "empty": 0, "too_short": 0, "repeated_in_file": 0}
    for record in records:
        text = clean_text(record["text"])
        if not text:
            stats["empty"] += 1
        elif len(text.split()) < MIN_WORDS:
            stats["too_short"] += 1
        elif (key := normalize(text)) in seen:
            stats["repeated_in_file"] += 1
        else:
            seen.add(key)
            kept.append({**record, "text": text})
    return kept, stats


def check_texts(raw: list[str]) -> tuple[list[str], dict[str, int]]:
    kept, stats = check_records([{"text": item} for item in raw])
    return [r["text"] for r in kept], stats


def load_real(session: Session, path: Path) -> dict[str, int]:
    """Insert missing real reviews; existing rows are never touched. The caller commits."""
    records, stats = check_records(read_records(path))
    rows = [
        {
            "review_id": real_review_id(r["text"]),
            "source": "real",
            "text": r["text"],
            "word_len": len(r["text"].split()),
            "split": "external_real",
            "split_assigned_at": func.now(),
            "publishable": False,
            "hotel_type": r.get("hotel_type") or None,
            "stars_given": parse_stars(r.get("stars_given", "")),
        }
        for r in records
    ]
    inserted = 0
    for start in range(0, len(rows), 1000):
        stmt = (
            insert(Review)
            .values(rows[start : start + 1000])
            .on_conflict_do_nothing(index_elements=["review_id"])
            .returning(Review.review_id)
        )
        inserted += len(session.execute(stmt).all())
    return {**stats, "valid": len(rows), "inserted": inserted, "already_present": len(rows) - inserted}


def main(argv: list[str]) -> int:
    from turotel.db.session import make_session_factory

    if len(argv) != 1:
        print("usage: python -m turotel.data.real <file>", file=sys.stderr)
        return 2
    with make_session_factory()() as session:
        report = load_real(session, Path(argv[0]))
        session.commit()
    for key, value in report.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
