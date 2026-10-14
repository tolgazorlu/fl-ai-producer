"""Build a complete FL Studio project file offline:

    template .flp  +  song blueprint (composer.arrange)  +  Vital presets  ->  out.flp

No FL Studio needed. Steps: copy template -> swap Vital presets (bridge.flp_vital) ->
tempo + pattern notes (flpkit) -> playlist clips (own writer, FL 2026 record layout) ->
read back and verify.

    .venv\\Scripts\\python.exe -m bridge.build_flp projects/underwater.song.json \
        --template templates/ambient-edm/ambient-edm.flp --out projects/underwater.flp
"""
from __future__ import annotations

import json
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

import flpkit

from .flp_vital import Event, apply_presets, build_flp, parse_flp

EVENT_PLAYLIST = 233
PATTERN_INDEX_BASE = 20480
TRACK_SPACE = 500
RECORD_HEAD = struct.Struct("<IHHIHH")  # position, pattern_base, item_index, length, 500-track, group
# Era tail (record bytes 16..88) copied from a clip FL Studio 2026.1.6 wrote itself
# (Projects/edm_1). Bytes 24..32 hold the cut window (u32 start, u32 end in ticks).
_FL26_TAIL = bytes.fromhex(
    "7800400040648080" "000080bf000080bf" "d100000000000000" "0000000000000000"
    "000000000000803f" "0000000000000000" "000000000000f03f" "00000000ffffffff" "0000000000000000"
)
assert len(_FL26_TAIL) == 72


@dataclass
class _Note:
    key: int; start: float; length: float; velocity: float = 0.8; pan: float = 0.5


def _playlist_blob(clips: list[dict], pattern_ids: dict[str, int], ppq: int) -> bytes:
    recs = []
    for c in clips:
        pos = round(c["start_bar"] * 4 * ppq)
        length = round(c["length_bars"] * 4 * ppq)
        tail = bytearray(_FL26_TAIL)
        struct.pack_into("<II", tail, 24 - 16, 0, length)
        head = RECORD_HEAD.pack(pos, PATTERN_INDEX_BASE, PATTERN_INDEX_BASE + pattern_ids[c["pattern"]],
                                length, TRACK_SPACE - int(c["track"]), 0)
        recs.append((pos, head + bytes(tail)))
    recs.sort(key=lambda r: r[0])
    return b"".join(r for _, r in recs)


def _write_playlist(path: Path, blob: bytes) -> None:
    header, events = parse_flp(path.read_bytes())
    idx = [i for i, e in enumerate(events) if e.id == EVENT_PLAYLIST]
    if not idx:
        raise RuntimeError("template has no playlist event (233)")
    events[idx[0]] = Event(EVENT_PLAYLIST, blob)
    path.write_bytes(build_flp(header, events))


def build(song: dict, template: Path, out: Path, preset_index: Path | None = None) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    # 1. presets
    mapping = {}
    if song.get("presets"):
        idx = json.loads((preset_index or Path("library-index/vital_presets.json")).read_text(encoding="utf-8"))
        by_name = {p["name"].lower(): Path(p["path"]) for p in idx}
        for chan, name in song["presets"].items():
            if name and name.lower() in by_name:
                mapping[chan] = by_name[name.lower()]
            else:
                print(f"!! preset {name!r} for {chan} not in index; keeping template sound")
    if mapping:
        done = apply_presets(template, out, mapping)
        print("presets:", done)
    else:
        shutil.copy(template, out)
    # 2. tempo + notes
    flpkit.set_tempo(out, float(song["tempo_bpm"]))
    chan_of = song["channels"]
    pattern_ids = {}
    for i, (pname, spec) in enumerate(song["patterns"].items(), start=1):
        notes = [_Note(n["pitch"], n["time_bars"] * 4, n["length_bars"] * 4, n["velocity"]) for n in spec["notes"]]
        got = flpkit.write_notes(out, notes, pattern=i, channel=chan_of[spec["channel"]], mode="replace")
        pattern_ids[pname] = i
        print(f"pattern {i:2d} {pname:14s} -> {spec['channel']:7s} {len(got)} notes")
    # 3. playlist
    ppq = flpkit.read(out).ppq
    _write_playlist(out, _playlist_blob(song["playlist"], pattern_ids, ppq))
    proj = flpkit.read(out)
    print(f"playlist: {len(proj.playlist)} clips, {song.get('total_bars')} bars, tempo {proj.tempo}")
    return {"out": str(out), "patterns": pattern_ids, "clips": len(proj.playlist)}


if __name__ == "__main__":
    args = sys.argv[1:]
    song = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    template = Path(args[args.index("--template") + 1]) if "--template" in args else Path("templates/ambient-edm/ambient-edm.flp")
    out = Path(args[args.index("--out") + 1]) if "--out" in args else Path(f"projects/{song['name']}.flp")
    build(song, template, out)
