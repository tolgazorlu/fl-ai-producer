# AI Music Producer for FL Studio — Research & Plan

Date: 2026-10-14 · Machine: Windows 11, FL Studio 2026 (26.1.6), Vital VST3, RTX 5060 Ti 16 GB, Node 24, ffmpeg 9, uv 0.12 (no system Python yet)

---

## 1. Short answer: are you right?

**Mostly true, with three honest corrections.**

| Your idea | Verdict | Reality |
|---|---|---|
| Claude can control FL Studio and write music into it | **True** | Several open-source MCP servers already do this (notes, patterns, mixer, plugin parameters, transport). FL Studio 2026 also has an internal AI tool channel (Gopher) that can add channels and effects. |
| Claude can analyze an MP3 and get tempo, key, chords, structure, notes | **True (approximate)** | Tempo/key/structure/loudness/spectrum: reliable. Notes: good for bass, lead, pads and chords after stem separation; imperfect for dense polyphony. Ambient EDM is one of the *easiest* genres for this (slow, sparse, sustained sounds). |
| Claude can detect **which plugin or sample pack** was used | **False** | No tool can do this from a mixed MP3. There is no fingerprint of "Serum preset X" in audio. What *is* possible: describe each sound's character, find the **closest matching sound in your own library** (Vital presets, FL stock, Splice samples) via audio-embedding search, and approximate synth settings by sound-matching. |
| Zero learning, fully automatic | **~90% true** | You will still: install things once, press one key in FL to apply notes each session (FL's scripting rules), and press Export when you want a file. Everything creative, technical, mixing and mastering can be driven by prompts. |

**Bottom line:** build it as "reverse-engineer → recreate in the same *spirit* with your own sounds → refine by prompt", not "exact clone". That is what any human producer does when remaking a track.

---

## 2. What exists (research results)

### 2.1 FL Studio control from Claude

| Project | What it does | Notes |
|---|---|---|
| [rosasynthesiz/flstudio-mcp](https://github.com/rosasynthesiz/flstudio-mcp) | **67 tools**: notes/chords/scales, multi-pattern arrangement, mixer, plugin params, preset suggestions, "Mix Doctor", reference matching, tempo/key estimation, melody→MIDI | MIT, Windows, needs FL 2025+ (you have 2026). **Primary candidate.** Communicates via loopMIDI virtual ports + a daemon; notes are applied by a piano-roll script (`MCP_Apply`) you run once per session. |
| [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) | Transport, mixer, channels, plugin params, piano roll notes | MIT, 211 stars, simpler, no pattern management. Good fallback. |
| [szichedelic/fl-studio-mcp](https://github.com/szichedelic/fl-studio-mcp), [calvinw/fl-studio-mcp](https://github.com/calvinw/fl-studio-mcp) | Smaller variants (Node.js / macOS-focused) | Reference only. |
| [sadoway7/flaik](https://github.com/sadoway7/flaik) | Hijacks FL Studio 2026's built-in **Gopher** AI panel via Chrome DevTools; exposes FL's internal 44 tools incl. **add/remove channels, add/remove mixer effects**, piano-roll scripts | Proof-of-concept, 8 commits, "gray area" with Image-Line ToS. Interesting because it is the only route that can **add plugins** programmatically. Optional/experimental. |
| [Official MIDI Scripting API](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/midi_scripting.htm) and [Piano Roll Scripting API](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/pianoroll_scripting_api.htm) | What all of the above are built on | **Cannot**: add channels, load plugins/presets, place clips in playlist, render audio. **Can**: notes, patterns (clone/rename), mixer levels/routing, plugin params of loaded plugins, transport, save. No sockets/threads inside FL's Python. |

**Key design consequence:** since scripts can't load plugins, we pre-build **template .flp projects** (e.g. 8× Vital, FLEX, Sytrus, Harmor, FPC, Fruity Reverb 2, Fruity Delay 3, Maximus, etc. already loaded and routed). Claude then opens a template and fills it. This is how every serious FL automation project works around the limit.

### 2.2 FL project files offline (no FL running)

| Project | Status |
|---|---|
| [flpkit](https://github.com/clarkipeng/flpkit) (PyPI 0.8.1, Sept 2026, MIT, Py ≥3.11) | Reads/writes **tempo, notes, channel levels, playlist clips, automation points, mixer-effect references** without FL. Verified on FL 2026. Plugin state is opaque bytes. **Good for batch note writing and playlist placement.** |
| [Meowrium/PyFLP](https://github.com/Meowrium/PyFLP) | Fork of PyFLP fixed for FL 24/25/26 parsing. Best for *reading/inspecting* projects. Upstream PyFLP is dead since 2023. |

### 2.3 Audio analysis / reverse engineering

| Task | Tool | Quality |
|---|---|---|
| Download reference | yt-dlp + ffmpeg (installed) | — |
| Tempo, beats, key, chroma, structure | librosa, madmom, Essentia (AGPL) | Reliable |
| Stem separation (vocals/drums/bass/other, or 6 stems w/ piano/guitar) | Demucs (htdemucs), BS-RoFormer | Very good; GPU helps |
| Audio → MIDI (polyphonic) | [Basic Pitch](https://github.com/spotify/basic-pitch) per stem; NeuralNote | Good on clean stems; needs cleanup |
| Chord progression | Essentia / chroma template matching / madmom | Good for ambient (slow harmonic rhythm) |
| Drum hits → MIDI | onset detection + drum classifier on the Demucs drum stem | Decent for 4/4 EDM |
| Loudness / spectrum / stereo / dynamics vs. reference | [mixref](https://pypi.org/project/mixref/), pyloudnorm, custom | Reliable |
| Auto-mastering to match reference | [Matchering 2](https://github.com/sergree/matchering) | Good, open source |
| Find similar sounds in your library | CLAP embeddings ([shira-audio](https://pypi.org/project/shira-audio/) or own code with LAION-CLAP + FAISS) | Good for "closest preset/sample" |
| Synth preset from audio | Research only ([InverSynth II](https://github.com/inversynth/InverSynth2)); commercial MicroMusic Replicate (Vital/Serum). Practical DIY: render all your Vital presets via [vita](https://pypi.org/project/vita/) Python bindings or [DawDreamer](https://github.com/DBraun/DawDreamer), embed with CLAP, nearest-neighbour + parameter tweaks | Approximate |

### 2.4 Direct AI audio generation (complementary track)

| Model | Fit |
|---|---|
| [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) | MIT, runs on your 16 GB GPU (2B turbo/sft + 1.7B LM), text→music, **reference-audio**, cover/repaint, **stem output**, BPM/key control, REST API, LoRA training on ~8 songs. Excellent for ambient textures, drafts, and generating custom samples/pads to drop into FL. |
| Stable Audio Open / MusicGen | Short loops & sound-design samples (older, non-commercial licences) |

### 2.5 Existing Claude skills for music
[glincker/ableton-skills](https://github.com/glincker/ableton-skills) (Ableton) is the closest model for what we'll build for FL: skills on top of an MCP server that encode *producer knowledge* (voice leading, arrangement, mix diagnostics). Nothing equivalent exists for FL Studio yet, so we will create it.

---

## 3. Your machine (checked)

- FL Studio 2026 (26.1.6) with full stock plugin set: 3x Osc, FLEX, Harmor, Harmless, Sytrus, Sakura, Morphine, Ogun, Toxic Biohazard, Kepler, Minisynth, FPC, DirectWave, Slicex, Patcher, 90 effects.
- Vital.vst3 + 75 Vital presets in 12 packs (Factory, Mr Bill, Billain, Halcyon Future Riddim, …).
- Splice app installed but **0 samples downloaded** (Documents\Splice\Samples is empty).
- GPU: RTX 5060 Ti 16 GB → Demucs, Basic Pitch, CLAP and ACE-Step all run locally.
- Missing: Python (will install 3.11/3.12 via `uv`), loopMIDI (virtual MIDI, needed by the MCP server), PyTorch.
- Existing FL projects: edm_1, Project_1..3 (useful to test the file readers).

---

## 4. Architecture

```
                 +--------------------------------------------------+
                 |  Claude Code  +  genre SKILLS (ambient-edm, ...) |
                 +-------+---------------------------+--------------+
                         |                           |
            +------------v-----------+   +-----------v-----------------+
            | 1. ANALYZER (Python)   |   | 3. FL BRIDGE                |
            | mp3/YouTube ->         |   |  a) flstudio-mcp (live FL)  |
            |  analysis.json         |   |  b) flpkit (offline .flp)   |
            |  stems/*.wav           |   |  c) template .flp projects  |
            |  midi/*.mid            |   +-----------^-----------------+
            |  sounds.json           |               |
            +------------+-----------+               |
                         |                           |
            +------------v---------------------------+-------+
            | 2. COMPOSER (Claude + music libs)              |
            | analysis.json -> blueprint.json                |
            | (sections, chords, melodies, bass, drums,      |
            |  sound choices, mixer plan, automation)        |
            +------------+-----------------------------------+
                         |
            +------------v-----------+   +--------------------------+
            | 4. LISTEN & COMPARE    |<--| FL export (one key) or   |
            | mixref / matchering /  |   | DawDreamer render (Vital)|
            | CLAP similarity score  |   +--------------------------+
            +------------------------+
                 loop: "make the pad warmer", "more sidechain", ...
```

**Why a `blueprint.json` in the middle:** it is the editable "source of truth" of the song. Prompts change the blueprint; the bridge re-applies it. Everything stays reproducible and version-controlled.

---

## 5. Roadmap (phases)

### Phase 0 — Environment (half a day)
1. `uv python install 3.11` and `3.12`; one venv per tool group (analysis stack on 3.11 for Basic Pitch, ACE-Step on 3.12).
2. Install loopMIDI; create ports `FLStudioMCP RX` / `FLStudioMCP TX`.
3. Install [rosasynthesiz/flstudio-mcp](https://github.com/rosasynthesiz/flstudio-mcp); register with Claude Code; `fl_ping` works.
4. Install PyTorch (CUDA), demucs, basic-pitch, librosa, madmom/essentia, laion-clap, flpkit, Meowrium/PyFLP, matchering, mixref, yt-dlp.

### Phase 1 — Reverse-engineering tool `analyze` (2–3 days)
CLI: `analyze <mp3|url> --out analysis/<name>/`
Produces:
- `analysis.json`: tempo, beat grid, key/scale, chord progression per bar, sections (intro/build/drop/break/outro with bar numbers), loudness (LUFS), dynamic range, spectral balance, stereo width, energy curve.
- `stems/`: vocals, drums, bass, other (+ optional 6-stem).
- `midi/`: bass.mid, chords.mid, lead.mid, drums.mid (quantized to the grid, cleaned).
- `sounds.json`: per stem/section a plain-language timbre description (bright/dark, attack/release, width, FX) + **top-5 closest sounds from your library** (Vital presets, FL stock presets, any samples) by CLAP similarity.
- `report.md`: human-readable summary.
First test target: **Hyzteria – Underwater** (your reference link).

### Phase 2 — FL Studio templates + bridge validation (1–2 days)
- Build `templates/ambient-edm.flp`: channels pre-loaded (Vital ×6 named Pad/Lead/Bass/Pluck/Texture/Sub, FLEX, FPC or sample channels for kick/clap/hat, Sytrus), each routed to its own mixer insert with reverb/delay/EQ/compressor/sidechain (Fruity Peak Controller or Fruity Limiter) already in slots, Maximus on master.
- Verify from Claude: set tempo, write notes into patterns, set plugin parameters, mixer levels, run `MCP_Apply`.
- Verify flpkit can write notes + playlist clips to the template offline (fallback path, and faster for whole-song arrangement).
- Decide (experimentally) whether to use the FLaiK/Gopher channel for adding channels/effects on the fly.

### Phase 3 — Recreate pipeline `recreate` (3–5 days)
`recreate analysis/<name>/ --template ambient-edm --out projects/<name>.flp`
1. Claude turns `analysis.json` into `blueprint.json` (sections, chord voicings, melodic lines, bass, drum patterns, sound assignments, mixer plan, automation like filter sweeps and sidechain depth).
2. Bridge applies: tempo, patterns + notes, playlist arrangement, chosen presets (pre-loaded in template or loaded by a one-time manual step Claude asks you for), plugin parameters, mixer settings.
3. You press Export (or we automate the keystroke); `compare` scores the render vs. the reference (loudness, spectrum per band, width, CLAP similarity per section) and Claude proposes the next adjustments.

### Phase 4 — Prompt-driven editing + genre skills (ongoing)
- `.claude/skills/ambient-edm/SKILL.md`: tempo 100–128, chord vocabularies (minor 7/9, sus2, add9), progression templates, Vital sound-design recipes (pad: 2 detuned saws + unison 6, lowpass 2–4 kHz, 1.5 s attack, 3 s release, long hall reverb; pluck; sub), arrangement template (8-bar intro / 16 build / 16 drop …), mixing checklist (sidechain, high-pass everything but sub, reverb sends), mastering target (−9 to −8 LUFS).
- Later skills: melodic techno, lo-fi, progressive house, drum & bass, synthwave, cinematic ambient, each with the same structure.
- Editing commands become natural language: "make the drop hit harder", "replace the lead with something glassier", "halve the tempo feel in the break".

### Phase 5 — Optional generation track
- Run ACE-Step 1.5 locally: text + reference-audio generation of full ambient EDM drafts and custom samples (pads, textures, risers) that get imported into FL as audio clips. LoRA-train on a handful of your favourite tracks for a "your taste" model.

---

## 6. Risks & decisions

- **Exact clone is impossible and legally a derivative work.** Goal = same style/mood/structure with your sounds. Fine for learning and original music.
- **FL scripting limits** (no plugin loading, no render) are worked around with templates, flpkit, and a one-key export. Accept that or try the Gopher/FLaiK route (experimental, ToS gray).
- **Transcription accuracy** varies; Claude will clean and "musicalize" MIDI rather than trust it blindly.
- **Licences:** Essentia is AGPL (fine for personal use); ACE-Step MIT; Vital GPL (vita bindings); MusicGen non-commercial.
- **Splice library is empty.** Download some ambient/EDM packs if you want sample-based matching; otherwise Vital + FL stock + ACE-Step-generated samples cover everything.

---

## 7. Suggested repo layout

```
fl-ai-producer/
  README.md
  pyproject.toml            # uv-managed
  analyzer/                 # Phase 1 (python)
  composer/                 # blueprint schema + music-theory helpers
  bridge/                   # flstudio-mcp wrapper, flpkit writer, templates/
  compare/                  # mixref/matchering/CLAP scoring
  templates/*.flp
  library-index/            # CLAP embeddings of your Vital/FL/Splice sounds
  .claude/skills/<genre>/SKILL.md
  analysis/<song>/ , projects/<song>.flp
```

---

## 8. First milestone (proposed next session)

1. Environment: Python via uv, loopMIDI, flstudio-mcp, `fl_ping` OK.
2. Analyze **Hyzteria – Underwater**: tempo, key, sections, stems, MIDI, sound descriptions.
3. Build the ambient-edm template .flp.
4. Have Claude write an 8-bar loop (chords + bass + drums) into FL Studio from the analysis. Listen. Iterate by prompt.

---

## Sources
- FL MCP servers: [rosasynthesiz/flstudio-mcp](https://github.com/rosasynthesiz/flstudio-mcp), [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp), [szichedelic/fl-studio-mcp](https://github.com/szichedelic/fl-studio-mcp), [calvinw/fl-studio-mcp](https://github.com/calvinw/fl-studio-mcp), [calvinw/MacFLStudioMCP](https://github.com/calvinw/MacFLStudioMCP)
- FL 2026 Gopher takeover: [FLaiK forum thread](https://forum.image-line.com/viewtopic.php?p=2075724), [sadoway7/flaik](https://github.com/sadoway7/flaik), [MCP feature request](https://forum.image-line.com/viewtopic.php?p=2065698)
- Official APIs: [MIDI scripting](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/midi_scripting.htm), [Piano roll scripting](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/pianoroll_scripting_api.htm), [FL 2026.1.7 notes](https://forum.image-line.com/viewtopic.php?p=2076291)
- FLP files: [flpkit (PyPI)](https://pypi.org/project/flpkit/), [Meowrium/PyFLP](https://github.com/Meowrium/PyFLP), [PyFLP limitations](https://pyflp.readthedocs.io/en/latest/limitations.html)
- Transcription/separation: [Best audio-to-MIDI 2026](https://futureproofmusicschool.com/blog/best-audio-to-midi-converters), [arXiv 2412.06703](https://arxiv.org/pdf/2412.06703), [Essentia](https://essentia.upf.edu/), [madmom](https://best-of-web.builder.io/library/CPJKU/madmom)
- Reference comparison/mastering: [Matchering](https://github.com/sergree/matchering), [mixref](https://pypi.org/project/mixref/)
- Sound matching: [InverSynth](https://arxiv.org/pdf/1812.06349), [InverSynth II](https://archives.ismir.net/ismir2023/paper/000076.pdf), [Neural proxies (2025)](https://www.arxiv.org/pdf/2509.07635), [MicroMusic Replicate](https://www.kvraudio.com/product/replicate-by-micromusic), [vita (Vital bindings)](https://pypi.org/project/vita/), [DawDreamer](https://github.com/DBraun/DawDreamer), [shira-audio (CLAP search)](https://pypi.org/project/shira-audio/)
- Generation: [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5), [ACE-Step 1.5 paper](https://arxiv.org/pdf/2602.00744), [open music models 2026](https://www.it-jim.com/blog/best-open-source-ai-music-generator/), [YuE2](https://www.mindstudio.ai/blog/yue2-open-music-generation-model)
- Skills model: [glincker/ableton-skills](https://github.com/glincker/ableton-skills)
