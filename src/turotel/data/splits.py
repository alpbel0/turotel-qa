"""One-time, locked train/validation/gold splits of the HUMIR reviews (docs/PROJE_PLANI.md section 5.1).

Rules:
- Gold pool (400 = 100 gold_dev + 200 gold_test + 100 gold_reserve) is drawn with a fixed seed, 70% negative /
  30% positive in total and inside each gold split, only from reviews without a duplicate group, and without
  looking at any Jev output. No other filter (short and long reviews stay eligible).
- The rest is split by duplicate group (a group never spans two splits): ~90% train, ~10% silver_val.
- Splits are assigned once (`split_assigned_at`); assigning again is refused. `reset` is allowed only while no
  annotation run exists. The single exception is `transfer_reserve`, which moves gold_reserve exactly once.
- Every assignment/transfer writes a `split_snapshot` (sha256 over sorted review_id + split); `verify` fails when
  the data no longer matches the latest snapshot or a duplicate group spans two splits.

Commands (development database):

    uv run python -m turotel.data.splits assign
    uv run python -m turotel.data.splits verify
    uv run python -m turotel.data.splits transfer-reserve {300|200|150}
    uv run python -m turotel.data.splits reset
"""

import hashlib
import random
import sys
from collections import defaultdict

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from turotel.db.models import AnnotationRun, Review, ReviewAnnotation, SplitSnapshot

SEED = 42
SCOPE = "source=humir"
GOLD_SIZES = {"gold_dev": 100, "gold_test": 200, "gold_reserve": 100}
NEGATIVE_SHARE = 0.7
SILVER_SHARE = 0.1
FINAL_TEST_SIZES = (300, 200, 150)


class SplitError(RuntimeError):
    """A split rule was violated; nothing was changed."""


def _humir(session: Session):
    return select(Review).where(Review.source == "humir")


def _counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(Review.split, func.count()).where(Review.source == "humir").group_by(Review.split)
    ).all()
    return {str(split): n for split, n in rows if split is not None}


