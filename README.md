# ZAĞANOS intake simülasyonu

FTC intake (mecanum + huni) için numpy tabanlı top–robot temas simülasyonu ve tasarım taramaları.

- `sim3.py` fizik, `rounds.py` tur tanımları, `batch3.py` tarayıcı (`SHARD=i/n` ile parçalı çalışır).
- GitHub Actions: **Actions → sweep → Run workflow**, tur adı (ör. `r4`) ve parça sayısı. Sonuç `<tur>-sonuc` artifact'inde.
- Yerel: `python batch3.py r4 r4.jsonl`

Sonuçlar simülasyondur; gerçek top/roller ölçümüyle doğrulanmadı.
