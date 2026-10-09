# Faz 1 — Veri

## Faz amacı

Ham verileri ve etiket şemasını veritabanına almak; bölmeleri bir kez ve kilitli biçimde atamak. Taksonomi
(9 ana / 29 alt kategori, 11 departman, 13 neden, 13 aksiyon) tek kaynak olarak Postgres'e girer. HUMIR
temizlenir, tekrar grupları bulunur ve bölmelere ayrılır; altın havuz Jev'e bakılmadan seçilir. Bu fazın
sonunda her koşuyu denetleyen `validate_run` ve sonraki tüm ölçümlerin kullanacağı değerlendirme çekirdeği
hazırdır. Takvim: Hafta 1 (değerlendirme çekirdeği Hafta 3'e kadar).

## Task 1.1 — Taksonomi yükleme (şema v1)

**Repo:** `turotel-qa`
**Alan:** `data`
**Durum:** Tamamlandı (2026-10-07)
**Bağımlılıklar:** Task 0.3

**Referanslar:** `docs/PROJE_PLANI.md` §4, `docs/VERI_KATMANI.md` §3 (Taksonomi)

**Hedef dosyalar:** `src/turotel/data/`

### Checklist

- [x] `schema_versions`'a v1.
- [x] Ana/alt kategori, departman (kapsam kuralıyla), neden faktörü (grubuyla), aksiyon tabloları §4'teki
      ad ve tanımlarla; değişmez kimlikler, `introduced_in = v1`.
- [x] Rehber eşlemeleri: `subcategory_departments` (alt kategori → olası departmanlar), `cause_actions`
      (§4.2 aksiyon tablosunun "tipik neden" sütunu).
- [x] Tekrar çalıştırılabilir (aynı sürüm ikinci kez yüklenince değişiklik yok).

**Kabul kriteri:** 9 / 29 / 11 / 13 / 13 kayıt ve rehber eşlemeleri yüklü; her alt kategori bir ana
kategoriye bağlı; ikinci çalıştırma hiçbir şey değiştirmiyor.

## Task 1.2 — HUMIR yükleme, temizlik ve tekrar grupları

**Repo:** `turotel-qa`
**Alan:** `data`
**Durum:** Tamamlandı (2026-10-07)
**Bağımlılıklar:** Task 0.3

**Referanslar:** `docs/VERI_NOTLARI.md` (HUMIR), `docs/PROJE_PLANI.md` §5.1

**Hedef dosyalar:** `src/turotel/data/`

### Checklist

- [x] `data/raw/humir/HUMIRSentimentDatasets.csv` (`;` ayraçlı, UTF-8 BOM) → yalnız `Type == "Hotel Review"`
      (11.600 satır) → `reviews` (`source=humir`, `humir_class`, `word_len`).
- [x] Birebir tekrarlar tek kayda iner (~11.190 yorum); çok benzer metinler aynı `duplicate_group_id`'yi
      alır (yöntem ve eşik koda ve README'ye yazılır).
- [x] 5 kelimeden kısa yorumlar **çıkarılmaz** (657 yorum).
- [x] Türkçe karakter kontrolü (bozuk kodlama yok).

Sapmalar: kenar boşlukları kırpıldığı için tekrar sonrası 11.167 yorum (notlarda ~11.189); 5 kelimeden kısa yorum
tekrar silindikten sonra 455 (657 ham satırdı). Yinelenen yorum eşiği 0,4 (kelime 3-gram Jaccard); 97 grup / 200 yorum.
Ham CSV `data/raw/humir/` altına Hugging Face'ten indirildi (gitignore'da).

**Kabul kriteri:** Yüklenen yorum sayısı, tekrar grubu sayısı ve uzunluk dağılımı `docs/VERI_NOTLARI.md`
ölçümleriyle uyuşuyor (fark varsa nedeni belgelenir); rastgele 20 yorumda karakterler doğru.

## Task 1.3 — Bölmeler, altın havuz seçimi ve `split_snapshot`

**Repo:** `turotel-qa`
**Alan:** `data`
**Durum:** Tamamlandı (2026-10-07)
**Bağımlılıklar:** Task 1.2

**Referanslar:** `docs/PROJE_PLANI.md` §5.1 (Bölümler), `docs/VERI_KATMANI.md` §3 (Veri)

**Hedef dosyalar:** `src/turotel/data/`

### Checklist

- [x] Altın havuz 300 yorum (100 `gold_dev` + 200 `gold_test`) + 100 `gold_reserve`, HUMIR etiketine göre
      %70 olumsuz / %30 olumlu, sabit tohumla; Jev'e bakılmaz. Kalanın ~%90'ı `train`, ~%10'u `silver_val`.
- [x] Tekrar grubundaki tüm yorumlar aynı bölmeye düşer; HUMIR'in hazır train/test ayrımı kullanılmaz.
- [x] `split_assigned_at` yazılır; bölme betiği atanmış satırı değiştirmeyi reddeder. Yeniden bölme yalnız
      etiketleme başlamadan, açık bir "sıfırla" komutuyla.
- [x] `split_snapshot`: kapsam `source=humir`, sıralı (review_id, split) sha256, bölme başına sayılar.
- [x] Rezerv aktarım komutu: `gold_reserve` bir kez `gold_test`'e (son test 300) veya `train`'e (200/150; 150'de
      artan 50 `gold_test` de `train`'e) aktarılır; yeni `split_snapshot` yazılır. Başka hiçbir bölme
      değiştirilemez. Pilotlar (Task 2.3, 3.3) `gold_reserve`'den yorum almaz.

Notlar: altın havuz yalnız tekrar grubu olmayan yorumlardan, uzunluk filtresi olmadan (karar 2026-10-07); tohum 42;
her altın bölme kendi içinde %70/%30. Geliştirme veritabanında: gold_dev 100, gold_test 200, gold_reserve 100,
silver_val 1.077, train 9.690; snapshot 1.

**Kabul kriteri:** Bölme sayıları plana uyuyor; hiçbir tekrar grubu iki bölmeye yayılmıyor; betik ikinci kez
çalışınca hiçbir satırı değiştirmiyor; elle bir `split` değiştirildiğinde snapshot doğrulaması hata veriyor.

## Task 1.4 — M-ABSA yükleme ve kategori eşlemesi

**Repo:** `turotel-qa`
**Alan:** `data`
**Durum:** Tamamlandı (2026-10-07)
**Bağımlılıklar:** Task 1.1

**Referanslar:** `docs/VERI_NOTLARI.md` (M-ABSA), `docs/PROJE_PLANI.md` §5.1

**Hedef dosyalar:** `src/turotel/data/`

### Checklist

- [x] `data/raw/mabsa_tr_hotel/{train,dev,test}.txt` → cümleler `reviews`'a (`source=mabsa`,
      `split=external_mabsa`, `publishable=false`), etiketler `mabsa_sentences`'e (ayrıştırma regex ile; Türkçe
      kesme işareti `ast.literal_eval`'i bozar). `split_snapshot` kapsamına girmez.
- [x] Temiz eşleşen kategoriler → alt kategori eşlemesi; `service general` yalnız "Hizmet ve personel" ana
      kategorisine; karşılığı olmayanlar (rezervasyon, check-in, fatura, güvenlik, Wi-Fi, animasyon) kapsam
      dışı olarak listelenir.
- [x] 20 cümle elle incelenir: çeviri mi? Sonuç `docs/VERI_NOTLARI.md`'ye yazılır; çeviriyse raporda
      "çevrilmiş Türkçede test edildi".

Notlar: ham dosyalar Hugging Face'ten indirildi (gitignore'da). Eşleme düzeyi kararı: net eşleşenler alt kategori
(1.134 etiket), belirsizler yalnız ana kategori (1.735), kapsam dışı 89 etiket. 20 cümle incelendi: çeviri doğrulandı.
Gerçek Türkçe otel alternatifi arandı, uygun hazır veri çıkmadı (ayrıntı `docs/VERI_NOTLARI.md`).