def snapshot_hash(session: Session) -> str:
    rows = session.execute(
        select(Review.review_id, Review.split).where(Review.source == "humir").order_by(Review.review_id)
    ).all()
    payload = "\n".join(f"{review_id}\t{split}" for review_id, split in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_snapshot(session: Session) -> SplitSnapshot:
    snapshot = SplitSnapshot(scope=SCOPE, sha256=snapshot_hash(session), counts=_counts(session))
    session.add(snapshot)
    session.flush()
    return snapshot


def _set_split(session: Session, review_ids: list[str], split: str | None, stamp: bool = False) -> None:
    if not review_ids:
        return
    values: dict = {"split": split}
    if stamp:
        values["split_assigned_at"] = func.now() if split is not None else None
    session.execute(update(Review).where(Review.review_id.in_(review_ids)).values(**values))


def _draw_gold(singletons: list[Review], rng: random.Random) -> dict[str, list[str]]:
    """Stratified draw: every gold split has the 70/30 negative/positive ratio."""
    pools = {
        "negative": sorted(r.review_id for r in singletons if r.humir_class == "negative"),
        "positive": sorted(r.review_id for r in singletons if r.humir_class == "positive"),
    }
    for pool in pools.values():
        rng.shuffle(pool)
    result: dict[str, list[str]] = {}
    for split, size in GOLD_SIZES.items():
        n_neg = round(size * NEGATIVE_SHARE)
        if len(pools["negative"]) < n_neg or len(pools["positive"]) < size - n_neg:
            raise SplitError("not enough duplicate-free reviews to draw the gold pool")
        result[split] = [pools["negative"].pop() for _ in range(n_neg)] + [
            pools["positive"].pop() for _ in range(size - n_neg)
        ]
    return result


def assign_splits(session: Session, seed: int = SEED) -> SplitSnapshot:
    """Assign every HUMIR review to a split, once. The caller commits."""
    reviews = session.scalars(_humir(session)).all()
    if not reviews:
        raise SplitError("no HUMIR reviews loaded; run `python -m turotel.data.humir` first")
    if any(r.split_assigned_at is not None or r.split is not None for r in reviews):
        raise SplitError("splits are already assigned; use `reset` (only before labelling starts)")

    rng = random.Random(seed)
    gold = _draw_gold([r for r in reviews if r.duplicate_group_id is None], rng)
    gold_ids = {rid for ids in gold.values() for rid in ids}

    units: dict[str, list[str]] = defaultdict(list)  # a duplicate group or a lone review
    for r in sorted(reviews, key=lambda r: r.review_id):
        if r.review_id not in gold_ids:
            units[r.duplicate_group_id or r.review_id].append(r.review_id)
    keys = sorted(units)
    rng.shuffle(keys)
    silver_target = round(SILVER_SHARE * sum(len(v) for v in units.values()))
    silver: list[str] = []
    train: list[str] = []
    for key in keys:
        (silver if len(silver) < silver_target else train).extend(units[key])

    for split, ids in {**gold, "silver_val": silver, "train": train}.items():
        _set_split(session, ids, split, stamp=True)
    return write_snapshot(session)


def verify_splits(session: Session) -> SplitSnapshot:
    """Raise SplitError unless the data matches the latest snapshot and duplicate groups are intact."""
    snapshot = session.scalars(
        select(SplitSnapshot).where(SplitSnapshot.scope == SCOPE).order_by(SplitSnapshot.snapshot_id.desc()).limit(1)
    ).first()
    if snapshot is None:
        raise SplitError("no split_snapshot exists")
    if snapshot_hash(session) != snapshot.sha256:
        raise SplitError(f"splits differ from snapshot {snapshot.snapshot_id}: a split was changed by hand")
    spread = session.execute(
        text(
            "SELECT duplicate_group_id FROM reviews WHERE source = 'humir' AND duplicate_group_id IS NOT NULL "
            "GROUP BY duplicate_group_id HAVING count(DISTINCT split) > 1"
        )
    ).all()
    if spread:
        raise SplitError(f"{len(spread)} duplicate group(s) span more than one split")
    return snapshot


def reset_splits(session: Session) -> None:
    """Clear all HUMIR splits. Allowed only while no annotation run exists. The caller commits."""
    if session.scalar(select(func.count()).select_from(AnnotationRun)):
        raise SplitError("annotation runs exist; splits can no longer be reset")
    session.execute(
        update(Review).where(Review.source == "humir").values(split=None, split_assigned_at=None)
    )


def transfer_reserve(session: Session, final_test_size: int, seed: int = SEED) -> SplitSnapshot:
    """Move gold_reserve exactly once: 300 -> gold_test; 200 or 150 -> train (150 also moves 50 gold_test)."""
    if final_test_size not in FINAL_TEST_SIZES:
        raise SplitError(f"final test size must be one of {FINAL_TEST_SIZES}")
    reserve = session.scalars(_humir(session).where(Review.split == "gold_reserve")).all()
    if not reserve:
        raise SplitError("gold_reserve is empty: the reserve transfer was already done")
    verify_splits(session)

    reserve_ids = sorted(r.review_id for r in reserve)
    if final_test_size == 300:
        _set_split(session, reserve_ids, "gold_test")
    else:
        _set_split(session, reserve_ids, "train")
        if final_test_size == 150:
            test = session.scalars(_humir(session).where(Review.split == "gold_test")).all()
            rng = random.Random(seed)
            moved: list[str] = []
            for cls, n in (("negative", round(50 * NEGATIVE_SHARE)), ("positive", 50 - round(50 * NEGATIVE_SHARE))):
                ids = sorted(r.review_id for r in test if r.humir_class == cls)
                rng.shuffle(ids)
                moved.extend(ids[:n])
            if session.scalar(
                select(func.count()).select_from(ReviewAnnotation).where(ReviewAnnotation.review_id.in_(moved))
            ):
                raise SplitError("some gold_test reviews to be moved are already labelled")
            _set_split(session, moved, "train")
    return write_snapshot(session)


def main(argv: list[str]) -> int:
    from turotel.db.session import make_session_factory

    command = argv[0] if argv else ""
    with make_session_factory()() as session:
        try:
            if command == "assign":
                snapshot = assign_splits(session)
            elif command == "verify":
                snapshot = verify_splits(session)
            elif command == "transfer-reserve" and len(argv) == 2 and argv[1].isdigit():
                snapshot = transfer_reserve(session, int(argv[1]))
            elif command == "reset":
                reset_splits(session)
                session.commit()
                print("splits cleared")
                return 0
            else:
                print(__doc__)
                return 2
        except SplitError as error:
            session.rollback()
            print(f"refused: {error}")
            return 1
        session.commit()
    counts = dict(sorted(snapshot.counts.items()))
    print(f"snapshot {snapshot.snapshot_id} sha256={snapshot.sha256}\ncounts={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
