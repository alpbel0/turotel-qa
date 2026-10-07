# Faz 0 — İskelet

## Faz amacı

Projenin fiziksel iskeletini kurmak: uv paketi ve `docs/PROJE_PLANI.md` §8.1'deki klasör yapısı, Docker
Compose ile ayağa kalkan PostgreSQL + pgvector ve Neo4j, `docs/VERI_KATMANI.md` §3'teki tüm tabloları,
kısıtları ve view'ları kuran Alembic migration'ları ve geliştirme verisine dokunamayan bir test ortamı.
Bu fazda iş mantığı yazılmaz. İki konu baştan doğru kurulur: DDL'nin tek kaynağının migration'lar olması
(view'lar sızıntı sınırıdır) ve testlerin geliştirme veritabanlarını silememesi.
Takvim: Hafta 1 (`docs/PROJE_PLANI.md` §6).

## Task 0.1 — uv paketi ve klasör iskeleti

**Repo:** `turotel-qa`
**Alan:** `root`
**Durum:** Tamamlandı (2026-10-07)
**Bağımlılıklar:** —

**Referanslar:** `docs/PROJE_PLANI.md` §8, §8.1

**Hedef dosyalar:** `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `.env.example`,
`src/turotel/__init__.py`, `src/turotel/config.py`, `tests/`

### Checklist

- [x] `uv init --package` ile paket kur (hatchling, `packages = ["src/turotel"]`),
      Python 3.11.
- [x] Çekirdek bağımlılıklar: SQLAlchemy, Alembic, psycopg, neo4j, pyarrow, python-dotenv. Gruplar
      `labeling`, `ml`, `causal`, `demo`, `dev`; `default-groups = ["dev"]`. TimesFM hiçbir grupta yok.
- [x] §8.1'deki klasörleri oluştur (`src/turotel/` alt paketleri, `migrations/`, `notebooks/`, `tests/`,
      `results/`, `docs/report/`, `data/exports/`, `artifacts/`).
- [x] `config.py`: tüm ayarlar `.env`'den, tek yerden. `.env.example` tüm anahtar adlarıyla, gizli olmayan
      yerel geliştirme şifreleri ve boş Jev anahtarıyla; repoda düz metin anahtar yok.
- [x] `.gitignore`: `.venv/`, `.env`, `data/raw/`, `data/exports/`, `artifacts/`, `__pycache__/`,
      `.ipynb_checkpoints/`. `uv.lock` ve `.python-version` repoda.
- [x] Boş pytest suite'i `uv run pytest` ile yeşil koşsun.

**Kabul kriteri:** Temiz bir klonda `uv sync` ve `uv run pytest` hatasız bitiyor; `uv run python -c "import
turotel"` çalışıyor; repoda hiçbir sır dosyası yok.

## Task 0.2 — Docker Compose: Postgres + pgvector ve Neo4j

**Repo:** `turotel-qa`
**Alan:** `infra`
**Durum:** Tamamlandı (2026-10-07)
**Bağımlılıklar:** Task 0.1

**Referanslar:** `docs/PROJE_PLANI.md` §8.1, `docs/VERI_KATMANI.md` §1

**Hedef dosyalar:** `docker-compose.yml`, `.env.example`

### Checklist

- [x] `pgvector/pgvector:pg17` ve `neo4j:5-community` servisleri; veriler named volume'larda (proje
      klasöründe değil).
- [x] Portlar yalnız `127.0.0.1`: Postgres 5432, Neo4j 7474 ve 7687. Uygulama servisi yok; kod host'ta
      çalışır.
- [x] Şifreler `.env`'den, `${VAR:?…}` biçiminde: `.env` eksikse compose hemen hata verir.
- [x] Her servise gerçek sağlık kontrolü (Postgres'e sorgu, Neo4j'ye Cypher ping; port açık olması değil).
- [x] `test` profili: ayrı Neo4j (`127.0.0.1:7688`, ayrı volume). Geliştirme ve test volume'ları hiçbir
      şeyi paylaşmaz.
- [x] Windows'un rezerve port aralıklarıyla çakışma kontrolü (`netsh interface ipv4 show excludedportrange`);
      çakışan varsa başka port seçilip belgelenir.
      (Çakışma yok: rezerve aralıklar 50000–50059, 50174–50273, 56018–56417; port değişmedi.)

**Kabul kriteri:** `docker compose up -d` sonrası iki servis healthy; `docker compose --profile test up -d`
test Neo4j'sini ayrıca kaldırıyor; host'tan `127.0.0.1` adresleriyle bağlanılabiliyor, dış ağ arayüzünden
bağlanılamıyor.

## Task 0.3 — Alembic: tüm Postgres şeması ve view'lar

**Repo:** `turotel-qa`
**Alan:** `db`
**Durum:** Tamamlandı (2026-10-07)
**Bağımlılıklar:** Task 0.2

**Referanslar:** `docs/VERI_KATMANI.md` §3

**Hedef dosyalar:** `alembic.ini`, `migrations/`, `src/turotel/db/`

### Checklist

