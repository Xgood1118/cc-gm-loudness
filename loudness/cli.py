# -*- coding: utf-8 -*-
"""命令行：响度归一 + 限峰，并打印前后指标。"""

import argparse
import math

from . import core


def _distortion_percent(before, after):
    """限峰引入的失真：残差能量比（%）。"""
    num = sum((x - y) ** 2 for x, y in zip(before, after))
    den = sum(x * x for x in before)
    if den == 0:
        return 0.0
    return 100.0 * math.sqrt(num / den)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="loudness.cli", description="响度归一与限峰")
    ap.add_argument("input", help="输入 16 位单声道 WAV")
    ap.add_argument("--target", type=float, default=-14.0, help="目标整体响度 (LUFS)")
    ap.add_argument("--ceiling", type=float, default=-1.0, help="峰值上限 (dBFS)")
    ap.add_argument("--out", required=True, help="输出 WAV 路径")
    a = ap.parse_args(argv)

    rate, samples = core.read_wav_samples(a.input)
    before = core.loudness_lufs(samples, rate)

    gain = core.normalize(samples, rate, a.target)
    gained = [int(round(s * gain)) for s in samples]
    normalized = core.loudness_lufs(gained, rate)

    limited = core.limit_peak(gained, rate, a.ceiling)
    after = core.loudness_lufs(limited, rate)

    ceil_amp = int(32768 * 10.0 ** (a.ceiling / 20.0))
    overs = sum(1 for s in limited if abs(s) > ceil_amp)
    dist = _distortion_percent(gained, limited)

    core.write_wav_samples(a.out, rate, limited)

    print("输入响度:   %.2f LUFS" % before)
    print("归一增益:   %+.2f dB" % (20.0 * math.log10(gain) if gain > 0 else 0.0))
    print("归一后响度: %.2f LUFS" % normalized)
    print("超限样本数: %d (上限 %d)" % (overs, ceil_amp))
    print("限峰后响度: %.2f LUFS" % after)
    print("限峰失真:   %.4f %%" % dist)
    print("已写出:     %s" % a.out)


if __name__ == "__main__":
    main()
