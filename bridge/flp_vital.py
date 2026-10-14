"""Swap Vital presets inside a .flp WITHOUT opening FL Studio.

Reverse-engineered on FL Studio 2026 (26.1.6) + Vital VST3, 2026-10-14.
Layout of a Vital channel's plugin-state event (FL event id 213, varint size):

  [Fruity Wrapper header ... chunks of (u32 id, u64 size, data) ...]
  chunk id 53  : the VST3 state block (u64 size at JSON-290+282 ...)
    +0..+88    : wrapper-internal fields; LE u32 at +88 = size of the VstW block
    'VstW' hdr : 16 bytes
    'CcnK'     : fxb/fxp chunk-set magic, BE u32 byteSize, 'FBCh', version,
                 fxID 'Vita', fxVersion, numPrograms, future[128], BE u32 chunkSize
    chunk data : Vital JSON preset text (+ a few trailing bytes), then
                 'JUCEPrivateData' block (left untouched)

So replacing the JSON needs 5 length fields updated by the same delta:
  FL event varint size, chunk-53 u64 size, wrapper LE u32 block size,
  CcnK BE u32 byteSize, FBCh BE u32 chunkSize.
Everything else is copied byte-for-byte. Always verify by re-reading.
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path


# ------------------------------------------------------------------ events
def _read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    size = shift = 0
    while True:
        b = buf[pos]; pos += 1
        size |= (b & 0x7F) << shift; shift += 7
        if not b & 0x80:
            return size, pos


def _write_varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b); return bytes(out)


@dataclass
class Event:
    id: int
    data: bytes

    def encode(self) -> bytes:
        if self.id >= 192 or self.id == 0xAC:
            return bytes([self.id]) + _write_varint(len(self.data)) + self.data
        return bytes([self.id]) + self.data


def parse_flp(raw: bytes) -> tuple[bytes, list[Event]]:
    """Return (header chunk bytes incl. 'FLhd'..., events)."""
    assert raw[:4] == b"FLhd", "not an FLP"
    hl = struct.unpack("<I", raw[4:8])[0]
    pos = 8 + hl
    assert raw[pos:pos + 4] == b"FLdt"
    header = raw[:pos]
    pos += 8
    events = []
    while pos < len(raw):
        eid = raw[pos]; pos += 1
        if eid >= 192 or eid == 0xAC:
            size, pos = _read_varint(raw, pos)
        elif eid < 64:
            size = 1
        elif eid < 128:
            size = 2
        else:
            size = 4
        events.append(Event(eid, raw[pos:pos + size])); pos += size
    return header, events


def build_flp(header: bytes, events: list[Event]) -> bytes:
    body = b"".join(e.encode() for e in events)
    return header + b"FLdt" + struct.pack("<I", len(body)) + body


# ------------------------------------------------------------------ vital
EV_CHANNEL_NAME = 203
EV_PLUGIN_STATE = 213


def _json_bounds(data: bytes) -> tuple[int, int] | None:
    j0 = data.find(b'{"author"')
    if j0 < 0:
        return None
    depth = 0; i = j0; instr = esc = False
    while i < len(data):
        c = data[i]
        if instr:
            if esc: esc = False
            elif c == 0x5C: esc = True
            elif c == 0x22: instr = False
        else:
            if c == 0x22: instr = True
            elif c == 0x7B: depth += 1
            elif c == 0x7D:
                depth -= 1
                if depth == 0:
                    return j0, i + 1
        i += 1
    return None


@dataclass
class VitalSlot:
    event_index: int
    channel: str
    json_start: int
    json_end: int

    @property
    def length(self) -> int:
        return self.json_end - self.json_start


def find_vital_slots(events: list[Event]) -> list[VitalSlot]:
    slots, last_name = [], ""
    for i, e in enumerate(events):
        if e.id == EV_CHANNEL_NAME:
            last_name = e.data.decode("utf-16-le", "ignore").rstrip("\x00")
        elif e.id == EV_PLUGIN_STATE and b"Vita" in e.data[:600]:
            b = _json_bounds(e.data)
            if b:
                slots.append(VitalSlot(i, last_name, b[0], b[1]))
    return slots


def embedded_preset(events: list[Event], slot: VitalSlot) -> dict:
    return json.loads(events[slot.event_index].data[slot.json_start:slot.json_end])


def _size_field_offsets(data: bytes, j0: int) -> dict[str, tuple[int, str]]:
    """Locate the 4 inner length fields relative to the JSON start, validating magics."""
    ccnk = data.rfind(b"CcnK", 0, j0)
    vstw = data.rfind(b"VstW", 0, j0)
    assert ccnk > 0 and vstw > 0 and data[ccnk + 8:ccnk + 12] == b"FBCh", "unexpected Vital state layout"
    chunk_size_at = ccnk + 8 + 4 + 4 + 4 + 4 + 4 + 128      # FBCh ver fxID fxVer nProg future[128]
    assert chunk_size_at + 4 == j0, f"chunkSize field not directly before JSON ({chunk_size_at + 4} != {j0})"
    wrapper_size_at = vstw - 4                                  # LE u32 = size of VstW..end of chunk data
    # chunk 53 header: u32 id, u64 size; the state block starts 8 bytes after the size field
    c53 = data.rfind(struct.pack("<I", 53), 0, vstw)
    assert c53 > 0, "chunk 53 not found"
    return {"fbch_chunk_size": (chunk_size_at, ">I"), "ccnk_byte_size": (ccnk + 4, ">I"),
            "wrapper_block_size": (wrapper_size_at, "<I"), "chunk53_size": (c53 + 4, "<Q")}


def set_preset(events: list[Event], slot: VitalSlot, preset: dict) -> None:
    """Replace the slot's JSON with `preset` (dict from a .vital file), fixing all sizes."""
    e = events[slot.event_index]
    data = bytearray(e.data)
    old = json.loads(bytes(data[slot.json_start:slot.json_end]))
    merged = {**old, **preset}
    new_json = json.dumps(merged, separators=(",", ":")).encode("utf-8")
    delta = len(new_json) - slot.length
    fields = _size_field_offsets(bytes(data), slot.json_start)
    for name, (off, fmt) in fields.items():
        n = struct.calcsize(fmt)
        cur = struct.unpack(fmt, bytes(data[off:off + n]))[0]
        data[off:off + n] = struct.pack(fmt, cur + delta)
    data[slot.json_start:slot.json_end] = new_json
    e.data = bytes(data)
    slot.json_end = slot.json_start + len(new_json)


