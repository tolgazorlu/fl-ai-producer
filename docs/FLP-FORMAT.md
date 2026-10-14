# FLP format notes (learned 2026-10-14, FL Studio 2026.1.6)

Sources: PyFLP source (event enum), flpkit source, the 81 .flp files bundled with FL Studio
(Data/Demo projects, Data/Templates), the user's own projects, and byte-level experiments
verified by loading the results in FL Studio 2026.

## Container
```
"FLhd" u32 len=6 | u16 format | u16 channel_count | u16 ppq (96)
"FLdt" u32 len   | events...
event: u8 id; id<64 -> 1 byte; <128 -> 2 bytes; <192 -> 4 bytes; >=192 -> varint length + data
FL 2026 exception: id 0xAC (172) is ALSO varint-length (Meowrium/PyFLP fork, confirmed here).
```
`channel_count` in FLhd must match the number of `64` events or flpkit warns (FL tolerates).

## Event ids used by this project
| id | name | notes |
|---|---|---|
| 64 | ChannelID.New (u16 index) | starts a channel block |
| 21 | ChannelID.Type (u8) | 0 sampler, 2 native, 4 instrument(VST), 5 automation |
| 104 | **channel -> mixer insert** (u16) | not in PyFLP; found by diffing demo channels |
| 196 | ChannelID.SamplePath (utf16) | `%FLStudioFactoryData%`-style macros or absolute paths |
| 203 | PluginID.Name (utf16) | channel/insert slot display name |
| 201 | PluginID.InternalName (utf16) | plugin name, e.g. "Fruity Wrapper", "FPC", "Fruity Reeverb 2" |
| 212 | PluginID.Wrapper | wrapper settings |
| 213 | PluginID.Data | plugin state (see Vital below) |
| 215 | ChannelID.Parameters (168 B) | arp/stretch/etc; NOT routing |
| 219/229/221/218/228 | levels / level adjusts / polyphony / env-LFO / tracking | |
| 65 | PatternID.New (u16) | starts a pattern block |
| 224 | PatternID.Notes | 24-byte note records (flpkit writes them) |
| 193 | PatternID.Name (utf16) | put right after the pattern's 224 event |
| 99 / 241 / 233 / 238 / 239 | arrangement new / name / playlist items / track data / track name | |
| 42 | insert start marker (u8) | mixer section, one per insert, in order 0..N |
| 204 | InsertID.Name | right after 42 |
| 236 | InsertID.Flags | |
| 98 | SlotID.Index (u16) | one per effect slot (10 per insert); slot block precedes it |
| 235 / 154 / 147 | insert routing / input / output | |
| 199 | ProjectID.FLVersion (ascii) | |

## Channel block
`64, 21, 201, 212, 203, 155, 128, 41, [213], 0, 209, 138, 139, 89, 97, 48, 69, 86, 71, 83, 74, 75, 76,
85, 131, 70, 104, 50, 219, 229, 221, 215, 132, 144, 145, 32, 228, 228, 218x5, 143, 20, [196], 170, 51`
Identical sequence across FL 2026 files, so a block can be cloned between files
(bridge/flp_channels.py): change 64 index, 203 name, 196 path; Vital state via 213.

## Playlist item (FL 2026: 88 bytes)
`u32 position(ticks) | u16 pattern_base=20480 | u16 item_index (base+pattern) | u32 length | u16 500-track |
u16 group | 72-byte era tail` - tail bytes 8..16 of the tail = cut window (u32 start, u32 end).
Tail template copied from an FL-2026-authored clip (bridge/build_flp.py).

## Vital state inside 213 (Fruity Wrapper -> VST3)
Wrapper chunks `(u32 id, u64 size, data)`; chunk 53 = VST3 state:
`... LE u32 block_size | 'VstW' hdr(16) | 'CcnK' BE u32 byteSize | 'FBCh' ver 'Vita' fxVer nProg future[128]
BE u32 chunkSize | JSON preset | trailing bytes + 'JUCEPrivateData' block`.
Replace the JSON and add the delta to: event varint size, chunk-53 u64, wrapper u32, CcnK byteSize,
FBCh chunkSize (bridge/flp_vital.py). `.vital` files are the same JSON (author, comments, macro1-4,
preset_name, preset_style, settings{775 params, lfos, modulations, wavetables, sample}, synth_version).

## Vital parameter facts (from mtytel/vital source)
- tempo lists (`kSyncedFrequencyNames`): 0 Freeze, 1 32/1, 2 16/1, 3 8/1, 4 4/1, 5 2/1, 6 1/1, 7 1/2,
  **8 1/4**, 9 1/8, 10 1/16, 11 1/32, 12 1/64 (lfo_N_tempo, delay_tempo, chorus_tempo...)
- `lfo_N_sync_type`: 0 Trigger, **1 Sync** (to host), 2 Envelope, 3 Sustain Env, 4 Loop Point, 5 Loop Hold
- LFO points are `[x0,y0,x1,y1,...]` with y inverted (stored 1 = output 0)
- `filter_1_cutoff` 8..136 semitones (60 = ~262 Hz, default 60); `volume` 0..7399 (sqrt scale)
- `modulations[i]` <-> `modulation_{i+1}_amount/bipolar/bypass/power/stereo`
- sources: lfo_N, env_N, random_N, macro_control_N, velocity, note, mod_wheel, lift, stereo

## Typical effect chains in Image-Line demo projects (3551 slot blocks)
Most used: Parametric EQ 2 (1117), Fruity Limiter (343), Reeverb 2 (323), PanOMatic (192), Maximus (113),
Delay 3 (110), Soundgoodizer (96), Fruity Compressor (88). Master is usually EQ2 > Maximus > Soft Clipper
or a Limiter; pads/leads/hats get EQ2 (+ Reeverb 2 / Delay 3).

## FL Studio script API limits (why files are edited offline)
MIDI/piano-roll scripting cannot add channels, load plugins/presets, place playlist clips or render audio.
`flpianoroll.Note.number` lands one octave above the MIDI number (write MIDI-12).
