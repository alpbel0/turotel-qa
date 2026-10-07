# Faz 2 — Elle etiketleme

## Faz amacı

Projenin ölçüm temelini kurmak: kör altın etiketler. Önce etiket rehberi ve Postgres'e yazan Streamlit
aracı hazırlanır, 30 örnekle şema denenir. Ardından kullanıcı 100 yorumluk altın dev'i Jev'i görmeden
etiketler ve süre ölçülür; pilot verisine göre şema dondurulur; son test şema dondurulduktan sonra
etiketlenir. Tüm altın etiketleri tek etiketçi (kullanıcı) bir kez yapar; insan uyumu ölçülmez ve bu
raporda sınırlama olarak yazılır. Takvim: Hafta 2–6.

## Task 2.1 — Etiket rehberi v1

**Repo:** `turotel-qa`
**Alan:** `docs`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 1.1

**Referanslar:** `docs/PROJE_PLANI.md` §4, §5.2 (Rehber)

**Hedef dosyalar:** `docs/annotation_guidelines.md`

### Checklist

- [ ] 29 alt kategori: tanım, örnek, sınır örnekleri; "bahsedilmiyor / olumlu / olumsuz / nötr" kuralları.
- [ ] Departman: "sorunu üreten / düzeltici aksiyonun sahibi" kuralı, sınır kuralları, alt kategori →
      olası departman yardımcı tablosu (zorunlu değil).
- [ ] Ciddiyet: 4 seviye, yalnız somut etki; abartılı dil yükseltmez, telafi düşürmez.
- [ ] Neden ve aksiyon: yalnız ciddiyet ≥ 2; durum kodları (kanıt yetersiz, kapsam dışı, gerekmiyor);
      en fazla 3 sırasız aksiyon.
- [ ] Belge sürümü taksonomi şema sürümüyle aynı (v1).

**Kabul kriteri:** Rehber, §3'teki örnek yorumu ve 5 zor sınır örneğini tek anlamlı biçimde çözüyor;
şemadaki her etiketin tanımı var.

## Task 2.2 — Streamlit etiketleme aracı

**Repo:** `turotel-qa`
**Alan:** `labeling`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 1.3, Task 1.5

**Referanslar:** `docs/PROJE_PLANI.md` §5.2 (Araç, Akış), `docs/VERI_KATMANI.md` §3 (Etiketler)

**Hedef dosyalar:** `src/turotel/labeling/app.py`, `src/turotel/labeling/`

### Checklist

- [ ] Çalıştırma: `uv run --group labeling streamlit run src/turotel/labeling/app.py`.
- [ ] Koşu seçimi/oluşturma (`kind=human`); seçilen bölmeden sıradaki etiketsiz yorum.
- [ ] 29 alt kategori tablo halinde; "olumsuz" seçilen satırda şikâyet alanları açılır (departman,
      ciddiyet, ≥ 2 ise neden ve 1–3 aksiyon, durum kodları); belirsizlik notu.
- [ ] **Kör:** Jev ve model çıktılarına hiçbir yerden erişmez.
- [ ] Her kayıt anında Postgres'e (`review_annotations` süreyle, `aspect_labels`, `complaints`,
      `complaint_actions`); `done` / `skip` / `needs_review`; araç kapanırsa veri kaybı yok.
