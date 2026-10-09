# TurOtel-QM — Veri Katmanı

> Son güncelleme: 2026-10-06. Codex `gpt-5.6-sol` (medium) ve OpenCode Grok 4.7 ile 3 tur değerlendirildi;
> değişiklik geçmişi `KARARLAR.md`'de. Kapsam: veritabanları, graf modeli, tablolar, doğrulama ve veri akışları.
> **İlke:** aşırı mühendislik yok; ürünleştirme (auth, API servisi, CI/CD, HA, trigger zinciri) yok.

## 1. Genel yapı

| Bileşen | Rol |
|---|---|
| **PostgreSQL 17 + pgvector** | Asıl kaynak: yorumlar, bölmeler, etiketler, Jev cevapları, model tahminleri, embedding'ler, deney sonuçları |
| **Neo4j 5 Community** (eklentisiz) | Türev bilgi grafı; her zaman Postgres'ten betikle yeniden kurulur, elle yazılmaz |
| `docker-compose.yml` | İkisi yerelde, tek komutla |
| Python | SQLAlchemy + Alembic (sürümlü migration), psycopg 3, resmi `neo4j` sürücüsü |

- Benzerlik araması yalnız pgvector'da; nedensellik/KPI verisi yalnız Postgres'te.
- Herkese açık yayının (HF Space) şekli Hafta 12'de kararlaştırılır (ücretsiz Space'te DB çalıştırmak zor;
  muhtemelen dışa aktarılmış anlık görüntü).

## 2. Graf modeli (Neo4j)

İki katman. Düğümlerde Postgres'teki değişmez `id` ve `schema_version` tutulur; `name` yalnız gösterim içindir.

### Katman A — Şema katmanı
Düğümler: `MainCategory` (9), `Subcategory` (29), `Department` (11), `CauseFactor` (13, `group` özelliği),
`Action` (13). "Kanıt yetersiz" gibi durum kodları düğüm değildir. Yalnız koşunun şema sürümünde geçerli
kimlikler yüklenir.
```
(Subcategory)-[:BELONGS_TO]->(MainCategory)
(Subcategory)-[:LIKELY_DEPARTMENT {source:"guideline"}]->(Department)   // skora ve geri çekilmeye girmez
(CauseFactor)-[:TYPICAL_ACTION {source:"schema"}]->(Action)              // skora ve geri çekilmeye girmez
```
Rehber kenarları yalnız gösterim ve "veri uzman beklentisiyle örtüşüyor mu" karşılaştırması içindir.

### Katman B — Vaka katmanı
Kaynak: tek dondurulmuş ve doğrulanmış Jev koşusu, yalnız `train` bölmesi, yalnız maskesiz alanlar.
Düğümler: `Review` (review_id, source, word_len; metin yok), `Complaint` (complaint_id, severity).
```
(Review)-[:HAS_COMPLAINT]->(Complaint)
(Complaint)-[:ABOUT]->(Subcategory)
(Complaint)-[:ASSIGNED_TO]->(Department)     // departman maskeliyse yok
(Complaint)-[:LIKELY_CAUSE]->(CauseFactor)  // ciddiyet ≥ 2, cause_status=selected, maskesiz
(Complaint)-[:SUGGESTED_ACTION]->(Action)   // ciddiyet ≥ 2, action_status=recommended, maskesiz
```
Ciddiyet düğüm değil, şikâyet özelliğidir (benzer vaka sıralamasında küçük bonus).

### Bilerek yok
- `SIMILAR_TO` kenarları, GDS/Louvain: benzerlik pgvector'da; kopyası bayatlar.
- Özet kenarları (alt→neden, neden→aksiyon): uç uca eklenince hiçbir vakada birlikte geçmeyen yapay zincir üretir.
- Sentetik KPI/nedensellik alt grafı: gerçek şikâyet grafıyla karışmasın.
- `MENTIONS` (olumlu/nötr bahsedilmeler): duygu Postgres'te; öneri sorgusu kullanmıyor.
- Otel düğümü: HUMIR'de otel bilgisi yok.
- Altın set, gerçek yorumlar, model tahminleri: sızıntı; Postgres'te kalır.

