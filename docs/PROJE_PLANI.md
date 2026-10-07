# TurOtel-QM — Proje Planı

> Son güncelleme: 2026-10-06 — soru-cevap gözden geçirmesi tamamlandı (Bölüm 1–2 kullanıcıyla,
> Bölüm 3–11 Codex `gpt-5.6-sol` danışmanlığıyla karara bağlandı). Aynı gün veri katmanı (PostgreSQL + pgvector,
> Neo4j) eklendi, ayrıntısı `VERI_KATMANI.md`'de. Takvim 14 hafta.
> QM = Quality Management. HF adları: `turotel-qm-dataset`, `turotel-qm-model`, `turotel-qm-demo`.

## 1. Amaç ve kapsam

Türkçe otel yorumlarını okuyup **her konunun duygusunu**, **her şikâyetin sorumlu departmanını ve
ciddiyetini**, ve şikâyetler için **olası neden faktörünü ve önerilen aksiyonu** üreten açık kaynak bir sistem.
Yanında sentetik otel göstergeleri üzerinde nedensellik (PCMCI+) ve tahmin/anomali (TimesFM-3) deneyleri.

- **Modüller (dördü de):** (1) konu bazında duygu + şikâyet sınıflandırma, (2) benzer vaka + bilgi grafı
  ile olası neden/aksiyon önerisi, (3) PCMCI+ nedensellik deneyi, (4) TimesFM-3 tahmin ve anomali tespiti.
- **Yayın:** Hugging Face (veri seti + model + Gradio Space) ve GitHub. Metinler İngilizce + kısa Türkçe
  özet; demo arayüzü Türkçe.
- **Akademik hedef (isteğe bağlı):** sonuçlar ilginç çıkarsa hocayla kongre bildirisine dönüştürülebilir.
- Kişisel CV/portföy projesi; tek kişi, haftada ~8–10 saat.

## 2. Neden bu proje?

- HF'te Türkçe otel verisiyle yapılan işler yalnızca ikili duygu analizinde kalıyor; konu bazında duygu,
  departman, neden ve aksiyon önerisi yapan çalışma yok (bkz. `VERI_NOTLARI.md`).
- Otel kalite yönetimi alanındaki yöntemlerin (Türkçe NLP ile bilgi çıkarımı, vaka tabanlı öneri,
  zamansal nedensellik, tahmin) küçük ve açık bir versiyonu.

## 3. Örnek

> *"Odalar tertemizdi ama akşam yemeği soğuktu, garsonlar da çok ilgisizdi."*

| Alt kategori | Duygu | Şikâyet? | Departman | Ciddiyet | Olası neden faktörü | Önerilen aksiyonlar |
|---|---|---|---|---|---|---|
| Oda temizliği | olumlu | — | — | — | — | — |
| Yİ kalite/lezzet | olumsuz | ✔ | Yiyecek-içecek | 2 | Standart/denetim zafiyeti | Prosedür/checklist revizyonu |
| Tutum/nezaket | olumsuz | ✔ | Yiyecek-içecek | 2 | Hizmet icrası/yetkinlik | Eğitim, koçluk ve performans takibi |

+ her şikâyet için en benzer 3 geçmiş vaka, destek sayısı ve önerinin hangi geri çekilme seviyesinden geldiği.
Olası neden **doğrulanmış kök neden değildir**; misafir yorumu yalnızca yakın nedeni gösterir.

## 4. Etiket şeması

### 4.1 Konu bazında duygu (yorum düzeyi)
Her **alt kategori** için: `bahsedilmiyor` · `olumlu` · `olumsuz` · `nötr`. 9 ana / 29 alt kategori
(Codex önerisi; literatürde SemEval otel şeması da iki seviyeli varlık–öznitelik yapısındadır):

| Ana kategori | Alt kategoriler |
|---|---|
| Genel otel deneyimi | genel memnuniyet · otel kalitesi/beklentiyi karşılama · atmosfer-tasarım-gürültü |
| Oda ve banyo | oda geneli/büyüklük · yatak-konfor-iklim · oda temizliği · banyo/su · oda ekipmanı-bakım-arıza |
| Yiyecek-içecek | kalite/lezzet · çeşit/seçenek · servis-sunum · fiyat |
| Hizmet ve personel | tutum/nezaket · yetkinlik/sorun çözme · hız-bekleme · iletişim/bilgilendirme |
| Rezervasyon ve ön büro | rezervasyon doğruluğu · check-in/out ve oda hazırlığı · ödeme-fatura-iptal |
| Tesis ve aktiviteler | havuz-plaj · spa-spor · animasyon-aile/çocuk · Wi-Fi/teknoloji · ortak alan-otopark-bakım |
| Konum ve ulaşım | erişim/ulaşım · çevre/manzara/yakınlık |
| Fiyat ve değer | genel fiyat-performans · ek ücret/fiyat şeffaflığı |
| Güvenlik | kişi/eşya/tesis güvenliği |

- Ana kategori ayrıca etiketlenmez; alt kategorilerden türetilir (herhangi bir alt kategori bahsedildiyse
  ana kategori bahsedilmiş, herhangi biri olumsuzsa ana kategoride şikâyet var).
- Pilot sonrası seyrek/sürekli karışan alt kategoriler kardeşiyle birleştirilebilir (karar zamanı gelince,
  veriye göre; hedef aralık 20–24).
- Kaldırılanlar: yorum düzeyi tek duygu, "ana konu", yorum düzeyi "ana/ilgili departman".