- [ ] Araç içinde şema kuralları (ör. ciddiyet 1'de neden alanı kapalı) ve kayıttan sonra `validate_run`.

**Kabul kriteri:** 10 yorum etiketlenip `validate_run`'dan geçiyor; araç ortada kapatılıp açıldığında
kaldığı yerden devam ediyor; arayüzde Jev çıktısı hiçbir biçimde görünmüyor.

## Task 2.3 — 30 örnek pilot

**Repo:** `turotel-qa`
**Alan:** `labeling`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 2.1, Task 2.2

**Referanslar:** `docs/PROJE_PLANI.md` §6 (Hafta 2)

**Hedef dosyalar:** `docs/annotation_guidelines.md`, `docs/KARARLAR.md`

### Checklist

- [ ] `train` bölmesinden 30 yorum (altın havuzdan değil) ayrı bir pilot koşusunda etiketlenir.
- [ ] Rehberde belirsiz kalan noktalar düzeltilir; araç kullanılabilirlik sorunları giderilir.
- [ ] Pilot koşusu altın değerlendirmede kullanılmaz.

**Kabul kriteri:** 30 yorum tamam; rehber v1.1 ve araç düzeltmeleri yapılmış; değişiklikler KARARLAR'a
işlenmiş.

## Task 2.4 — 100 kör altın dev

**Repo:** `turotel-qa`
**Alan:** `labeling`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 2.3

**Referanslar:** `docs/PROJE_PLANI.md` §5.1, §5.2 (Süre tahmini)

**Hedef dosyalar:** —

### Checklist

- [ ] `gold_dev`'in 100 yorumu kör etiketlenir (Jev pilotundan önce ya da ondan habersiz).
- [ ] Medyan süre hesaplanır. **Proje içinde karar:** medyan ≤ 3 dk ise son test 300'e çıkabilir, > 5 dk
      ise 150'ye iner. Karar sonrası Task 1.3'teki rezerv aktarım komutu çalıştırılır (Task 3.5'ten önce).
- [ ] Koşu `validate_run`'dan geçer.

**Kabul kriteri:** 100 `done` kayıt doğrulanmış; medyan süre ve son test boyutu kararı KARARLAR'da.

## Task 2.5 — Şemanın dondurulması

**Repo:** `turotel-qa`
**Alan:** `data`, `docs`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 2.4, Task 3.3

**Referanslar:** `docs/PROJE_PLANI.md` §4.1 (birleştirme), §4.2 (pilot kontrolleri), `docs/VERI_KATMANI.md`
§3 (Taksonomi)

**Hedef dosyalar:** `src/turotel/data/`, `docs/annotation_guidelines.md`, `docs/KARARLAR.md`

### Checklist

- [ ] Altın dev + Jev pilotu verisiyle: seyrek / sürekli karışan alt kategoriler (hedef 20–24 aralığı,
      **Proje içinde karar**); "planlama/koordinasyon – standart/denetim – hizmet icrası" karışması;
      30 ciddiyet-1 şikâyetinin kör denetim sonucu (Task 3.3).
- [ ] Birleştirme olursa: yeni şema sürümü, `merged_into` / `retired_in`; eski kayıtlar silinmez; anlamı
      değişen kategoriye yeni kimlik.
- [ ] `schema_versions.frozen_at` yazılır; rehber yeni sürüme güncellenir.
- [ ] Altın dev kimliklerinin yeni sürüme çözümlenmesi eval view'larında doğrulanır.

**Kabul kriteri:** Şema sürümü dondurulmuş; altın dev eval view'ı tüm etiketleri dondurulmuş sürümün
kimlikleriyle döndürüyor; kararlar gerekçeleriyle KARARLAR'da.

## Task 2.6 — Kör son test etiketleme

**Repo:** `turotel-qa`
**Alan:** `labeling`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 2.5

**Referanslar:** `docs/PROJE_PLANI.md` §5.1 (Son test)

**Hedef dosyalar:** —

### Checklist

- [ ] `gold_test` (200, ya da Task 2.4 kararıyla 150/300) dondurulmuş şemayla, kör etiketlenir.
- [ ] Etiketleme bitince koşu dondurulur ve doğrulanır; sonuçlara Task 8.2'ye kadar bakılmaz (hiçbir
      metrik hesaplanmaz).

**Kabul kriteri:** Tüm son test yorumları `done`; koşu dondurulmuş ve doğrulanmış; `eval_results`'ta
`gold_test` için hiç satır yok.

## Task 2.7 — Gerçek yorumların etiketlenmesi

**Repo:** `turotel-qa`
**Alan:** `labeling`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 1.7, Task 2.5

**Referanslar:** `docs/PROJE_PLANI.md` §5.1 (Gerçek yorumlar)

**Hedef dosyalar:** —

### Checklist

- [ ] Kullanıcının topladığı 100 gerçek yorum (Hafta 1–6 boyunca) dondurulmuş şemayla kör etiketlenir.
- [ ] Koşu dondurulur ve doğrulanır; Task 8.2'ye kadar metrik hesaplanmaz.

**Kabul kriteri:** 100 `external_real` yorum `done`, koşu doğrulanmış.
