"""Apply a blueprint.json to the running FL Studio project through the daemon.

For each part: find the channel by name, create/select a pattern named after the
part, point the Piano roll at that channel, write the notes.

    .venv-flmcp\\Scripts\\python.exe -m bridge.apply_blueprint projects/x.blueprint.json [--tempo]

Requires: daemon running, FL open, MCP_Apply armed once this session.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .fl_client import FL


def find_channel(channels: list[dict], name: str) -> int | None:
    want = name.lower()
    for c in channels:
        if c.get("name", "").lower() == want:
            return int(c["i"] if "i" in c else c["index"])
    for c in channels:
        have = c.get("name", "").lower()
        if want in have or (len(have) >= 3 and have in want):
            return int(c["i"] if "i" in c else c["index"])
    return None


def apply(bp: dict, set_tempo: bool = True, parts: list[str] | None = None) -> list[dict]:
    fl = FL()
    print("ping:", fl.ping())
    if set_tempo:
        print("tempo:", fl.set_tempo(bp["tempo_bpm"]))
    chan_list = fl.channels()
    print("channels:", [c.get("name") for c in chan_list])
    results = []
    for part, spec in bp["parts"].items():
        if parts and part not in parts:
            continue
        idx = find_channel(chan_list, spec["channel"])
        if idx is None:
            print(f"!! no channel named '{spec['channel']}' for part {part}; skipping")
            results.append({"part": part, "ok": False, "reason": "channel not found"})
            continue
        pat = fl.new_pattern(part.upper())
        time.sleep(0.3)
        res = fl.write_notes(spec["notes"], mode="replace", channel=idx)
        time.sleep(1.2)  # give FL time to run the pyscript before the next pattern
        print(f"{part}: pattern={pat} channel={idx} notes={len(spec['notes'])} -> {res.get('ok')} "
              f"triggered={res.get('triggered')} {res.get('error', '')}")
        results.append({"part": part, "ok": bool(res.get("ok")), "pattern": pat, "channel": idx})
    return results


if __name__ == "__main__":
    args = sys.argv[1:]
    bp = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    only = [a for a in args[1:] if not a.startswith("--")] or None
    apply(bp, set_tempo="--no-tempo" not in args, parts=only)
