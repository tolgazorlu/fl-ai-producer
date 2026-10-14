"""Add channels to a .flp by cloning channel event blocks (no FL Studio needed).

A channel block = event 64 (u16 channel index) followed by ~46 per-channel events
(type, plugin wrapper, name 203, plugin state 213 for generators, sample path 196
for samplers, levels, envelopes ...). The sequence is identical across FL 2026
files, so a block copied from any FL-authored project is a valid template:
  * sampler block  -> set index, name (203), sample path (196)
  * Vital block    -> set index, name (203); preset via bridge.flp_vital later
Blocks are inserted after the last existing channel block, before the arrangement
section (first event 99).
"""
from __future__ import annotations

import json
from pathlib import Path

from .flp_vital import Event, build_flp, parse_flp

EV_NEW_CHANNEL = 64
EV_NEW_ARRANGEMENT = 99
EV_NEW_PATTERN = 65
EV_CHANNEL_NAME = 203
EV_SAMPLE_PATH = 196
EV_PLUGIN_NAME = 201
EV_PLUGIN_STATE = 213
EV_PLUGIN_WRAPPER = 212


def _u16(n: int) -> bytes:
    return int(n).to_bytes(2, "little")


def _text(s: str) -> bytes:
    return s.encode("utf-16-le") + b"\x00\x00"


def _read_text(e: Event) -> str:
    return e.data.decode("utf-16-le", "ignore").rstrip("\x00")


def channel_blocks(events: list[Event]) -> list[dict]:
    """[{index, name, plugin, start, end}] where end is exclusive and stops at the
    next channel, the first pattern (65) or arrangement (99) event."""
    starts = [i for i, e in enumerate(events) if e.id == EV_NEW_CHANNEL]
    out = []
    for n, s in enumerate(starts):
        limit = starts[n + 1] if n + 1 < len(starts) else len(events)
        end = s + 1
        while end < limit and events[end].id not in (EV_NEW_PATTERN, EV_NEW_ARRANGEMENT):
            end += 1
        blk = {"index": int.from_bytes(events[s].data, "little"), "start": s, "end": end, "name": "", "plugin": ""}
        for e in events[s + 1:end]:
            if e.id == EV_CHANNEL_NAME: blk["name"] = _read_text(e)
            if e.id == EV_PLUGIN_NAME: blk["plugin"] = _read_text(e)
            if e.id == EV_SAMPLE_PATH: blk["sample"] = _read_text(e)
        out.append(blk)
    return out


def extract_block(events: list[Event], blk: dict) -> list[Event]:
    return [Event(e.id, e.data) for e in events[blk["start"]:blk["end"]]]


def retarget_block(block: list[Event], index: int, name: str, sample_path: str | None = None) -> list[Event]:
    out = []
    for e in block:
        if e.id == EV_NEW_CHANNEL:
            out.append(Event(e.id, _u16(index)))
        elif e.id == EV_CHANNEL_NAME:
            out.append(Event(e.id, _text(name)))
        elif e.id == EV_SAMPLE_PATH and sample_path is not None:
            out.append(Event(e.id, _text(sample_path)))
        else:
            out.append(Event(e.id, e.data))
    return out


def insert_point(events: list[Event]) -> int:
    """Index at which new channel blocks go: after the last channel block's end."""
    blocks = channel_blocks(events)
    return blocks[-1]["end"] if blocks else len(events)


def add_channels(src_flp: Path, dst_flp: Path, new_channels: list[dict],
                 sampler_template_flp: Path | None = None) -> list[dict]:
    """new_channels: [{"name": "Kick", "kind": "sampler", "sample": "C:/..wav"} |
                      {"name": "Pluck", "kind": "vital", "clone_from": "Lead"}]
    Returns the resulting channel list."""
    header, events = parse_flp(src_flp.read_bytes())
    blocks = channel_blocks(events)
    by_name = {b["name"].lower(): b for b in blocks}
    sampler_block = None
    if sampler_template_flp:
        _, tev = parse_flp(sampler_template_flp.read_bytes())
        for b in channel_blocks(tev):
            if "sample" in b and not b["plugin"]:
                sampler_block = extract_block(tev, b); break
    new_blocks: list[Event] = []
    next_index = max(b["index"] for b in blocks) + 1 if blocks else 0
    for spec in new_channels:
        kind = spec.get("kind", "sampler")
        if kind == "sampler":
            if sampler_block is None:
                raise RuntimeError("need sampler_template_flp containing a sampler channel")
            blk = retarget_block(sampler_block, next_index, spec["name"], spec.get("sample", ""))
        else:
            src = by_name[spec.get("clone_from", "lead").lower()]
            blk = retarget_block(extract_block(events, src), next_index, spec["name"])
        new_blocks += blk
        next_index += 1
    ip = insert_point(events)
    events = events[:ip] + new_blocks + events[ip:]
    # FLhd: 'FLhd' u32 len | u16 format | u16 channel_count | u16 ppq
    header = bytearray(header)
    header[10:12] = len(channel_blocks(events)).to_bytes(2, "little")
    dst_flp.parent.mkdir(parents=True, exist_ok=True)
    dst_flp.write_bytes(build_flp(bytes(header), events))
    _, ev2 = parse_flp(dst_flp.read_bytes())
    return [{k: b[k] for k in ("index", "name", "plugin") if k in b} | ({"sample": b["sample"]} if "sample" in b else {})
            for b in channel_blocks(ev2)]


if __name__ == "__main__":
    import sys
    _, ev = parse_flp(Path(sys.argv[1]).read_bytes())
    for b in channel_blocks(ev):
        print(b)
