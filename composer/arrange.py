"""Full-song blueprint from an analysis.json: sections -> patterns per part -> playlist.

The song blueprint extends the loop blueprint:
{
  "name", "tempo_bpm", "key", "mode", "ppq_note": "bars",
  "channels": {"Chords": 1, ...}            # FL channel index per part (template order)
  "patterns": {"CHORDS_A": {"channel": "Chords", "bars": 8, "notes": [...]}, ...},
  "playlist": [{"pattern": "CHORDS_A", "track": 1, "start_bar": 0, "length_bars": 16}, ...],
  "sections": [{"name": "intro", "start_bar": 0, "bars": 16}, ...],
  "presets": {"Bass": "Thumpus", "Chords": "Analog Pad", "Lead": "Distant Majestic Lead"}
}
Musical rules (ambient EDM): 8-bar phrases; intro = pad (+ sparse lead late); build = pad + bass
+ hats, lead enters; drop = everything; break = pad + lead, no kick; outro = pad + bass fading.
"""
from __future__ import annotations

import json
from pathlib import Path

from .blueprint import NOTE_NAMES, bass_line, chord_pad, drums_four_on_floor, melody_from_scale, note, parse_chord

PART_TRACK = {"Chords": 1, "Bass": 2, "Lead": 3, "Drums": 4}


def progression_from_analysis(a: dict, bars_per_chord: int = 2) -> list[tuple[str, float]]:
    """Reduce per-bar chord detections to a clean 4-chord loop in the detected key."""
    key, mode = a["key"], a["mode"]
    chords = [c["chord"] for c in a["chords_per_bar"]]
    # count the most common chords, keep those that fit the key
    from collections import Counter
    counts = Counter(chords)
    root = NOTE_NAMES.index(key)
    scale = (0, 2, 3, 5, 7, 8, 10) if mode == "minor" else (0, 2, 4, 5, 7, 9, 11)
    diatonic = []
    for sym, n in counts.most_common():
        if sym == "N":
            continue
        r, _ = parse_chord(sym)
        if (r - root) % 12 in scale:
            diatonic.append(sym)
        if len(diatonic) == 4:
            break
    # order them as they first appear in the song for a natural loop
    order = sorted(diatonic, key=lambda s: chords.index(s))
    if len(order) < 2:  # fallback: i - VI - III - VII in minor, I - V - vi - IV in major
        deg = [0, 5, 2, 6] if mode == "minor" else [0, 4, 5, 3]
        q = ["m", "", "", ""] if mode == "minor" else ["", "", "m", ""]
        order = [NOTE_NAMES[(root + scale[d]) % 12] + qq for d, qq in zip(deg, q)]
    return [(s, float(bars_per_chord)) for s in order]