### Öneri akışı
1. Sorgu şikâyeti: alt kategori, departman, ciddiyet (oracle'da altından, uçtan uca modda model tahmininden).
2. Graf: tam yol desteği = (dep, alt, neden, aksiyon) yolunu taşıyan farklı şikâyet sayısı. Destek eşiğin
   altındaysa geri çekilme: dep+alt → alt → ana → genel çoğunluk → sus. Eşik min 5, {5,10,15,20} arasından MRR
   ile. n, yumuşatılmış koşullu olasılık ve PPMI yalnız bu tam yollardan hesaplanır.
3. pgvector: aynı alt kategoride exact en yakın eğitim şikâyetleri (yetmezse ana kategori) → gösterilen 3 benzer
   vaka ve sıralamada ek sinyal.
4. Çıktı `recommendations` tablosuna: aksiyon, neden, destek, geri çekilme seviyesi, kullanılan komşu kimlikleri.

```cypher
MATCH (s:Complaint)-[:ABOUT]->(:Subcategory {id:$sub}),
      (s)-[:ASSIGNED_TO]->(:Department {id:$dep}),
      (s)-[:LIKELY_CAUSE]->(c:CauseFactor),
      (s)-[:SUGGESTED_ACTION]->(a:Action)
RETURN c.id, a.id, count(DISTINCT s) AS support, collect(s.complaint_id)[..5] AS sample_cases
ORDER BY support DESC
```

### Yeniden kurma sözleşmesi
1. `run_id` kontrolü: `kind=jev`, `is_frozen`, `validated_at` dolu, `split_snapshot` uyumlu; değilse dur.
2. Constraint'leri kur → tüm grafı sil.
3. Katman A'yı koşunun şema sürümünde geçerli taksonomi kimlikleriyle yükle.
4. Katman B'yi `v_graph_train` view'ından yükle.
5. Düğüm/kenar sayılarını **aynı view'ın** toplamlarıyla karşılaştır; uyuşmazsa hata.

## 3. Postgres şeması

### Veri
- `reviews`: review_id, source (humir/real/mabsa), text, humir_class, word_len, duplicate_group_id,
  split ENUM (train / silver_val / gold_dev / gold_test / gold_reserve / external_real / external_mabsa), split_assigned_at,
  publishable (CHECK: source ∈ {real, mabsa} ⇒ publishable=false)
  hotel_type text, stars_given smallint 1-5 (yalnız `source=real`'de dolu; migration 0003)
- `split_snapshot`: created_at, kapsam (`source=humir`), sha256 (sıralı review_id+split), bölme başına sayılar.
  Bölme betiği `split_assigned_at` dolu satırı değiştirmeyi reddeder; yeniden bölme yalnız etiketleme
  başlamadan, açık bir "sıfırla" komutuyla. Tek istisna: `gold_reserve`'ün bir kez, açık bir komutla
  `gold_test` veya `train`'e aktarılması (yeni `split_snapshot` yazılır, işlem KARARLAR'a).
- `mabsa_sentences`: review_id PK/FK → `reviews` (metin orada), orig_split, raw_labels jsonb, mapped_labels jsonb.
  M-ABSA cümleleri `reviews`'a `source=mabsa`, `split=external_mabsa` olarak girer; Jev/model tahminleri diğer
  yorumlar gibi `aspect_labels` / `complaints`'e yazılır. Referans `mapped_labels`'tır; yalnız eşleşen alt
  kategoriler puanlanır (karşılığı olmayanlar "bahsedilmiyor" sayılmaz, dışarıda kalır).

### Taksonomi
- `schema_versions`: version, frozen_at, note
- `main_categories`, `subcategories`, `departments`, `cause_factors`, `actions`: değişmez id, ad, tanım,
  `introduced_in`, `retired_in` NULL, `merged_into` NULL. Hafta 4 birleştirmesinde eski kayıt silinmez; anlam
  değişirse yeni kimlik açılır.
- `subcategory_departments`, `cause_actions`: rehber/şema eşlemeleri, onlar da `introduced_in` / `retired_in`.
- Geçerlilik: kimlik `v` sürümünde geçerli ⇔ `introduced_in <= v` ve (`retired_in` NULL veya `v < retired_in`).
  Yeni yazım yalnız yazılan sürümde geçerli kimliklerle.

### Etiketler (insan, Jev, model aynı tablolarda; kaynak = koşu)
- `annotation_runs`: run_id, kind ENUM (human / jev / model), annotator_or_model, model_id NULL,
  schema_version, prompt_version NULL, is_frozen, validated_at NULL, params jsonb, created_at
- `review_annotations`: (run_id, review_id) PK, status (done / skip / needs_review), duration_sec, note
- `aspect_labels`: (run_id, review_id, subcategory_id) PK, status ENUM (not_mentioned / positive / negative / neutral),
  confidence NULL
- `complaints`: complaint_id PK, run_id, review_id, subcategory_id
  - FK (run_id, review_id, subcategory_id) → `aspect_labels`; aynı üçlü UNIQUE
  - department_id, department_conf, severity, severity_conf
  - cause_status ENUM (selected / insufficient_evidence / out_of_scope) NULL, cause_factor_id NULL, cause_conf
  - action_status ENUM (recommended / not_needed / insufficient_evidence / out_of_scope) NULL, action_conf
  - CHECK severity 1–4; CHECK severity = 1 ⇒ cause_factor_id NULL; CHECK cause_status = selected ⇔
    cause_factor_id NOT NULL. ("Uygulanamaz" yalnız şikâyet yokken sistemde; satırda yok.)
- `complaint_actions`: (complaint_id, action_id) PK, sırasız
- `confidence_thresholds`: run_id, family (aspect / department / severity / cause / action), threshold,
  chosen_on, note. Eşikler doğrulamadan önce kesinleşir; doğrulanmış koşunun eşiği değişirse `validated_at`
  silinir ve doğrulama yeniden çalışır.
- Yayında etiketçi kimliği yok.

### View'lar
- `v_labels_masked`: eşiğin altındaki alanlar NULL; maskeli olumsuz etiketin şikâyeti tamamen düşer. Eşik satırı
  yoksa veya `confidence` NULL ise (insan etiketleri) maske yok.
- `v_train_export`, `v_silver_val_export`, `v_graph_train` ve embedding üretimi **yalnız** `v_labels_masked`'tan
  ve **yalnız tek dondurulmuş + doğrulanmış Jev koşusundan** okur. (PostgreSQL view'ları parametre almaz:
  view'lar `run_id` sütununu taşır, `src/turotel/db/` sorguları açıkça `WHERE run_id = :run_id` uygular ve
  koşunun `kind=jev`, `is_frozen`, `validated_at` koşullarını kontrol eder; gizli "aktif koşu" durumu yok.)
- `v_gold_dev_eval`, `v_gold_test_eval` (yalnız son test betiği), `v_external_eval` (seçim betikleri kullanmaz):
  referans yalnız kör insan koşusu, `status=done`. Jev ve modeller bu referansa karşı tahmin
  koşusu olarak kıyaslanır. Altın kimlikler `merged_into` zinciriyle graf/modelin dondurulmuş şema sürümüne
  çözülür; oracle sorgu çözülmüş kimlikle gider.
- Tüm export/graf/embedding işleri önce `split_snapshot`'ı doğrular.

### Doğrulama: `validate_run(run_id)`
Python, yükleme sonrası. Başarılıysa `validated_at` yazar; export ve graf yalnız doğrulanmış koşudan.
1. Şikâyet ⇔ etiket, çift yönlü ve **ham** düzeyde: her şikâyetin etiketi `negative`; her `negative` etikete tam
   bir şikâyet.
2. `review_annotations.status=done` ⇒ şema sürümünde geçerli tüm alt kategoriler için birer `aspect_labels`;
   `skip` ⇒ hiç etiket yok.
3. (Yalnız human/jev) Ciddiyet 1 ⇒ `cause_status=out_of_scope`, `action_status=out_of_scope`;
   ciddiyet ≥ 2 ⇒ `cause_status ∈ {selected, insufficient_evidence}`, `action_status ∈ {recommended, not_needed, insufficient_evidence}`.
4. `action_status=recommended` ⇒ 1..üst sınır aksiyon (jev 1, human 3); diğer durumlar ⇒ 0 aksiyon.
5. Koşu türü: human/jev satırlarında durum alanları NULL olamaz; model satırlarında `cause_*` /
   `action_*` NULL ve aksiyon yok (Model A/B yalnız durum, departman, ciddiyet yazar).
6. Kullanılan taksonomi kimlikleri koşunun şema sürümünde geçerli; tekrar grubu tek bölmede.

Satırlar arası kurallar trigger ile değil bu fonksiyonla denetlenir.

### Jev önbelleği
- `jev_calls`: call_id, request_hash UNIQUE (çağrı türü + şema/prompt/Jev sürümü + normalize girdi),
  call_type (1/2), target_type (review / complaint), review_id NULL, subcategory_id NULL, request jsonb (API anahtarı/başlık yok), response jsonb, jev_version, latency_ms, cost, created_at
- Ham cevap + güven burada ve etiket tablolarında saklanır; maske sonradan eşikle türetilir.

### Embedding ve öneri
- `complaint_embeddings`: (complaint_id, model_name, input_variant) PK, embedding vector(d). Yalnız eğitim
  şikâyetleri; sorgu şikâyetlerinin embedding'i anlık hesaplanır, indekse girmez. Exact arama
  (`ORDER BY embedding <=> $q`); HNSW yalnız ölçülen gecikme gerektirirse.
- `recommendations`: rec_id, query_complaint_id, prediction_run_id NULL (oracle'da NULL), graph_run_id,
  config jsonb (eşik, ablasyon türü), rank, cause_factor_id, action_id, support, backoff_level, score, neighbor_ids

### Model ve sonuçlar
- `models`: model_id, task (A/B), base_encoder, train_size, hyperparams, artifact_path, train_manifest_id
- `export_manifests`: manifest_id, view_name, run_id, schema_version, splits, row_count, sha256, created_at
- `eval_results`: prediction_run_id NULL (oracle'da NULL), reference_run_id, eval_mode (oracle / end_to_end),
  config jsonb, split, metric, scope, value, ci_low, ci_high, n, created_at
- Model tahminleri `kind=model` koşusu olarak `aspect_labels` / `complaints`'e yazılır.

### Sentetik deneyler
- `kpi_daily`: scenario, seed, day, variable, value (planlanan doluluk ayrı değişken)
- `causal_true_edges`: scenario, source, target, lag, coef (üreteç dondurulunca yazılır)
- `causal_edges`: scenario, seed, method (pcmci_parcorr / pcmci_cmiknn / xcorr), source, target, lag, strength, p_value
- `forecasts`: seed, target, origin_day, horizon, q10, q50, q90, actual, method
- `anomaly_events` (enjekte): seed, target, type, start_day, end_day
- `anomaly_alerts` (tespit): seed, target, day, method

## 4. Colab akışları
Colab yerel veritabanına bağlanamaz; veri Parquet + manifest ile taşınır.
- **NLP:** `v_train_export` / `v_silver_val_export` → Parquet + manifest → Drive → Colab eğitim → model artifact
  (manifest_id kaydıyla) indirilir → yerelde çıkarım → `kind=model` koşusu.
- **TimesFM:** yerel sentetik üretim → `kpi_daily` → Parquet + manifest → Colab çıkarım → forecast Parquet →
  içe aktarmada manifest ve satır anahtarları doğrulanır → `forecasts`, `anomaly_alerts`.
