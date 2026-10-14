"""Human-readable report.md from analysis.json."""
from __future__ import annotations

import json
from pathlib import Path


def write_report(analysis: dict, out: Path) -> None:
    f = analysis
    lines = [f"# Analysis: {f.get('source', '')}", ""]
    lines += [
        f"- Duration: {f['duration_s']} s",
        f"- Tempo: **{f['tempo_bpm']} BPM** (4/4), {f['bar_count']} bars, first beat at {f['first_beat_offset_s']} s",
        f"- Key: **{f['key']} {f['mode']}** (confidence {f['confidence']})",
        f"- Loudness: {f['loudness']['integrated_lufs']} LUFS, peak {f['loudness']['true_peak_dbfs']} dBFS, "
        f"stereo width {f['loudness']['stereo_width_side_mid_ratio']}",
        f"- Spectrum (dB rel. total): " + ", ".join(f"{k} {v}" for k, v in f['spectrum']['band_energy_db_rel'].items()),
        "",
        "## Sections",
        "| # | name | bars | length | energy |", "|---|---|---|---|---|",
    ]
    for i, s in enumerate(f["sections"], 1):
        lines.append(f"| {i} | {s['name']} | {s['start_bar']}-{s['end_bar']} | {s['bars']} | {s['energy_rel']} |")
    lines += ["", "## Chord progression (run-length)", "", "`" + " | ".join(f["chord_progression"][:64]) + "`", ""]
    lines += ["## Chords per bar (first 32)", ""]
    lines.append(" ".join(f"{c['bar']}:{c['chord']}" for c in f["chords_per_bar"][:32]))
    if "stems" in f:
        lines += ["", "## Stems / sounds", ""]
        for name, d in f["stems"].items():
            if not d.get("present"):
                lines.append(f"- **{name}**: (silent)")
                continue
            lines.append(f"- **{name}**: {d['description']} (centroid {d['spectral_centroid_hz']} Hz, "
                         f"{d['onsets_per_second']} onsets/s)")
    if "midi" in f:
        lines += ["", "## MIDI", ""]
        for name, d in f["midi"].items():
            lines.append(f"- {name}: `{Path(d['file']).name}` " + json.dumps({k: v for k, v in d.items() if k != 'file'}))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