- [x] `CREATE EXTENSION vector`.
- [x] Veri, taksonomi, etiket, Jev önbelleği, embedding/öneri, model/sonuç ve sentetik tablolarının hepsi
      (`docs/VERI_KATMANI.md` §3'teki alanlarla). ENUM'lar, PK/FK'ler, `complaints` → `aspect_labels`
      bileşik FK, UNIQUE'ler.
- [x] Satır içi kurallar CHECK ile: ciddiyet 1–4; ciddiyet 1 ⇒ neden boş; `cause_status=selected` ⇔ neden
      dolu; `source ∈ {real, mabsa}` ⇒ `publishable=false`. Satırlar arası kurallar trigger ile **değil**,
      `validate_run` ile (Task 1.5).
- [x] View'lar yalnız migration'da: `v_labels_masked`, `v_train_export`, `v_silver_val_export`,
      `v_graph_train`, `v_gold_dev_eval`, `v_gold_test_eval`, `v_external_eval`. View'lar `run_id` sütununu
      taşır (view'lar parametre almaz).
- [x] `src/turotel/db/`: SQLAlchemy modelleri, bağlantı ve view sorguları; **DDL yok**. View'ı okuyan
      sorgular `WHERE run_id = :run_id` ve koşu koşullarını açıkça uygular.

**Kabul kriteri:** Boş veritabanında `uv run alembic upgrade head` baştan sona çalışıyor, ikinci kez hiçbir
şey değiştirmeden bitiyor, `downgrade base` temiz geri alıyor; ciddiyeti 1 olup nedeni dolu bir şikâyet
veritabanına yazılamıyor.

**Uygulama notları:** İki migration var: `0001_tables` (extension, ENUM'lar, tüm tablolar) ve `0002_views`
(7 view). Taksonomi kimlikleri `text`; `complaint_embeddings.embedding` boyutsuz `vector` (boyut
encoder seçilince belli olur). `v_gold_*_eval` / `v_external_eval` referansı `kind=human` ve
`status=done` ile seçer; "kör" koşu ayrımı view'da değil, çağıran sorguda `run_id` ile yapılır.
`v_external_eval` M-ABSA için `mapped_labels` taşır (`run_id` NULL). `merged_into` çözümü
`turotel.db.views.resolve_merged_id` ile.

## Task 0.4 — Geliştirmeden ayrı test ortamı

**Repo:** `turotel-qa`
**Alan:** `infra`, `db`
**Durum:** Tamamlandı (2026-10-07)
**Bağımlılıklar:** Task 0.3

**Referanslar:** `docs/PROJE_PLANI.md` §8.1 (Testler)

**Hedef dosyalar:** `src/turotel/db/` (test DB kurulumu), `tests/conftest.py`

### Checklist

- [x] İdempotent test DB kurulumu: yönetim DB'sine bağlanır, adın `_test` ile bittiğini doğrular, yoksa
      `turotel_test`'i transaction dışında oluşturur, sonra `alembic upgrade head`.
- [x] Koruma: test fixture'ları adı `_test` ile bitmeyen Postgres'e ve 7688 dışındaki Neo4j'ye yazmayı
      reddeder.
- [x] Testler `.env`'deki geliştirme adreslerini **okumaz**; test adresleri ayrı ayardan gelir.
- [x] Tek komut: test Neo4j profilini kaldır → test DB kurulumu → `uv run pytest`.

**Kabul kriteri:** Geliştirme veritabanlarında veri varken testler koşuyor; geliştirme Postgres'i ve
geliştirme Neo4j'si test öncesi ve sonrası birebir aynı (satır/düğüm sayıları); yanlış bağlantı adresiyle
başlatılan test hemen hata veriyor.

**Uygulama notları:** Kurulum ve korumalar `src/turotel/db/testing.py`; test adresleri `config.load_test_settings()`
ile yalnız `TEST_*` anahtarlarından (`.env.example`'da). Tek komut: `uv run python -m turotel.db.testing`
(ek pytest argümanları geçirilebilir). Her test `db_session` ile transaction içinde çalışır ve geri alınır.
Kalıcı testler: `tests/test_test_env.py` (korumalar, yanlış adres) ve `tests/test_schema.py` (0.3'ün CHECK'leri
ve view'ları). Geliştirme DB'lerinin test öncesi/sonrası aynılığı otomatik testle değil, işaretli veri
koyularak elle doğrulandı (Postgres satır sayıları ve Neo4j düğüm sayısı aynı kaldı).

## Task 0.5 — Neo4j şema dosyası

**Repo:** `turotel-qa`
**Alan:** `graph`
**Durum:** Tamamlandı (2026-10-07)
**Bağımlılıklar:** Task 0.2

**Referanslar:** `docs/VERI_KATMANI.md` §2

**Hedef dosyalar:** `src/turotel/recommend/` (Neo4j şema/constraint tanımı)

### Checklist

- [x] Constraint'ler: her düğüm türünde Postgres'teki değişmez `id` benzersiz (`MainCategory`, `Subcategory`,
      `Department`, `CauseFactor`, `Action`, `Review`, `Complaint`).
- [x] Tekrar çalıştırılınca bozulmayacak biçimde (`IF NOT EXISTS`). Yeniden kurma betiği (Task 5.2) önce
      bunu çağırır.
- [x] Neo4j'ye elle yazılmaz kuralı README'de belirtilir.

**Kabul kriteri:** Boş Neo4j'de constraint'ler kuruluyor; ikinci çalıştırma hiçbir şey değiştirmiyor; aynı
`id` ile ikinci düğüm oluşturulamıyor.

**Uygulama notları:** Dosya `src/turotel/recommend/graph_schema.py` (`apply_constraints(driver)`); constraint adları
`<etiket>_<özellik>_unique`. Özellik adı taksonomi düğümlerinde `id`, `Review` için `review_id`, `Complaint` için
`complaint_id` (`docs/VERI_KATMANI.md` §2'deki öneri sorgusuyla uyumlu). Testler `tests/test_graph_schema.py`
(test Neo4j'de). Geliştirme Neo4j'sine constraint'ler henüz uygulanmadı; Task 5.2 yeniden kurma betiği önce bunu
çağıracak. Faz 0 tamamlandı.
