"""Programmatic Vital sound design: role patches built from factory presets + overrides.

A 'role' (pad, bass, sub, lead, pluck, arp, texture) picks a base preset from the
user's library (wavetables and oscillator design stay as the preset author made them)
and then shapes it for the role: envelopes, filter, unison, polyphony, Vital's own
effects (reverb/delay/chorus/compressor) and an optional tempo-synced 'pump' LFO on the
oscillator levels (sidechain feel without a mixer sidechain).

Knowledge used (verified against factory preset JSON, 2026-10-14):
  env times are seconds-ish (attack 0..?); filter cutoff in semitone-like units (0..136,
  ~60 = 262 Hz, ~100 = 2.6 kHz); reverb_dry_wet / delay_dry_wet 0..1; lfo tempo index
  7 ~ 1/2 note, 8 ~ 1/4 note (Vital list: Freeze,32/1,...,1/1,1/2,1/4,1/8,1/16...);
  LFO point y is inverted (stored y=1 -> output 0); modulations[i] pairs with
  settings['modulation_{i+1}_amount'].
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

INDEX = Path("library-index/vital_presets.json")

# candidate base presets per role, in preference order (names from the user's library)
ROLE_BASES = {
    "pad": ["Analog Pad", "Space Station", "Fleet", "Snowcrash", "Strings Section", "Float Chords"],
    "bass": ["Moog Pluck", "Simple Weoum", "Thumpus", "THUNK"],
    "sub": ["Moog Pluck", "Simple Weoum", "Thumpus"],
    "lead": ["Distant Majestic Lead", "Moving Harmonics", "Synthetic Quartet", "Damped Horn", "LORN Style Lead"],
    "pluck": ["Super Nice Pluck", "Super Pluck", "Plucked String", "Moog Pluck", "Ceramic"],
    "arp": ["Super Pluck", "Super Nice Pluck", "Plucked String", "Keystation"],
    "keys": ["Chorusy Keys", "Satellites", "Piano from the yard sale", "Keystation", "Salomon"],
    "texture": ["Cinema Bells", "Crescendo Bells", "Abbysun", "Drowning Machine"],
}

# role shaping: overrides applied on top of the base preset
ROLE_SHAPE = {
    "pad": dict(env_1_attack=1.6, env_1_decay=2.0, env_1_sustain=0.85, env_1_release=3.5,
                filter_1_on=1, filter_1_cutoff=72, filter_1_resonance=0.15,
                reverb_on=1, reverb_dry_wet=0.38, reverb_size=0.75, reverb_decay_time=0.85,
                chorus_on=1, chorus_dry_wet=0.35, delay_on=0, polyphony=12, legato=0,
                _unison=(6, 1.6), _pump=0.55),
    "bass": dict(env_1_attack=0.0, env_1_decay=0.6, env_1_sustain=0.75, env_1_release=0.12,
                 filter_1_on=1, filter_1_cutoff=66, filter_1_resonance=0.1,
                 reverb_on=0, delay_on=0, chorus_on=0, polyphony=1, legato=1, portamento_time=-10.0,
                 _unison=(1, 0.0), _pump=0.0, _mono_low=True),
    "sub": dict(env_1_attack=0.0, env_1_decay=0.4, env_1_sustain=1.0, env_1_release=0.08,
                filter_1_on=1, filter_1_cutoff=52, filter_1_resonance=0.0,
                reverb_on=0, delay_on=0, chorus_on=0, polyphony=1, legato=1,
                _unison=(1, 0.0), _pump=0.0),
    "lead": dict(env_1_attack=0.05, env_1_decay=0.8, env_1_sustain=0.7, env_1_release=0.9,
                 filter_1_on=1, filter_1_cutoff=92, filter_1_resonance=0.1,
                 reverb_on=1, reverb_dry_wet=0.28, reverb_size=0.6, reverb_decay_time=0.7,
                 delay_on=1, delay_dry_wet=0.22, delay_sync=1, delay_tempo=9, delay_feedback=0.35,
                 chorus_on=0, polyphony=4, legato=0, _unison=(3, 0.9), _pump=0.2),
    "pluck": dict(env_1_attack=0.0, env_1_decay=0.45, env_1_sustain=0.0, env_1_release=0.35,
                  filter_1_on=1, filter_1_cutoff=88, filter_1_resonance=0.2,
                  reverb_on=1, reverb_dry_wet=0.32, reverb_size=0.7, reverb_decay_time=0.75,
                  delay_on=1, delay_dry_wet=0.3, delay_sync=1, delay_tempo=9, delay_feedback=0.4,
                  chorus_on=0, polyphony=8, legato=0, _unison=(2, 0.6), _pump=0.25),
    "arp": dict(env_1_attack=0.0, env_1_decay=0.3, env_1_sustain=0.0, env_1_release=0.25,
                filter_1_on=1, filter_1_cutoff=84, filter_1_resonance=0.25,
                reverb_on=1, reverb_dry_wet=0.3, reverb_size=0.65, reverb_decay_time=0.7,
                delay_on=1, delay_dry_wet=0.35, delay_sync=1, delay_tempo=9, delay_feedback=0.45,
                chorus_on=0, polyphony=6, legato=0, _unison=(2, 0.5), _pump=0.3),
    "keys": dict(env_1_attack=0.01, env_1_decay=1.2, env_1_sustain=0.3, env_1_release=0.8,
                 reverb_on=1, reverb_dry_wet=0.3, chorus_on=1, chorus_dry_wet=0.25, delay_on=0,
                 polyphony=8, legato=0, _unison=(2, 0.4), _pump=0.3),
    "texture": dict(env_1_attack=2.5, env_1_decay=2.0, env_1_sustain=0.8, env_1_release=4.0,
                    reverb_on=1, reverb_dry_wet=0.5, reverb_size=0.9, reverb_decay_time=0.9,
                    delay_on=1, delay_dry_wet=0.3, delay_sync=1, delay_tempo=8, delay_feedback=0.5,
                    polyphony=8, _unison=(4, 1.2), _pump=0.4),
}

PUMP_TEMPO_INDEX = 8   # ~ 1/4 note (see module docstring); change if the pump is twice too slow/fast


def _load_index() -> dict[str, dict]:
    return {p["name"].lower(): p for p in json.loads(INDEX.read_text(encoding="utf-8"))}


def load_preset(name: str) -> dict:
    idx = _load_index()
    p = idx[name.lower()]
    d = json.loads(Path(p["path"]).read_text(encoding="utf-8", errors="ignore"))
    d.setdefault("preset_name", p["name"])
    return d


def pick_base(role: str, preferred: str | None = None) -> str:
    idx = _load_index()
    for name in ([preferred] if preferred else []) + ROLE_BASES.get(role, []):
        if name and name.lower() in idx:
            return idx[name.lower()]["name"]
    # fallback: any preset tagged with a matching style
    style = {"pad": "Pad", "bass": "Bass", "sub": "Bass", "lead": "Lead", "pluck": "Keys", "arp": "Sequence",
             "keys": "Keys", "texture": "Pad"}[role]
    for p in idx.values():
        if p["style"] == style:
            return p["name"]
    return next(iter(idx.values()))["name"]


def _add_modulation(s: dict, source: str, destination: str, amount: float, bipolar: int = 0) -> None:
    mods = s.setdefault("modulations", [])
    # reuse an empty slot (Vital keeps 64 entries; empty ones have no source)
    for i, m in enumerate(mods):
        if not m.get("source"):
            mods[i] = {"source": source, "destination": destination}
            n = i + 1
            s[f"modulation_{n}_amount"] = float(amount); s[f"modulation_{n}_bipolar"] = float(bipolar)
            s[f"modulation_{n}_bypass"] = 0.0; s[f"modulation_{n}_power"] = 0.0; s[f"modulation_{n}_stereo"] = 0.0
            return
    mods.append({"source": source, "destination": destination})
    n = len(mods)
    s[f"modulation_{n}_amount"] = float(amount); s[f"modulation_{n}_bipolar"] = float(bipolar)
    s[f"modulation_{n}_bypass"] = 0.0; s[f"modulation_{n}_power"] = 0.0; s[f"modulation_{n}_stereo"] = 0.0


def _free_lfo(s: dict) -> int:
    used = {int(m["source"].split("_")[1]) for m in s.get("modulations", [])
            if m.get("source", "").startswith("lfo_")}
    for n in range(8, 0, -1):          # take the highest unused LFO
        if n not in used:
            return n
    return 8


def add_pump(s: dict, depth: float, tempo_index: int = PUMP_TEMPO_INDEX) -> None:
    """Tempo-synced duck on all active oscillator levels (sidechain feel)."""
    if depth <= 0:
        return
    n = _free_lfo(s)
    lfos = s.setdefault("lfos", [])
    while len(lfos) < n:
        lfos.append({"name": "Triangle", "num_points": 3, "points": [0.0, 1.0, 0.5, 0.0, 1.0, 1.0],
                     "powers": [0.0, 0.0, 0.0], "smooth": False})
    # output = 1 - y : full duck at beat start, released by 35% of the cycle, flat after
    lfos[n - 1] = {"name": "Pump", "num_points": 3, "points": [0.0, 0.0, 0.35, 1.0, 1.0, 1.0],
                   "powers": [0.0, -2.0, 0.0], "smooth": True}
    s[f"lfo_{n}_sync"] = 1.0; s[f"lfo_{n}_tempo"] = float(tempo_index); s[f"lfo_{n}_sync_type"] = 1.0
    s[f"lfo_{n}_phase"] = 0.0; s[f"lfo_{n}_fade_time"] = 0.0; s[f"lfo_{n}_delay_time"] = 0.0
    for o in (1, 2, 3):
        if s.get(f"osc_{o}_on", 0) >= 1:
            lvl = float(s.get(f"osc_{o}_level", 0.7))
            _add_modulation(s, f"lfo_{n}", f"osc_{o}_level", -depth * lvl)
    if s.get("sample_on", 0) >= 1:
        _add_modulation(s, f"lfo_{n}", "sample_level", -depth * float(s.get("sample_level", 0.5)))


def design(role: str, base: str | None = None, *, pump: float | None = None, cutoff: float | None = None,
           brightness: float = 0.0, space: float = 0.0, name: str | None = None) -> dict:
    """Return a full Vital preset dict for `role`. brightness/space in -1..1 nudge filter and reverb."""
    base_name = pick_base(role, base)
    d = copy.deepcopy(load_preset(base_name))
    s = d["settings"]
    shape = dict(ROLE_SHAPE[role])
    unison = shape.pop("_unison", None)
    pump_depth = shape.pop("_pump", 0.0) if pump is None else pump
    mono_low = shape.pop("_mono_low", False)
    for k, v in shape.items():
        if k in s or k.startswith(("env_", "filter_", "reverb_", "delay_", "chorus_", "polyphony", "legato", "portamento")):
            s[k] = float(v)
    if cutoff is not None:
        s["filter_1_cutoff"] = float(cutoff)
    if brightness:
        s["filter_1_cutoff"] = float(min(136, max(8, s.get("filter_1_cutoff", 80) + 20 * brightness)))
    if space:
        s["reverb_dry_wet"] = float(min(0.8, max(0.0, s.get("reverb_dry_wet", 0.2) + 0.25 * space)))
        if space > 0:
            s["reverb_on"] = 1.0
    if unison:
        voices, detune = unison
        for o in (1, 2, 3):
            if s.get(f"osc_{o}_on", 0) >= 1:
                s[f"osc_{o}_unison_voices"] = float(voices)
                s[f"osc_{o}_unison_detune"] = float(detune)
    if mono_low:
        # make sure the bass is not an octave too high: oscillators at or below 0 transpose
        for o in (1, 2, 3):
            if s.get(f"osc_{o}_on", 0) >= 1 and s.get(f"osc_{o}_transpose", 0) > 0:
                s[f"osc_{o}_transpose"] = 0.0
    # route filter 1 to all oscillators so the cutoff shaping is audible
    if s.get("filter_1_on", 0) >= 1:
        for o in (1, 2, 3):
            s[f"osc_{o}_destination"] = 0.0       # 0 = filter 1
    add_pump(s, pump_depth)
    d["preset_name"] = name or f"{role}:{base_name}"
    d["preset_style"] = role.capitalize()
    d["comments"] = f"fl-ai-producer {role} patch based on '{base_name}'"
    return d


if __name__ == "__main__":
    for role in ROLE_SHAPE:
        d = design(role)
        print(role, "->", d["preset_name"], "mods:", sum(1 for m in d["settings"]["modulations"] if m.get("source")))