### 4.2 Şikâyet (olumsuz çıkan her alt kategori = 1 şikâyet)

**Birincil departman (11)** — "sorunu üreten / düzeltici aksiyonun sahibi olan birim":

| Departman | Kapsam / sınır kuralı |
|---|---|
| Ön büro / misafir ilişkileri | resepsiyon, check-in/out, concierge, misafir iletişimi; şikâyetin iletildiği yer değil, hatayı üreten birim esas |
| Kat hizmetleri | oda/ortak alan temizliği, tekstil, buklet, oda hazırlığı; cihaz arızası teknikte |
| Yiyecek-içecek | mutfak, restoran, bar, oda servisi; garson/bekleme burada; gizli ücret ticari işlemlerde |
| Teknik servis / BT | klima, elektrik, su, asansör, Wi-Fi, cihaz ve yapı bakımı |
| Animasyon / çocuk aktiviteleri | şovlar, eğlence, mini club; spor alanının fiziksel durumu rekreasyonda |
| Spa & wellness | spa, hamam, sauna, masaj |
| Havuz-plaj-rekreasyon | havuz, plaj, şezlong, su sporları; pompa/ısıtma arızası teknikte |
| Güvenlik | kişi, eşya, erişim, olay müdahalesi; bozuk kasa cihazı teknikte |
| Rezervasyon ve ticari işlemler | rezervasyon doğruluğu, fiyat koşulu, iptal, iade, ödeme, fatura |
| Genel yönetim | **yalnızca** politika, konsept veya birden çok birimi açıkça kapsayan şikâyetler |
| Belirsiz / kanıt yetersiz | şikâyet var ama sorumlu birim anlaşılamıyor; sadece "kötüydü" diyen yorum buraya |

Departman konudan sabit tabloyla türetilmez. Rehberde 29 alt kategori için "olası departmanlar" tablosu
yardımcı olarak bulunur (zorunlu kural değil).

**Ciddiyet (4 seviye)** — yalnızca metindeki **somut etkiye** göre; abartılı dil puan yükseltmez, telafi
ciddiyeti düşürmez, ortak sonuç yalnızca nedensel olarak bağlı şikâyete yazılır:

| Seviye | Tanım | Örnek |
|---|---|---|
| 1 Küçük | Kısa, tekil, temel hizmeti etkilemeyen kusur | "Bir havlu eskiydi." |
| 2 Orta | Belirgin rahatsızlık; tekrar eden, birkaç saatlik aksama, bir yan hizmetin kullanılamaması | "Kahvaltıda üç gün sıcak su yoktu." |
| 3 Ciddi | Temel işlevde önemli kayıp; günlerce süren/çözülmeyen; oda değişimi, iade, erken ayrılma | "Klima iki gün çalışmadı, başka oda verilmedi." |
| 4 Kritik | Sağlık/güvenlik ihlali ya da konaklamanın sürdürülememesi | "Yemekten sonra hastaneye kaldırıldık." |

"Uygulanamaz" yalnızca şikâyet yokken (sistem atar). Şikâyet var ama etkisi belirsizse metindeki en düşük
somut seviye (genelde 1) verilir.

**Olası neden faktörü (13 + durum kodu)** — yalnızca **ciddiyet ≥ 2** şikâyetlerde:

| Grup | Faktör | Tipik ipucu |
|---|---|---|
| İnsan | personel kapasitesi | "tek garson vardı" |
| İnsan | hizmet icrası / yetkinlik | "sorunu çözemedi" |
| Süreç | planlama / koordinasyon | "üç birim birbirine yönlendirdi" |
| Süreç | standart / denetim zafiyeti | "her gün havlu unutuldu" |
| Kapasite | talep / kapasite uyumsuzluğu | "şezlong yetmedi", "uzun kuyruk" |
| Malzeme | tedarik / stok | "içecekler bitti" |
| Teknik | bakım / arıza | "klima bozuktu" |
| Fiziksel | tasarım / kapasite kısıtı | "banyo çok dar", "tek asansör" |
| Fiziksel | yıpranma / yenileme ihtiyacı | "her yer eski" |
| İletişim | bilgilendirme kopukluğu | "kimse açıklamadı" |
| Ticari | politika / vaat uyumsuzluğu | "fotoğraftaki havuz kapalıydı" |
| Çevre | dış etken / üçüncü taraf | hava, belediye altyapısı, acente hatası |
| Uyum | ürün / beklenti uyuşmazlığı | "çocuk oteli bana uygun değilmiş" |
| Durum | kanıt yetersiz | ayrıntı yok |

Pilot kontrolü: ilk 100 etiketten sonra "planlama/koordinasyon", "standart/denetim" ve "hizmet icrası"
arasındaki karışma oranına bakılır; çok karışıyorsa birleştirilir.

**Aksiyon (13 sistemsel aksiyon ailesi)** — yalnızca **ciddiyet ≥ 2** şikâyetlerde:

