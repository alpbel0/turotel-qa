"""M-ABSA Turkish hotel sentences: external topic exam only (docs/VERI_NOTLARI.md, docs/PROJE_PLANI.md 5.1).

The text is machine-translated English hotel reviews (see VERI_NOTLARI.md), so results are reported as
"tested on translated Turkish". Sentences go to `reviews` (`source=mabsa`, `split=external_mabsa`,
`publishable=false`, not part of any `split_snapshot`); the original labels go to `mabsa_sentences.raw_labels`
and the labels mapped to our schema to `mabsa_sentences.mapped_labels`.

Mapping level (decision 2026-10-07): M-ABSA categories are coarser than our 29 subcategories, so
- a clean 1:1 match is scored at subcategory level (`level="subcategory"`),
- an ambiguous category is scored at main-category level only (`level="main"`),
- categories with no safe counterpart are listed as out of scope (`level=None`) and are not scored; they are
  NOT counted as "not mentioned".
`service general` maps only to the main category "Hizmet ve personel".

    uv run python -m turotel.data.mabsa
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from turotel.config import PROJECT_ROOT
from turotel.data.taxonomy import MAIN_CATEGORIES, SUBCATEGORIES
from turotel.db.models import MabsaSentence, Review

MABSA_DIR = PROJECT_ROOT / "data" / "raw" / "mabsa_tr_hotel"
FILES = ("train", "dev", "test")
SEPARATOR = "####"
# Turkish apostrophes break ast.literal_eval, so triples are matched with a regex.
_TRIPLE = re.compile(r"\['(.*?)', '([a-z_ ]+)', '(positive|negative|neutral)'\]")

# M-ABSA category -> (level, target id in our schema or None)
CATEGORY_MAP: dict[str, tuple[str | None, str | None]] = {
    "hotel general": ("subcategory", "general_satisfaction"),
    "hotel quality": ("subcategory", "hotel_quality_expectation"),
    "hotel design_features": ("subcategory", "atmosphere_design_noise"),
    "hotel comfort": ("main", "general_experience"),
    "hotel prices": ("main", "price_value"),
    "hotel cleanliness": (None, None),
    "hotel miscellaneous": (None, None),
    "rooms general": ("main", "room_bath"),
    "rooms design_features": ("main", "room_bath"),
    "rooms quality": ("main", "room_bath"),
    "rooms cleanliness": ("subcategory", "room_cleanliness"),
    "rooms comfort": ("subcategory", "bed_comfort_climate"),
    "rooms prices": ("main", "price_value"),
    "rooms miscellaneous": (None, None),
    "room_amenities general": ("main", "room_bath"),
    "room_amenities quality": ("main", "room_bath"),
    "room_amenities design_features": ("main", "room_bath"),
    "room_amenities comfort": ("main", "room_bath"),
    "room_amenities cleanliness": ("main", "room_bath"),
    "room_amenities prices": ("main", "price_value"),
    "food_drinks quality": ("subcategory", "food_quality_taste"),
    "food_drinks style_options": ("subcategory", "food_variety_choice"),
    "food_drinks prices": ("subcategory", "food_price"),
    "food_drinks miscellaneous": ("main", "food_beverage"),
    "service general": ("main", "service_staff"),
    "location general": ("main", "location_access"),
    "facilities general": ("main", "facilities_activities"),
    "facilities quality": ("main", "facilities_activities"),
    "facilities design_features": ("main", "facilities_activities"),
    "facilities comfort": ("main", "facilities_activities"),
    "facilities cleanliness": ("main", "facilities_activities"),
    "facilities miscellaneous": ("main", "facilities_activities"),
    "facilities prices": ("main", "price_value"),
    # source artifact: a polarity value leaked into the category field; not interpretable
    "polarity positive": (None, None),
}


@dataclass(frozen=True)
class Sentence:
    review_id: str
    orig_split: str
    text: str
    triples: list[tuple[str, str, str]]  # (term, category, polarity); term "NULL" = implicit aspect


def parse_line(line: str) -> tuple[str, list[tuple[str, str, str]]]:
    text, _, labels = line.partition(SEPARATOR)
    return text.strip(), _TRIPLE.findall(labels)


def read_sentences(directory: Path = MABSA_DIR) -> list[Sentence]:
    sentences: list[Sentence] = []
    for name in FILES:
        lines = (directory / f"{name}.txt").read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines):
            if SEPARATOR not in line:
                continue
            text, triples = parse_line(line)
            if text:
                sentences.append(Sentence(f"mabsa-{name}-{number:04d}", name, text, triples))
    return sentences


def map_triple(term: str, category: str, polarity: str) -> dict:
    level, target = CATEGORY_MAP.get(category, (None, None))
    return {
        "term": term,
        "category": category,
        "polarity": polarity,
        "level": level,
        "subcategory_id": target if level == "subcategory" else None,
        "main_category_id": (
            target if level == "main" else next(m for s, m, _, _ in SUBCATEGORIES if s == target)
        )
        if target
        else None,
    }


def coverage_report(sentences: list[Sentence]) -> dict:
    """Counts for VERI_NOTLARI.md: what is scored at which level, what is out of scope."""
    total = scored_sub = scored_main = out = unknown = 0
    unlabelled = sum(1 for s in sentences if not s.triples)
    for s in sentences:
        for _, category, _ in s.triples:
            total += 1
            if category not in CATEGORY_MAP:
                unknown += 1
                continue
            level = CATEGORY_MAP[category][0]
            if level == "subcategory":
                scored_sub += 1
            elif level == "main":
                scored_main += 1
            else:
                out += 1
    sub_targets = {t for lvl, t in CATEGORY_MAP.values() if lvl == "subcategory"}
    main_targets = {t for lvl, t in CATEGORY_MAP.values() if lvl == "main"} | {
        m for s, m, _, _ in SUBCATEGORIES if s in sub_targets
    }
    return {
        "sentences": len(sentences),
        "unlabelled_sentences": unlabelled,
        "labels": total,
        "scored_subcategory": scored_sub,
        "scored_main_only": scored_main,
        "out_of_scope_labels": out,
        "unknown_categories": unknown,
        "subcategories_scored": sorted(sub_targets),
        "subcategories_without_counterpart": sorted({s for s, *_ in SUBCATEGORIES} - sub_targets),
        "main_categories_without_counterpart": sorted({m for m, _ in MAIN_CATEGORIES} - main_targets),
    }


def load_mabsa(session: Session, directory: Path = MABSA_DIR) -> dict[str, int]:
    """Insert missing sentences; existing rows are never touched. The caller commits."""
    sentences = read_sentences(directory)
    review_rows = [
        {
            "review_id": s.review_id,
            "source": "mabsa",
            "text": s.text,
            "word_len": len(s.text.split()),
            "split": "external_mabsa",
            "split_assigned_at": func.now(),
            "publishable": False,
        }
        for s in sentences
    ]
    label_rows = [
        {
            "review_id": s.review_id,
            "orig_split": s.orig_split,
            "raw_labels": [list(t) for t in s.triples],
            "mapped_labels": [map_triple(*t) for t in s.triples],
        }
        for s in sentences
    ]
    inserted = labelled = 0
    for start in range(0, len(sentences), 1000):
        stmt = (
            insert(Review)
            .values(review_rows[start : start + 1000])
            .on_conflict_do_nothing(index_elements=["review_id"])
            .returning(Review.review_id)
        )
        inserted += len(session.execute(stmt).all())
        stmt = (
            insert(MabsaSentence)
            .values(label_rows[start : start + 1000])
            .on_conflict_do_nothing(index_elements=["review_id"])
            .returning(MabsaSentence.review_id)
        )
        labelled += len(session.execute(stmt).all())
    return {"sentences": len(sentences), "inserted_reviews": inserted, "inserted_labels": labelled}


def main() -> int:
    from turotel.db.session import make_session_factory

    with make_session_factory()() as session:
        result = load_mabsa(session)
        session.commit()
    print(result)
    print(json.dumps(coverage_report(read_sentences()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
