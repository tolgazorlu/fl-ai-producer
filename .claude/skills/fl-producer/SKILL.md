---
name: fl-producer
description: Operate the fl-ai-producer pipeline - analyze a reference track, drive FL Studio through the fl-studio MCP bridge, write notes/patterns/mixer settings, and iterate on a song by prompt. Use whenever the user asks to make, analyze, recreate or edit music in FL Studio.
---

# fl-producer

## Session start (always)
1. `fl_ping`. If `alive: false`: the daemon may be down. Start it in the background:
   `.venv-flmcp\Scripts\python.exe -m fl_studio_mcp.daemon` (transport tcp), then ping again.
   If still dead, FL Studio is closed or MIDI Settings changed; see docs/KURULUM-TR.md.
2. Before the first note write of a session, remind the user once: open the Piano roll and run
   **Scripting > MCP_Apply**. Then `fl_write_piano_roll_notes` works.
3. `fl_get_project_state` + `fl_get_channel_state` to learn what is loaded. The scripting API
   cannot load plugins: if a needed instrument is missing, ask the user to open a template from
   `templates/` or add the plugin manually (tell them exactly which channel to add).

## Analyze a reference
`.venv\Scripts\python.exe -m analyzer.cli run <file|url> --out analysis/<name>`
Produces analysis.json (tempo, key, chords per bar, sections, loudness, spectrum), stems/, midi/, report.md.
Read report.md first, analysis.json for details. Treat transcribed MIDI as a sketch: clean it up
musically (snap to the key, remove ghost notes, simplify) before writing it to FL.

## Write music into FL
- Tempo: `fl_set_tempo`.
- New pattern per part: `fl_arrange_new_pattern(name)` then `fl_arrange_select_channel` to point the
  Piano roll at the right channel, then `fl_write_piano_roll_notes(notes, mode="replace")`.
  Notes use `time_bars`/`length_bars` (1 bar = 4 beats); pitch 60 = C5 in FL.
- Drums: prefer step-grid patterns on sampler channels (kick/clap/hat) via the channel tools, or the drums
  pattern in the Piano roll on an FPC channel.
- Mixer: `fl_set_mixer_volume/pan`, `fl_set_route`, `fl_apply_eq_intent`, `fl_apply_reverb_intent`,
  `fl_apply_compression_intent`, `fl_diagnose_mix`, `fl_reference_match`.
- Always `fl_take_snapshot` before a batch of changes; `fl_rollback_last_change` if the user dislikes it.

## Genre knowledge
Genre skills live in `.claude/skills/<genre>/SKILL.md` (ambient-edm first). Load the matching one before
composing. Default when unknown: 4/4, 8-bar phrases, intro/build/drop/break/drop/outro.

## Limits to state plainly
No plugin loading, no playlist clip placement, no audio render from the API. Rendering = the user presses
Export (File > Export > WAV); then `compare/` scores it against the reference.
