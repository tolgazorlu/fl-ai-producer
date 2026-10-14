"""Audio -> MIDI for melodic stems (Basic Pitch) and drums (onset + band classification).

All timings are snapped to the *detected* beat grid (beat_times), subdivided into
1/16 notes, instead of a fixed tempo+offset. This absorbs small beat-tracker drift.
"""
from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import pretty_midi
import soundfile as sf


class Grid:
    """1/16-note grid built from detected beat times."""

    def __init__(self, beat_times: list[float], tempo: float, duration: float, div: int = 4):
        b = np.asarray(beat_times, dtype=float)
        step = 60.0 / tempo
        if len(b) < 2:
            b = np.arange(0, duration + step, step)
        # extend grid to cover the whole file
        pre = np.arange(b[0] - step, -step, -step)[::-1]
        post = np.arange(b[-1] + step, duration + step, step)
        b = np.concatenate([pre, b, post])
        self.beats = b
        self.div = div
        pts = []
        for i in range(len(b) - 1):
            pts.extend(b[i] + (b[i + 1] - b[i]) * np.arange(div) / div)
        pts.append(b[-1])
        self.points = np.array(pts)
        self.tempo = tempo

    def snap(self, t: float) -> float:
        i = int(np.argmin(np.abs(self.points - t)))
        return float(self.points[i])

    def step_at(self, t: float) -> float:
        i = int(np.argmin(np.abs(self.points - t)))
        j = min(i + 1, len(self.points) - 1)
        return float(self.points[j] - self.points[i]) or 60.0 / self.tempo / self.div


def transcribe_stem(wav: Path, out_mid: Path, grid: Grid, *, monophonic: bool = False,
                    min_hz: float | None = None, max_hz: float | None = None,
                    onset_threshold: float = 0.5, frame_threshold: float = 0.3,
                    min_note_len_ms: float = 80.0) -> dict:
    """Basic Pitch on one stem, then quantize to the grid and clean up."""
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    _, midi_data, _ = predict(
        str(wav), ICASSP_2022_MODEL_PATH,
        onset_threshold=onset_threshold, frame_threshold=frame_threshold,
        minimum_note_length=min_note_len_ms, minimum_frequency=min_hz, maximum_frequency=max_hz,
        melodia_trick=True,
    )
    pm = pretty_midi.PrettyMIDI(initial_tempo=grid.tempo)
    inst = pretty_midi.Instrument(program=0, name=wav.stem)
    notes = []
    for src in midi_data.instruments:
        for n in src.notes:
            s = grid.snap(n.start)
            e = max(s + grid.step_at(s), grid.snap(n.end))
            notes.append(pretty_midi.Note(velocity=int(n.velocity), pitch=int(n.pitch), start=s, end=e))
    notes.sort(key=lambda n: (n.start, -n.velocity))
    if monophonic:
        mono, last = [], None
        for n in notes:
            if last is not None and abs(n.start - last.start) < 1e-6:
                continue
            if last is not None and n.start < last.end:
                last.end = n.start
            mono.append(n); last = n
        notes = mono
    inst.notes = notes
    pm.instruments.append(inst)
    out_mid.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(out_mid))
    pitches = [n.pitch for n in notes]
    return {"file": str(out_mid), "note_count": len(notes),
            "pitch_range": [int(min(pitches)), int(max(pitches))] if pitches else None}


# GM drum notes
KICK, SNARE, HAT = 36, 38, 42


def transcribe_drums(wav: Path, out_mid: Path, grid: Grid) -> dict:
    """Onsets on the drum stem, each classified by band energy ratio: kick / snare / hat."""
    y, sr = sf.read(str(wav), dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    hop = 256
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop, delta=0.25, wait=3)
    times = librosa.frames_to_time(frames, sr=sr, hop_length=hop)
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    low = (freqs >= 30) & (freqs < 150)
    mid = (freqs >= 150) & (freqs < 3000)
    high = (freqs >= 5000) & (freqs < 12000)
    env_max = env.max() + 1e-9
    pm = pretty_midi.PrettyMIDI(initial_tempo=grid.tempo)
    inst = pretty_midi.Instrument(program=0, is_drum=True, name="drums")
    counts = {"kick": 0, "snare": 0, "hat": 0}
    seen = set()
    for t, f in zip(times, frames):
        f0, f1 = f, min(f + 4, S.shape[1])  # ~25 ms after onset
        e_low, e_mid, e_high = S[low, f0:f1].sum(), S[mid, f0:f1].sum(), S[high, f0:f1].sum()
        tot = e_low + e_mid + e_high + 1e-12
        r_low, r_mid, r_high = e_low / tot, e_mid / tot, e_high / tot
        s = grid.snap(float(t))
        vel = int(np.clip(50 + 77 * env[f] / env_max, 40, 127))
        hits = []
        if r_low > 0.45:
            hits.append(("kick", KICK))
        if r_mid > 0.35 and r_high > 0.05 and r_low < 0.7:
            hits.append(("snare", SNARE))
        if r_high > 0.3:
            hits.append(("hat", HAT))
        if not hits:
            hits.append(("kick", KICK) if r_low >= r_mid else ("hat", HAT))
        for name, note in hits:
            key = (note, round(s, 3))
            if key in seen:
                continue
            seen.add(key)
            counts[name] += 1
            inst.notes.append(pretty_midi.Note(velocity=vel, pitch=note, start=s, end=s + 0.1))
    pm.instruments.append(inst)
    out_mid.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(out_mid))
    return {"file": str(out_mid), "hits": counts}
