# P00 source-to-target feature matrix

Snapshot checked on 2026-10-29. Source: mutador `7319e19b`; target desktop
main `a43cd4f`. This is a **code inventory**, not a claim of functional
parity. Paths in the source column are relative to `I:/Github/mutador`; target
paths are relative to this repository.

Status vocabulary: **present** means a corresponding desktop mechanism
exists; **different** means behavior/format needs comparison; **missing** means
the named mutador extension was not found in the desktop parameter/menu
inventory; **unknown** needs behavioral or binary verification.

| Area / plan ID | mutador source and IDs | Desktop target and IDs | MIDI CC / storage fields | Status and next check |
| --- | --- | --- | --- | --- |
| Baseline Euclid / P00 | `mainboard/LxrStm32/src/Sequencer/EuklidGenerator.c`; old AVR menu path | `Core/Src/Soundengine/Sequencer/EuklidGenerator.c`, `Core/Src/menu/menu.c`, `Core/Src/buttonHandler.c`; `PAR_EUKLID_LENGTH`, `PAR_EUKLID_STEPS`, `PAR_EUKLID_ROTATION` | Pattern step bits and track length in `.pat` | **Unknown:** official 1.71 fixes Euclid, but source is labelled 1.7 and has no later Euclid commit. Compare identical length/steps/rotation cases with official 1.71 image and current built image. |
| MIDI channels and note recording / P01 | `mainboard/LxrStm32/src/MIDI/MidiParser.c`, `front/LxrAvr/Parameters.h`; `PAR_MIDI_CHAN_PC`, `PAR_MIDI_CHAN_GLOBAL`, `PAR_MIDI_CHAN_1..7` | `Core/Src/Soundengine/MIDI/MidiParser.c`, `Core/Src/Soundengine/MIDI/CortexParser.c`, `Core/Inc/Parameters.h`; global and voice channels/notes already exist, `PAR_MIDI_CHAN_PC` not found | mutador Control/PC CC1..83, voice CC map; desktop has its own MIDI CC map | **Different:** compare channel precedence, Kit note-map, recording and MIDI echo before allocating a Control/PC channel. Existing USB/DIN routing must survive. |
| Step probability and copy / P02 | `front/LxrAvr/Parameters.h`, `mainboard/LxrStm32/src/Sequencer/sequencer.c`, `front/LxrAvr/copyClearTools.c`; `PAR_STEP_PROB`, `PAR_PERF_NOTE_PROB`, `PAR_PERF_NOTE_REPEAT_CHANCE`, `PAR_PERF_RANDOM_VELO` | `Core/Inc/Parameters.h`, `Core/Src/Soundengine/Sequencer/sequencer.c`, `Core/Src/menu/copyClearTools.c`; `PAR_STEP_PROB` already present | mutador Control/PC CC6..9, CC45; desktop `.pat` has per-step data, main-step bitsets and lengths | **Present + missing:** basic probability exists; extra repeat/chance/random-velocity behavior and copy scope require comparison. Do not overwrite step layout blindly. |
| Groove and scale / P03 | `front/LxrAvr/Parameters.h`, `mainboard/LxrStm32/src/Sequencer/sequencer.c`; `PAR_SHUFFLE`, `PAR_GROOVE_SH2..SH4`, `PAR_GLOBAL_SCALE`, `PAR_SHUFFLE_LOAD` | `Core/Inc/Parameters.h`, `Core/Src/Soundengine/Sequencer/sequencer.c`, `Core/Src/Preset/presetManager.c`; `PAR_SHUFFLE`, `seq_patternSet.shuffle[]` | mutador Control/PC CC40..43 and CC80..83; mutador `glo.cfg` extension v6 and Performance/All groove fields; desktop `.pat` stores shuffle byte | **Different + missing:** desktop shuffle exists; four-step groove, global scale and load policy not found. Map old project behavior before new persistent fields. |
| Clock / P04 | `mainboard/LxrStm32/src/Sequencer/clockSync.c`, trigger output/input code, `front/LxrAvr/Parameters.h`; `PAR_CLOCK_OFFSET` | `Core/Src/Soundengine/Sequencer/clockSync.c`, `Core/Src/Soundengine/TriggerOut.c`, `Core/Src/Soundengine/MIDI/CortexParser.c`; `PAR_BPM`, `PAR_PRESCALER_CLOCK_IN`, `PAR_PRESCALER_CLOCK_OUT1` | MIDI realtime Start/Clock/Stop; mutador 2/4/24-PPQ trigger behavior; desktop `cki` 4/24 and `cko` 2/4/8/16/24/48 | **Different:** preserve desktop `EXT` analogue and `MID` MIDI modes. Check physical jack mapping on desktop; mutador's CO1/CO2 mapping is for different hardware. |
| Performance MIDI delay / P05 | `front/LxrAvr/Parameters.h`, `mainboard/LxrStm32/src/MIDI/MidiParser.c` and sequencer; `PAR_PERF_DELAY_MODE`, `PAR_PERF_REPEAT_COUNT`, `PAR_PERF_REPEAT_SYNC`, `PAR_PERF_BOUNCE`, `PAR_PERF_BOUNCE_EXP`, `PAR_PERF_DELAY_PITCH` | `Core/Src/Soundengine/MIDI/MidiParser.c`, `Core/Src/Soundengine/Sequencer/sequencer.c`, `Core/Inc/Parameters.h`; named mutador performance-delay IDs not found. Desktop FX delay is a separate audio effect (`PAR_FX_DELAY_TYPE`). | mutador Control/PC CC10..16, CC60..66; Performance/All stored globals | **Missing:** design MIDI-event queue and timing independently of desktop audio FX delay. Record mono/poly capacity and file-format impact. |
| Pattern/Performance loading / P06 | `front/LxrAvr/Preset/presetManager.c`, `front/LxrAvr/Parameters.h`; `PAR_PATTERN_LINK_SAVE`, `PAR_LOAD_KIT` | `Core/Src/Preset/presetManager.c`, `Core/Src/menu/menu.c`, `Core/Src/Soundengine/Sequencer/sequencer.c`; existing kit/pattern/project/All load paths | mutador `.pat`, `.prf`, `.all`, `FILE_VERSION 12`, `PATTERN_STATE_LEN 6` (`L6S`); desktop `.snd`, `.pat`, `.all`, `.prj`, `.sng`, `FILE_VERSION 2` | **Different:** desktop project format and 64-pattern RAM differ from mutador's 8-pattern/128-step layout. Do not copy serialized blocks or version numbers. Design versioned migration and old-file round trip. |
| Performance controls, velocity and LFO / P07 | `front/LxrAvr/Parameters.h`, `mainboard/LxrStm32/src/MIDI/MidiParser.c`, DSP/LFO files; `PAR_GLOBAL_PITCH`, `PAR_GLOBAL_DECAY`, `PAR_PERF_VELO_*`, `PAR_PITCH_BEND_RANGE` | `Core/Inc/Parameters.h`, `Core/Src/Soundengine/MIDI/ParameterArray.c`, `Core/Src/Soundengine/DSPAudio/`, `Core/Inc/menu/menuPages.h`; voice LFO and velocity modulation already exist | mutador Control/PC CC27..29, CC44..52; per-voice CC78..81 and pitch bend; Kit/Morph/All fields may change | **Different + missing:** compare modulation order and neutral values; preserve existing voice parameter indices and old kit loading. |
| Master FX / P08 | `front/LxrAvr/Parameters.h`, DSP mixer/filter source; `PAR_MASTER_FILTER`, `PAR_MASTER_FILTER_RESO`, `PAR_MASTER_FILTER_DRIVE`, `PAR_FX_SEND_MODE` | `Core/Inc/Parameters.h`, `Core/Inc/menu/menuPages.h`, `Core/Src/Soundengine/DSPAudio/`; `PAR_FX_TYPE`, `PAR_FX_ROUTING`, `PAR_FX_DRY_WET` already exist | mutador Control/PC CC30..39; `fxm` st2/lr2; All and Settings fields | **Present + missing:** desktop has FX bus/drive/ring/compressor/delay; compare routing before adding master LP/HP and bipolar sends. |
| New voice synthesis / P09 | `front/LxrAvr/Parameters.h`, DSP voice files; `PAR_MEMBRANE1..3`, `PAR_SNARE_MEMBRANE`, `PAR_SNARE_NOISE_*`, `PAR_SNARE_LAYER_*` | `Core/Inc/Parameters.h`, `Core/Src/Soundengine/DSPAudio/`, `Core/Src/Preset/presetManager.c`; these named extension IDs not found | mutador per-voice CC111 and Snare CC112..118; mutador extended Kit/Morph/Performance/All blocks | **Missing:** one voice feature per branch or small related batch; explicitly version desktop kit blocks and test legacy kits. |