| Aksiyon | Tipik neden faktörleri |
|---|---|
| İş gücü / kaynak ayarlaması | personel kapasitesi; talep/kapasite |
| Eğitim, koçluk ve performans takibi | hizmet icrası/yetkinlik |
| Vardiya ve iş yükü planlama | planlama/koordinasyon; personel kapasitesi |
| Prosedür, checklist ve denetim revizyonu | standart/denetim; planlama/koordinasyon |
| Talep ve kapasite kontrolü | talep/kapasite uyumsuzluğu |
| Stok, satın alma ve tedarikçi yönetimi | tedarik/stok; üçüncü taraf |
| Arıza giderme ve planlı bakım | bakım/arıza; yıpranma |
| Yenileme ve ekipman değişimi | yıpranma/yenileme |
| Fiziksel düzen / kapasite yatırımı | tasarım/kapasite kısıtı |
| Misafir bilgilendirme ve beklenti yönetimi | bilgilendirme kopukluğu; ürün/beklenti |
| Politika, vaat ve içerik revizyonu | politika/vaat; ürün/beklenti |
| Fiyat–değer / paket gözden geçirme | politika/vaat; ürün/beklenti |
| Üçüncü taraf yönetimi ve yedek plan | dış etken/üçüncü taraf; tedarik/stok |

- Ayrı **aksiyon durumu** alanı: önerildi (`recommended`) · gerekmiyor (`not_needed`) · kanıt yetersiz
  (`insufficient_evidence`) · öneri kapsamı dışında (`out_of_scope`, ciddiyet 1) · uygulanamaz (yalnız sistemde, satırda yok). Bunlar öneri listesine girmez.
- Altın sette şikâyet başına **en fazla 3, sırasız** kabul edilebilir aksiyon (normalde 1). "Kanıt yetersiz"
  ise aksiyon seçilmez.
- Anlık telafi (özür, oda değişimi, iade) ayrı bir alan olarak **eklenmedi** (v2 fikri).
- Rastgele 30 ciddiyet-1 şikâyeti pilotta neden/aksiyon açısından kör denetlenir; anlamlı aksiyonlar sık
  çıkarsa eşik yeniden açılır.

Olası neden ve aksiyon **modele öğretilmez**; graf + benzer vaka üretir (§5.6).

## 5. Aşamalar

### 5.1 Veri (Hafta 1)
- **HUMIR** (~11.190 yorum, tekrarlar silinince): eğitim + altın havuz. **Kısa yorumlar (657, <5 kelime) kalır.**
- **M-ABSA Türkçe otel** (~2.150 cümle): yalnızca dış sınav (konu alanı). Hafta 1'de 20 cümleye bakılır;
  çeviri çıkarsa "çevrilmiş Türkçede test edildi" diye raporlanır. Eşleme: temiz eşleşen kategoriler;
  `service general` yalnız "Hizmet ve personel" ana kategorisine; rezervasyon, check-in, fatura, güvenlik,
  Wi-Fi, animasyon için karşılık yok — kapsam ayrıca raporlanır.
- **Gerçek yorumlar:** kullanıcı Hafta 1–6'da **100** yorum toplar (farklı otel tipleri/kaynaklar);
  kişisel bilgi silinir, ham metin yayınlanmaz, scraping yok. Dış test.
- **Google Maps** veri seti incelendi, kullanılmıyor (otel etiketli 3.655 yorum, 9 işletme).

**Bölümler:**

| Bölüm | Boyut | Etiket | Kullanım |
|---|---|---|---|
| Eğitim | ~%90 (~9.800) | Jev (gümüş) | Model eğitimi, graf ve embedding indeksi |
| Gümüş doğrulama | ~%10 (~1.100) | Jev (gümüş) | Erken durdurma |
| Altın dev | 100 | Kör, elle | Model seçimi, eşikler, ablasyon, Jev karşılaştırması |
| Altın rezerv | 100 | — | Son test 300'e çıkarsa `gold_test`'e geçer; yoksa Jev tam etiketlemesinden önce `train`'e döner |
| Son test | **200** | Kör, elle | Yalnızca **Hafta 13'te bir kez** açılır |
| Dış test | 100 gerçek yorum | Kör, elle | Hafta 13 |
| Dış sınav | M-ABSA | Hazır | Hafta 13, konu alanı |

- Altın havuz (300 + 100 rezerv) HUMIR etiketine göre **%70 olumsuz / %30 olumlu**, Jev'e bakılmadan seçilir; eğitimden ayrı.
- Aynı/çok benzer yorumlar aynı bölüme düşer; hazır HUMIR ayrımı kullanılmaz (39 metin iki tarafta).
- Graf ve embedding indeksi yalnızca eğitimden. Son test şema dondurulduktan sonra etiketlenir.
- İlk 100 etiketten sonra medyan süre ≤ 3 dk ise son test 300'e çıkarılabilir (`gold_reserve` → `gold_test`);
  > 5 dk ise 150'ye inilir (artan 50 ve rezerv → `train`). Bu tek seferlik, KARARLAR'a yazılan kayıtlı bir
  işlemdir ve Jev tam etiketlemesinden önce yapılır; hiçbir pilot (elle 30, Jev 500) rezerve dokunmaz.
- Tüm veri Postgres'e yüklenir; bölmeler bir kez atanır, değiştirilemez ve `split_snapshot` ile korunur.
  Eğitim/graf/embedding yalnız tanımlı view'lardan okur (`VERI_KATMANI.md` §3).

### 5.2 Elle etiketleme (Hafta 2–6)
- **Araç:** projeye özel küçük **Streamlit** arayüzü (yerel, ~6–10 saat). 29 alt kategori tablo halinde;
  olumsuz seçilen satırda şikâyet alanları açılır. Jev çıktısına erişmez (kör). Kayıtta `review_id`, şema
  sürümü, etiketler, süre, durum. Kayıtlar doğrudan Postgres'e (`aspect_labels`, `complaints`; her etiketçi bir koşu) yazılır.
  İlk 10 kayıt `validate_run` ile kontrol edilir.
