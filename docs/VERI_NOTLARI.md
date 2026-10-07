# Veri Notları

İncelenme tarihi: 2026-10-05. Ham veriler `data/raw/` altındadır.

## İndirilen kaynaklar

### HUMIR — `data/raw/humir/HUMIRSentimentDatasets.csv`
- Kaynak: HF `Alaettin/Humir-Sentiment-Datasets` (Hacettepe HUMIR; otelpuan.com + beyazperde.com), lisans apache-2.0 (HF kartında)
- Makale: "SentiWordNet for New Language: Automatic Translation Approach" (IEEE, doc 7907484)
- Format: `;` ayraçlı, UTF-8 BOM. Sütunlar: `ReviewId;Type;Content;Class;Split;Fold`
- Otel kısmı: `Type == "Hotel Review"` → 11.600 satır (5.800 Positive / 5.800 Negative; train 5.800 / test 5.800; Fold hep 1)
- Uzunluk (kelime): ortalama 77, medyan 48, maks. 2.724
- 411 tekrar eden metin (699 satır tekrar grubunda, 288 benzersiz metin); 657 yorum 5 kelimeden kısa
- **Hazır train/test ayrımında 39 metin iki tarafta da var** → hazır ayrım kullanılmaz (Grok 4.7 ölçümü)
- Kelime uzunluğu dağılımı: p90 177, p95 240, p99 447; >128 kelime %17,6, >256 %4,4, >512 yalnızca 80 yorum (%0,7)
- Yorumların yalnızca ~%36'sında noktalama var → cümle bölme güvenilir değil; etiketleme yorum düzeyinde yapılmalı
- Türkçe karakterler doğru (Windows konsolunda bozuk görünürse `PYTHONIOENCODING=utf-8`)

### M-ABSA Türkçe otel — `data/raw/mabsa_tr_hotel/{train,dev,test}.txt`
- Kaynak: HF `Multilingual-NLP/M-ABSA` (`hotel/tr/`), makale arXiv:2502.11824
- 2.147 cümle (train 1.254 / dev 307 / test 583 satır); 419'unda etiket yok (`[]`)
- Format: `cümle####[['terim', 'kategori', 'polarite'], ...]`
  - Türkçe kesme işareti (ör. `Affinia'ya`) `ast.literal_eval`'i bozar → regex ile ayrıştır
- Polarite: positive 2.429, negative 452, neutral 77 (olumluya çok kayık)
- 558 cümlede birden fazla kategori
- En sık kategoriler: hotel general 695, service general 518, location general 412,
  rooms design_features 180, rooms general 151, food_drinks quality 116, hotel prices 110,
  rooms cleanliness 99, facilities general 80
- Cümleler büyük ihtimalle İngilizceden çeviri (doğrulanmadı)
- Kullanım: Hafta 13'te temiz eşleşen alt kümede Jev ve modelimiz için konu alanında ortak dış sınav (PROJE_PLANI §5.9). Hafta 1 incelemesinde çeviri olduğu görülürse yalnızca "şema aktarım testi" olarak raporlanır.

### Alanya derlemi — `data/raw/alanya/`
- Kaynak: Zenodo DOI 10.5281/zenodo.20766305 (GitHub `humanizemyai/alanya-tourism-nlp` v1.0.0), CC-BY-4.0
- `reviews_deidentified.csv`: 12.222 satır, **metin sütunu yok** (puan, dil, mekân türü, tarih, türetilmiş duygu ve yön skorları, konu id)
  - category: restaurant 4.000, hotel 3.972, attraction 2.500, beach 1.750
- Metin etiketlemede kullanılamaz.
- `data/forecast/antalya_monthly.csv` ile TimesFM-3 denemesi düşünülmüştü; 2. tur değerlendirmede plandan çıkarıldı. Bu proje için kullanılmıyor.

### Google Maps (incelendi, kullanılmıyor) — `data/raw/gmaps/train.csv`
- Kaynak: HF `opdullah/turkish-google-maps-reviews` (838.583 yorum, 300 MB CSV; dataset viewer istatistikleri çalışmıyor)
- Otel/pansiyon/tatil etiketli `place_category`: yalnızca **3.655 yorum, 9 işletme**; kategoriler çoğunlukla
  "Restoran, Otel, Plaj Kulübü" gibi karma (asıl işletme restoran/plaj/golf kulübü)
- Puan: 5★ 2.358, 4★ 563, 3★ 277, 2★ 122, 1★ 335; medyan 13 kelime; bir kısmı İngilizce
- Karar (2026-10-06): eğitime eklenmedi; 9 işletme çeşitlilik sağlamaz

## Hugging Face taraması özeti (2026-10-05)

Türkçe + otel alanında bulunanlar:
- Veri: HUMIR (yukarıda), `Fath-Karaman/turkish-deception-detection-hotel-reviews` (HUMIR'in etiketsiz kopyası), M-ABSA tr/hotel, `firatmihci/alanya-tourism-reviews`
- Modeller: `anilguven/{bert,albert,distilbert,electra}_tr_turkish_hotel_reviews` (HUMIR üzerinde ikili duygu, ALBERT doğruluk %96,6), `Apoksk1/*-HotelSentiment` (kart boş)
- Space'ler: çoğu oyuncak/şablon; en ciddisi `ESMATUGBA/Hotel-Demand-Forecasting` (LSTM)
- **Departman / kök neden / aksiyon / DÖF odaklı Türkçe çalışma yok.**

Genel Türkçe yardımcı kaynaklar: `ytu-ce-cosmos/absa-tr`, `STNM-NLPhoenix/turkish-absa`,
`winvoker/turkish-sentiment-analysis-dataset`, `maydogan/Turkish_SentimentAnalysis_TRSAv1`,
`nanelimon/complaint-classification-dataset`, `opdullah/turkish-google-maps-reviews` (838k).
