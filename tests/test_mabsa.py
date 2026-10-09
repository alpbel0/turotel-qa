"""M-ABSA parsing, category mapping and the idempotent load (synthetic files, test database)."""

import pytest
from sqlalchemy import text

from turotel.data import mabsa as m
from turotel.data import taxonomy as t


def test_apostrophes_in_terms_do_not_break_parsing():
    sentence, triples = m.parse_line(
        "Affinia'ya yakın.####[[\"x\", 'a b', 'positive']] ["
        "['Affinia'ya', 'hotel general', 'positive'], ['NULL', 'location general', 'negative']]"
    )
    assert sentence == "Affinia'ya yakın."
    assert ("Affinia'ya", "hotel general", "positive") in triples
    assert ("NULL", "location general", "negative") in triples


def test_empty_labels():
    assert m.parse_line("Merhaba.####[]") == ("Merhaba.", [])


def test_mapping_targets_exist_in_taxonomy():
    subs = {s for s, *_ in t.SUBCATEGORIES}
    mains = {i for i, _ in t.MAIN_CATEGORIES}
    for category, (level, target) in m.CATEGORY_MAP.items():
        if level == "subcategory":
            assert target in subs, category
        elif level == "main":
            assert target in mains, category
        else:
            assert target is None, category


def test_service_general_maps_only_to_main_category():
    assert m.CATEGORY_MAP["service general"] == ("main", "service_staff")
    mapped = m.map_triple("personel", "service general", "negative")
    assert mapped["subcategory_id"] is None and mapped["main_category_id"] == "service_staff"


def test_subcategory_mapping_also_gives_main():
    mapped = m.map_triple("oda", "rooms cleanliness", "positive")
    assert (mapped["subcategory_id"], mapped["main_category_id"]) == ("room_cleanliness", "room_bath")


def test_out_of_scope_category_is_not_scored():
    mapped = m.map_triple("NULL", "hotel miscellaneous", "positive")
    assert mapped["level"] is None and mapped["main_category_id"] is None


def _files(tmp_path):
    (tmp_path / "train.txt").write_text(
        "Oda temizdi.####[['Oda', 'rooms cleanliness', 'positive']]\nBoş cümle.####[]\n", encoding="utf-8"
    )
    (tmp_path / "dev.txt").write_text("Personel kaba.####[['Personel', 'service general', 'negative']]\n", encoding="utf-8")
    (tmp_path / "test.txt").write_text("Konum iyi.####[['NULL', 'location general', 'positive']]", encoding="utf-8")
    return tmp_path


def test_load_is_idempotent_and_marks_not_publishable(db_session, tmp_path):
    directory = _files(tmp_path)
    first = m.load_mabsa(db_session, directory)
    assert first == {"sentences": 4, "inserted_reviews": 4, "inserted_labels": 4}
    row = db_session.execute(
        text("SELECT source, split, publishable, humir_class FROM reviews WHERE review_id = 'mabsa-train-0000'")
    ).one()
    assert (row.source, row.split, row.publishable, row.humir_class) == ("mabsa", "external_mabsa", False, None)
    assert db_session.execute(text("SELECT count(*) FROM mabsa_sentences WHERE mapped_labels = '[]'::jsonb")).scalar_one() == 1
    second = m.load_mabsa(db_session, directory)
    assert second["inserted_reviews"] == 0 and second["inserted_labels"] == 0


def test_coverage_report_counts(tmp_path):
    report = m.coverage_report(m.read_sentences(_files(tmp_path)))
    assert report["sentences"] == 4 and report["unlabelled_sentences"] == 1
    assert report["labels"] == 3 and report["scored_subcategory"] == 1 and report["scored_main_only"] == 2
    assert "reservation_frontdesk" in report["main_categories_without_counterpart"]
    assert "safety" in report["main_categories_without_counterpart"]


def test_humir_snapshot_ignores_mabsa(db_session, tmp_path):
    from turotel.data import splits

    m.load_mabsa(db_session, _files(tmp_path))
    assert splits.snapshot_hash(db_session) == splits.snapshot_hash(db_session)
    with pytest.raises(splits.SplitError):
        splits.assign_splits(db_session)  # no HUMIR rows: mabsa never enters the humir split