- **Akış:** yorumu oku → 29 alt kategoriye durum ver → her olumsuz için departman, ciddiyet, (≥2 ise) neden
  ve 1–3 aksiyon → gerekirse belirsizlik notu.
- **Süre tahmini:** yorum başına ~3–5 dk → 400 yorum (100 dev + 200 test + 100 gerçek) ≈ 20–33 saat.
- **Rehber:** her etiketin tanımı, örnekleri, sınır örnekleri, alt kategori → olası departman tablosu.

### 5.3 Altın etiket kalitesi
Tüm altın etiketler (dev, son test, gerçek yorumlar) **tek etiketçi** (kullanıcı) tarafından, kör ve bir kez
yapılır; ikinci etiketçi veya ikinci geçiş yok, insan uyumu ölçülmez. Kalite; etiket rehberi, Hafta 2 pilotu,
araçtaki şema kısıtları ve `validate_run` ile korunur. Raporda ve veri kartında "altın etiketler tek etiketçi
tarafından yapıldı; etiketçiler arası uyum ölçülmedi" sınırlaması açıkça yazılır.

### 5.4 Jev ile etiketleme (Hafta 3–4)
- **Çağrı 1 (yorum başına):** 29 alt kategori için ayrı `choice` (bahsedilmiyor/olumlu/olumsuz/nötr).
- **Çağrı 2 (şikâyet başına ayrı):** `state` = yorum + `complaint_id` + hedef alt kategori adı/tanımı +
  "yalnız bu şikâyeti değerlendir". Sorular: departman `choice`, ciddiyet `choice` (4 seviye),
  ciddiyet ≥ 2 ise olası neden `choice` ve aksiyon `choice` (**top-1**; gümüşte çoklu aksiyon üretilmez).
- **Hacim:** ~10.890 × (1 + r) çağrı; r = yorum başına olumsuz alt kategori sayısı (pilotta ölçülür;
  r = 1 ise ~21.800 çağrı).
- **Pilot (500 yorum) ölçümleri:** r, güven dağılımı, altın dev'de doğruluk, geçersiz cevap oranı, süre,
  maliyet, nadir kategori dağılımı, 20–30 yorumda tekrar çağrı kararlılığı. Pilot görülmeden tam çağrı yok.
- **Düşük güven:** yorum atılmaz, ağırlıklandırılmaz, "bahsedilmiyor"a çekilmez; yalnızca ilgili alan
  **maskelenir** (neden/aksiyon düşükse graf kenarı üretilmez). Eşik soru ailesi başına (alt kategori
  durumu, departman, ciddiyet, neden, aksiyon) altın dev'de seçilir: cevapların ≥ %80'ini koruyan eşikler
  içinde hatayı en aza indiren; bootstrap duyarlılığı raporlanır.
- Cevaplar Postgres `jev_calls` önbelleğinde (aynı istek tekrar gönderilmez); kullanılan Jev sürümü kayda
  yazılır; API anahtarı yalnızca `.env`'de. Maske yazımda saklanmaz; eşik tablosundan view ile türetilir.

### 5.5 Model (Hafta 7)
Sıfırdan model eğitilmez; hazır Türkçe encoder'a ince ayar yapılır (Colab Pro). Veri Postgres'ten manifestli
Parquet ile Colab'a gider; model indirilir, tahminler yerelde `kind=model` koşusu olarak yazılır.

- **Model A (yorum düzeyi):** yorum bir kez kodlanır; 29 başlık × 4 durum.
  Kayıp ikiye ayrılır: `L_konu` (bahsedildi/bahsedilmedi) + `L_duygu` (yalnız bahsedilenlerde
  olumlu/olumsuz/nötr); kategori içinde sonra kategoriler arasında eşit ortalama; sınıf ağırlıkları
  frekanstan, en fazla ~5. Yeniden örnekleme yok; focal loss yalnızca ablasyon.
- **Model B (şikâyet düzeyi):** girdi `"[alt kategori] [SEP] yorum"`; ortak encoder üstünde departman
  (sınıf ağırlıklı CE) ve ciddiyet (**CORAL sıralı sınıflandırma**) başlıkları. Çıkarım: A → olumsuz alt
  kategoriler → her biri için B.
- **Adaylar:** TF-IDF + LR (baseline; 29 "bahsedildi" LR + 29 duygu LR; kelime 1–2 gram + karakter 3–5 gram;
  Model B için alt kategori adı metne eklenir), BERTurk (`dbmdz/bert-base-turkish-cased`),
  ModernBERT-TR (`ytu-ce-cosmos/modernbert-tr-base`, ana aday).
- **Sabit protokol:** aynı bölmeler/epoch/öğrenme oranı/batch; erken durdurma gümüş doğrulamada.
- **Seçim metriği (altın dev):** 29 alt kategoride "olumsuz şikâyet var/yok" **mikro F1**; güven aralıkları
  çakışıyorsa model değiştirilmez (ana aday korunur).
