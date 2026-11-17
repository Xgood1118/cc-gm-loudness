# -*- coding: utf-8 -*-
"""响度归一与限峰"""



def read_wav_samples(path):
    """读 16 位单声道 WAV"""
    raise NotImplementedError("read_wav_samples 尚未实现")


def write_wav_samples(path, rate, samples):
    """写 16 位单声道 WAV"""
    raise NotImplementedError("write_wav_samples 尚未实现")


def loudness_lufs(samples, rate):
    """算整体响度"""
    raise NotImplementedError("loudness_lufs 尚未实现")


def normalize(samples, rate, target_lufs):
    """按响度归一，返回增益"""
    raise NotImplementedError("normalize 尚未实现")


def limit_peak(samples, rate, ceiling_db):
    """软限峰"""
    raise NotImplementedError("limit_peak 尚未实现")