## Storage and ABI warning

- The symbolic `PAR_*` names above identify **roles**, not compatible numeric
  positions. The two enums diverge after their original sound parameter
  block. Allocate desktop IDs only after inspecting all read/write paths.
- mutador uses an AVR front panel, STM32F4 mainboard, 8 patterns, 128 step
  slots and `FILE_VERSION 12` for its Performance/All format. Desktop uses
  STM32F765, 64 patterns, 64 steps and `FILE_VERSION 2` in
  `Core/Src/Preset/presetManager.c`. Version numbers are not directly
  comparable.
- Desktop pattern data includes `seq_subStepPattern`, `seq_stepTiming`,
  `seq_mainSteps`, shuffle, track lengths and linked kit number. Any port
  touching step timing, scale or saved pattern state must define migration.
- Treat `I:/Github/mutador/manual/chapters/07_midi.md` as a candidate
  specification; verify each mapped CC in its parser and
  then choose a noncolliding desktop mapping.

## Next evidence needed

1. Successful untouched desktop image with a supported compiler.
2. Same Euclid input cases run on official 1.71 and the built desktop image.
3. Hardware smoke test for audio, save/load, DIN/USB MIDI and analogue sync.
4. For P01, a checked numeric CC table and channel-precedence test before
   source changes.
