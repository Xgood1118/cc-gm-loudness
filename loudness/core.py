# -*- coding: utf-8 -*-
"""响度归一与限峰。

- 响度：ITU-R BS.1770 风格 K 加权 + 两级门控（绝对 -70 LUFS、相对 -10 LU）的整体响度。
- 归一：按整体响度差给出线性增益。
- 限峰：5 ms 前瞻 + 快攻慢放的增益包络软限峰，保证任何采样不超过上限。

仅使用 Python 标准库，全部计算确定性，两次运行输出逐字节一致。
"""

import math
import struct
import wave
from collections import deque

__all__ = [
    "read_wav_samples",
    "write_wav_samples",
    "loudness_lufs",
    "normalize",
    "limit_peak",
]

_FULL_SCALE = 32768.0

# 限峰器时间常数（秒）
_LOOKAHEAD_S = 0.005   # 前瞻 5 ms
_ATTACK_S = 0.001      # 增益下压时间常数 1 ms
_RELEASE_S = 0.050     # 增益恢复时间常数 50 ms


def read_wav_samples(path):
    """读 16 位单声道 WAV，返回 (rate, samples)，samples 为 int 列表。"""
    with wave.open(path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("仅支持 16 位单声道 WAV")
        rate = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    samples = list(struct.unpack("<%dh" % n, raw)) if n else []
    return rate, samples


def write_wav_samples(path, rate, samples):
    """写 16 位单声道 WAV，采样裁剪到 [-32768, 32767] 并取整。"""
    ints = [max(-32768, min(32767, int(round(v)))) for v in samples]
    frames = struct.pack("<%dh" % len(ints), *ints) if ints else b""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


# ---------------------------------------------------------------- 响度

def _biquad_high_shelf(rate):
    """K 加权第一级：高架滤波器（BS.1770 预滤波器，按采样率重算系数）。"""
    f0, g_db, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    A = 10.0 ** (g_db / 40.0)
    w0 = 2.0 * math.pi * f0 / rate
    alpha = math.sin(w0) / (2.0 * q)
    cw = math.cos(w0)
    sa = 2.0 * math.sqrt(A) * alpha
    b0 = A * ((A + 1.0) + (A - 1.0) * cw + sa)
    b1 = -2.0 * A * ((A - 1.0) + (A + 1.0) * cw)
    b2 = A * ((A + 1.0) + (A - 1.0) * cw - sa)
    a0 = (A + 1.0) - (A - 1.0) * cw + sa
    a1 = 2.0 * ((A - 1.0) - (A + 1.0) * cw)
    a2 = (A + 1.0) - (A - 1.0) * cw - sa
    return (b0 / a0, b1 / a0, b2 / a0), (a1 / a0, a2 / a0)


def _biquad_high_pass(rate):
    """K 加权第二级：RLB 高通滤波器。"""
    f0, q = 38.13547087602444, 0.5003270373238773
    w0 = 2.0 * math.pi * f0 / rate
    alpha = math.sin(w0) / (2.0 * q)
    cw = math.cos(w0)
    b0 = (1.0 + cw) / 2.0
    b1 = -(1.0 + cw)
    b2 = (1.0 + cw) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cw
    a2 = 1.0 - alpha
    return (b0 / a0, b1 / a0, b2 / a0), (a1 / a0, a2 / a0)


def _biquad_run(b, a, xs):
    b0, b1, b2 = b
    a1, a2 = a
    x1 = x2 = y1 = y2 = 0.0
    out = []
    for x in xs:
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1 = x1, x
        y2, y1 = y1, y
        out.append(y)
    return out


def loudness_lufs(samples, rate):
    """整体响度（LUFS）：K 加权 + 400 ms 块（75% 重叠）+ 绝对/相对两级门控。

    静音门限：块响度低于 -70 LUFS（绝对门限）或低于未门控整体响度 10 LU
    （相对门限）的块不计入，静音段因此不会拉低结果。
    全被门控掉（如纯静音）时返回 -inf。
    """
    n = len(samples)
    if n == 0:
        return float("-inf")
    xs = [s / _FULL_SCALE for s in samples]
    for b, a in (_biquad_high_shelf(rate), _biquad_high_pass(rate)):
        xs = _biquad_run(b, a, xs)

    block = max(1, int(round(0.400 * rate)))
    hop = max(1, int(round(0.100 * rate)))
    if n < block:
        block, starts = n, (0,)
    else:
        starts = range(0, n - block + 1, hop)

    # 前缀和加速块能量计算
    prefix = [0.0] * (n + 1)
    acc = 0.0
    for i, v in enumerate(xs):
        acc += v * v
        prefix[i + 1] = acc
    energies = [(prefix[s0 + block] - prefix[s0]) / block for s0 in starts]

    abs_thr = 10.0 ** ((-70.0 + 0.691) / 10.0)  # -70 LUFS 对应的能量
    gated = [e for e in energies if e > abs_thr]
    if not gated:
        return float("-inf")
    rel_thr = (sum(gated) / len(gated)) / 10.0  # 相对门限：低 10 LU
    gated = [e for e in gated if e > rel_thr]
    if not gated:
        return float("-inf")
    return -0.691 + 10.0 * math.log10(sum(gated) / len(gated))


def normalize(samples, rate, target_lufs):
    """按整体响度归一，返回线性增益（>1 表示需要放大）。"""
    loud = loudness_lufs(samples, rate)
    if loud == float("-inf"):
        return 1.0
    return 10.0 ** ((target_lufs - loud) / 20.0)


# ---------------------------------------------------------------- 限峰

def _sliding_min(values, window):
    """out[i] = min(values[i : i + window + 1])，单调队列 O(n)。"""
    n = len(values)
    dq = deque()
    out = []
    for i in range(n):
        if i == 0:
            new = range(0, min(window, n - 1) + 1)
        else:
            j = i + window
            new = (j,) if j < n else ()
        for k in new:
            while dq and values[dq[-1]] >= values[k]:
                dq.pop()
            dq.append(k)
        while dq and dq[0] < i:
            dq.popleft()
        out.append(values[dq[0]])
    return out


def limit_peak(samples, rate, ceiling_db):
    """软限峰：前瞻 + 包络平滑，保证输出任何采样 |s| <= floor(32768*10^(ceiling/20))。

    增益包络 = 前瞻窗口内所需增益的最小值，再经 1 ms 攻击 / 50 ms 释放平滑；
    最后用瞬时所需增益兜底，数学上保证不超限。
    """
    ceil_amp = int(_FULL_SCALE * 10.0 ** (ceiling_db / 20.0))
    if ceil_amp < 1:
        ceil_amp = 1
    n = len(samples)
    if n == 0:
        return []

    xs = [float(s) for s in samples]
    desired = [ceil_amp / v if v > ceil_amp else 1.0 for v in (abs(x) for x in xs)]

    look = max(1, int(round(_LOOKAHEAD_S * rate)))
    env = _sliding_min(desired, look)

    attack = 1.0 - math.exp(-1.0 / (_ATTACK_S * rate))
    release = 1.0 - math.exp(-1.0 / (_RELEASE_S * rate))

    g = env[0]  # 从包络初值起步，避免起音瞬态
    out = []
    for i in range(n):
        t = env[i]
        g += (t - g) * (attack if t < g else release)
        d = desired[i]
        ge = g if g < d else d  # 兜底：增益永不超过瞬时所需值
        y = xs[i] * ge
        if y > ceil_amp:
            y = float(ceil_amp)
        elif y < -ceil_amp:
            y = float(-ceil_amp)
        out.append(int(round(y)))
    return out
