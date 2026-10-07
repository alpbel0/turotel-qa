# Faz 4 — Model

## Faz amacı

Jev'in gümüş etiketlerinden kendi açık modelimizi eğitmek. Sıfırdan eğitim yok; hazır Türkçe encoder'lara
Colab'da ince ayar yapılır. Model A yorumdaki 29 alt kategorinin durumunu, Model B her şikâyetin
departmanını ve ciddiyetini tahmin eder. Veri Colab'a manifestli Parquet ile gider; model indirilir,
tahminler yerelde `kind=model` koşusu olarak yazılır. Seçim altın dev'de yapılır, son test açılmaz.
Takvim: Hafta 7.

## Task 4.1 — Colab gidiş-dönüşü: export ve manifest

**Repo:** `turotel-qa`
**Alan:** `ml`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 3.6

**Referanslar:** `docs/VERI_KATMANI.md` §4, §3 (Model ve sonuçlar)

**Hedef dosyalar:** `src/turotel/export.py`, `notebooks/`, `notebooks/requirements-colab.txt`

### Checklist

- [ ] `v_train_export` / `v_silver_val_export` → `data/exports/` altında Parquet + manifest (view, run_id,
      şema sürümü, bölmeler, satır sayısı, sha256) → `export_manifests`.
- [ ] Export öncesi `split_snapshot` ve koşu koşulları (`kind=jev`, `is_frozen`, `validated_at`) doğrulanır.
- [ ] Colab defter şablonu: manifest doğrulama → eğitim → artifact + `manifest_id` kaydı.
- [ ] `requirements-colab.txt` ile Colab bağımlılıkları sabit.

**Kabul kriteri:** Export iki kez çalıştırılınca aynı sha256'yı veriyor; altın veya gerçek yorum satırı
export'ta yok; manifest bozulunca Colab defteri duruyor.

## Task 4.2 — TF-IDF baseline (Model A + B)

**Repo:** `turotel-qa`
**Alan:** `ml`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 4.1, Task 1.6

**Referanslar:** `docs/PROJE_PLANI.md` §5.5 (Adaylar)

**Hedef dosyalar:** `src/turotel/models/`

### Checklist

- [ ] Yerelde eğitim (`uv run --group ml …`): 29 "bahsedildi" LR + 29 duygu LR; kelime 1–2 gram + karakter
      3–5 gram.
- [ ] Model B: alt kategori adı metne eklenir; departman ve ciddiyet LR.
- [ ] Çıkarım A → olumsuz alt kategoriler → her biri için B; `kind=model` koşusu, `validate_run`.

**Kabul kriteri:** Baseline koşusu doğrulanmış; altın dev'de tüm metrikler `eval_results`'ta (oracle ve
uçtan uca).

## Task 4.3 — Encoder ince ayarı: BERTurk ve ModernBERT-TR

**Repo:** `turotel-qa`
**Alan:** `ml`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 4.1

**Referanslar:** `docs/PROJE_PLANI.md` §5.5

**Hedef dosyalar:** `notebooks/`

### Checklist

- [ ] Model A: yorum bir kez kodlanır, 29 başlık × 4 durum; kayıp `L_konu` + `L_duygu` (yalnız
      bahsedilenlerde), kategori içinde sonra kategoriler arasında eşit ortalama; sınıf ağırlıkları
      frekanstan, en fazla ~5; yeniden örnekleme yok.
- [ ] Model B: `"[alt kategori] [SEP] yorum"`; departman (sınıf ağırlıklı CE) + ciddiyet (**CORAL**).
- [ ] `dbmdz/bert-base-turkish-cased` ve `ytu-ce-cosmos/modernbert-tr-base` aynı protokolle (bölmeler,
      epoch, öğrenme oranı, batch); erken durdurma gümüş doğrulamada.
- [ ] Öğrenme eğrisi: 500 / 2.000 / tüm gümüş veri (ana aday için).
- [ ] Focal loss yalnız ablasyon.
- [ ] Artifact'ler `artifacts/`'a indirilir, `models` tablosuna kaydedilir.

**Kabul kriteri:** Her aday için A ve B artifact'i `manifest_id` ile kayıtlı; eğitim defterleri tekrar
çalıştırılabilir durumda repoda.

## Task 4.4 — Yerel çıkarım ve model koşuları

**Repo:** `turotel-qa`
**Alan:** `ml`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 4.3

**Referanslar:** `docs/VERI_KATMANI.md` §3 (Etiketler, Model ve sonuçlar)

**Hedef dosyalar:** `src/turotel/models/`

### Checklist

- [ ] İndirilen artifact'lerle CPU'da çıkarım: A → olumsuz alt kategoriler → B.
- [ ] Her model için `kind=model` koşusu; yalnız durum, departman, ciddiyet yazılır (neden/aksiyon NULL).
- [ ] `validate_run`.

**Kabul kriteri:** Her aday için altın dev ve gümüş doğrulama tahmin koşuları doğrulanmış.

## Task 4.5 — Altın dev'de karşılaştırma ve model seçimi

**Repo:** `turotel-qa`
**Alan:** `eval`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 4.2, Task 4.4

**Referanslar:** `docs/PROJE_PLANI.md` §5.5 (Seçim metriği, Metrikler, Kalibrasyon)

**Hedef dosyalar:** `src/turotel/evaluation/`, `results/`

### Checklist

- [ ] TF-IDF, BERTurk, ModernBERT-TR ve Jev aynı kör altın dev referansına karşı; oracle ve uçtan uca.
- [ ] Seçim: 29 alt kategoride "olumsuz şikâyet var/yok" mikro F1; güven aralıkları çakışıyorsa ana aday
      (ModernBERT-TR) korunur.
- [ ] Sadakat (Jev'e benzeme) ve doğruluk (altına göre) ayrı raporlanır; Jev ile fark eşleştirilmiş
      bootstrap; kategori başına sonuç ve destek.
- [ ] Kalibrasyon: duygu ve şikâyet tespitinde ECE (5 kova), gümüş doğrulamada sıcaklık ölçekleme, risk–kapsam
      eğrisi; kısa yorum (< 5 kelime) performansı ayrı.

**Kabul kriteri:** Seçilen model ve gerekçesi KARARLAR'da ("dev'de seçildi, n = …"); karşılaştırma tablosu ve öğrenme eğrisi
`results/`'ta; `gold_test` için hiç metrik yok.
