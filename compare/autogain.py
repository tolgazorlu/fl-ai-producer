"""Closed-loop level balancing: measure rendered stems, derive gain changes per channel.

Targets are integrated LUFS over the whole song per mixer insert (stems rendered with
'split mixer tracks'). Returns {channel: {"fl_volume": 0..1, "vital_gain_db": float}}.

FL channel volume: 0.8 ~= 0 dB (template default 0.78 = -0.2 dB), 1.0 ~= +5.6 dB, so
v = 0.8 * 10^(dB/20) clipped to [0.03, 1.0]. Extra boost for Vital channels goes into the
preset's 'volume' parameter: Vital shows dB = sqrt(v) - 80 (range -80..+6.02, default -6.02).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

# which mixer insert (stem file) each channel feeds, and the target stem loudness
CHANNEL_STEM = {"Chords": "Pad", "Bass": "Bass", "Lead": "Lead", "Pluck": "Pluck", "Arp": "Arp",
                "Kick": "Kick", "Clap": "Clap", "Hat": "Hats", "OpenHat": "Hats",
                "Crash": "FX", "Riser": "FX", "Impact": "FX"}
TARGET_LUFS = {"Pad": -17.0, "Bass": -15.0, "Lead": -17.0, "Pluck": -19.0, "Arp": -19.0,
               "Kick": -14.0, "Clap": -18.0, "Hats": -22.0, "FX": -22.0}
VITAL_CHANNELS = {"Chords", "Bass", "Lead", "Pluck", "Arp"}


# FL's channel volume knob is not a plain linear gain: measured on FL 2026 renders,
# a knob ratio r changes the level by ~1.6 * 20*log10(r) dB (0.78 = unity).
FL_KNOB_EXP = 1.6


def fl_volume_for_db(db: float) -> float:
    return max(0.03, min(1.0, 0.78 * 10 ** (db / (20 * FL_KNOB_EXP))))


def db_of_fl_volume(v: float) -> float:
    return FL_KNOB_EXP * 20 * math.log10(max(v, 1e-4) / 0.78)


def plan(stem_stats: dict[str, dict], current: dict[str, dict] | None = None) -> dict[str, dict]:
    """stem_stats: {stem name: stats dict with 'lufs'}; current: previous plan (for iteration)."""
    out = {}
    for chan, stem in CHANNEL_STEM.items():
        st = stem_stats.get(stem)
        if not st or st["lufs"] in (None, float("-inf")) or st["lufs"] < -60:
            continue
        delta = TARGET_LUFS[stem] - st["lufs"]           # dB to add
        cur = (current or {}).get(chan, {"fl_volume": 0.78, "vital_gain_db": -6.02})
        cur_db = db_of_fl_volume(cur["fl_volume"])
        want_db = cur_db + delta
        entry = {"fl_volume": fl_volume_for_db(want_db), "vital_gain_db": cur.get("vital_gain_db", -6.02), "delta_db": round(delta, 1)}
        if chan in VITAL_CHANNELS:
            # put up to +6 dB of boost into Vital's own volume; anything beyond that into the oscillator levels
            short = want_db - db_of_fl_volume(entry["fl_volume"])   # what the fader could not provide (positive = still short)
            vg = cur.get("vital_gain_db", -6.02) + short
            entry["vital_gain_db"] = max(-40.0, min(6.0, vg))
            extra = vg - entry["vital_gain_db"]
            entry["osc_boost_db"] = round(max(0.0, cur.get("osc_boost_db", 0.0) + extra), 1)
        out[chan] = entry
    return out


def vital_volume_param(gain_db: float) -> float:
    return float(min(7399.4404, max(0.0, (80.0 + gain_db) ** 2)))


if __name__ == "__main__":
    import sys
    prefix = sys.argv[1]            # e.g. renders/vB_
    import glob
    from compare.render import stats
    stem_stats = {}
    for f in glob.glob(prefix + "*.wav"):
        name = Path(f).stem[len(Path(prefix).name):]
        stem_stats[name] = stats(Path(f))
    p = plan(stem_stats)
    print(json.dumps(p, indent=1))
