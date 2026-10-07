# Faz 7 — Tahmin ve anomali: TimesFM-3

## Faz amacı

Aynı sentetik otelde TimesFM-3'ün şikâyet ve operasyon serilerini 14 gün ileriye ne kadar iyi tahmin
ettiğini ve tahmin bandının dışına çıkan olayları ne kadar yakaladığını ölçmek. Gerçek olaylar bilinçli
olarak enjekte edilir; basit baseline'larla karşılaştırılır. Nihai çalıştırmalar Colab GPU'da yapılır.
Tahmin iyileşmesi nedensellik kanıtı sayılmaz. Takvim: Hafta 11.

## Task 7.1 — Olay enjeksiyonu ve Colab export'u

**Repo:** `turotel-qa`
**Alan:** `forecast`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 6.1, Task 4.1

**Referanslar:** `docs/PROJE_PLANI.md` §5.8 (Anomali), `docs/VERI_KATMANI.md` §4

**Hedef dosyalar:** `src/turotel/synthetic/`, `src/turotel/export.py`

### Checklist

- [ ] Senaryo A, aynı 10 tohum; hedefler ham ölçekte: oda/banyo günlük şikâyet sayısı, hizmet/personel günlük
      şikâyet sayısı, medyan oda hazırlama süresi.
- [ ] Tohum başına 9 olay (her hedefe: 1 günlük +4 SD sıçrama, 7 günlük +2 SD seviye kayması, 14 günlük
      0→+3 SD kademeli bozulma); çakışmasız, arada ≥ 7 temiz gün → 90 olay; `anomaly_events`.
- [ ] Yan değişkenler: geleceği bilinen (haftanın günü, mevsim, 14 gün önceden planlanan doluluk); yalnız
      geçmişi bilinen (eğitim saati, yeni personel oranı). Gelecek bilgisi sızıntısı yok.
- [ ] Parquet + manifest.

**Kabul kriteri:** 90 olay kayıtlı ve çakışmasız; export manifesti doğrulanıyor.

## Task 7.2 — TimesFM-3 tahmini ve baseline'lar

**Repo:** `turotel-qa`
**Alan:** `forecast`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 7.1

**Referanslar:** `docs/PROJE_PLANI.md` §5.8

**Hedef dosyalar:** `notebooks/`, `src/turotel/synthetic/`

### Checklist

- [ ] Yerelde yalnız kurulum denemesi ve tek seri hız ölçümü; nihai çalıştırma Colab GPU.
- [ ] Ufuk 14 gün, bağlam 512 gün; rolling origin; q10 / q50 / q90.
- [ ] Baseline'lar: son değer ve mevsimsel naif.
- [ ] Forecast Parquet'i içe aktarılırken manifest ve satır anahtarları doğrulanır → `forecasts`.

**Kabul kriteri:** Her tohum, hedef ve başlangıç noktası için TimesFM ve iki baseline tahmini `forecasts`'ta.

## Task 7.3 — Kalibre bant, anomali ve ölçüm

**Repo:** `turotel-qa`
**Alan:** `eval`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 7.2

**Referanslar:** `docs/PROJE_PLANI.md` §5.8

**Hedef dosyalar:** `src/turotel/evaluation/`, `results/`

### Checklist

- [ ] Tahmin: MAE / MASE, kantil kaybı, kapsama; TimesFM vs baseline'lar.
- [ ] q10–q90 bandı temiz kalibrasyon dönemindeki hatalarla %95 kapsamaya genişletilir; dışı işaretlenir →
      `anomaly_alerts`.
- [ ] Olay düzeyinde precision / recall / F1, ilk tespit gecikmesi, olay dışı yanlış alarm oranı; olay
      türleri ayrı.
- [ ] Grafikler demo için önceden üretilir.

**Kabul kriteri:** Tahmin ve anomali tabloları ile grafikler `results/`'ta; "sentetik deney" ve TimesFM-3
ağırlıklarının ticari olmayan lisansı not edilmiş.
