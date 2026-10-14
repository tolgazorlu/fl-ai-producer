"""Plain-language timbre descriptions per stem (what a producer would say about the sound)."""
from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


def describe_stem(wav: Path, sections: list[dict], bar_starts: list[float]) -> dict:
    y, sr = sf.read(str(wav), dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if sr != 22050:
        y = librosa.resample(y, orig_sr=sr, target_sr=22050); sr = 22050
    rms_all = float(np.sqrt((y ** 2).mean() + 1e-12))
    if rms_all < 1e-4:
        return {"present": False}
    cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    flat = librosa.feature.spectral_flatness(y=y)[0]
    rms = librosa.feature.rms(y=y)[0]
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    dur = len(y) / sr
    onset_rate = len(onsets) / max(dur, 1e-6)
    # attack: how sharp are the onsets (mean onset strength normalized)
    attack = float(np.mean(onset_env[onsets]) / (onset_env.max() + 1e-9)) if len(onsets) else 0.0
    c = float(np.median(cent))
    words = []
    words.append("dark" if c < 800 else "warm" if c < 1800 else "bright" if c < 4000 else "very bright")
    words.append("noisy/airy" if float(np.median(flat)) > 0.2 else "tonal")
    words.append("sustained/pad-like" if onset_rate < 0.8 else "rhythmic" if onset_rate < 4 else "busy/percussive")
    words.append("sharp attack" if attack > 0.5 else "soft attack")
    # per-section presence
    per_sec = []
    edges = list(bar_starts) + [dur]
    hop = 512
    for s in sections:
        f0 = int(edges[s["start_bar"] - 1] * sr / hop)
        f1 = int(min(edges[min(s["end_bar"], len(edges) - 1)], dur) * sr / hop)
        lvl = float(rms[f0:f1].mean()) if f1 > f0 else 0.0
        per_sec.append({"section": s["name"], "start_bar": s["start_bar"], "level_rel": round(lvl / (rms.max() + 1e-9), 3)})
    return {
        "present": True,
        "description": ", ".join(words),
        "spectral_centroid_hz": round(c, 1),
        "flatness": round(float(np.median(flat)), 3),
        "onsets_per_second": round(onset_rate, 2),
        "per_section_level": per_sec,
    }
