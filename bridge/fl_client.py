"""Thin Python client for the running flstudio-mcp daemon (TCP 127.0.0.1:9787).

Lets scripts apply a whole blueprint to FL Studio without going through the MCP
tool layer one call at a time. Requires the daemon to be running and the
`.venv-flmcp` interpreter (fl_studio_mcp is installed there):

    .venv-flmcp\\Scripts\\python.exe -m bridge.apply_blueprint blueprint.json
"""
from __future__ import annotations

import os

os.environ.setdefault("FLSTUDIO_MCP_TRANSPORT", "tcp")

from fl_studio_mcp import protocol  # noqa: E402
from fl_studio_mcp.connection import get_bridge  # noqa: E402


class FL:
    def __init__(self):
        self.b = get_bridge()

    def call(self, cmd: str, params: dict | None = None):
        return self.b.call(cmd, params or {})

    # --- state
    def ping(self):
        return self.call(protocol.CMD_PING)

    def project_state(self):
        return self.call(protocol.CMD_GET_PROJECT_STATE)

    def channels(self):
        return self.call(protocol.CMD_CHANNEL_LIST)

    def patterns(self):
        return self.call(protocol.CMD_PATTERN_LIST)

    # --- transport
    def set_tempo(self, bpm: float):
        return self.call(protocol.CMD_SET_TEMPO, {"bpm": float(bpm)})

    # --- arrangement
    def new_pattern(self, name: str):
        return self.call(protocol.CMD_ARRANGE_NEW_PATTERN, {"name": name})

    def select_pattern(self, index: int):
        return self.call(protocol.CMD_PATTERN_SELECT, {"pattern": int(index)})

    def select_channel(self, index: int):
        return self.call(protocol.CMD_CHANNEL_SELECT, {"channel": int(index)})

    def ensure_piano_roll(self):
        return self.call(protocol.CMD_ENSURE_PIANO_ROLL)

    def add_marker(self, bar: int, name: str):
        return self.call(protocol.CMD_ARRANGE_ADD_MARKER, {"bar": int(bar), "name": name})

    # --- notes (pyscript bridge; MCP_Apply must be armed once per FL session)
    def write_notes(self, notes: list[dict], mode: str = "replace", channel: int | None = None):
        """notes: [{pitch, time_bars, length_bars, velocity 0-1}]"""
        if channel is not None:
            self.select_channel(channel)
        self.ensure_piano_roll()
        return self.b.apply_notes(notes, mode)

    # --- mixer / channel levels
    def channel_volume(self, index: int, vol: float):
        return self.call(protocol.CMD_CHANNEL_SET_VOLUME, {"channel": int(index), "volume": float(vol)})

    def mixer_volume(self, track: int, vol: float):
        return self.call(protocol.CMD_MIXER_SET_VOLUME, {"track": int(track), "volume": float(vol)})

    def mixer_name(self, track: int, name: str):
        return self.call(protocol.CMD_MIXER_SET_NAME, {"track": int(track), "name": name})

    def route_channel(self, channel: int, track: int):
        return self.call(protocol.CMD_MIXER_SET_ROUTE, {"channel": int(channel), "track": int(track)})


if __name__ == "__main__":
    fl = FL()
    print(fl.ping())
    print(fl.project_state())
