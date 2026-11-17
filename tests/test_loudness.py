# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import loudness as mod  # noqa: E402


def test_loudness_moves_towards_target():
    rate, s = loudness.read_wav_samples("data/quiet.wav")
    g = loudness.normalize(s, rate, -14.0)
    assert g > 1.0, "这份素材偏轻，增益应大于 1"


def test_peak_limit_zero_over():
    rate, s = loudness.read_wav_samples("data/quiet.wav")
    out = loudness.limit_peak(s, rate, -1.0)
    peak = max(abs(v) for v in out) / 32768.0
    assert peak <= 1.0
