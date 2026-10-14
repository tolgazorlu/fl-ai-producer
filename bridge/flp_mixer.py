"""Mixer editing in .flp files: route channels to inserts, name inserts, add effect slots.

Learned from FL Studio 2026 files (2026-10-14):
  * channel -> insert routing: WORD event 104 inside the channel block (value = insert number)
  * mixer section (after the arrangement events): one block per insert, in order 0..N:
      [149 color] 42 [95 icon] [204 name] 236 flags
      slot blocks: 201 internal-name, 212 wrapper, [203 name], 155 icon, 128, 41, 213 state
      then 98 slot-index (one 98 per slot, 10 slots; empty slots are just a 98)
      235 routing, 165, 166, 49, 154 input, 147 output
  * effect states (213) copied from FL's bundled demo projects are valid "presets";
    library-index/fx_chains.pkl holds every slot block of those projects.
"""
from __future__ import annotations

import pickle
from pathlib import Path

from .flp_channels import channel_blocks
from .flp_vital import Event, build_flp, parse_flp

EV_ROUTE = 104
EV_INSERT_START = 42
EV_INSERT_NAME = 204
EV_INSERT_FLAGS = 236
EV_SLOT = 98
EV_INSERT_OUT = 147
FX_LIB = Path("library-index/fx_chains.pkl")


def _text(s: str) -> bytes:
    return s.encode("utf-16-le") + b"\x00\x00"


def mixer_start(events: list[Event]) -> int:
    return max((i for i, e in enumerate(events) if e.id in (99, 233, 238, 241)), default=0) + 1


def insert_spans(events: list[Event]) -> list[tuple[int, int]]:
    """(start, end) event indexes of each insert block (start = the 42 marker, end exclusive)."""
    s0 = mixer_start(events)
    starts = [i for i in range(s0, len(events)) if events[i].id == EV_INSERT_START]
    spans = []
    for n, s in enumerate(starts):
        e = starts[n + 1] if n + 1 < len(starts) else len(events)
        # trim to just after the insert's output event
        for j in range(s, e):
            if events[j].id == EV_INSERT_OUT:
                e = j + 1
                break
        spans.append((s, e))
    return spans


def set_channel_routes(events: list[Event], routes: dict[str, int]) -> None:
    for b in channel_blocks(events):
        if b["name"] in routes:
            for e in events[b["start"]:b["end"]]:
                if e.id == EV_ROUTE:
                    e.data = int(routes[b["name"]]).to_bytes(2, "little")


def _load_lib() -> list[dict]:
    return pickle.load(open(FX_LIB, "rb"))


def pick_block(lib: list[dict], plugin: str, hint: str = "", min_version: str = "20") -> list[Event]:
    """Newest-version slot block for `plugin`, preferring inserts whose name contains `hint`."""
    cands = [b for b in lib if b["plugin"] == plugin and b["version"] >= min_version]
    if not cands:
        cands = [b for b in lib if b["plugin"] == plugin]
    if not cands:
        raise KeyError(f"no library block for {plugin!r}")
    def score(b):
        return (hint.lower() in b["insert_name"].lower() if hint else False, b["version"])
    best = max(cands, key=score)
    return [Event(i, d) for i, d in best["events"]]


def add_effects(events: list[Event], insert: int, chain: list[tuple[str, str]], name: str | None = None) -> None:
    """chain: [(plugin name, hint)] placed in slots 0..n-1 of `insert` (replacing nothing: slots must be empty)."""
    lib = _load_lib()
    spans = insert_spans(events)
    s, e = spans[insert]
    block = events[s:e]
    out = [block[0]]                                   # the 42 marker
    rest = block[1:]
    # name right after the marker (drop an existing one)
    rest = [x for x in rest if x.id != EV_INSERT_NAME]
    if name:
        out.append(Event(EV_INSERT_NAME, _text(name)))
    slot_i = 0
    chain_blocks = [pick_block(lib, p, h) for p, h in chain]
    for x in rest:
        if x.id == EV_SLOT:
            if slot_i < len(chain_blocks):
                # only fill if this slot is empty (no 201 directly before it in the original)
                out.extend(chain_blocks[slot_i])
            slot_i += 1
        out.append(x)
    events[s:e] = out


def apply_mixer(src: Path, dst: Path, routes: dict[str, int], inserts: dict[int, dict]) -> None:
    """inserts: {index: {"name": "Pad", "chain": [("Fruity Parametric EQ 2", "pad"), ...]}}"""
    header, events = parse_flp(src.read_bytes())
    set_channel_routes(events, routes)
    for idx in sorted(inserts):           # ascending: spans are recomputed inside add_effects
        spec = inserts[idx]
        add_effects(events, idx, spec.get("chain", []), spec.get("name"))
    dst.write_bytes(build_flp(header, events))


def describe(path: Path) -> list[str]:
    _, events = parse_flp(path.read_bytes())
    lines = []
    for n, (s, e) in enumerate(insert_spans(events)):
        name, plugs = "", []
        for x in events[s:e]:
            if x.id == EV_INSERT_NAME: name = x.data.decode("utf-16-le", "ignore").rstrip("\x00")
            if x.id == 201: plugs.append(x.data.decode("utf-16-le", "ignore").rstrip("\x00"))
        if name or plugs:
            lines.append(f"insert {n:2d} {name!r}: {' > '.join(plugs)}")
    routes = {b["name"]: next((int.from_bytes(x.data, "little") for x in events[b["start"]:b["end"]] if x.id == EV_ROUTE), None)
              for b in channel_blocks(events)}
    lines.append(f"routes: {routes}")
    return lines


if __name__ == "__main__":
    import sys
    print("\n".join(describe(Path(sys.argv[1]))))
