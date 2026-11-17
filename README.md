# 响度归一与限峰

一个按整体响度做归一、同时不破坏峰值的母带处理器。仅用 Python 标准库，输出确定性（两次运行逐字节一致）。

## 保留签名

- `read_wav_samples(path)` → `(rate, samples)`，16 位单声道 WAV，samples 为 int 列表
- `write_wav_samples(path, rate, samples)` → 写 16 位单声道 WAV
- `loudness_lufs(samples, rate)` → 整体响度（LUFS）
- `normalize(samples, rate, target_lufs)` → 线性增益
- `limit_peak(samples, rate, ceiling_db)` → 限峰后的 samples

## 算法与判据

### 响度（ITU-R BS.1770 风格）

- K 加权滤波（高架 + RLB 高通，系数按采样率重算），400 ms 块、75% 重叠。
- **静音门限**：块响度低于 **-70 LUFS**（绝对门限）或低于未门控整体响度 **10 LU**（相对门限）的块不计入，静音段不会拉低整体响度；不同节目素材的结果因此可比。
- 归一命中窗口：目标 **±0.5 LU**。

### 限峰

- 5 ms 前瞻取所需增益的窗口最小值，再经 1 ms 攻击 / 50 ms 释放的包络平滑，最后以瞬时所需增益兜底——数学上保证任何采样 `|s| ≤ floor(32768·10^(ceiling/20))`，超限样本计数为 0。
- 限峰后响度相对目标值的偏差不超过 **±1 LU**（与峰值上限同时满足）。

### 失真

- 限峰引入的总谐波失真（THD，前 10 次谐波）阈值 **0.5%**；同输入下硬截断约 22%，软限峰实测约 0.001%。
- **泵动判据**：叠加 50 ms 大瞬态后 150 ms 处，持续音的短时分组电平相对瞬态前回落不超过 **1 dB**。

## 自测

```
python -m pytest tests -q
python -m loudness.cli data/quiet.wav --target -14 --ceiling -1 --out loud.wav
```

## 实测（data/quiet.wav，target -14 LUFS，ceiling -1 dBFS）

| 指标 | 数值 |
| --- | --- |
| 归一前响度 | -29.98 LUFS |
| 归一增益 | +15.98 dB |
| 归一后响度 | -14.00 LUFS |
| 超限样本数 | 0（上限 29204） |
| 限峰后响度 | -14.00 LUFS |
| 限峰失真 | 0.0000 % |

两次运行输出 176444 字节，逐字节一致。