- **Öğrenme eğrisi:** 500 / 2.000 / tüm gümüş veri.
- **Metrikler:** konu tespiti mikro+makro F1; bahsedilenlerde duygu makro F1; şikâyet tespiti mikro+makro F1;
  departman makro F1 (oracle ve uçtan uca); ciddiyet MAE + kuadratik ağırlıklı kappa (oracle ve uçtan uca);
  ana kategori düzeyi alt kategoriler birleştirilerek yeniden hesaplanır; kategori başına sonuç ve destek
  zorunlu; Jev ile fark eşleştirilmiş bootstrap; sadakat (Jev'e benzeme) ve doğruluk (altına göre) ayrı.
- **Kalibrasyon:** ECE yalnız duygu ve şikâyet tespitinde, 5 kova; gümüş doğrulamada sıcaklık ölçekleme;
  testte risk–kapsam eğrisi.

**Neden kendi açık modelimiz?** Gizlilik (veri dışarıdaki API'ye gitmez), kontrol ve tekrarlanabilirlik,
açıklık; maliyet yalnızca ek avantaj (Jev zaten ucuz).

### 5.6 Benzer vaka + bilgi grafı (Hafta 8–9)
- **Graf (Neo4j):** şema katmanı (kategori, departman, neden, aksiyon) + vaka katmanı (eğitimdeki yorum ve
  şikâyet düğümleri; `ABOUT`, `ASSIGNED_TO`, `LIKELY_CAUSE`, `SUGGESTED_ACTION` ilişkileri). Tek dondurulmuş Jev
  koşusundan, Postgres'ten betikle yeniden kurulur. Model ve sorgular: `VERI_KATMANI.md` §2.
  **Aday (neden, aksiyon) çifti, tam yolu (dep, alt, neden, aksiyon) taşıyan farklı şikâyet sayısıyla
  puanlanır**; n, yumuşatılmış koşullu olasılık ve PPMI bu tam yollardan hesaplanır.
  Ciddiyet düğüm/filtre değil, metadata (açıklamada ve benzer vaka sıralamasında küçük bonus).
- **Geri çekilme:** departman + alt kategori → alt kategori → ana kategori → genel çoğunluk → sus.
  Her öneride seviye ve destek sayısı gösterilir.
- **Destek eşiği:** mutlak alt sınır 5 şikâyet; nihai eşik altın dev'de {5, 10, 15, 20} arasından **MRR**
  ile seçilir (susulan uygun sorgular sıfır puanla paydada). Belirsizse daha ihtiyatlı eşik.
- **Embedding:** `ytu-ce-cosmos/modernbert-tr-embed`; her şikâyet ayrı kayıt, metin
  `"[alt kategori] [SEP] tam yorum"`; arama önce aynı alt kategoride, yetmezse aynı ana kategoride.
  Vektörler pgvector'da, exact arama. Ablasyon: önekli/öneksiz. Embedding API yok.
- **Değerlendirme (altın aksiyonlara karşı):** **MRR birincil**, Hit@1 ve Hit@3; oracle ve uçtan uca; kapsam;
  ablasyon (yalnız embedding / yalnız graf / birleşim / koşullu çoğunluk / en sık 3 aksiyon); 20 sorguda
  benzer vakaların elle kontrolü (kategori uygunluğu, olgusal benzerlik, alakasız konu etkisi).

### 5.7 Nedensellik deneyi: PCMCI+ (Hafta 10)
**Sentetik otel:** 760 gün üretilir, ilk 30 atılır → 730 gün. Değişkenler:
doluluk oranı · yeni personel oranı · kişi başı eğitim saati · medyan oda hazırlama süresi ·
"Oda ve banyo" şikâyeti/100 dolu oda · "Hizmet ve personel" şikâyeti/100 dolu oda.
Doluluğa yıllık (genlik ~0,20) ve haftalık (~0,04) mevsimsellik; diğerlerine bağımsız mevsimsellik yok.
Tüm serilerde AR(1) = 0,35; gürültü ~1 SD.

| Neden → sonuç | Gecikme | Katsayı |
|---|---:|---:|
| Doluluk → oda hazırlama süresi | 1 gün | +0,45 |
| Doluluk → hizmet/personel şikâyeti | 1 gün | +0,30 |
| Yeni personel → hazırlama süresi | 3 gün | +0,25 |
| Yeni personel → hizmet/personel şikâyeti | 3 gün | +0,35 |
| Eğitim saati → hizmet/personel şikâyeti | 14 gün | −0,30 |
| Hazırlama süresi → oda/banyo şikâyeti | 1 gün | +0,40 |

- **A:** yukarıdaki ilişkiler. **B:** gözlenmeyen "personel devamsızlığı" aynı gün hazırlama süresini ve
  hizmet şikâyetini +0,50 etkiler (veride yok; aralarında doğrudan kenar yok). **C:** doluluk→hizmet şikâyeti
  doğrusal kenarı yerine yalnızca doluluk > %90 iken +0,80 SD. **K:** hiç çapraz bağlantı yok.
- **tigramite:** A, B, K'da `ParCorr`; C'de `ParCorr` ve `CMIknn`; `tau_min=0`, `tau_max=21`,
  `pc_alpha=0.05`, `fdr_method="fdr_bh"`, `max_conds_dim=3`, `max_combinations=1`; **10 tohum**.
  Takvim bileşenleri PCMCI+ öncesi çıkarılır ve standartlaştırılır. CMIknn süresi önce tek tohumla ölçülür.
- **Değerlendirme:** kenar = (kaynak, hedef, tam gecikme); TP yalnız üçü doğruysa. Gerçek ilişkilerin hepsi ≥ 1 gün gecikmeli olduğundan bulunan her aynı-gün (gecikme 0) çapraz kenarı yanlış
  pozitiftir; yönsüz (`o-o`) aynı-gün kenarı çift başına tek yanlış pozitif sayılır.
  Çapraz kenarlarda
  precision/recall/F1 (10 tohum ortalama ± SD); öz-kenarlar ayrı; ikincil: gecikmesiz yönlü F1, gecikme
  mutlak hatası, ±1 gün toleranslı F1, B'de sahte kenar oranı (özellikle aynı gün hazırlama süresi — hizmet
  şikâyeti; PCMCI+ gizli ortak neden olmadığını varsaydığından kanması beklenir), K'da tohum başına yanlış pozitif.
- **Baseline:** AR(1) artıklarında 0–21 gün Pearson çapraz korelasyon, BH (q < 0,05), çift başına en güçlü gecikme.
- Üreteç ve parametreler sonuçlara bakılmadan dondurulur.

### 5.8 Tahmin ve anomali tespiti: TimesFM-3 (Hafta 11)
- Aynı üretecin A senaryosu, aynı 10 tohum; hedefler ham ölçekte: oda/banyo günlük şikâyet sayısı,
  hizmet/personel günlük şikâyet sayısı, medyan oda hazırlama süresi.
- **Ufuk 14 gün, bağlam 512 gün** (7/28 gün ek deney yok).
- **Yan değişkenler:** geleceği bilinen — haftanın günü, mevsim, 14 gün önceden üretilmiş *planlanan*
  doluluk (gerçekleşenden kontrollü hata içerir); yalnızca geçmiş — eğitim saati, yeni personel oranı.
- **Baseline:** son değer + mevsimsel naif; rolling origin; MAE/MASE, kantil kaybı, kapsama.
- **Anomali:** TimesFM-3'ün q10–q90 bandı, temiz kalibrasyon dönemindeki hatalarla **%95 kapsamaya**
  genişletilir; dışı işaretlenir. Tohum başına 9 olay (her hedefe: 1 günlük +4 SD sıçrama, 7 günlük +2 SD
  seviye kayması, 14 günlük 0→+3 SD kademeli bozulma); çakışmasız, arada ≥ 7 temiz gün → 90 olay.
  Olay düzeyinde precision/recall/F1, ilk tespit gecikmesi, olay dışı yanlış alarm oranı; türler ayrı.
- Tahmin iyileşmesi nedensellik kanıtı sayılmaz. Ağırlıklar ticari olmayan lisanslı (kişisel proje için uygun).
- **Donanım:** nihai deneyler Colab GPU; yerelde yalnız kurulum ve tek seri hız ölçümü (CPU performansı doğrulanmadı).

### 5.9 Son test, demo ve yayın (Hafta 12–14)
- **Yayın şekli (Hafta 12):** ücretsiz Space'te Postgres/Neo4j çalıştırmak zor; muhtemelen DB'lerden dışa
  aktarılmış anlık görüntüyle çalışır, tam sistem `docker compose` ile GitHub'da. Karar Hafta 12'de.
- **Hafta 13:** son test bir kez açılır; Jev vs model, öneri metrikleri; gerçek yorum dış testi;
  M-ABSA dış sınavı. Test sonucuna göre model ayarı yapılmaz.
- **Gradio Space (3 sekme):**
  - *Tek yorum (canlı):* yalnız bahsedilen alt kategoriler, olumsuzlar önde; her şikâyet kartında alt kategori,
    duygu güveni, departman, ciddiyet, olası neden, ilk 3 aksiyon, destek sayısı, geri çekilme seviyesi;
    benzer 3 vaka açılır bölümde; "kanıt yetersiz" açık sonuç.
  - *Toplu analiz (canlı, ≤ 200 yorum CSV):* ana/alt kategori memnuniyet oranı (olumlu/bahsedilen) +
    bahsedilme sayısı, departman bazında şikâyet ve ciddiyet dağılımı, şablonla özet (ek dil modeli yok).
  - *Nedensellik ve tahmin:* önceden hesaplanmış grafikler, senaryo seçici, "sentetik deney" ibaresi.
  - CPU Basic (2 vCPU / 16 GB): ONNX/int8, tek istek kuyruğu, hazır indeks, sonuç önbelleği, hazır örnekler.
    HF'te Space oluşturma koşulları (ücretsiz plan) yayın öncesi doğrulanacak.
- **HF veri seti:** `silver` (train, validation) ve `gold` (dev, test) konfigürasyonları. Alanlar: `review_id`,
  `text`, `source`, `duplicate_group_id`, `schema_version`, 29 alt kategori etiketi, `complaints` listesi
  (`subcategory`, `department`, `severity`, `cause_factor`, `accepted_actions`), `label_source`, gümüşte
  genel Jev güveni. Jev olasılıkları ayrı `jev_scores` dosyası (soru kimliği, olasılıklar, güven, model/şema
  sürümü). `annotation_guidelines.md`, makine-okunur kategori JSON'u; etiketçi kimliği yok. Gerçek yorumlar ve onların embedding'leri yayınlanmaz.
  HUMIR `text` alanı yalnız Faz 8'de orijinal HUMIR kullanım şartları kontrol edilip yeniden yayına izin
  verdiği görülürse yayımlanır (HF'teki apache-2.0 bilgisi üçüncü kişinin kartından); değilse yalnız
  `review_id` + etiketler ve HUMIR'den birleştirme talimatı.
- **Model kartı:** özet ve taban model; amaçlanan/kapsam dışı kullanım; şema; eğitim verisi ve sızıntı kuralları;
  ön işleme ve eşikler; eğitim ayarları; altın test sonuçları (güven aralıklı); TF-IDF/BERTurk/Jev karşılaştırması;
  kalibrasyon ve kısa yorum performansı; dış test sonuçları; sınırlamalar ve hata örnekleri; kullanım örneği.
  **Olası neden ve aksiyonun modelin çıktısı olmadığı, doğrulanmış kök neden sayılmadığı** açıkça yazılır.
- GitHub: tüm kod, Colab notebook'ları, deney sonuçları, rapor.

## 6. Takvim (14 hafta, haftada ~8–10 saat)

| Hafta | İş |
|---|---|
| 1 | Docker (Postgres + pgvector, Neo4j); Alembic ile şema; taksonomi yükleme; HUMIR/M-ABSA yükleme, temizlik ve bölmeler + `split_snapshot`; `validate_run` iskeleti |
| 2 | Etiket rehberi v1; Streamlit etiketleme aracı (Postgres'e yazar); 30 örnek pilot |
| 3 | 100 kör dev etiketi (süre ölçülür); 500 yorumluk Jev pilotu + uçtan uca mini sistem |
| 4 | Şemanın dondurulması (gerekirse alt kategori birleştirme); Jev ile tam etiketleme ve kalite kontrolü |
| 5–6 | 200 kör son test etiketi; gerçek yorumların etiketlenmesi |
| 7 | TF-IDF, BERTurk, ModernBERT-TR (Model A + B); öğrenme eğrisi; dev'de Jev karşılaştırması |
| 8 | Embedding'ler pgvector'a; Neo4j yeniden kurma betiği; öneri sorguları |
| 9 | Geri çekilme; eşik seçimi; ablasyonlar; 20 sorgu elle kontrol |
| 10 | PCMCI+ senaryoları A, B, C, K |
| 11 | TimesFM-3 tahmin + anomali; baseline'lar |
| 12 | Demo entegrasyonu, yayın şekli kararı, CPU profili, kart/rapor taslakları |
| 13 | Son testin bir kez açılması; gerçek yorum ve M-ABSA testleri |
| 14 | Rapor, demo sağlamlaştırma, HF + GitHub yayını |
| 1–6 boyunca | Kullanıcı 100 gerçek yorum toplar ve (araç hazır olunca) kör etiketler |

**En riskli hafta:** 6 (etiket yorgunluğu). Önlem: Hafta 3'te medyan süre ölçülür;
yük aşarsa önce son test 150'ye iner, ikincil görselleştirmeler azaltılır.

## 7. Beklenen kazanımlar

- **CV satırı:** "Türkçe otel yorumları için konu bazında duygu ve şikâyet şeması (9 ana / 29 alt kategori),
  kör altın setli etiketli veri seti, güncel Türkçe encoder üzerinde iki aşamalı
  sınıflandırıcı, bilgi grafı destekli açıklanabilir öneri, nedensellik ve tahmin deneyleri; ticari bir
  modelle karşılaştırmalı değerlendirme (Hugging Face: veri seti + model + demo)."
- **Beceriler:** şema tasarımı, ilişkisel veri modelleme (PostgreSQL, pgvector), graf veri modelleme (Neo4j,
  Cypher), etiketleme aracı geliştirme, kör değerlendirme, LLM ile etiketleme,
  ABSA, encoder ince ayarı, sıralı sınıflandırma (CORAL), model değerlendirme, embedding araması, bilgi grafı,
  zaman serisi nedenselliği, temel model ile tahmin, Gradio, HF yayıncılığı.

## 8. Ortam

| | |
|---|---|
| Proje klasörü | `C:\Users\yigit\Desktop\turotel-qa` |
| Yerel makine | i7-1165G7 (4 çekirdek), 40 GB RAM, NVIDIA MX450 2 GB (eğitim için yetersiz) |
| Python | 3.11.9, sanal ortam `.venv` (proje klasöründe, uv ile) |
| Model eğitimi / TimesFM | Google Colab Pro |
| Etiketleme | TypeSafe Jev API + yerel Streamlit aracı |
| Veritabanları | PostgreSQL 17 + pgvector, Neo4j 5 Community; yerelde Docker Compose (Docker 29.6 kurulu) |
| Danışman model | Codex `gpt-5.6-sol` (salt okunur) |

### 8.1 Proje yapısı
Grok 4.7 ve Codex `gpt-5.6-sol` ile değerlendirildi (2026-10-06, ikisi de değişikliklerle kabul).
Klasörler Hafta 1'de oluşturulur.

```
turotel-qa/
├─ pyproject.toml             # uv paketi (hatchling, packages = ["src/turotel"]); default-groups = ["dev"]
├─ uv.lock                    # repoda
├─ .python-version            # 3.11, repoda
├─ .gitignore                 # .venv, .env, data/raw, data/exports, artifacts, __pycache__, .ipynb_checkpoints
├─ .env.example               # 127.0.0.1 adresleri, gizli olmayan yerel geliştirme şifreleri, boş Jev anahtarı (repoda)
├─ .env                       # gerçek şifreler + Jev anahtarı (gitignore)
├─ docker-compose.yml         # Postgres+pgvector, Neo4j; named volume; 127.0.0.1 portlar; "test" profili
├─ alembic.ini
├─ README.md
├─ docs/
│  └─ report/                 # nihai rapor (repoda)
├─ results/                   # yayınlanabilir küçük tablolar ve grafikler (repoda; ağır ara çıktılar değil)
├─ migrations/                # Alembic: extension, tablolar, CHECK'ler, CREATE VIEW (tek DDL kaynağı)
├─ src/turotel/
│  ├─ config.py               # .env okuma (tek yer)
│  ├─ db/                     # SQLAlchemy modelleri, bağlantı, view sorguları (DDL yok), test DB kurulumu
│  ├─ data/                   # HUMIR/M-ABSA yükleme, temizlik, bölmeler, split_snapshot
│  ├─ validation.py           # validate_run
│  ├─ labeling/               # Streamlit aracı
│  ├─ jev/                    # Jev istemcisi, istek şablonları, jev_calls önbelleği
│  ├─ export.py               # Colab Parquet + manifest; HF veri seti paketi (gerçek yorum/embedding hariç)
│  ├─ models/                 # TF-IDF baseline (yerel eğitim) + encoder çıkarımı
│  ├─ recommend/              # embedding, Neo4j yükleyici, öneri sorguları
│  ├─ synthetic/              # KPI üreteci, PCMCI+, TimesFM içe aktarma, anomali
│  ├─ evaluation/             # metrikler, bootstrap, eval_results
│  └─ demo/                   # Gradio (HF Space klasörü Hafta 12 kararıyla)
├─ notebooks/                 # Colab: encoder eğitimi, TimesFM
│  └─ requirements-colab.txt  # Colab bağımlılık sabitlemesi (uv grubu değil)
├─ tests/
├─ data/                      # gitignore
│  ├─ raw/
│  └─ exports/
└─ artifacts/                 # Colab'dan inen modeller (gitignore)
```

- **uv:** Çekirdek bağımlılıklar SQLAlchemy, Alembic, psycopg, neo4j, pyarrow, python-dotenv. Gruplar
  `labeling`, `ml`, `causal`, `demo`, `dev`; varsayılan yalnız `dev`, diğerleri gerektiğinde `uv sync --group <ad>`.
  TimesFM hiçbir grupta yok (yalnız Colab). `.venv` `uv sync` ile kurulur.
- **Komutlar:** iş betikleri `uv run python -m turotel.<modül>`; araçlar `uv run alembic …`, `uv run pytest`;
  grup gerektirenler grubu açıkça belirtir, ör. `uv run --group labeling streamlit run src/turotel/labeling/app.py`,
  `uv run --group ml python -m turotel.models…`. Ayrı `scripts/` yok.
- **Docker:** yalnız veritabanları container'da, uygulama host'ta çalışır (uygulama servisi yok). Bağlantılar
  `127.0.0.1:5432` (Postgres), `bolt://127.0.0.1:7687` ve `:7474` (Neo4j). DB verisi named volume'larda,
  proje klasöründe değil. Compose değişkenleri `${VAR:?…}` biçiminde; `.env` eksikse hemen hata verir.
- **Testler:** Postgres'te aynı container'da ayrı `turotel_test` veritabanı. `turotel.db` altındaki idempotent
  kurulum modülü yönetim DB'sine bağlanır, `_test` son ekini doğrular, DB yoksa oluşturur (transaction dışında),
  sonra Alembic migration'larını çalıştırır; adı `_test` ile bitmeyen DB'ye test yazmayı reddeder. Neo4j Community tek veritabanı olduğundan compose'da
  `test` profilli ayrı Neo4j (`127.0.0.1:7688`, ayrı volume); yeniden kurma testleri geliştirme grafını silmez.
- Klasör adı `turotel-qa` kalır; paket adı `turotel`; HF adları `turotel-qm-*`.
- **Git:** geliştirme yerel `work` dalında, istenildiği kadar commit. `main` commit'lerini ve push'u **yalnız
  kullanıcı** yapar: push istendiğinde Claude İngilizce, 1–2 cümlelik, somut olarak ne yapıldığını anlatan
  mesaj(lar) önerir (gerekirse bölme noktalarıyla); onaydan sonra `work`'ün ağacından `git commit-tree` ile
  main commit'lerini kuran bir PowerShell betiği (UTF-8 BOM, içinde push yok) ve tek bir cmd satırı verir;
  kullanıcı çalıştırıp `git push origin main` yapar. Hiçbir commit mesajında Claude/Sonnet satırı
  (`Co-Authored-By`, `Claude-Session`) yok. Force-push ve yayınlanmış geçmişi yeniden yazma yok. Kod yazan
  ajanlar `work`'e commit atabilir, push edemez.

## 9. Sınırlar ve kurallar

- Jev etiketleri gümüştür; doğruluk kör altın setlerle ölçülür.
- Yorumlar misafir görüşüdür; "olası neden" doğrulanmış kök neden değildir.
- Nedensellik/tahmin deneyleri sentetiktir; yöntemi gösterir, gerçek otel hakkında kanıt sunmaz.
- Altın dev'de yapılan her seçim (model, Jev güven eşikleri, destek eşiği, ablasyon kararları) KARARLAR'a
  "dev'de seçildi, n = …" diye yazılır ve raporun sınırlamalar bölümünde listelenir (100 yorumlu dev'e çok
  seçim yükleniyor; seyrek kategorilerde destek düşük).
- **Gizlilik:** Kullanıcının katılacağı TÜBİTAK projesine ait hiçbir içerik (öneri metni, sunum, proje/ontoloji
  adları, firma verisi, firma adı) bu projeye ve HF'e girmez.