def apply_presets(src: Path, dst: Path, mapping: dict[str, Path | dict]) -> dict[str, str]:
    """mapping: {channel name: .vital path or preset dict}. Returns {channel: preset name}."""
    header, events = parse_flp(src.read_bytes())
    slots = {s.channel.lower(): s for s in find_vital_slots(events)}
    done = {}
    for chan, preset in mapping.items():
        slot = slots.get(chan.lower())
        if slot is None:
            raise KeyError(f"no Vital channel named {chan!r}; have {list(slots)}")
        if isinstance(preset, (str, Path)):
            p = Path(preset)
            pd = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            pd.setdefault("preset_name", p.stem)
        else:
            pd = preset
        set_preset(events, slot, pd)
        done[slot.channel] = pd.get("preset_name", "?")
    out = build_flp(header, events)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)
    # verify: re-parse and re-find
    _, ev2 = parse_flp(out)
    check = {s.channel: embedded_preset(ev2, s).get("preset_name") for s in find_vital_slots(ev2)}
    for chan, name in done.items():
        assert check.get(chan) == name, f"verify failed for {chan}: {check}"
    return done


if __name__ == "__main__":
    import sys
    src = Path(sys.argv[1])
    _, ev = parse_flp(src.read_bytes())
    for s in find_vital_slots(ev):
        d = embedded_preset(ev, s)
        print(f"{s.channel!r}: preset_name={d.get('preset_name')!r} style={d.get('preset_style')!r} "
              f"json={s.length} bytes, keys={list(d)[:10]}")
