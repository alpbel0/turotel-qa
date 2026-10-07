# Faz 5 — Benzer vaka ve bilgi grafı

## Faz amacı

Ciddiyeti 2 ve üstü her şikâyet için olası neden ve aksiyon önermek ve öneriyi gerçek eğitim vakalarıyla
açıklamak. Embedding'ler pgvector'da tutulur, benzer vaka araması orada yapılır. Neo4j grafı tek
dondurulmuş Jev koşusundan Postgres'ten yeniden kurulur; aday (neden, aksiyon) çiftleri tam yolu taşıyan
farklı şikâyet sayısıyla puanlanır, destek yetmezse geri çekilir, hiç yetmezse susar. Olası neden ve
aksiyon modelin çıktısı değildir ve doğrulanmış kök neden sayılmaz. Takvim: Hafta 8–9.

## Task 5.1 — Şikâyet embedding'leri (pgvector)

**Repo:** `turotel-qa`
**Alan:** `recommend`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 3.6

**Referanslar:** `docs/PROJE_PLANI.md` §5.6 (Embedding), `docs/VERI_KATMANI.md` §3 (Embedding ve öneri)

**Hedef dosyalar:** `src/turotel/recommend/`

### Checklist

- [ ] `ytu-ce-cosmos/modernbert-tr-embed` yerelde; her eğitim şikâyeti ayrı kayıt, metin
      `"[alt kategori] [SEP] tam yorum"`; ablasyon için öneksiz varyant da.
- [ ] Yalnız maskeli view'dan, yalnız dondurulmuş Jev koşusunun `train` şikâyetleri;
      `complaint_embeddings` (complaint_id, model_name, input_variant).
- [ ] Exact arama (`ORDER BY embedding <=> $q`): önce aynı alt kategori, yetmezse aynı ana kategori;
      sorgu şikâyetlerinin embedding'i anlık hesaplanır, indekse girmez. HNSW yalnız ölçülen gecikme
      gerektirirse.

**Kabul kriteri:** Eğitim şikâyeti sayısı kadar vektör (her varyant için); altın veya gerçek yorumdan vektör
yok; tek sorgunun gecikmesi ölçülüp raporlanmış.

## Task 5.2 — Neo4j yeniden kurma betiği

**Repo:** `turotel-qa`
**Alan:** `graph`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 0.5, Task 3.6

**Referanslar:** `docs/VERI_KATMANI.md` §2 (Yeniden kurma sözleşmesi)

**Hedef dosyalar:** `src/turotel/recommend/`, `tests/`

### Checklist

- [ ] `run_id` kontrolü: `kind=jev`, `is_frozen`, `validated_at` dolu, `split_snapshot` uyumlu; değilse dur.
- [ ] Constraint'ler (Task 0.5) → tüm grafı sil → Katman A (koşunun şema sürümünde geçerli kimlikler,
      `BELONGS_TO` + `source` işaretli rehber kenarları) → Katman B `v_graph_train`'den (`HAS_COMPLAINT`, `ABOUT`,
      `ASSIGNED_TO`, `LIKELY_CAUSE`, `SUGGESTED_ACTION`; maskeli alanlarda kenar yok).
- [ ] Sonda düğüm/kenar sayıları aynı view'ın toplamlarıyla karşılaştırılır; uyuşmazsa hata.
- [ ] Test: test Neo4j profilinde küçük bir sabit koşuyla.

**Kabul kriteri:** Betik iki kez çalıştırılınca aynı graf; pilot veya model koşusu verilince reddediyor;
sayı karşılaştırması geçiyor.

## Task 5.3 — Öneri sorgusu ve geri çekilme

**Repo:** `turotel-qa`
**Alan:** `recommend`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 5.1, Task 5.2

**Referanslar:** `docs/PROJE_PLANI.md` §5.6, `docs/VERI_KATMANI.md` §2 (Öneri akışı)

**Hedef dosyalar:** `src/turotel/recommend/`

### Checklist

- [ ] Tam yol desteği (dep, alt, neden, aksiyon) Cypher ile; n, yumuşatılmış koşullu olasılık, PPMI yalnız
      tam yollardan.
- [ ] Geri çekilme: dep+alt → alt → ana → genel çoğunluk → sus; her öneride seviye ve destek.
- [ ] pgvector'dan en benzer 3 eğitim vakası (gösterim + sıralamada ek sinyal); ciddiyet sıralamada küçük
      bonus.
- [ ] Oracle (altın alt kategori/departman, `merged_into` ile dondurulmuş sürüme çözülmüş) ve uçtan uca
      (model tahmini) modları; çıktılar `recommendations`'a (kullanılan komşu kimlikleriyle).

**Kabul kriteri:** Plandaki örnek yorum için öneri, destek, seviye ve 3 benzer vaka dönüyor; destek eşiğin
altındaki bir sorgu bir üst seviyeye çekiliyor; hiç destek yoksa açıkça "kanıt yetersiz" dönüyor.

## Task 5.4 — Eşik seçimi, ablasyonlar ve baseline'lar

**Repo:** `turotel-qa`
**Alan:** `eval`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 5.3, Task 4.5

**Referanslar:** `docs/PROJE_PLANI.md` §5.6 (Destek eşiği, Değerlendirme)

**Hedef dosyalar:** `src/turotel/evaluation/`, `results/`

### Checklist

- [ ] Destek eşiği altın dev'de {5, 10, 15, 20} arasından MRR ile (susulan uygun sorgular sıfır puanla
      paydada); belirsizse daha ihtiyatlı eşik.
- [ ] Altın aksiyonlara karşı MRR (birincil), Hit@1, Hit@3, kapsam; oracle ve uçtan uca; yalnız ciddiyet ≥ 2.
- [ ] Ablasyonlar: yalnız embedding / yalnız graf / birleşim / koşullu çoğunluk / en sık 3 aksiyon;
      önekli / öneksiz embedding.

**Kabul kriteri:** Seçilen eşik ve tüm ablasyonlar güven aralıklarıyla `results/`'ta; seçim KARARLAR'da ("dev'de seçildi, n = …").

## Task 5.5 — 20 sorguda benzer vakaların elle kontrolü

**Repo:** `turotel-qa`
**Alan:** `eval`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 5.3

**Referanslar:** `docs/PROJE_PLANI.md` §5.6

**Hedef dosyalar:** `results/`

### Checklist

- [ ] Altın dev'den 20 şikâyet; her birinin 3 benzer vakası elle puanlanır: kategori uygunluğu, olgusal
      benzerlik, alakasız konu etkisi.
- [ ] Sonuç tablosu ve dikkat çeken hata örnekleri.

**Kabul kriteri:** 20 sorgunun puanları ve özeti `results/`'ta.