**Kabul kriteri:** 2.147 cümle yüklü; eşleme tablosu ve kapsam dışı listesi belgelenmiş; 20 cümlelik
inceleme sonucu yazılı.

## Task 1.5 — `validate_run`

**Repo:** `turotel-qa`
**Alan:** `db`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 0.3, Task 1.1

**Referanslar:** `docs/VERI_KATMANI.md` §3 (Doğrulama)

**Hedef dosyalar:** `src/turotel/validation.py`, `tests/`

### Checklist

- [ ] Kural 1–6 (`docs/VERI_KATMANI.md`): şikâyet ⇔ ham olumsuz etiket (çift yönlü); `done` yorumda tam alt
      kategori kümesi, `skip`'te etiket yok; ciddiyete göre durumlar (yalnız human/jev); `recommended` ⇒
      1..üst sınır aksiyon (jev 1, human 3), diğerleri 0; koşu türüne göre NULL kuralları; taksonomi
      kimliklerinin şema sürümünde geçerliliği ve tekrar grubu tek bölmede.
- [ ] Başarılıysa `validated_at` yazar; hata raporu kural ve satır kimliğiyle.
- [ ] Eşik değişirse doğrulanmış koşunun `validated_at`'ini silen yardımcı.
- [ ] Her kural için bilerek bozulmuş örnekle test.

