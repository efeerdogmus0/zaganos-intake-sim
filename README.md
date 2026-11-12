# ZAĞANOS intake simülasyonu

FTC intake (mecanum + huni) için numpy tabanlı top–robot temas simülasyonu ve tasarım taramaları.

- `sim3.py` fizik, `rounds.py` tur tanımları, `batch3.py` tarayıcı (`SHARD=i/n` ile parçalı çalışır).
- GitHub Actions: **Actions → sweep → Run workflow**, tur adı (ör. `r4`) ve parça sayısı. Sonuç `<tur>-sonuc` artifact'inde.
- Yerel: `pip install -r requirements.txt` sonra `python batch3.py r4 r4.jsonl`
- Hiz: fizik dongusu `fastk.py` icinde numba ile derlenir (cozucu, mesh temaslari, silindir/makara SDF).
  Numba yoksa `sim3.World.run_ref` eski saf Python cozucudur. M1'de r4 (592 is, 6 isci) ~6600 s -> ~300 s.
  Sonuclar eski surumle 1516 topun 1514'unde ayni; farklar kaotik temasta 1e-16 yuvarlama buyumesi.

Sonuçlar simülasyondur; gerçek top/roller ölçümüyle doğrulanmadı.
