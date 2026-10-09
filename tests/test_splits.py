"""Split assignment rules on synthetic reviews (test database, rolled back after each test)."""

import pytest
from sqlalchemy import text

from turotel.data import splits as s
from turotel.db.models import Review


@pytest.fixture
def reviews(db_session):
    """600 negative + 400 positive reviews without duplicates, plus 30 duplicate pairs."""
    rows = []
    for i in range(1000):
        rows.append(Review(review_id=f"humir-{i:05d}", source="humir", text=f"t{i}", word_len=1,
                           humir_class="negative" if i < 600 else "positive"))
    for g in range(30):
        for k in range(2):
            rows.append(Review(review_id=f"humir-d{g:03d}{k}", source="humir", text=f"d{g}{k}", word_len=1,
                               humir_class="negative", duplicate_group_id=f"dup-{g}"))
    db_session.add_all(rows)
    db_session.flush()
    return rows


def _map(session):
    return dict(session.execute(text("SELECT review_id, split FROM reviews WHERE source = 'humir'")).all())


def _count(session, split, cls=None):
    sql = "SELECT count(*) FROM reviews WHERE split = :s" + (" AND humir_class = :c" if cls else "")
    return session.execute(text(sql), {"s": split, "c": cls}).scalar_one()


def test_assign_matches_plan(db_session, reviews):
    snapshot = s.assign_splits(db_session)
    assert (_count(db_session, "gold_dev"), _count(db_session, "gold_test"), _count(db_session, "gold_reserve")) == (100, 200, 100)
    for split, size in s.GOLD_SIZES.items():
        assert _count(db_session, split, "negative") == round(size * 0.7)
        assert _count(db_session, split, "positive") == size - round(size * 0.7)
    rest = 1060 - 400
    assert _count(db_session, "silver_val") == round(rest * 0.1)
    assert _count(db_session, "train") == rest - round(rest * 0.1)
    assert snapshot.counts["gold_test"] == 200
    assert db_session.execute(text("SELECT count(*) FROM reviews WHERE split_assigned_at IS NULL")).scalar_one() == 0
    gold_in_groups = db_session.execute(
        text("SELECT count(*) FROM reviews WHERE split::text LIKE 'gold%' AND duplicate_group_id IS NOT NULL")
    ).scalar_one()
    assert gold_in_groups == 0
    assert s.verify_splits(db_session).snapshot_id == snapshot.snapshot_id


def test_no_duplicate_group_spans_two_splits(db_session, reviews):
    s.assign_splits(db_session)
    spread = db_session.execute(
        text("SELECT count(*) FROM (SELECT 1 FROM reviews WHERE duplicate_group_id IS NOT NULL "
             "GROUP BY duplicate_group_id HAVING count(DISTINCT split) > 1) x")
    ).scalar_one()
    assert spread == 0


def test_second_assignment_is_refused_and_changes_nothing(db_session, reviews):
    s.assign_splits(db_session)
    before = _map(db_session)
    with pytest.raises(s.SplitError):
        s.assign_splits(db_session)
    assert _map(db_session) == before


def test_same_seed_gives_same_splits(db_session, reviews):
    s.assign_splits(db_session)
    first = _map(db_session)
    s.reset_splits(db_session)
    assert all(v is None for v in _map(db_session).values())
    s.assign_splits(db_session)
    assert _map(db_session) == first


def test_hand_edit_fails_verification(db_session, reviews):
    s.assign_splits(db_session)
    db_session.execute(text("UPDATE reviews SET split = 'train' WHERE review_id = 'humir-00000'"))
    db_session.execute(text("UPDATE reviews SET split = 'silver_val' WHERE review_id = 'humir-00001'"))
    with pytest.raises(s.SplitError):
        s.verify_splits(db_session)


def test_reset_refused_after_labelling_started(db_session, reviews):
    s.assign_splits(db_session)
    db_session.execute(text("INSERT INTO schema_versions VALUES (1, now(), 'v1') ON CONFLICT DO NOTHING"))
    db_session.execute(
        text("INSERT INTO annotation_runs (kind, annotator_or_model, schema_version) VALUES ('human','x',1)")
    )
    with pytest.raises(s.SplitError):
        s.reset_splits(db_session)


@pytest.mark.parametrize(
    "size,expected",
    [
        (300, {"gold_test": 300, "train": None, "gold_reserve": 0}),
        (200, {"gold_test": 200, "gold_reserve": 0}),
        (150, {"gold_test": 150, "gold_reserve": 0}),
    ],
)
def test_reserve_transfer_once(db_session, reviews, size, expected):
    s.assign_splits(db_session)
    train_before = _count(db_session, "train")
    snapshot = s.transfer_reserve(db_session, size)
    for split, n in expected.items():
        if n is not None:
            assert _count(db_session, split) == n
    assert _count(db_session, "gold_dev") == 100
    assert _count(db_session, "train") == train_before + {300: 0, 200: 100, 150: 150}[size]
    if size == 150:
        assert _count(db_session, "gold_test", "negative") == 105
    assert s.verify_splits(db_session).snapshot_id == snapshot.snapshot_id
    with pytest.raises(s.SplitError):
        s.transfer_reserve(db_session, size)
