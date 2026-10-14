"""Stem separation with Demucs (htdemucs: drums / bass / other / vocals)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

STEMS = ("drums", "bass", "other", "vocals")


def separate(audio_path: Path, out_dir: Path, model: str = "htdemucs", device: str = "cuda") -> dict[str, Path]:
    """Run demucs as a subprocess (same interpreter) and return {stem: wav path}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / model / audio_path.stem
    if all((target / f"{s}.wav").exists() for s in STEMS):
        return {s: target / f"{s}.wav" for s in STEMS}
    cmd = [sys.executable, "-m", "demucs", "-n", model, "-d", device, "-o", str(out_dir), str(audio_path)]
    subprocess.run(cmd, check=True)
    return {s: target / f"{s}.wav" for s in STEMS}
