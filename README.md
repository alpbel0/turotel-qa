# turotel-qa

Turkish hotel-review aspect sentiment, complaint root-cause and action recommendation.
Plan: `docs/PROJE_PLANI.md`, data layer: `docs/VERI_KATMANI.md`, task order: `roadmap/`.

## Setup

```
cp .env.example .env            # local non-secret dev defaults; put the real Jev key only in .env
uv sync
docker compose up -d            # Postgres + pgvector and Neo4j, bound to 127.0.0.1
uv run alembic upgrade head     # the only source of Postgres DDL (tables and views)
```

## Tests

```
uv run python -m turotel.db.testing    # starts the test Neo4j, sets up turotel_test, runs pytest
```

Tests use a separate Postgres database (name must end in `_test`) and a separate Neo4j
(`127.0.0.1:7688`, `test` compose profile); they refuse anything else.

## Neo4j is derived data: never write to it by hand

Postgres is the source of truth. The Neo4j graph is always rebuilt from Postgres by the
rebuild script (Task 5.2), which first applies the constraints in
`src/turotel/recommend/graph_schema.py` and then deletes and reloads the whole graph.
Hand-written nodes or relationships would be wiped by the next rebuild and are never a valid result.

## Data: HUMIR hotel reviews

`data/raw/humir/HUMIRSentimentDatasets.csv` is gitignored. Download it from Hugging Face
`Alaettin/Humir-Sentiment-Datasets`, then load it (after `alembic upgrade head`):

    uv run python -m turotel.data.humir

Only `Type == "Hotel Review"` rows are used (11,600). Exact duplicates (identical text after trimming) collapse to the
lowest ReviewId: 11,167 reviews remain (docs/VERI_NOTLARI.md says 11,189 because it did not trim; 22 texts differ only
by edge whitespace). Short reviews (< 5 words) are kept: 455 remain after de-duplication (657 before; most removed
ones were repeated one-liners). 97 near-duplicate groups cover 200 reviews (91 pairs, 6 triples). Near-duplicates share a `duplicate_group_id`
(`dup-<lowest review_id>`): normalised text (Turkish-aware lowercase, punctuation removed), Jaccard similarity of
word 3-gram shingles >= 0.4, connected components; texts under 8 words group only when identical after
normalisation. The 0.4 threshold comes from inspecting pairs: everything >= 0.4 was the same review with small edits,
boilerplate matches ("genel olarak memnun kaldım") start below 0.3. `duplicate_group_id` is NULL for reviews that have
no duplicate, so splitting must treat NULL as a group of one. The load is idempotent. The ready-made HUMIR train/test
split is not used.

## Data: splits (`turotel.data.splits`)

    uv run python -m turotel.data.splits assign            # once; a second run is refused
    uv run python -m turotel.data.splits verify            # checks the latest split_snapshot and duplicate groups
    uv run python -m turotel.data.splits transfer-reserve 300|200|150   # gold_reserve, exactly once
    uv run python -m turotel.data.splits reset             # only while no annotation run exists

Seed 42. Gold pool: 400 reviews drawn only from reviews without a duplicate group (no length filter), 70% negative
/ 30% positive inside each of `gold_dev` (100), `gold_test` (200) and `gold_reserve` (100). The rest is split by
duplicate group into `train` (9,690) and `silver_val` (1,077). `verify` fails if a split was edited by hand.
`transfer-reserve`: 300 moves the reserve to `gold_test`; 200 moves it to `train`; 150 also moves 50 stratified
`gold_test` reviews to `train`. Every assignment and transfer writes a new `split_snapshot`.

## Data: M-ABSA (external topic exam only)

`data/raw/mabsa_tr_hotel/{train,dev,test}.txt` (Hugging Face `Multilingual-NLP/M-ABSA`, `hotel/tr/`; gitignored).

    uv run python -m turotel.data.mabsa

Loads 2,147 sentences into `reviews` (`source=mabsa`, `split=external_mabsa`, `publishable=false`; not in any
`split_snapshot`) and the original plus mapped labels into `mabsa_sentences`. The text is machine-translated, so
results are reported as "tested on translated Turkish". The category mapping (`CATEGORY_MAP`) and its coverage are
described in `docs/VERI_NOTLARI.md`.