**Kabul kriteri:** Her kuralı ihlal eden bir test koşusu doğru kural adıyla reddediliyor; geçerli bir koşu
`validated_at` alıyor.

## Task 1.6 — Değerlendirme çekirdeği

**Repo:** `turotel-qa`
**Alan:** `eval`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 0.3

**Referanslar:** `docs/PROJE_PLANI.md` §5.5 (Metrikler), §5.6 (Değerlendirme), `docs/VERI_KATMANI.md` §3
(Model ve sonuçlar)

**Hedef dosyalar:** `src/turotel/evaluation/`, `tests/`

### Checklist

- [ ] Tahmin koşusu vs referans koşu karşılaştırması (eval view'ları üzerinden): konu tespiti mikro+makro
      F1, bahsedilenlerde duygu makro F1, şikâyet tespiti mikro+makro F1, departman makro F1, ciddiyet MAE +
      kuadratik ağırlıklı kappa, ana kategori düzeyinde yeniden hesap.
- [ ] Öneri metrikleri: MRR (susulan uygun sorgular sıfır puanla paydada), Hit@1, Hit@3, kapsam.
- [ ] Yorum düzeyinde bootstrap güven aralıkları; eşleştirilmiş bootstrap fark testi; desteği 5'ten az
      sınıflar makro F1 dışında, destekleri raporlanır.
- [ ] Sonuçlar `eval_results`'a (`prediction_run_id` oracle'da NULL, `eval_mode`, `config`).

**Kabul kriteri:** Elle hesaplanmış küçük bir örnekte tüm metrikler birebir tutuyor; aynı tohumla bootstrap
aynı aralığı veriyor.

## Task 1.7 — Gerçek yorum girişi

**Repo:** `turotel-qa`
**Alan:** `data`
**Durum:** Başlamadı
**Bağımlılıklar:** Task 0.3

**Referanslar:** `docs/PROJE_PLANI.md` §5.1 (Gerçek yorumlar)

**Hedef dosyalar:** `src/turotel/data/`

### Checklist

- [ ] Kullanıcının topladığı yorumları (toplama protokolü kullanıcıya ait) `reviews`'a `source=real`,
      `split=external_real`, `publishable=false` olarak ekleyen komut.
- [ ] Kişisel bilgi temizliği kullanıcı tarafından yapılmış olarak gelir; komut yalnız boş/çok kısa/tekrar
      kontrolü yapar.
- [ ] Bu yorumlar `split_snapshot` kapsamına girmez.

**Kabul kriteri:** Örnek bir dosyadan eklenen yorumlar `external_real` olarak görünüyor; HUMIR snapshot
doğrulaması bozulmuyor; `publishable=true` yapılmaya çalışıldığında veritabanı reddediyor.
