"""Blueprint = the editable source of truth for a song section.

Schema (JSON):
{
  "name": "underwater-drop-loop",
  "tempo_bpm": 129,
  "key": "A", "mode": "minor",
  "bars": 8,
  "parts": {
    "<part name>": {
      "channel": "<FL channel name to write into>",
      "notes": [{"pitch": 57, "time_bars": 0.0, "length_bars": 2.0, "velocity": 0.7}, ...]
    }
  }
}
Helpers below build parts from chord symbols so Claude can compose at the level of
"F - Dm - Am - C, 2 bars each, bass pulses 1/8, hats offbeat" instead of raw notes.
"""
from __future__ import annotations

import json
from pathlib import Path

NOTE_NAMES = "C C# D D# E F F# G G# A A# B".split()
CHORD_INTERVALS = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10),
                   "maj7": (0, 4, 7, 11), "sus2": (0, 2, 7), "sus4": (0, 5, 7), "add9": (0, 4, 7, 14),
                   "m9": (0, 3, 7, 10, 14)}


def parse_chord(sym: str) -> tuple[int, tuple[int, ...]]:
    """'Fmaj7' -> (5, (0,4,7,11)). Root as pitch class."""
    root = sym[:2] if len(sym) > 1 and sym[1] == "#" else sym[:1]
    quality = sym[len(root):]
    return NOTE_NAMES.index(root), CHORD_INTERVALS[quality]


def note(pitch: int, t: float, length: float, vel: float = 0.7) -> dict:
    return {"pitch": int(pitch), "time_bars": round(float(t), 4), "length_bars": round(float(length), 4),
            "velocity": round(float(vel), 3)}


def chord_pad(progression: list[tuple[str, float]], octave: int = 4, vel: float = 0.6) -> list[dict]:
    """[(chord, bars), ...] -> sustained chord voicings (close voicing above octave*12)."""
    out, t = [], 0.0
    for sym, bars in progression:
        root, ivs = parse_chord(sym)
        base = 12 * (octave + 1) + root  # C4 = 60 convention (FL shows C5)
        for iv in ivs:
            out.append(note(base + iv, t, bars, vel))
        t += bars
    return out


def bass_line(progression: list[tuple[str, float]], octave: int = 1, pulse: float = 0.125,
              vel: float = 0.8, octave_jump_every: int | None = 4) -> list[dict]:
    """Root-note pulses (default 1/8 notes) with an occasional octave jump."""
    out, t = [], 0.0
    for sym, bars in progression:
        root, _ = parse_chord(sym)
        base = 12 * (octave + 1) + root
        n = int(round(bars / pulse))
        for i in range(n):
            p = base + (12 if octave_jump_every and i % octave_jump_every == octave_jump_every - 1 else 0)
            out.append(note(p, t + i * pulse, pulse * 0.9, vel if i % 2 == 0 else vel * 0.85))
        t += bars
    return out


def drums_four_on_floor(bars: int, kick: int = 36, clap: int = 38, hat: int = 42,
                        open_hat: int = 46) -> list[dict]:
    out = []
    for b in range(bars):
        for beat in range(4):
            out.append(note(kick, b + beat * 0.25, 0.2, 0.95))
            out.append(note(hat, b + beat * 0.25 + 0.125, 0.05, 0.55))  # offbeat hats
            if beat in (1, 3):
                out.append(note(clap, b + beat * 0.25, 0.1, 0.8))
        if b % 4 == 3:
            out.append(note(open_hat, b + 0.875, 0.1, 0.6))
    return out


def melody_from_scale(key: str, mode: str, pattern: list[tuple[int, float, float]], octave: int = 5,
                      vel: float = 0.75) -> list[dict]:
    """pattern: [(scale_degree (0-based, can exceed 7 for next octave, -1 = rest), start_bars, length_bars)]."""
    scale = (0, 2, 3, 5, 7, 8, 10) if mode == "minor" else (0, 2, 4, 5, 7, 9, 11)
    root = NOTE_NAMES.index(key)
    out = []
    for deg, t, ln in pattern:
        if deg < 0:
            continue
        p = 12 * (octave + 1) + root + scale[deg % 7] + 12 * (deg // 7)
        out.append(note(p, t, ln, vel))
    return out


def save(bp: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bp, indent=1), encoding="utf-8")
