# Faz 3 — Jev ile gümüş etiket

## Faz amacı

Eğitim verisini TypeSafe Jev ile etiketlemek. Her cevap Postgres önbelleğine yazılır, aynı istek iki kez
gönderilmez. Önce 500 yorumluk pilotla soru tasarımı, maliyet ve kalite ölçülür, aynı veriyle zincirin
tamamı kaba haliyle bir kez çalıştırılır (sorunlar başta çıksın). Şema dondurulduktan sonra tam etiketleme
yapılır; güven eşikleri altın dev'de seçilir; koşu doğrulanıp dondurulur. Bu dondurulmuş koşu eğitimin,
grafın ve embedding indeksinin tek kaynağıdır. Takvim: Hafta 3–4.

## Task 3.1 — Jev istemcisi ve `jev_calls` önbelleği

**Repo:** `turotel-qa`
**Alan:** `jev`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 0.3

**Referanslar:** `docs/PROJE_PLANI.md` §5.4, `docs/VERI_KATMANI.md` §3 (Jev önbelleği)

**Hedef dosyalar:** `src/turotel/jev/`, `tests/`

### Checklist

- [ ] API anahtarı yalnız `.env`'den; istek kaydında anahtar ve başlık yok.
- [ ] `request_hash` = çağrı türü + şema/prompt/Jev sürümü + normalize girdi; önbellekte varsa çağrı
      yapılmaz.
- [ ] Hedef türü: `review` / `complaint` (review_id + subcategory_id). M-ABSA cümleleri de `review`.
- [ ] Süre, maliyet, Jev sürümü kaydı; geçersiz cevap ayrı işaretlenir; zaman aşımı ve tekrar deneme
      (artan bekleme), 400/401 hemen hata.

**Kabul kriteri:** Sahte istemciyle testler: aynı istek ikinci kez gönderilmiyor; sürüm değişince yeni çağrı
yapılıyor; kayıtta anahtar yok.

## Task 3.2 — Çağrı 1 ve çağrı 2

**Repo:** `turotel-qa`
**Alan:** `jev`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 3.1, Task 2.1

**Referanslar:** `docs/PROJE_PLANI.md` §5.4

**Hedef dosyalar:** `src/turotel/jev/`

### Checklist

- [ ] Çağrı 1 (yorum başına): 29 alt kategori için ayrı `choice` (bahsedilmiyor/olumlu/olumsuz/nötr).
- [ ] Çağrı 2 (şikâyet başına ayrı): `state` = yorum + hedef alt kategori adı/tanımı + "yalnız bu şikâyeti
      değerlendir"; departman `choice`, ciddiyet `choice` (4 seviye), ciddiyet ≥ 2 ise neden ve aksiyon
      `choice` (**top-1**).
- [ ] Cevaplar `kind=jev` koşusuna: ham seçim + güven; maske yazılmaz. Durum alanları kurallara göre.
- [ ] Prompt sürümü koşuda (`prompt_version`).

**Kabul kriteri:** 10 yorumluk deneme koşusu `validate_run`'dan geçiyor; her olumsuz alt kategori için tam
bir şikâyet kaydı var.

## Task 3.3 — 500 yorumluk pilot

**Repo:** `turotel-qa`
**Alan:** `jev`, `eval`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 3.2, Task 2.4, Task 1.6

**Referanslar:** `docs/PROJE_PLANI.md` §5.4 (Pilot), §4.2 (ciddiyet-1 denetimi)

**Hedef dosyalar:** `docs/KARARLAR.md`, `results/`

### Checklist

- [ ] `train`'den 500 yorum + altın dev 100 (yalnız Task 2.4 bittikten sonra) ayrı bir pilot koşusunda.
- [ ] Ölçümler: r (yorum başına olumsuz alt kategori), güven dağılımı, altın dev'de doğruluk, geçersiz
      cevap oranı, süre, maliyet, nadir kategori dağılımı, 20–30 yorumda tekrar çağrı kararlılığı.
