"""`analyze` CLI: reference track -> analysis.json + stems + MIDI + report.

Usage:
  analyze run <mp3|wav|YouTube URL> --out analysis/<name> [--no-stems] [--no-midi]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich import print as rprint

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def _root():
    """fl-ai-producer analyzer."""


def _json_default(o):
    import numpy as np
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"not serializable: {type(o)}")


def _fetch(url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "reference.wav"
    if target.exists():
        return target
    cmd = [sys.executable, "-m", "yt_dlp", "-q", "-x", "--audio-format", "wav", "--audio-quality", "0",
           "--no-playlist", "-o", str(out_dir / "reference.%(ext)s"), url]
    subprocess.run(cmd, check=True)
    return target


@app.command()
def run(source: str = typer.Argument(..., help="Audio file path or YouTube URL"),
        out: Path = typer.Option(..., "--out", "-o", help="Output folder, e.g. analysis/underwater"),
        stems: bool = typer.Option(True, help="Run Demucs stem separation"),
        midi: bool = typer.Option(True, help="Transcribe stems to MIDI (needs stems)"),
        device: str = typer.Option("cuda", help="Demucs device: cuda or cpu")):
    from .audio import load
    from .features import analyze_features
    from .report import write_report

    t0 = time.time()
    out.mkdir(parents=True, exist_ok=True)
    src = _fetch(source, out) if source.startswith("http") else Path(source)
    rprint(f"[bold]source[/bold] {src}")
    a = load(src)
    rprint("[cyan]features...[/cyan]")
    analysis = {"source": str(src), **analyze_features(a)}
    rprint(f"  tempo {analysis['tempo_bpm']} BPM, key {analysis['key']} {analysis['mode']}, "
           f"{analysis['bar_count']} bars, {len(analysis['sections'])} sections")

    if stems:
        from .stems import separate
        from .sounds import describe_stem
        rprint("[cyan]stems (demucs)...[/cyan]")
        paths = separate(src, out / "stems", device=device)
        analysis["stem_files"] = {k: str(v) for k, v in paths.items()}
        analysis["stems"] = {k: describe_stem(v, analysis["sections"], analysis["bar_starts"]) for k, v in paths.items()}
        if midi:
            from .transcribe import Grid, transcribe_stem, transcribe_drums
            rprint("[cyan]midi (basic-pitch + drum onsets)...[/cyan]")
            grid = Grid(analysis["beat_times"], analysis["tempo_bpm"], analysis["duration_s"])
            mdir = out / "midi"
            analysis["midi"] = {
                "bass": transcribe_stem(paths["bass"], mdir / "bass.mid", grid, monophonic=True,
                                        min_hz=30, max_hz=400, min_note_len_ms=120),
                "other": transcribe_stem(paths["other"], mdir / "other.mid", grid, min_hz=60, max_hz=4000),
                "vocals": transcribe_stem(paths["vocals"], mdir / "vocals.mid", grid, monophonic=True,
                                          min_hz=80, max_hz=1500),
                "drums": transcribe_drums(paths["drums"], mdir / "drums.mid", grid),
            }

    (out / "analysis.json").write_text(json.dumps(analysis, indent=1, default=_json_default), encoding="utf-8")
    write_report(analysis, out / "report.md")
    rprint(f"[green]done[/green] in {time.time() - t0:.0f}s -> {out / 'analysis.json'}, {out / 'report.md'}")


if __name__ == "__main__":
    app()
