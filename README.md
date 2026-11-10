# Bugün Hava Nasıl? – Türkiye bölge bölge hava durumu botu

Meteoroloji Genel Müdürlüğü (MGM) verileriyle her sabah 7 coğrafi bölge için Instagram görseli üretir;
saatlik olarak MGM uyarılarını ve hava kaynaklı kapalı yolları (KGM) kontrol eder.

| Dosya | Görev |
|---|---|
| `hava_bot.py` | 7 bölge görseli + açıklama metni (`--demo`, `--gun 2`) |
| `uyari_bot.py` | Sarı/turuncu/kırmızı uyarı ve kapalı yol hikâye görselleri (`--demo`, `--kesif`, `--min-seviye`) |
| `.github/workflows/` | Günlük (07:17) ve saatlik otomatik çalışma |
| `durum.json` | Daha önce paylaşılan uyarılar (tekrar paylaşmamak için) |

Veri kaynakları: MGM (mgm.gov.tr), Karayolları Genel Müdürlüğü (kgm.gov.tr).
