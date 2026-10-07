# Faz 6 — Nedensellik: PCMCI+

## Faz amacı

Gerçek nedenleri bilinen sentetik bir otelde PCMCI+'ın gecikmeli nedensel ilişkileri ne kadar doğru
bulduğunu ölçmek. Üreteç ve parametreleri sonuçlara bakılmadan dondurulur; senaryolar zorlukları tek tek
ekler (gizli ortak neden, doğrusal olmayan ilişki, hiç ilişki olmayan kontrol). Bu deney yöntemi gösterir,
gerçek bir otel hakkında kanıt sunmaz. Takvim: Hafta 10.

## Task 6.1 — Sentetik otel üreteci

**Repo:** `turotel-qa`
**Alan:** `causal`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 0.3

**Referanslar:** `docs/PROJE_PLANI.md` §5.7, `docs/VERI_KATMANI.md` §3 (Sentetik deneyler)

**Hedef dosyalar:** `src/turotel/synthetic/`, `tests/`

### Checklist

- [ ] 6 değişken, 760 gün üretilip ilk 30 atılır (730 gün); doluluğa yıllık (~0,20) ve haftalık (~0,04)
      mevsimsellik; tüm serilerde AR(1) = 0,35; gürültü ~1 SD.
- [ ] Plan tablosundaki 6 ilişki (gecikme ve katsayılarıyla) = senaryo A. B: gözlenmeyen "personel
      devamsızlığı" (aynı gün +0,50, veride yok). C: doluluk→hizmet şikâyeti yalnız doluluk > %90 iken
      +0,80 SD. K: çapraz bağlantı yok.
- [ ] Planlanan doluluk ayrı değişken (Faz 7 için; gerçekleşenden kontrollü hata içerir).
- [ ] 10 tohum; `kpi_daily`. Üreteç dondurulunca `causal_true_edges` yazılır.

**Kabul kriteri:** Aynı tohum aynı seriyi üretiyor; A senaryosunda gerçek kenarların gecikmeli korelasyonu
beklenen işarette; üreteç parametreleri dondurulmuş ve KARARLAR'da.

## Task 6.2 — PCMCI+ ve korelasyon baseline'ı

**Repo:** `turotel-qa`
**Alan:** `causal`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 6.1

**Referanslar:** `docs/PROJE_PLANI.md` §5.7 (tigramite, Baseline)

**Hedef dosyalar:** `src/turotel/synthetic/`

### Checklist

- [ ] Takvim bileşenleri çıkarılır ve standartlaştırılır.
- [ ] tigramite (`uv run --group causal …`): A, B, K'da `ParCorr`; C'de `ParCorr` ve `CMIknn`; `tau_min=0`,
      `tau_max=21`, `pc_alpha=0.05`, `fdr_method="fdr_bh"`, `max_conds_dim=3`, `max_combinations=1`.
- [ ] CMIknn süresi önce tek tohumla ölçülür.
- [ ] Baseline: AR(1) artıklarında 0–21 gün Pearson çapraz korelasyon, BH (q < 0,05), çift başına en güçlü
      gecikme.
- [ ] Bulunan kenarlar `causal_edges`'e (yöntem, senaryo, tohum).

**Kabul kriteri:** 4 senaryo × 10 tohum × yöntemler için kenarlar kayıtlı; çalıştırma süreleri raporlu.

## Task 6.3 — Nedensellik değerlendirmesi

**Repo:** `turotel-qa`
**Alan:** `eval`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 6.2

**Referanslar:** `docs/PROJE_PLANI.md` §5.7 (Değerlendirme)

**Hedef dosyalar:** `src/turotel/evaluation/`, `results/`

### Checklist

- [ ] Kenar = (kaynak, hedef, tam gecikme); TP yalnız üçü doğruysa. Gerçek ilişkilerin hepsi gecikmeli
      olduğundan her aynı-gün çapraz kenarı yanlış pozitif; yönsüz (`o-o`) aynı-gün kenarı çift başına tek
      yanlış pozitif. Çapraz kenarlarda precision / recall / F1 (10 tohum ortalama ± SD); öz-kenarlar ayrı.
- [ ] İkincil: gecikmesiz yönlü F1, gecikme mutlak hatası, ±1 gün toleranslı F1, B'de sahte kenar oranı (aynı gün dahil),
      K'da tohum başına yanlış pozitif.
- [ ] PCMCI+ ile baseline yan yana; grafikler demo için önceden üretilir.

**Kabul kriteri:** Senaryo başına sonuç tablosu ve grafikler `results/`'ta; "sentetik deney" ibaresi her
çıktıda.
