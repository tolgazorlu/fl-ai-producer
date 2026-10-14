"""Song engine v2: musical arrangement for the v2 template (12 channels).

Channels (template v2): Bass, Chords, Lead, Drum(FPC, unused), Kick, Clap, Hat, OpenHat,
Crash, Riser, Impact, Pluck, Arp.

Design goals vs v1: voice-led chord voicings, section-specific textures, humanized
velocities/timing, drum variations + fills + transitions (crash/riser/impact), arp and
pluck layers, bass that breathes with the pump. Deterministic per seed.

Output: song blueprint dict (see composer.arrange docstring) with
  patterns: {name: {channel, bars, notes}}, playlist, sections, presets (design specs).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .blueprint import NOTE_NAMES, note, parse_chord
from .arrange import progression_from_analysis

SAMPLER_NOTE = 60          # samplers play the file at its original pitch on C4(60)
TRACKS = {"Chords": 1, "Bass": 2, "Lead": 3, "Pluck": 4, "Arp": 5, "Kick": 6, "Clap": 7, "Hat": 8,
          "OpenHat": 9, "Crash": 10, "Riser": 11, "Impact": 12}


# ----------------------------------------------------------------- helpers
def scale_of(key: str, mode: str) -> list[int]:
    root = NOTE_NAMES.index(key)
    ivs = (0, 2, 3, 5, 7, 8, 10) if mode == "minor" else (0, 2, 4, 5, 7, 9, 11)
    return [(root + i) % 12 for i in ivs]


def chord_pcs(sym: str) -> list[int]:
    r, ivs = parse_chord(sym)
    return [(r + i) % 12 for i in ivs]


def hum(rng: random.Random, v: float, spread: float = 0.08) -> float:
    return round(min(1.0, max(0.1, v + rng.uniform(-spread, spread))), 3)


def jitter(rng: random.Random, t: float, amt: float = 0.004) -> float:
    return max(0.0, t + rng.uniform(-amt, amt))


# ----------------------------------------------------------------- harmony
def voice_lead(prog: list[tuple[str, float]], low: int = 55, high: int = 76) -> list[list[int]]:
    """Chord voicings (MIDI) with minimal movement between successive chords."""
    voicings, prev = [], None
    for sym, _ in prog:
        pcs = chord_pcs(sym)
        cands = []
        # all placements of each pitch class within [low, high]
        import itertools
        options = [[p for p in range(low, high + 1) if p % 12 == pc] for pc in pcs]
        for combo in itertools.product(*options):
            v = sorted(set(combo))
            if len(v) < len(pcs) or v[-1] - v[0] > 19:
                continue
            spread_pen = sum(1 for a, b in zip(v, v[1:]) if b - a < 3)   # avoid muddy seconds
            if prev is None:
                cost = abs(sum(v) / len(v) - (low + high) / 2) + spread_pen * 2
            else:
                cost = sum(min(abs(x - y) for y in prev) for x in v) + spread_pen * 2
            cands.append((cost, v))
        cands.sort()
        v = cands[0][1]
        voicings.append(v); prev = v
    return voicings


def pad_part(prog, voicings, bars_total, rng, vel=0.6, swell=False) -> list[dict]:
    out, t = [], 0.0
    loop = sum(b for _, b in prog)
    reps = max(1, int(bars_total // loop))
    for r in range(reps):
        t = r * loop
        for (sym, bars), v in zip(prog, voicings):
            for i, p in enumerate(v):
                out.append(note(p, t, bars - 0.02, hum(rng, vel - 0.05 * i, 0.04)))
            t += bars
    return out


def stab_part(prog, voicings, bars_total, rng, vel=0.7) -> list[dict]:
    """Off-beat chord stabs (pluck) on the 'and' of every beat, skipping some for groove."""
    out = []
    loop = sum(b for _, b in prog)
    for bar in range(int(bars_total)):
        sym, v = None, None
        acc = 0.0
        for (s, b), vc in zip(prog, voicings):
            if acc <= (bar % loop) < acc + b:
                sym, v = s, vc
                break
            acc += b
        for beat in range(4):
            if rng.random() < 0.15:
                continue
            t = bar + beat * 0.25 + 0.125
            for p in v[-3:]:
                out.append(note(p + 12 if p < 60 else p, jitter(rng, t), 0.11, hum(rng, vel if beat % 2 else vel - 0.1)))
    return out


def arp_part(prog, voicings, bars_total, rng, vel=0.62, div=0.0625) -> list[dict]:
    """1/16 up-arpeggio over the chord tones across two octaves with accents."""
    out = []
    loop = sum(b for _, b in prog)
    for bar in range(int(bars_total)):
        acc = 0.0
        for (s, b), vc in zip(prog, voicings):
            if acc <= (bar % loop) < acc + b:
                v = vc; break
            acc += b
        tones = sorted(v) + [p + 12 for p in sorted(v)]
        steps = int(1 / div)
        for i in range(steps):
            p = tones[i % len(tones)]
            if p > 88:
                p -= 12
            acc_v = vel + (0.15 if i % 4 == 0 else 0.0) - (0.08 if i % 2 else 0.0)
            out.append(note(p, bar + i * div, div * 0.8, hum(rng, acc_v, 0.05)))
    return out


def bass_part(prog, bars_total, rng, style="pulse", vel=0.85) -> list[dict]:
    out = []
    loop = sum(b for _, b in prog)
    roots = []
    for sym, b in prog:
        r, _ = parse_chord(sym)
        roots.append((36 + r if 36 + r <= 43 else 24 + r, b))   # keep roots in C1..G1 region (MIDI 24-43)
    for bar in range(int(bars_total)):
        acc = 0.0
        idx = 0
        for i, (p, b) in enumerate(roots):
            if acc <= (bar % loop) < acc + b:
                idx = i; break
            acc += b
        p, b = roots[idx]
        nxt = roots[(idx + 1) % len(roots)][0]
        last_bar_of_chord = (bar % loop) == acc + b - 1
        if style == "long":
            out.append(note(p, bar, 0.98, hum(rng, vel - 0.15, 0.03)))
        elif style == "pulse":
            for i in range(8):
                t = bar + i * 0.125
                pitch = p
                if i == 7 and last_bar_of_chord:
                    pitch = nxt - 1 if rng.random() < 0.5 else p + 7     # approach / fifth
                elif i in (3, 7):
                    pitch = p + 12                                        # octave bounce
                v = vel if i % 2 == 0 else vel - 0.12
                out.append(note(pitch, t, 0.1, hum(rng, v, 0.04)))
        elif style == "offbeat":
            for i in range(4):
                out.append(note(p, bar + i * 0.25 + 0.125, 0.11, hum(rng, vel - 0.05, 0.04)))
                if i == 3 and last_bar_of_chord:
                    out.append(note(p + 7, bar + 0.9375, 0.06, hum(rng, vel - 0.2, 0.03)))
    return out


def lead_part(key, mode, prog, bars_total, rng, density=1.0, octave=5, vel=0.74) -> list[dict]:
    """Phrase-based melody: 2-bar phrases, chord tones on strong beats, stepwise motion,
    A A' B A' form over 8 bars, rests between phrases."""
    sc = scale_of(key, mode)
    loop = sum(b for _, b in prog)
    rhythms = [
        [(0.0, 0.5), (0.5, 0.25), (0.75, 0.25), (1.0, 0.75), (1.75, 0.25)],
        [(0.0, 0.25), (0.25, 0.25), (0.5, 0.5), (1.0, 0.5), (1.5, 0.5)],
        [(0.0, 0.75), (0.75, 0.25), (1.0, 0.25), (1.25, 0.25), (1.5, 0.5)],
        [(0.125, 0.375), (0.5, 0.5), (1.0, 1.0)],
    ]
    base_oct = 12 * (octave + 1)

    def chord_at(bar):
        acc = 0.0
        for s, b in prog:
            if acc <= (bar % loop) < acc + b:
                return chord_pcs(s)
            acc += b
        return chord_pcs(prog[0][0])

    def nearest_in(pcs, around, lo, hi):
        c = [p for p in range(lo, hi + 1) if p % 12 in pcs]
        return min(c, key=lambda p: abs(p - around))

    phrases = {}
    def make_phrase(seed_pitch, rhythm, start_bar):
        pitch = seed_pitch
        out = []
        for i, (t, ln) in enumerate(rhythm):
            bar = start_bar + int(t)
            strong = (t % 1.0) in (0.0, 0.5)
            if strong or i == 0:
                pitch = nearest_in(chord_at(bar), pitch + rng.choice([-2, 0, 2, 3]), base_oct - 5, base_oct + 14)
            else:
                step = rng.choice([-2, -1, 1, 2])
                cand = pitch
                for _ in range(3):
                    cand += step if step else 1
                    if cand % 12 in sc:
                        break
                pitch = min(base_oct + 14, max(base_oct - 5, cand))
            out.append((pitch, t, ln))
        return out

    out = []
    n_phr = int(bars_total // 2)
    a = make_phrase(base_oct + 7, rhythms[rng.randrange(len(rhythms))], 0)
    b = make_phrase(base_oct + 4, rhythms[rng.randrange(len(rhythms))], 0)
    for k in range(n_phr):
        form = ["A", "A2", "B", "A2"][k % 4]
        src = a if form.startswith("A") else b
        if rng.random() > density:
            continue
        for j, (p, t, ln) in enumerate(src):
            pitch = p
            if form == "A2" and j == len(src) - 1:
                pitch = nearest_in(chord_at(k * 2 + 1), p - 3, base_oct - 5, base_oct + 14)   # resolve lower
            v = vel + (0.08 if t % 1.0 == 0.0 else 0.0) - 0.04 * (j % 3)
            out.append(note(pitch, jitter(rng, k * 2 + t), ln * 0.92, hum(rng, v, 0.05)))
    return out


# ----------------------------------------------------------------- drums
def drum_parts(bars, rng, *, kick=True, clap=True, hat="eighth", open_hat=True, fill_at_end=False,
               crash_start=False, half_time=False) -> dict[str, list[dict]]:
    K, C, H, O, X = [], [], [], [], []
    for bar in range(bars):
        last = bar == bars - 1
        for beat in range(4):
            t = bar + beat * 0.25
            if kick and (not half_time or beat in (0, 2)):
                K.append(note(SAMPLER_NOTE, t, 0.2, hum(rng, 0.98, 0.02)))
            if clap and beat in (1, 3):
                C.append(note(SAMPLER_NOTE, t, 0.15, hum(rng, 0.88, 0.04)))
            if hat == "eighth":
                H.append(note(SAMPLER_NOTE, t + 0.125, 0.06, hum(rng, 0.6, 0.06)))
            elif hat == "sixteenth":
                for s in range(4):
                    v = 0.7 if s == 0 else 0.45 if s == 2 else 0.35
                    H.append(note(SAMPLER_NOTE, t + s * 0.0625, 0.05, hum(rng, v, 0.05)))
            elif hat == "sparse" and beat in (1, 3):
                H.append(note(SAMPLER_NOTE, t + 0.125, 0.06, hum(rng, 0.5, 0.05)))
        if open_hat and (bar % 2 == 1):
            O.append(note(SAMPLER_NOTE, bar + 0.875, 0.12, hum(rng, 0.62, 0.05)))
        if fill_at_end and last and clap:
            # clap roll: 1/8 for 2 beats then 1/16 for 2 beats
            C[:] = [n for n in C if n["time_bars"] < bar]
            for i in range(4):
                C.append(note(SAMPLER_NOTE, bar + i * 0.125, 0.1, hum(rng, 0.7 + 0.05 * i, 0.03)))
            for i in range(8):
                C.append(note(SAMPLER_NOTE, bar + 0.5 + i * 0.0625, 0.06, hum(rng, 0.75 + 0.03 * i, 0.03)))
    if crash_start:
        X.append(note(SAMPLER_NOTE, 0.0, 1.0, 0.9))
    return {"Kick": K, "Clap": C, "Hat": H, "OpenHat": O, "Crash": X}


# ----------------------------------------------------------------- song
def default_plan(analysis_sections) -> list[tuple[str, int]]:
    plan = []
    for s in analysis_sections or []:
        bars = max(8, int(s["bars"]) // 8 * 8)
        plan.append((s["name"], bars))
    if not plan:
        plan = [("intro", 16), ("build", 16), ("drop", 32), ("break", 16), ("build", 8), ("drop", 32), ("outro", 16)]
    # guarantee a drop exists after any build
    return plan


def build_song(a: dict, name: str, seed: int = 7, presets: dict | None = None) -> dict:
    rng = random.Random(seed)
    tempo = round(a["tempo_bpm"])
    key, mode = a["key"], a["mode"]
    prog = progression_from_analysis(a)
    voic = voice_lead(prog)
    plan = default_plan(a.get("sections"))
    patterns: dict[str, dict] = {}
    playlist: list[dict] = []
    sections = []
    bar = 0

    def put(pname, channel, notes, bars, start):
        if not notes:
            return
        patterns[pname] = {"channel": channel, "bars": bars, "notes": notes}
        playlist.append({"pattern": pname, "track": TRACKS[channel], "start_bar": start, "length_bars": bars})

    counts: dict[str, int] = {}
    for sname, bars in plan:
        counts[sname] = counts.get(sname, 0) + 1
        tag = f"{sname.upper()}{counts[sname]}"
        nxt_is_drop = False
        i = plan.index((sname, bars))
        if i + 1 < len(plan) and plan[i + 1][0] == "drop":
            nxt_is_drop = True
        if sname == "intro":
            put(f"{tag}_PAD", "Chords", pad_part(prog, voic, bars, rng, vel=0.5), bars, bar)
            put(f"{tag}_ARP", "Arp", arp_part(prog, voic, bars, rng, vel=0.5, div=0.125), bars, bar)
            if bars >= 16:
                put(f"{tag}_LEAD", "Lead", lead_part(key, mode, prog, bars, rng, density=0.5, vel=0.6), bars, bar)
            d = drum_parts(bars, rng, kick=False, clap=False, hat="sparse", open_hat=False)
            put(f"{tag}_HAT", "Hat", d["Hat"], bars, bar)
        elif sname == "build":
            put(f"{tag}_PAD", "Chords", pad_part(prog, voic, bars, rng, vel=0.6), bars, bar)
            put(f"{tag}_BASS", "Bass", bass_part(prog, bars, rng, style="offbeat"), bars, bar)
            put(f"{tag}_ARP", "Arp", arp_part(prog, voic, bars, rng, vel=0.6), bars, bar)
            put(f"{tag}_LEAD", "Lead", lead_part(key, mode, prog, bars, rng, density=0.8), bars, bar)
            d = drum_parts(bars, rng, kick=True, clap=True, hat="eighth", open_hat=True, fill_at_end=True,
                           half_time=True)
            for ch in ("Kick", "Clap", "Hat", "OpenHat"):
                put(f"{tag}_{ch.upper()}", ch, d[ch], bars, bar)
            # riser over the last 8 bars, reverse-cymbal impact on the last bar
            put(f"{tag}_RISER", "Riser", [note(SAMPLER_NOTE, max(0, bars - 8), 8.0, 0.8)], bars, bar)
            put(f"{tag}_IMPACT", "Impact", [note(SAMPLER_NOTE, bars - 1, 1.0, 0.85)], bars, bar)
        elif sname == "drop":
            put(f"{tag}_PAD", "Chords", pad_part(prog, voic, bars, rng, vel=0.68), bars, bar)
            put(f"{tag}_BASS", "Bass", bass_part(prog, bars, rng, style="pulse"), bars, bar)
            put(f"{tag}_LEAD", "Lead", lead_part(key, mode, prog, bars, rng, density=1.0, vel=0.78), bars, bar)
            put(f"{tag}_PLUCK", "Pluck", stab_part(prog, voic, bars, rng), bars, bar)
            if bars >= 16:
                half = bars // 2
                arp = arp_part(prog, voic, half, rng, vel=0.6)
                arp = [dict(n, time_bars=n["time_bars"] + half) for n in arp]   # arp joins in the 2nd half
                put(f"{tag}_ARP", "Arp", arp, bars, bar)
            d = drum_parts(bars, rng, kick=True, clap=True, hat="sixteenth" if bars >= 16 else "eighth",
                           open_hat=True, fill_at_end=True, crash_start=True)
            for ch in ("Kick", "Clap", "Hat", "OpenHat", "Crash"):
                put(f"{tag}_{ch.upper()}", ch, d[ch], bars, bar)
        elif sname == "break":
            put(f"{tag}_PAD", "Chords", pad_part(prog, voic, bars, rng, vel=0.55), bars, bar)
            put(f"{tag}_BASS", "Bass", bass_part(prog, bars, rng, style="long"), bars, bar)
            put(f"{tag}_PLUCK", "Pluck", arp_part(prog, voic, bars, rng, vel=0.5, div=0.125), bars, bar)
            put(f"{tag}_LEAD", "Lead", lead_part(key, mode, prog, bars, rng, density=0.6, vel=0.65), bars, bar)
            d = drum_parts(bars, rng, kick=False, clap=False, hat="sparse", open_hat=False, crash_start=True)
            put(f"{tag}_HAT", "Hat", d["Hat"], bars, bar)
            put(f"{tag}_CRASH", "Crash", d["Crash"], bars, bar)
            if nxt_is_drop:
                put(f"{tag}_RISER", "Riser", [note(SAMPLER_NOTE, max(0, bars - 8), 8.0, 0.8)], bars, bar)
                put(f"{tag}_IMPACT", "Impact", [note(SAMPLER_NOTE, bars - 1, 1.0, 0.85)], bars, bar)
        else:  # outro
            put(f"{tag}_PAD", "Chords", pad_part(prog, voic, bars, rng, vel=0.5), bars, bar)
            put(f"{tag}_BASS", "Bass", bass_part(prog, bars, rng, style="long"), bars, bar)
            put(f"{tag}_ARP", "Arp", arp_part(prog, voic, max(8, bars // 2), rng, vel=0.45, div=0.125), bars, bar)
            d = drum_parts(max(8, bars // 2), rng, kick=True, clap=True, hat="eighth", open_hat=False, crash_start=True)
            for ch in ("Kick", "Clap", "Hat", "Crash"):
                put(f"{tag}_{ch.upper()}", ch, d[ch], bars, bar)
        sections.append({"name": sname, "start_bar": bar, "bars": bars})
        bar += bars

    return {
        "name": name, "tempo_bpm": tempo, "key": key, "mode": mode,
        "progression": prog, "voicings": voic, "seed": seed,
        "template": "templates/ambient-edm-v3.flp",
        "presets": presets or {
            "Chords": {"role": "pad"}, "Bass": {"role": "bass"}, "Lead": {"role": "lead"},
            "Pluck": {"role": "pluck"}, "Arp": {"role": "arp"},
        },
        "patterns": patterns, "playlist": playlist, "sections": sections, "total_bars": bar,
    }


if __name__ == "__main__":
    import sys
    a = json.load(open(sys.argv[1]))
    nm = sys.argv[2] if len(sys.argv) > 2 else "song"
    bp = build_song(a, nm, seed=int(sys.argv[3]) if len(sys.argv) > 3 else 7)
    out = Path(f"projects/{nm}.song.json")
    out.write_text(json.dumps(bp, indent=1), encoding="utf-8")
    print(f"{len(bp['patterns'])} patterns, {len(bp['playlist'])} clips, {bp['total_bars']} bars,",
          "prog", bp["progression"], "->", out)