- [ ] Tam etiketleme çağrı sayısı ve maliyet tahmini (~10.890 × (1 + r)).
- [ ] Rastgele 30 ciddiyet-1 şikâyeti neden/aksiyon açısından kör denetlenir (Task 2.5 girdisi).
- [ ] Pilot görülmeden tam çağrı yok.

**Kabul kriteri:** Pilot raporu `results/`'ta; tam etiketleme maliyet/süre tahmini ve soru tasarımı
değişiklikleri KARARLAR'da.

## Task 3.4 — Uçtan uca mini sistem

**Repo:** `turotel-qa`
**Alan:** `ml`, `graph`, `eval`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 3.3

**Referanslar:** `docs/PROJE_PLANI.md` §6 (Hafta 3), `docs/KARARLAR.md` ("önce ~500 yorumla uçtan uca mini versiyon")

**Hedef dosyalar:** `src/turotel/` (ilgili modüllerin ilk kaba hali)

### Checklist

- [ ] Pilot koşusuyla zincirin her halkası kaba haliyle bir kez: view'dan export → TF-IDF + LR → tahmin
      koşusu → `validate_run` → basit bir (alt kategori, neden, aksiyon) destek sayımı → altın dev'de
      metrikler.
- [ ] Amaç kalite değil, kırılan yerleri bulmak; bulunan sorunlar ilgili task'lara not düşülür.

**Kabul kriteri:** Zincir baştan sona hatasız bir kez çalıştı; altın dev'de metrik satırları `eval_results`'ta;
bulunan sorunların listesi KARARLAR'da veya ilgili task'larda.

## Task 3.5 — Tam etiketleme

**Repo:** `turotel-qa`
**Alan:** `jev`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 3.4, Task 2.5

**Referanslar:** `docs/PROJE_PLANI.md` §5.4

**Hedef dosyalar:** —

### Checklist

- [ ] Dondurulmuş şemayla tek koşu: `train`, `silver_val`, `gold_dev` ve `gold_test` (kıyas için; son test
      çıktısına Task 8.2'ye kadar bakılmaz). Gerçek yorumlar ve M-ABSA için de çağrı (Task 8.2 kıyası).
- [ ] Kesilen çalıştırma önbellek sayesinde kaldığı yerden devam eder.
- [ ] Süre ve maliyet raporu.

**Kabul kriteri:** Tüm hedefler için cevap var (geçersizler raporlu); ikinci çalıştırma hiç yeni çağrı
yapmıyor.

## Task 3.6 — Güven eşikleri, doğrulama ve dondurma

**Repo:** `turotel-qa`
**Alan:** `jev`, `eval`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 3.5

**Referanslar:** `docs/PROJE_PLANI.md` §5.4 (Düşük güven), `docs/VERI_KATMANI.md` §3 (`confidence_thresholds`)

**Hedef dosyalar:** `src/turotel/jev/`, `results/`

### Checklist

- [ ] Soru ailesi başına (alt kategori durumu, departman, ciddiyet, neden, aksiyon) eşik altın dev'de:
      cevapların ≥ %80'ini koruyan eşikler içinde hatayı en aza indiren; bootstrap duyarlılığı raporlanır.
- [ ] Eşikler `confidence_thresholds`'a ve KARARLAR'a ("dev'de seçildi, n = …"); düşük güvende alan yalnız maskelenir (yorum atılmaz, ağırlık yok,
      "bahsedilmiyor"a çekilmez).
- [ ] `validate_run` → `is_frozen`. Bundan sonra eşik değişirse doğrulama yeniden çalışır.
- [ ] Maskeli view'dan eğitim/graf satır sayıları raporlanır.

**Kabul kriteri:** Jev koşusu dondurulmuş ve doğrulanmış; eşikler ve kapsam oranları `results/`'ta;
`v_train_export` yalnız bu koşudan satır döndürüyor.
