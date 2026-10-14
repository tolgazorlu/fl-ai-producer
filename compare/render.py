"""Render a .flp with FL Studio's command line and measure the result.

FL must NOT be running (a running instance swallows the command). Usage:
    python -m compare.render projects/x.flp [--out renders/x]   -> renders/x.wav + x.stats.json
Measures: duration, integrated LUFS, true peak, clipping samples, crest factor, silence ratio,
spectral centroid, band balance, and a per-8-bar loudness curve (to see arrangement dynamics).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

FL_EXE = Path(r"C:\Program Files\Image-Line\FL Studio 2026\FL64.exe")


def fl_running() -> bool:
    out = subprocess.run(["tasklist"], capture_output=True, text=True).stdout
    return "FL64.exe" in out


def render(flp: Path, out_base: Path, timeout: int = 900) -> Path:
    if fl_running():
        raise RuntimeError("FL Studio is running; close it first (command-line render needs a fresh instance)")
    out_base.parent.mkdir(parents=True, exist_ok=True)
    wav = out_base.with_suffix(".wav")
    if wav.exists():
        wav.unlink()
    cmd = [str(FL_EXE), f"/R{out_base}", "/Ewav", str(flp)]
    t0 = time.time()
    proc = subprocess.Popen(cmd)
    while time.time() - t0 < timeout:
        if wav.exists() and wav.stat().st_size > 1000 and proc.poll() is not None:
            break
        if proc.poll() is not None and not wav.exists():
            time.sleep(3)
            if not wav.exists():
                raise RuntimeError(f"FL exited ({proc.returncode}) without writing {wav}")
        time.sleep(1)
    if not wav.exists():
        proc.kill()
        raise TimeoutError("render timed out")
    return wav


def stats(wav: Path, tempo: float | None = None) -> dict:
    import numpy as np
    import soundfile as sf
    import librosa
    import pyloudnorm as pyln

    y, sr = sf.read(str(wav), dtype="float32", always_2d=True)
    mono = y.mean(axis=1)
    dur = len(mono) / sr
    meter = pyln.Meter(sr)
    lufs = float(meter.integrated_loudness(y)) if dur > 1 else -70.0
    peak = float(np.abs(y).max())
    clip = int((np.abs(y) >= 0.999).sum())
    rms = float(np.sqrt((mono ** 2).mean() + 1e-12))
    crest = 20 * np.log10(peak / (rms + 1e-9))
    frame = int(sr * 0.1)
    frames = mono[: len(mono) // frame * frame].reshape(-1, frame)
    silence = float((np.sqrt((frames ** 2).mean(axis=1)) < 1e-4).mean())
    ym = librosa.resample(mono, orig_sr=sr, target_sr=22050)
    S = np.abs(librosa.stft(ym, n_fft=4096)) ** 2
    freqs = librosa.fft_frequencies(sr=22050, n_fft=4096)
    tot = S.sum() + 1e-12
    bands = {}
    for name, (lo, hi) in {"sub": (20, 60), "bass": (60, 150), "low_mid": (150, 400), "mid": (400, 2000),
                           "high_mid": (2000, 6000), "air": (6000, 11000)}.items():
        m = (freqs >= lo) & (freqs < hi)
        bands[name] = round(float(10 * np.log10(S[m].sum() / tot + 1e-12)), 2)
    cent = float(librosa.feature.spectral_centroid(y=ym, sr=22050).mean())
    flat = float(librosa.feature.spectral_flatness(y=ym).mean())
    curve = []
    if tempo:
        seg = int(sr * 60 / tempo * 4 * 8)   # 8 bars
        for s in range(0, len(y) - seg, seg):
            try:
                curve.append(round(float(meter.integrated_loudness(y[s:s + seg])), 1))
            except Exception:
                curve.append(-70.0)
    return {"file": str(wav), "duration_s": round(dur, 2), "lufs": round(lufs, 2), "peak": round(peak, 3),
            "clipped_samples": clip, "crest_db": round(float(crest), 1), "silence_ratio": round(silence, 3),
            "spectral_centroid_hz": round(cent, 1), "flatness": round(flat, 4), "bands_db": bands,
            "lufs_per_8_bars": curve}


if __name__ == "__main__":
    args = sys.argv[1:]
    flp = Path(args[0])
    out = Path(args[args.index("--out") + 1]) if "--out" in args else Path("renders") / flp.stem
    tempo = float(args[args.index("--tempo") + 1]) if "--tempo" in args else None
    wav = render(flp, out)
    st = stats(wav, tempo)
    out.with_suffix(".stats.json").write_text(json.dumps(st, indent=1))
    print(json.dumps(st, indent=1))
