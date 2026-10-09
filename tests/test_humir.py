"""HUMIR cleaning and near-duplicate grouping on synthetic rows, plus the idempotent load."""

import csv

from sqlalchemy import text

from turotel.data import humir as h

LONG = "otel çok güzeldi personel ilgiliydi yemekler lezzetliydi havuz temizdi tekrar gelmek isteriz"


def _row(i, content, cls="Positive", type_="Hotel Review"):
    return {"ReviewId": str(i), "Type": type_, "Content": content, "Class": cls, "Split": "train", "Fold": "1"}


def _write(tmp_path, rows):
    path = tmp_path / "humir.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ReviewId", "Type", "Content", "Class", "Split", "Fold"], delimiter=";")
        w.writeheader()
        w.writerows(rows)
    return path


def test_only_hotel_rows(tmp_path):
    path = _write(tmp_path, [_row(1, LONG), _row(2, "film harikaydı", type_="Movie Review")])
    assert [r["ReviewId"] for r in h.read_hotel_rows(path)] == ["1"]


def test_exact_duplicates_collapse_to_lowest_id_and_short_reviews_stay():
    rows = [_row(5, LONG), _row(3, LONG, "Negative"), _row(9, "güzel"), _row(7, "Şişli İstanbul ğüşıöç")]
    kept, stats = h.dedupe_exact(rows)
    assert {r.review_id for r in kept} == {"humir-3", "humir-7", "humir-9"}
    assert stats["exact_duplicate_rows_removed"] == 1
    assert stats["duplicate_texts_with_conflicting_class"] == 1
    assert next(r for r in kept if r.review_id == "humir-9").word_len == 1
    assert next(r for r in kept if r.review_id == "humir-7").text == "Şişli İstanbul ğüşıöç"


def test_near_duplicates_share_a_group_and_distinct_texts_do_not():
    other = "oda kirliydi servis çok yavaştı kahvaltı yetersizdi bir daha asla gelmem fiyat da pahalıydı"
    reviews = [
        h.RawReview("a", LONG, "positive", 12),
        h.RawReview("b", "Harika! " + LONG + ".", "positive", 13),
        h.RawReview("c", other, "negative", 15),
        h.RawReview("d", "güzel", "positive", 1),
        h.RawReview("e", "Güzel!", "positive", 1),
    ]
    groups = h.assign_duplicate_groups(reviews)
    assert groups["a"] == groups["b"] == "dup-a"
    assert "c" not in groups
    assert groups["d"] == groups["e"]  # short texts group only when identical after normalisation


def test_turkish_lowercase():
    assert h.normalize("IŞIK İstanbul!") == "ışık istanbul"


def test_load_is_idempotent(db_session, tmp_path):
    path = _write(tmp_path, [_row(1, LONG), _row(2, LONG + " "), _row(3, "güzel", "Negative")])
    first = h.load_humir(db_session, path)
    assert first["inserted"] == 2
    n = db_session.execute(text("SELECT count(*) FROM reviews WHERE source = 'humir'")).scalar_one()
    assert n == 2
    second = h.load_humir(db_session, path)
    assert second["inserted"] == 0
