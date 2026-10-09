"""Real-review loading: checks, idempotency, external_real placement, snapshot untouched, DB rejects publishable."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from turotel.data import humir as h
from turotel.data import real as r
from turotel.data import splits

LONG = "otel çok güzeldi personel ilgiliydi yemekler lezzetliydi havuz temizdi tekrar gelmek isteriz"


def _csv(tmp_path, texts, delimiter=";"):
    path = tmp_path / "real.csv"
    lines = [f"id{delimiter}text"] + [f'{i}{delimiter}"{t}"' for i, t in enumerate(texts)]
    path.write_text("\n".join(lines), encoding="utf-8-sig")
    return path


def test_checks_skip_empty_short_and_repeats():
    kept, stats = r.check_texts([LONG, "  ", "güzel otel", LONG.capitalize() + ".", LONG + "!", "Oda  temiz  ve  sessizdi"])
    assert kept == [LONG, "Oda temiz ve sessizdi"]
    assert (stats["empty"], stats["too_short"], stats["repeated_in_file"]) == (1, 1, 2)


def test_read_csv_either_delimiter_and_plain_lines(tmp_path):
    assert r.read_texts(_csv(tmp_path, ["a b c", "d e f"], ";")) == ["a b c", "d e f"]
    assert r.read_texts(_csv(tmp_path, ["a b c"], ",")) == ["a b c"]
    plain = tmp_path / "r.txt"
    plain.write_text("bir iki üç\n\nüç dört beş\n", encoding="utf-8")
    assert r.read_texts(plain) == ["bir iki üç", "", "üç dört beş"]


def test_csv_without_text_column_is_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("a;b\n1;2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        r.read_texts(path)


def test_load_marks_external_real_and_is_idempotent(db_session, tmp_path):
    path = _csv(tmp_path, [LONG, "Oda temiz ve sessizdi", "kısa"])
    first = r.load_real(db_session, path)
    assert (first["valid"], first["inserted"], first["too_short"]) == (2, 2, 1)
    rows = db_session.execute(text("SELECT source, split, publishable, humir_class FROM reviews WHERE source = 'real'")).all()
    assert len(rows) == 2 and all(tuple(x) == ("real", "external_real", False, None) for x in rows)
    second = r.load_real(db_session, path)
    assert second["inserted"] == 0 and second["already_present"] == 2


def test_humir_snapshot_unchanged_by_real_load(db_session, tmp_path):
    humir_path = tmp_path / "humir.csv"
    humir_path.write_text("ReviewId;Type;Content;Class;Split;Fold\n1;Hotel Review;" + LONG + ";Positive;train;1\n", encoding="utf-8-sig")
    h.load_humir(db_session, humir_path)
    before = splits.snapshot_hash(db_session)
    r.load_real(db_session, _csv(tmp_path, [LONG + " ama farklı bir yorum", "Oda temiz ve sessizdi"]))
    assert splits.snapshot_hash(db_session) == before


def test_database_rejects_publishable_real(db_session, tmp_path):
    r.load_real(db_session, _csv(tmp_path, [LONG]))
    with pytest.raises(IntegrityError):
        db_session.execute(text("UPDATE reviews SET publishable = true WHERE source = 'real'"))


def test_meta_columns_are_stored_and_bad_stars_rejected(db_session, tmp_path):
    path = tmp_path / "meta.csv"
    path.write_text(
        "text,source,hotel_type,stars_given\n"
        f'"{LONG}",google,tatil,5\n"Oda temiz ve sessizdi",google,,\n',
        encoding="utf-8-sig",
    )
    r.load_real(db_session, path)
    rows = db_session.execute(text("SELECT hotel_type, stars_given FROM reviews WHERE source = 'real' ORDER BY word_len DESC")).all()
    assert [tuple(x) for x in rows] == [("tatil", 5), (None, None)]
    bad = tmp_path / "bad.csv"
    bad.write_text("text,stars_given\n" + f'"{LONG} yeni",7\n', encoding="utf-8")
    with pytest.raises(ValueError):
        r.load_real(db_session, bad)
