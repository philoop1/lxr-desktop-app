# P01 MIDI comparison: mutador and LXR V2 desktop

Code audit, 2026-10-29. Source snapshots: mutador `7319e19b`, desktop main
`a43cd4f`. This is the original baseline comparison. The mutador manual is
used as a map, but conclusions below were checked against the parsers.

Current fork status and executable channel/CC results are in the
[2026-10-29 channel audit](P01_CHANNEL_AUDIT.md). Pch/Morph CC2 now exist;
the audit also found and corrected a legacy voice-channel index error.

## Main behavioral differences

| Behavior | Desktop baseline | mutador | P01 decision |
| --- | --- | --- | --- |
| Channels | Seven voice channels plus one global channel in `midi_MidiChannels[8]`; no dedicated Control/PC channel. | Same eight channels plus `midi_ControlChannel`, set by `PAR_MIDI_CHAN_PC`; menu default is channel 16. | Add a separate configurable Control/PC channel without changing the meaning of existing voice/global channels. Decide precedence if channels are equal. |
| Global Note On | Plays the currently selected voice; that voice's `PAR_MIDI_NOTE*` can reject a note or map it to default pitch. | Searches all seven Kit-note assignments, triggers every matching track at default pitch; if none match, `ANY` can play the selected voice chromatically. | Port drum-map behavior behind an explicit choice or document the breaking change; verify overlap with existing projects. |
| Voice-channel Note On | Checks the voice's Kit note selector before playing. Incoming notes with `do_rec=1` can record and are echoed to the voice channel. | Voice channel identifies destination; every note plays chromatically and can be recorded, with no echo to its source channel. | Implement chromatic, non-echo voice path separately from Global drum-map path. Test shared-channel precedence. |
| Note Off | Parsed, but voice Note Off calls are commented out. | Also parsed without voice Note Off handling. | Existing gate behavior remains; P01 should not claim true held-note release. |
| Program Change | On global channel with `P` receive filter; passes program number to `seq_setNextPattern`, which rejects values outside 0..63. | On global channel with `P`; masks to 0..7 for eight patterns. | Keep desktop 0..63; never copy mutador's `& 0x07`. |
| Pitch bend | Parser recognizes status, but `parseMidiMessage` has TODO and does not apply it. | Global/Control bend applies master pitch; voice-channel bend applies locally; range adjustable 0..48 semitones. | Port after channel routing; define center, range and reset on channel/kit changes. |
| Per-voice CC | Fixed numeric CCs target specific voices through `midiParser_cc2voiceNr()`; allowed on assigned voice or global channel. | Adds a compact channel-aware map, e.g. CC7 volume, CC10 pan, CC14 coarse, CC16 cutoff, CC76..83 LFO. | Apply compact map only to dedicated voice channels. Keep legacy desktop CC map on global channel until explicit migration. |
| Performance CC | No separate channel; existing CC numbers control voice/synth parameters. | Dedicated Control/PC CC1..83, plus CC125 and pitch bend. Some performance CCs also accepted on global channel. | Never feed these CCs into the legacy handler on the same channel without a precedence rule. Split the contract into small stages. |
| MIDI routing | `off`, `U2M`, `M2M`, `A2M`, `M2U`, `M2A` in `midiParser_setRouting()`. | Same six modes and port directions. | Keep desktop implementation; regression test DIN↔USB forwarding. |
| Filters and sync | Separate TX/RX bitmaps for N, R, C, P; MIDI Clock/Start/Continue/Stop handled when external sync and R are enabled. Desktop `bpm=0` is analogue `EXT`, `bpm=1` MIDI `MID`. | Same filter classes; adds timestamped realtime handling, predictive start and other clock work. | Preserve desktop EXT/MID settings; defer clock-engine changes to P04. |

## Numeric CC collision examples

MIDI CC numbers are shared across channels. mutador avoids most clashes by
using a **separate Control/PC channel**. The desktop parser already assigns
many of the same numbers to synth parameters; adding a mutador handler on
the existing global channel would change old controller mappings.

