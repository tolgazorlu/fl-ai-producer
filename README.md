# fl-ai-producer

Claude Code ile FL Studio icin otomatik muzik uretim hatti.
An AI music-production pipeline for FL Studio driven by Claude Code.

**Hedef / Goal:** bir referans sarkiyi (MP3 / YouTube) analiz et, FL Studio icinde ayni tarzda
yeniden kur, sonra dogal dil komutlariyla duzenle. Plugin veya sample pack tespiti yapilmaz;
"ayni tarz, senin seslerinle" yaklasimi kullanilir.

## Yapi / Layout

```
analyzer/        MP3/YouTube -> analysis.json, stems, MIDI, sound descriptions
composer/        analysis.json -> blueprint.json (sections, chords, melodies, sounds, mix plan)
bridge/          FL Studio bridge: flstudio-mcp (live), flpkit (offline .flp), templates
compare/         render vs reference scoring (loudness, spectrum, CLAP similarity)
templates/       pre-built .flp templates (plugins + effect chains already loaded)
library-index/   CLAP embeddings of local sounds (Vital presets, FL stock, samples)
.claude/skills/  genre skills (ambient-edm, ...)
docs/PLAN.md     research + roadmap
```

## Durum / Status

- [x] Phase 0a: research and plan (docs/PLAN.md)
- [ ] Phase 0b: environment (Python via uv, loopMIDI, flstudio-mcp, torch)
- [ ] Phase 1: `analyze`
- [ ] Phase 2: templates + bridge validation
- [ ] Phase 3: `recreate`
- [ ] Phase 4: genre skills
- [ ] Phase 5: ACE-Step generation (optional)

## Requirements

Windows 11, FL Studio 2025+ (tested with 2026), NVIDIA GPU recommended, [uv](https://docs.astral.sh/uv/), ffmpeg, loopMIDI.