def default_lead(prog_bars: int) -> list[tuple[int, float, float]]:
    """A calm 8-bar pentatonic motif (scale degrees), repeated to prog_bars."""
    motif = [(4, 0.0, 0.5), (7, 0.5, 0.25), (6, 0.75, 0.25), (4, 1.0, 0.5), (2, 1.5, 0.5),
             (3, 2.0, 0.5), (4, 2.5, 0.25), (2, 2.75, 0.25), (0, 3.0, 1.0),
             (4, 4.0, 0.5), (7, 4.5, 0.25), (9, 4.75, 0.25), (7, 5.0, 0.5), (6, 5.5, 0.5),
             (4, 6.0, 0.5), (2, 6.5, 0.25), (4, 6.75, 0.25), (0, 7.0, 1.0)]
    out = []
    for rep in range(max(1, prog_bars // 8)):
        out += [(d, t + 8 * rep, ln) for d, t, ln in motif]
    return out


def build_song(a: dict, name: str, presets: dict | None = None, channels: dict | None = None) -> dict:
    tempo = round(a["tempo_bpm"])
    key, mode = a["key"], a["mode"]
    prog = progression_from_analysis(a)
    loop_bars = int(sum(b for _, b in prog))      # usually 8
    patterns: dict[str, dict] = {}

    def pat(name_, channel, notes, bars=loop_bars):
        patterns[name_] = {"channel": channel, "bars": bars, "notes": notes}
        return name_

    pad_soft = pat("CHORDS_SOFT", "Chords", chord_pad(prog, octave=4, vel=0.45))
    pad_full = pat("CHORDS_FULL", "Chords", chord_pad(prog, octave=4, vel=0.65)
                   + chord_pad(prog, octave=3, vel=0.4))                       # doubled an octave down
    bass_pulse = pat("BASS_PULSE", "Bass", bass_line(prog, octave=1, pulse=0.125, vel=0.85))
    bass_long = pat("BASS_LONG", "Bass", bass_line(prog, octave=1, pulse=1.0, vel=0.7, octave_jump_every=None))
    lead_main = pat("LEAD_MAIN", "Lead", melody_from_scale(key, mode, default_lead(loop_bars), octave=5, vel=0.72))
    lead_sparse = pat("LEAD_SPARSE", "Lead", melody_from_scale(
        key, mode, [(d, t, ln) for d, t, ln in default_lead(loop_bars) if t % 2 == 0], octave=5, vel=0.55))
    drums_full = pat("DRUMS_FULL", "Drums", drums_four_on_floor(loop_bars))
    drums_hats = pat("DRUMS_HATS", "Drums", [n for n in drums_four_on_floor(loop_bars) if n["pitch"] in (42, 46)])
    drums_build = pat("DRUMS_BUILD", "Drums",
                      [n for n in drums_four_on_floor(loop_bars) if n["pitch"] != 36]
                      + [note(36, b + q * 0.25, 0.2, 0.9) for b in range(loop_bars) for q in (0, 2)])  # half-time kick

    # section plan derived from the analysis (lengths), with a sensible fallback
    secs = a.get("sections") or []
    plan = []
    for s in secs:
        bars = int(s["bars"]) // loop_bars * loop_bars or loop_bars
        plan.append((s["name"], bars))
    if not plan:
        plan = [("intro", 16), ("build", 16), ("drop", 32), ("break", 16), ("drop", 32), ("outro", 16)]

    roles = {
        "intro": [pad_soft, bass_long, None, None],
        "build": [pad_soft, bass_pulse, lead_sparse, drums_build],
        "drop": [pad_full, bass_pulse, lead_main, drums_full],
        "break": [pad_soft, bass_long, lead_sparse, drums_hats],
        "outro": [pad_soft, bass_long, None, None],
    }
    playlist, sections, bar = [], [], 0
    for sname, bars in plan:
        parts = roles.get(sname, roles["drop"])
        for pname, track in zip(parts, (1, 2, 3, 4)):
            if pname:
                playlist.append({"pattern": pname, "track": track, "start_bar": bar, "length_bars": bars})
        sections.append({"name": sname, "start_bar": bar, "bars": bars})
        bar += bars

    return {
        "name": name, "tempo_bpm": tempo, "key": key, "mode": mode,
        "progression": prog, "loop_bars": loop_bars,
        "channels": channels or {"Bass": 0, "Chords": 1, "Lead": 2, "Drums": 3},
        "presets": presets or {},
        "patterns": patterns, "playlist": playlist, "sections": sections, "total_bars": bar,
    }


if __name__ == "__main__":
    import sys
    a = json.load(open(sys.argv[1]))
    bp = build_song(a, sys.argv[2] if len(sys.argv) > 2 else "song")
    out = Path(f"projects/{bp['name']}.song.json")
    out.write_text(json.dumps(bp, indent=1), encoding="utf-8")
    print("progression:", bp["progression"], "| sections:", [(s["name"], s["bars"]) for s in bp["sections"]],
          "| total bars:", bp["total_bars"], "->", out)
