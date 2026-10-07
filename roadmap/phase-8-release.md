# Faz 8 — Son test, demo ve yayın

## Faz amacı

Sistemi bir demo olarak birleştirmek, son testi bir kez açıp dürüstçe raporlamak ve her şeyi Hugging Face
ve GitHub'da yayımlamak. Son test sonucuna göre hiçbir model, eşik veya ayar değiştirilmez. Gerçek yorumlar
ve onların embedding'leri hiçbir yerde yayımlanmaz. **Ana milestone:** demo çalışıyor, son test raporlu,
veri seti + model + Space + GitHub yayında. Takvim: Hafta 12–14.

## Task 8.1 — Gradio demo ve yayın şekli kararı

**Repo:** `turotel-qa`
**Alan:** `demo`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 4.5, Task 5.4, Task 6.3, Task 7.3

**Referanslar:** `docs/PROJE_PLANI.md` §5.9 (Gradio Space, Yayın şekli)

**Hedef dosyalar:** `src/turotel/demo/`

### Checklist

- [ ] *Tek yorum (canlı):* yalnız bahsedilen alt kategoriler, olumsuzlar önde; şikâyet kartında alt
      kategori, duygu güveni, departman, ciddiyet, olası neden, ilk 3 aksiyon, destek, geri çekilme
      seviyesi; benzer 3 vaka açılır bölümde; "kanıt yetersiz" açık sonuç.
- [ ] *Toplu analiz (canlı, ≤ 200 yorum CSV):* ana/alt kategori memnuniyet oranı + bahsedilme sayısı,
      departman bazında şikâyet ve ciddiyet dağılımı, şablonla özet (dil modeli yok).
- [ ] *Nedensellik ve tahmin:* önceden üretilmiş grafikler, senaryo seçici, "sentetik deney" ibaresi.
- [ ] **Proje içinde karar:** HF Space'in çalışma şekli (muhtemelen DB'lerden dışa aktarılmış anlık
      görüntü; tam sistem `docker compose` ile GitHub'da). Ücretsiz Space koşulları doğrulanır.
- [ ] CPU Basic profili: ONNX/int8, tek istek kuyruğu, hazır indeks, sonuç önbelleği, hazır örnekler.

**Kabul kriteri:** Üç sekme yerelde çalışıyor; seçilen yayın şekliyle CPU'da tek yorum yanıt süresi ölçülüp
raporlanmış; karar KARARLAR'da.

## Task 8.2 — Son testin bir kez açılması ve dış testler

**Repo:** `turotel-qa`
**Alan:** `eval`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 2.6, Task 2.7, Task 4.5, Task 5.4, Task 1.4

**Referanslar:** `docs/PROJE_PLANI.md` §5.1 (Bölümler), §5.9

**Hedef dosyalar:** `src/turotel/evaluation/`, `results/`

### Checklist

- [ ] Tüm seçimler (model, eşikler, destek eşiği) dondurulmuş olduğu KARARLAR'da yazılı olmadan çalışmaz.
- [ ] `v_gold_test_eval` bir kez: seçilen model, TF-IDF, BERTurk ve Jev; sınıflandırma ve öneri metrikleri
      (oracle ve uçtan uca), güven aralıklarıyla.
- [ ] `v_external_eval`: 100 gerçek yorumda aynı karşılaştırma.
- [ ] M-ABSA (`external_mabsa`): tahmin koşuları `mapped_labels`'a karşı, yalnız eşleşen alt kategorilerde
      konu alanı dış sınavı (Jev ve model); kapsam dışı kategoriler ayrı raporlanır.
- [ ] Sonuca göre hiçbir ayar değiştirilmez; beklenmeyen sonuçlar olduğu gibi raporlanır.

**Kabul kriteri:** Son test, dış test ve M-ABSA sonuçları `results/`'ta; `eval_results`'ta `gold_test` için
tek bir değerlendirme oturumu var.

## Task 8.3 — HF veri seti ve model kartı

**Repo:** `turotel-qa`
**Alan:** `release`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 8.2

**Referanslar:** `docs/PROJE_PLANI.md` §5.9 (HF veri seti, Model kartı)

**Hedef dosyalar:** `src/turotel/export.py`, `docs/report/`

### Checklist

- [ ] `turotel-qm-dataset`: `silver` (train, validation) ve `gold` (dev, test) konfigürasyonları; alanlar
      plandaki gibi; ayrı `jev_scores`; `annotation_guidelines.md` ve makine-okunur kategori JSON'u; etiketçi
      kimliği yok; gerçek yorumlar ve embedding'leri **yok**. HUMIR'in orijinal kullanım şartları kontrol edilir: yeniden
      yayına izin veriyorsa `text` dahil, vermiyorsa yalnız `review_id` + etiketler ve birleştirme talimatı.
- [ ] Veri kartında: "altın etiketler tek etiketçi tarafından yapıldı; etiketçiler arası uyum ölçülmedi".
- [ ] `turotel-qm-model`: model kartı plandaki başlıklarla; olası neden ve aksiyonun model çıktısı olmadığı
      ve doğrulanmış kök neden sayılmadığı açıkça.
- [ ] Yayın öncesi veri setinde `source=real` satırı olmadığı kodla kontrol edilir.

**Kabul kriteri:** Veri seti ve model HF'te; veri setinde gerçek yorum yok (kodla doğrulandı); kartlar
eksiksiz.

## Task 8.4 — Rapor, Space ve GitHub yayını

**Repo:** `turotel-qa`
**Alan:** `release`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 8.1, Task 8.3

**Referanslar:** `docs/PROJE_PLANI.md` §1 (Yayın), §5.9, §7

**Hedef dosyalar:** `docs/report/`, `results/`, `README.md`

### Checklist

- [ ] Rapor: İngilizce + kısa Türkçe özet; yöntem, sonuçlar (güven aralıklı), sınırlamalar ve hata örnekleri.
      Sınırlamalarda altın dev'de yapılan tüm seçimler n'leriyle listelenir (KARARLAR'daki "dev'de seçildi"
      satırlarından).
- [ ] `turotel-qm-demo` Space yayında (Task 8.1 kararıyla).
- [ ] README: tek komutla tam sistem (`docker compose up` + `uv sync` + migration), demo ve HF linkleri.
- [ ] Repoda: kod, Colab defterleri, `results/`, rapor; sır, ham veri ve gerçek yorum yok.

**Kabul kriteri:** Temiz bir makinede README'yi izleyerek sistem kuruluyor ve demo açılıyor; Space, veri
seti ve model linkleri çalışıyor. **Proje tamam.**
