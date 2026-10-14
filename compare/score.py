"""Score a rendered mix against a reference: loudness, band balance, width, tempo/key agreement.

Usage: python -m compare.score <render.wav> <reference.wav|analysis.json> [--out diff.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from analyzer.audio import load
from analyzer.features import beat_grid, estimate_key, loudness, spectral_balance
import librosa


def _summary(path: Path) -> dict:
    a = load(path)
    chroma = librosa.feature.chroma_cqt(y=a.mono, sr=a.mono_sr)
    g = beat_grid(a)
    return {"tempo_bpm": g["tempo_bpm"], **estimate_key(chroma), "loudness": loudness(a),
            "spectrum": spectral_balance(a)}


def compare(render: Path, reference: Path) -> dict:
    r = _summary(render)
    ref = json.loads(reference.read_text()) if reference.suffix == ".json" else _summary(reference)
    bands = {k: round(r["spectrum"]["band_energy_db_rel"][k] - ref["spectrum"]["band_energy_db_rel"][k], 2)
             for k in r["spectrum"]["band_energy_db_rel"]}
    advice = []
    for k, d in bands.items():
        if d > 2.5:
            advice.append(f"{k} is {d:+.1f} dB louder than reference: cut it")
        elif d < -2.5:
            advice.append(f"{k} is {d:+.1f} dB quieter than reference: boost it")
    lufs_d = round(r["loudness"]["integrated_lufs"] - ref["loudness"]["integrated_lufs"], 2)
    if abs(lufs_d) > 1.5:
        advice.append(f"loudness {lufs_d:+.1f} LU vs reference: adjust limiter/master gain")
    wd = round(r["loudness"]["stereo_width_side_mid_ratio"] - ref["loudness"]["stereo_width_side_mid_ratio"], 3)
    if abs(wd) > 0.1:
        advice.append(f"stereo width {wd:+.2f} vs reference: {'narrow' if wd > 0 else 'widen'} pads/leads")
    if abs(r["tempo_bpm"] - ref["tempo_bpm"]) > 1:
        advice.append(f"tempo {r['tempo_bpm']} vs {ref['tempo_bpm']}")
    if (r["key"], r["mode"]) != (ref["key"], ref["mode"]):
        advice.append(f"key {r['key']} {r['mode']} vs reference {ref['key']} {ref['mode']}")
    return {"render": r, "band_delta_db": bands, "lufs_delta": lufs_d, "width_delta": wd, "advice": advice}


if __name__ == "__main__":
    args = sys.argv[1:]
    out = None
    if "--out" in args:
        i = args.index("--out"); out = Path(args[i + 1]); del args[i:i + 2]
    res = compare(Path(args[0]), Path(args[1]))
    txt = json.dumps(res, indent=1)
    if out:
        out.write_text(txt, encoding="utf-8")
    print(txt)
