# 响度归一与限峰

一个按整体响度做归一、同时不破坏峰值的母带处理器

## 保留签名

- `read_wav_samples(path)`
- `write_wav_samples(path, rate, samples)`
- `loudness_lufs(samples, rate)`
- `normalize(samples, rate, target_lufs)`
- `limit_peak(samples, rate, ceiling_db)`

## 自测

```
python -m pytest tests -q
python -m loudness.cli data/quiet.wav --target -14 --ceiling -1 --out loud.wav
```
