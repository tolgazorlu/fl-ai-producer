"""Global musical features: tempo/beat grid, key, chords, loudness, spectrum, sections."""
from __future__ import annotations

import numpy as np
import librosa
import pyloudnorm as pyln

from .audio import Audio

NOTE_NAMES = "C C# D D# E F F# G G# A A# B".split()
# Krumhansl-Schmuckler key profiles
_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


# ---------------------------------------------------------------- tempo / grid
def beat_grid(a: Audio) -> dict:
    """Tempo + beat times + bar starts (assumes 4/4, EDM)."""
    y, sr = a.mono, a.mono_sr
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(beat_frames, sr=sr)
    # Snap to a stable grid: EDM tempo is constant, so fit bpm precisely from beat intervals
    if len(beats) > 8:
        ivl = np.diff(beats)
        ivl = ivl[(ivl > 0.2) & (ivl < 2.0)]
        tempo = float(60.0 / np.median(ivl))
    # Downbeat: pick the phase (0..3) whose beats coincide with harmonic change
    # (chroma novelty) plus onset energy. Four-on-the-floor kicks make onset
    # energy alone ambiguous, so harmony decides.
    hop = 512
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    bf = np.clip(librosa.time_to_frames(beats, sr=sr, hop_length=hop), 0, chroma.shape[1] - 1)
    seg = []
    for i in range(len(bf)):
        a0, a1 = bf[i], (bf[i + 1] if i + 1 < len(bf) else chroma.shape[1])
        v = chroma[:, a0:max(a0 + 1, a1)].mean(axis=1)
        seg.append(v / (np.linalg.norm(v) + 1e-9))
    seg = np.array(seg)
    novelty = np.zeros(len(seg))
    novelty[1:] = 1.0 - np.sum(seg[1:] * seg[:-1], axis=1)  # cosine distance to previous beat
    strengths = onset_env[beat_frames] / (onset_env.max() + 1e-9) if len(beat_frames) else np.zeros(1)
    score = [novelty[p::4].mean() + 0.3 * strengths[p::4].mean() for p in range(4)]
    phase = int(np.argmax(score))
    bar_starts = beats[phase::4]
    return {
        "tempo_bpm": round(tempo, 2),
        "beat_times": [round(float(t), 4) for t in beats],
        "bar_starts": [round(float(t), 4) for t in bar_starts],
        "beats_per_bar": 4,
        "bar_count": int(len(bar_starts)),
        "first_beat_offset_s": round(float(beats[0]) if len(beats) else 0.0, 4),
    }


# ---------------------------------------------------------------------- key
def estimate_key(chroma: np.ndarray) -> dict:
    prof = chroma.mean(axis=1)
    best = (-2.0, "C", "major")
    for i in range(12):
        for p, mode in ((_MAJ, "major"), (_MIN, "minor")):
            c = float(np.corrcoef(prof, np.roll(p, i))[0, 1])
            if c > best[0]:
                best = (c, NOTE_NAMES[i], mode)
    return {"key": best[1], "mode": best[2], "confidence": round(best[0], 3)}


# -------------------------------------------------------------------- chords
def _chord_templates():
    names, mats = [], []
    for root in range(12):
        for q, ivs in (("", (0, 4, 7)), ("m", (0, 3, 7)), ("m7", (0, 3, 7, 10)),
                       ("maj7", (0, 4, 7, 11)), ("sus2", (0, 2, 7)), ("7", (0, 4, 7, 10))):
            v = np.zeros(12)
            for iv in ivs:
                v[(root + iv) % 12] = 1.0
            v[root] = 1.3  # root weight
            names.append(NOTE_NAMES[root] + q)
            mats.append(v / np.linalg.norm(v))
    return names, np.array(mats)


def chords_per_bar(chroma: np.ndarray, sr: int, hop: int, bar_starts: list[float],
                   duration: float) -> list[dict]:
    names, T = _chord_templates()
    out = []
    edges = list(bar_starts) + [duration]
    for i in range(len(bar_starts)):
        f0 = int(edges[i] * sr / hop)
        f1 = max(f0 + 1, int(edges[i + 1] * sr / hop))
        seg = chroma[:, f0:f1].mean(axis=1)
        if seg.sum() <= 0:
            out.append({"bar": i + 1, "chord": "N", "confidence": 0.0})
            continue
        seg = seg / np.linalg.norm(seg)
        scores = T @ seg
        j = int(np.argmax(scores))
        out.append({"bar": i + 1, "chord": names[j], "confidence": round(float(scores[j]), 3)})
    return out


def chord_progression(chords: list[dict]) -> list[str]:
    """Collapse per-bar chords into a run-length list like ['Am', 'F', 'C', 'G']."""
    prog = []
    for c in chords:
        if not prog or prog[-1] != c["chord"]:
            prog.append(c["chord"])
    return prog


