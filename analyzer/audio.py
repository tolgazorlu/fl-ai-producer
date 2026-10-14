"""Audio loading helpers shared by the analyzer modules."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

ANALYSIS_SR = 22050


@dataclass
class Audio:
    path: Path
    sr: int                 # native sample rate
    stereo: np.ndarray      # (n, 2) float32, native sr
    mono: np.ndarray        # (n,) float32 at ANALYSIS_SR
    mono_sr: int = ANALYSIS_SR

    @property
    def duration(self) -> float:
        return self.stereo.shape[0] / self.sr


def load(path: str | Path) -> Audio:
    path = Path(path)
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if y.shape[1] == 1:
        y = np.repeat(y, 2, axis=1)
    mono = y.mean(axis=1)
    if sr != ANALYSIS_SR:
        mono = librosa.resample(mono, orig_sr=sr, target_sr=ANALYSIS_SR)
    return Audio(path=path, sr=sr, stereo=y, mono=mono.astype(np.float32))
