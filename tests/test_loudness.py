# -*- coding: utf-8 -*-
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import loudness as mod  # noqa: E402
loudness = mod

RATE = 44100


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_hex(path):
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def sine(freq, amp, seconds, rate=RATE):
    n = int(seconds * rate)
    return [int(amp * 32767 * math.sin(2 * math.pi * freq * i / rate))
            for i in range(n)]


def goertzel_power(x, freq, rate=RATE):
    w = 2 * math.pi * freq / rate
    c = 2 * math.cos(w)
    s0 = s1 = s2 = 0.0
    for v in x:
        s0 = v + c * s1 - s2
        s2 = s1
        s1 = s0
    return s1 * s1 + s2 * s2 - c * s1 * s2


def thd(samples, fund, rate=RATE, harmonics=10):
    p1 = goertzel_power(samples, fund, rate)
    ph = sum(goertzel_power(samples, h * fund, rate)
             for h in range(2, harmonics + 1))
    return math.sqrt(ph / p1)


def rms_db(samples):
    e = sum(v * v for v in samples) / len(samples)
    return 10 * math.log10(e) if e > 0 else float("-inf")


# ---------------------------------------------------------------- 原有测试

def test_loudness_moves_towards_target():
    rate, s = loudness.read_wav_samples("data/quiet.wav")
    g = loudness.normalize(s, rate, -14.0)
    assert g > 1.0, "这份素材偏轻，增益应大于 1"


def test_peak_limit_zero_over():
    rate, s = loudness.read_wav_samples("data/quiet.wav")
    out = loudness.limit_peak(s, rate, -1.0)
    peak = max(abs(v) for v in out) / 32768.0
    assert peak <= 1.0


# ---------------------------------------------------------------- 响度

def test_loudness_hits_target_window():
    """归一后整体响度落在目标 ±0.5 LU 窗口内。"""
    rate, s = loudness.read_wav_samples("data/quiet.wav")
    g = loudness.normalize(s, rate, -14.0)
    gained = [int(round(v * g)) for v in s]
    loud = loudness.loudness_lufs(gained, rate)
    assert abs(loud - (-14.0)) <= 0.5, "归一后响度 %.2f 超出窗口" % loud


def test_silence_does_not_drag_loudness():
    """静音段不应把整体响度拉低超过 1 LU（门控生效）。"""
    tone = sine(440, 0.3, 1.0)
    with_silence = tone + [0] * RATE + tone
    l_tone = loudness.loudness_lufs(tone + tone, RATE)
    l_mix = loudness.loudness_lufs(with_silence, RATE)
    assert abs(l_mix - l_tone) <= 1.0, \
        "静音把响度拉低了 %.2f LU" % (l_tone - l_mix)


# ---------------------------------------------------------------- 限峰

def test_limit_zero_samples_over_ceiling():
    """热信号限峰后超限样本计数必须为 0。"""
    hot = sine(1000, 0.98, 1.0)
    out = loudness.limit_peak(hot, RATE, -1.0)
    ceil_amp = int(32768 * 10 ** (-1.0 / 20.0))
    overs = sum(1 for v in out if abs(v) > ceil_amp)
    assert overs == 0, "有 %d 个样本超限" % overs


def test_limit_keeps_loudness_near_target():
    """归一到目标后再限峰，响度不能掉出目标 ±1 LU。"""
    rate, s = loudness.read_wav_samples("data/quiet.wav")
    g = loudness.normalize(s, rate, -14.0)
    gained = [int(round(v * g)) for v in s]
    # 用 -11 dB 上限强迫限峰器介入，两个目标须同时满足
    out = loudness.limit_peak(gained, rate, -11.0)
    ceil_amp = int(32768 * 10 ** (-11.0 / 20.0))
    assert sum(1 for v in out if abs(v) > ceil_amp) == 0
    loud = loudness.loudness_lufs(out, rate)
    assert abs(loud - (-14.0)) <= 1.0, \
        "限峰后响度 %.2f 偏离目标超过容差" % loud


# ---------------------------------------------------------------- 失真

def test_thd_within_bound():
    """限峰引入的 THD 须低于 0.5%（硬截断同样输入约 22%）。"""
    hot = sine(1000, 0.98, 1.0)
    out = loudness.limit_peak(hot, RATE, -6.0)
    seg = out[4410:-4410]  # 去掉首尾建立段
    assert thd(seg, 1000) < 0.005


def test_no_pumping_on_attack():
    """起音瞬态过后 150 ms，持续音电平回落不超过 1 dB（无泵动）。"""
    tone = [0.1 * math.sin(2 * math.pi * 440 * i / RATE) for i in range(RATE)]
    for i in range(RATE // 2, RATE // 2 + int(0.05 * RATE)):
        tone[i] += 0.95 * math.sin(2 * math.pi * 2000 * i / RATE)
    sig = [int(v * 32767) for v in tone]
    out = loudness.limit_peak(sig, RATE, -1.0)
    pre = rms_db(out[int(0.40 * RATE):int(0.48 * RATE)])
    post = rms_db(out[int(0.70 * RATE):int(0.78 * RATE)])
    assert pre - post <= 1.0, "起音后电平被压低 %.2f dB，存在泵动" % (pre - post)


# ---------------------------------------------------------------- 输出

def test_output_byte_identical(tmp_path):
    """完整流程跑两次，输出 WAV 逐字节一致。"""
    rate, s = loudness.read_wav_samples("data/quiet.wav")
    blobs = []
    for name in ("a.wav", "b.wav"):
        g = loudness.normalize(s, rate, -14.0)
        gained = [int(round(v * g)) for v in s]
        out = loudness.limit_peak(gained, rate, -1.0)
        p = str(tmp_path / name)
        loudness.write_wav_samples(p, rate, out)
        blobs.append(read_bytes(p))
    assert blobs[0] == blobs[1]
