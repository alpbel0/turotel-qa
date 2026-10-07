# TurOtel-QM — Roadmap

> Bu doküman "ne inşa edeceğiz" değil (bkz. `docs/PROJE_PLANI.md`, `docs/VERI_KATMANI.md`),
> "hangi sırayla inşa edeceğiz" dokümanıdır. Haftalık takvim `docs/PROJE_PLANI.md` §6'dadır; burada
> faz sırası, her fazın amacı ve her fazın kendi dosyasındaki task kırılımı var. Her faz `roadmap/`
> klasöründe kendi dosyasındadır; task'lar orada Repo/Alan/Durum/Bağımlılıklar/Referanslar/Hedef
> dosyalar/Checklist/Kabul kriteri alanlarıyla ayrıntılandırılmıştır.
>
> Kod 2026-10-07 itibarıyla yoktur; `data/raw/` altındaki ham veriler ve `docs/` dışında her şey bu
> roadmap'le kurulur.

## Proje hedefi

Türkçe bir otel yorumu sisteme girer; 29 alt kategorinin her biri için duygu bulunur; olumsuz çıkan her
alt kategori bir şikâyettir ve ona departman ve ciddiyet atanır; ciddiyeti 2 ve üstü şikâyetler için
bilgi grafındaki gerçek eğitim vakalarına dayanarak olası neden ve aksiyon önerilir, destek sayısı ve
benzer vakalarla açıklanır. Yanında sentetik otel göstergeleriyle PCMCI+ nedensellik ve TimesFM-3
tahmin/anomali deneyleri. Sonuçlar kör altın setlerle ölçülür; Hugging Face (veri seti + model + demo)
ve GitHub'da yayımlanır. (Ayrıntılar: `docs/PROJE_PLANI.md`.)

## Fazlar

- [Faz 0 — İskelet](phase-0-skeleton.md) — uv paketi, klasör yapısı, Docker Compose (Postgres + pgvector,
  Neo4j), Alembic ile tüm şema ve view'lar, geliştirmeden ayrı test ortamı.
- [Faz 1 — Veri](phase-1-data.md) — Taksonomi, HUMIR ve M-ABSA yükleme, temizlik ve tekrar grupları,
  kilitli bölmeler, `validate_run` ve değerlendirme çekirdeği.
- [Faz 2 — Elle etiketleme](phase-2-annotation.md) — Etiket rehberi, Streamlit aracı, pilot, kör altın dev,
  şemanın dondurulması, kör son test ve gerçek yorumlar.
- [Faz 3 — Jev ile gümüş etiket](phase-3-jev.md) — Jev istemcisi ve önbellek, iki çağrı, 500 yorumluk
  pilot, uçtan uca mini sistem, güven eşikleri, tam etiketleme ve dondurma.
- [Faz 4 — Model](phase-4-model.md) — Colab gidiş-dönüşü, TF-IDF baseline, BERTurk ve ModernBERT-TR
  (Model A + B), yerel çıkarım, dev'de karşılaştırma.
- [Faz 5 — Benzer vaka ve bilgi grafı](phase-5-recommendation.md) — pgvector embedding'leri, Neo4j
  yeniden kurma, öneri sorgusu ve geri çekilme, eşik seçimi ve ablasyonlar, elle kontrol.
- [Faz 6 — Nedensellik: PCMCI+](phase-6-causal.md) — Sentetik otel üreteci, A/B/C/K senaryoları, baseline
  ve değerlendirme.
- [Faz 7 — Tahmin ve anomali: TimesFM-3](phase-7-forecast.md) — Olay enjeksiyonu, Colab tahmini,
  baseline'lar, kalibre bant ve anomali ölçümü.
- [Faz 8 — Son test, demo ve yayın](phase-8-release.md) — Gradio demo, yayın şekli kararı, son testin bir
  kez açılması, HF veri seti ve model kartı, rapor ve GitHub (ana milestone).
- [Sonrası](post-mvp.md) — Sadece fikir listesi; ayrıntılar proje bittikten sonra konuşulacak.

---

## Notlar

- Fazlar arasında sıkı bir "önce bitir sonra geç" kuralı yok; özellikle Faz 2 (elle etiketleme) Faz 3 ve 4
  ile paralel ilerler, gerçek yorum toplama Hafta 1–6 boyunca sürer. Gerçek sıra her task'ın
  **Bağımlılıklar** alanındadır.
- Her task'ın kabul kriteri gerçek veriyle doğrulanır; uydurma veriyle "tamam" sayılmaz (sentetik deneyler
  hariç — onların verisi tanım gereği sentetiktir).
- **Kör değerlendirme kuralları her fazda geçerlidir:** altın etiketleme Jev çıktısını görmez; son test
  (`gold_test`) yalnız Task 8.2'de bir kez açılır ve sonucuna göre hiçbir ayar yapılmaz; graf, embedding
  indeksi ve eğitim yalnız `train` bölmesindeki tek dondurulmuş Jev koşusundan beslenir.
- Task numaraları sıralama değil **kalıcı kimliktir**: bir task taşınırsa eski numarası boş bırakılır,
  başka bir task'a yeniden atanmaz.
- Açık soru yoktur. Bilinçli olarak ilgili fazda kullanıcıyla verilecek kararlar task'larda
  "Proje içinde karar" olarak işaretlidir.
- Adlandırma: kod, dosya adları, Postgres tablo/sütun/ENUM değerleri ve Neo4j etiket/ilişki/özellik adları
  **İngilizcedir** (`docs/VERI_KATMANI.md`). Türkçe yalnız gösterilen metinlerde (kategori adları, demo arayüzü).
- Toplam task sayısı: **45** (Faz 0: 5, Faz 1: 7, Faz 2: 7, Faz 3: 6, Faz 4: 5, Faz 5: 5, Faz 6: 3,
  Faz 7: 3, Faz 8: 4). `grep -c "^## Task " roadmap/phase-*.md` toplamıyla doğrulanabilir.
