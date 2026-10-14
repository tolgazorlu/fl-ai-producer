"""First milestone: an 8-bar 'drop' loop in the spirit of Hyzteria - Underwater.

From analysis/underwater: 129 BPM, A minor, progression F - Dm - Am - C (2 bars each),
four-on-the-floor drums, pulsing bass, wide pad, simple pentatonic lead.
Run:  python -m composer.underwater_loop  -> projects/underwater-loop.blueprint.json
"""
from pathlib import Path

from .blueprint import bass_line, chord_pad, drums_four_on_floor, melody_from_scale, save

PROG = [("Fmaj7", 2), ("Dm7", 2), ("Am7", 2), ("Cmaj7", 2)]

# lead: A minor, degrees 0=A 1=B 2=C 3=D 4=E 5=F 6=G ; 7=A (next octave)
LEAD = [
    (4, 0.0, 0.5), (7, 0.5, 0.25), (6, 0.75, 0.25), (4, 1.0, 0.5), (2, 1.5, 0.5),
    (3, 2.0, 0.5), (4, 2.5, 0.25), (2, 2.75, 0.25), (0, 3.0, 1.0),
    (4, 4.0, 0.5), (7, 4.5, 0.25), (9, 4.75, 0.25), (7, 5.0, 0.5), (6, 5.5, 0.5),
    (4, 6.0, 0.5), (2, 6.5, 0.25), (4, 6.75, 0.25), (0, 7.0, 1.0),
]


def build() -> dict:
    return {
        "name": "underwater-loop",
        "tempo_bpm": 129,
        "key": "A", "mode": "minor",
        "bars": 8,
        "parts": {
            "Chords": {"channel": "Chords", "notes": chord_pad(PROG, octave=4, vel=0.6)},
            "Bass": {"channel": "Bass", "notes": bass_line(PROG, octave=1, pulse=0.125, vel=0.85)},
            "Lead": {"channel": "Lead", "notes": melody_from_scale("A", "minor", LEAD, octave=5, vel=0.7)},
            "Drums": {"channel": "Drums", "notes": drums_four_on_floor(8)},
        },
    }


if __name__ == "__main__":
    bp = build()
    out = Path("projects/underwater-loop.blueprint.json")
    save(bp, out)
    for k, v in bp["parts"].items():
        print(f"{k}: {len(v['notes'])} notes")
    print("->", out)