| CC | Desktop legacy meaning (`MidiMessages.h`) | mutador Control/PC meaning | Safe interpretation |
| ---: | --- | --- | --- |
| 1 | Mod wheel | Global sample-rate reduction | Only on the new Control/PC channel |
| 2 | Drum 1 oscillator waveform | Morph amount | Only on Control/PC; voice channel retains compact-map meaning separately |
| 6 | NRPN data entry coarse | Chance Step Repeat | Keep NRPN on legacy channels; intercept on Control/PC |
| 7 | Cymbal waveform 1 | Step Chance | Voice compact map also uses CC7 for voice volume; channel precedence is essential |
| 10 | Voice 1 fine tune | Step repeat amount | Voice compact map uses CC10 for pan; three meanings require strict channel routing |
| 11..16 | Voice fine/coarse tuning CCs | Delay scale/repeats/bounce/pitch/poly mode | Delay CCs are P05, after the new channel contract |
| 20..26 | Voice tuning/waveform CCs | Six Voice VCAs and Master VCA | Control channel only |
| 27..29 | Synth waveform/noise/mix CCs | Global pitch/decay/filter | Control channel only |
| 30..39 | FM/filter CCs | Voice and Master FX sends, Master filter | P08 controls, but reserve their Control-channel mapping in P01 |
| 40..52 | Filter, resonance and envelope CCs | Groove, probability and velocity destinations | P03/P07 controls; reserve Control-channel mapping |
| 60..66 | Envelopes and slopes | MIDI-delay voice toggles | P05 controls; reserve Control-channel mapping |
| 71..78 | Pitch/volume/LFO CCs | Voice mute and mute-state toggle | Control channel only; per-voice CC78 remains LFO bias |
| 80..83 | Pitch slopes/FM CCs | Global scale selection | Control channel only; per-voice compact CC80/81 remain LFO selectors |
| 125 | LFO amount | Performance step repeat | Control/global special handling needs explicit precedence |

The table lists **collision risks**, not proposed changes to legacy CC
numbers. It does not replace a full 0..127 table; before implementation,
generate numeric tests from both `MidiMessages.h` enums and parser branches.

## Code and persistent-data touch points

| Concern | mutador source | Desktop target |
| --- | --- | --- |
| Channel and note parser | `mainboard/LxrStm32/src/MIDI/MidiParser.c` | `Core/Src/Soundengine/MIDI/MidiParser.c` |
| MIDI CC enum and internal front-panel commands | `mainboard/LxrStm32/src/MIDI/MidiMessages.h`, `front/LxrAvr/frontPanelParser.h` | `Core/Inc/Soundengine/MIDI/MidiMessages.h`, `Core/Src/Soundengine/MIDI/CortexParser.c` |
| Menu parameters and settings | `front/LxrAvr/Parameters.h`, `front/LxrAvr/Menu/menu.c`, `front/LxrAvr/Menu/menuPages.h` | `Core/Inc/Parameters.h`, `Core/Src/menu/menu.c`, `Core/Inc/menu/menuPages.h` |
| Saved globals | `front/LxrAvr/Preset/presetManager.c`: settings extension version 6 includes new channel/control data | `Core/Src/Preset/presetManager.c`: `glo.cfg` stores a contiguous global parameter range; current file version 2 is for different preset files |
| Recording/echo and 64-pattern selection | `mainboard/LxrStm32/src/Sequencer/sequencer.c` (8 patterns) | `Core/Src/Soundengine/Sequencer/sequencer.c` (64 patterns) |

Adding `PAR_MIDI_CHAN_PC` in the middle of the desktop enum would shift
existing saved/global parameter positions. Reserve a new ID deliberately,
provide an old-file default and check `glo.cfg`, project and All loading.
Do not transplant mutador's AVR→STM32 front-panel command number without
checking the desktop command table.

## Proposed P01 implementation slices

1. **Channel contract:** add Control/PC setting with a default and a saved
   migration path. Test equal Control/Global/Voice channel cases and filter
   gates before exposing any new CC behavior.
2. **Note routing:** add Global Kit-note drum map and dedicated Voice
   chromatic/no-echo recording. Keep desktop 64-pattern Program Change.
   Test muted tracks, duplicate Kit notes, `ANY`, zero-velocity Note On and
   record mode.
3. **Compact Voice CC map:** translate only on dedicated voice channels;
   retain desktop legacy map on Global. Verify all 7 tracks including the
   open/closed hi-hat relationship and the existing front-panel feedback.
4. **Core Control CC and bend:** implement a small useful subset (Voice VCA,
   Master VCA, morph, pitch bend) with documented priority. Leave delay,
   groove, master filter and scale CCs for P03/P05/P07/P08; reserve numbers
   now so they do not collide later.

Each slice should have parser-level checks and an on-device DIN+USB check.
One feature branch may contain slices 1–2 if review remains manageable;
otherwise split. Do not mark P01 done from emulator results alone.