# ------------------------------------------------------------------ loudness
def loudness(a: Audio) -> dict:
    meter = pyln.Meter(a.sr)
    integrated = meter.integrated_loudness(a.stereo)
    peak = float(np.abs(a.stereo).max())
    # short-term curve (3 s windows, 1 s hop)
    win, hop = 3 * a.sr, a.sr
    curve = []
    for s in range(0, max(1, a.stereo.shape[0] - win), hop):
        block = a.stereo[s:s + win]
        try:
            curve.append(round(float(meter.integrated_loudness(block)), 2))
        except Exception:
            curve.append(-70.0)
    mid = a.stereo.mean(axis=1)
    side = (a.stereo[:, 0] - a.stereo[:, 1]) / 2
    width = float(np.sqrt((side ** 2).mean()) / (np.sqrt((mid ** 2).mean()) + 1e-9))
    return {
        "integrated_lufs": round(float(integrated), 2),
        "true_peak_dbfs": round(20 * np.log10(peak + 1e-9), 2),
        "short_term_lufs_curve_1s": curve,
        "stereo_width_side_mid_ratio": round(width, 3),
    }


# ------------------------------------------------------------------ spectrum
BANDS = {"sub": (20, 60), "bass": (60, 150), "low_mid": (150, 400), "mid": (400, 2000),
         "high_mid": (2000, 6000), "air": (6000, 16000)}


def spectral_balance(a: Audio) -> dict:
    y, sr = a.mono, a.mono_sr
    S = np.abs(librosa.stft(y, n_fft=4096)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)
    total = S.sum() + 1e-12
    bands = {}
    for name, (lo, hi) in BANDS.items():
        m = (freqs >= lo) & (freqs < hi)
        bands[name] = round(float(10 * np.log10(S[m].sum() / total + 1e-12)), 2)
    cent = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
    roll = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.9).mean()
    return {"band_energy_db_rel": bands, "spectral_centroid_hz": round(float(cent), 1),
            "rolloff90_hz": round(float(roll), 1)}


# ------------------------------------------------------------------ sections
def energy_per_bar(a: Audio, bar_starts: list[float]) -> list[float]:
    y, sr = a.mono, a.mono_sr
    edges = list(bar_starts) + [a.duration]
    out = []
    for i in range(len(bar_starts)):
        s, e = int(edges[i] * sr), int(edges[i + 1] * sr)
        seg = y[s:e]
        out.append(round(float(np.sqrt((seg ** 2).mean() + 1e-12)), 5))
    return out


def sections(a: Audio, bar_starts: list[float], energy: list[float], chroma, mfcc, sr, hop) -> list[dict]:
    """Segment into sections on 4-bar boundaries using feature novelty + energy steps."""
    n = len(bar_starts)
    if n < 8:
        return [{"name": "all", "start_bar": 1, "end_bar": n, "energy": float(np.mean(energy))}]
    edges = list(bar_starts) + [a.duration]
    feats = []
    for i in range(n):
        f0 = int(edges[i] * sr / hop); f1 = max(f0 + 1, int(edges[i + 1] * sr / hop))
        feats.append(np.concatenate([chroma[:, f0:f1].mean(axis=1), mfcc[1:13, f0:f1].mean(axis=1) / 50.0,
                                     [np.log(energy[i] + 1e-6)]]))
    feats = np.array(feats)
    # novelty at 4-bar candidates: distance between the 4 bars before and after
    cands = list(range(4, n - 3, 4))
    nov = []
    for b in cands:
        before, after = feats[max(0, b - 4):b].mean(axis=0), feats[b:b + 4].mean(axis=0)
        nov.append(np.linalg.norm(before - after))
    nov = np.array(nov)
    thr = nov.mean() + 0.6 * nov.std()
    cuts = [0] + [cands[i] for i in range(len(cands)) if nov[i] > thr] + [n]
    # merge sections shorter than 4 bars
    merged = [cuts[0]]
    for c in cuts[1:]:
        if c - merged[-1] >= 4 or c == n:
            merged.append(c)
    secs = []
    emax = max(energy) + 1e-9
    for i in range(len(merged) - 1):
        s, e = merged[i], merged[i + 1]
        en = float(np.mean(energy[s:e])) / emax
        secs.append({"start_bar": s + 1, "end_bar": e, "bars": e - s, "energy_rel": round(en, 3)})
    # name by energy rank / position
    for i, sc in enumerate(secs):
        if i == 0:
            sc["name"] = "intro"
        elif i == len(secs) - 1:
            sc["name"] = "outro"
        elif sc["energy_rel"] >= 0.8:
            sc["name"] = "drop"
        elif sc["energy_rel"] <= 0.45:
            sc["name"] = "break"
        else:
            sc["name"] = "build"
    return secs


# ---------------------------------------------------------------- aggregate
def analyze_features(a: Audio) -> dict:
    hop = 512
    grid = beat_grid(a)
    chroma = librosa.feature.chroma_cqt(y=a.mono, sr=a.mono_sr, hop_length=hop)
    mfcc = librosa.feature.mfcc(y=a.mono, sr=a.mono_sr, hop_length=hop, n_mfcc=13)
    key = estimate_key(chroma)
    chords = chords_per_bar(chroma, a.mono_sr, hop, grid["bar_starts"], a.duration)
    energy = energy_per_bar(a, grid["bar_starts"])
    secs = sections(a, grid["bar_starts"], energy, chroma, mfcc, a.mono_sr, hop)
    return {
        "duration_s": round(a.duration, 2),
        "sample_rate": a.sr,
        **grid,
        **key,
        "chords_per_bar": chords,
        "chord_progression": chord_progression(chords),
        "energy_per_bar": energy,
        "sections": secs,
        "loudness": loudness(a),
        "spectrum": spectral_balance(a),
    }
