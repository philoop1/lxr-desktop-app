# P01 channel priority and CC audit

2026-10-29. Desktop source: `9c98ebe` plus the current 0.1.3/0.1.4 changes
and the CC channel-index correction described below. mutador: `7319e19b`.
This is a source and native dispatcher test; DIN/USB hardware testing is open.

Update: this document's note rows describe the audit before the requested
Mutador note import. The current 0.1.6 contract and expanded tests are recorded
in [session 014](sessions/014-mutador-note-routing.md) and the MIDI manual.
0.1.6 includes the CC-index correction and has a successful release build;
the failed approval below remains the historical 0.1.5 attempt.

0.1.7 additionally imports full pitch composition, Pch CC27 and Global/Voice
bend. Pch notes are consumed before RX/Thru, matching Mutador. The current
contract is in [session 016](sessions/016-complete-pitch-and-perf.md).

## Current channel contract

Later additions are recorded in [018](sessions/018-accent-and-midi-delay.md)
and [020](sessions/020-four-point-groove.md): Delay/Accent/CNT and Groove
Pch CC40..43. The generated numeric CC table includes these additions;
the original audit below remains a historical snapshot.

Channels in this document are displayed MIDI channels 1..16. Firmware arrays
store 0..15. `Pch` means performance control; it is not Program Change.

| Incoming message | Channel assignment | Current local result |
| --- | --- | --- |
| CC2 | Pch distinct from Global and every voice | Morph: 0..126 maps to 0..252 in steps of 2; 127 maps to 255. Requires RX C. |
| Other CC | Dedicated Pch | Ignored locally. CC1 srt is not implemented yet. |
| Any CC | Pch overlaps any Global/voice assignment | Pch handler is disabled for the whole channel. Legacy CC rules below apply. |
| Voice-specific legacy CC | Global or that sound voice's assigned channel | Legacy synth parameter; automation is recorded on the active track and front-panel feedback is sent. |
| Voice-specific legacy CC | Another voice's channel | Rejected (after the index correction). |
| Common legacy CC0/1/6/98/99 or master CC115 | Any configured Global/voice channel | Accepted by the legacy dispatcher. CC0/1 have no synth action; CC6/98/99 are NRPN controls. Master CC115 is sample rate. |
| Note On | Global | Selected voice, plus other voices sharing that channel; selected voice is not triggered twice. Kit note selector still applies downstream. |
| Note On | One or several voice channels | All matching voices; no compact voice CC map is present. |
| Note On | Dedicated Pch | No local note route. |
| Note Off / zero-velocity Note On | Global/voice | No voice-release call; unchanged baseline behavior. |
| Program Change | Global | Pattern request; actual sequencer accepts 0..63. Pch alone does not select patterns. |
| Pitch bend | Any channel | Not applied by this dispatcher yet. |

Legacy sound target groups 1..6 correspond to BD1, BD2, BD3, snare,
cymbal and the shared hi-hat sound. The seventh sequencer track (open hat)
has its own note channel, but no separate sound CC target group. Group 0 is
common and group 7 means master/all; they are not voice-array indices.

The current policy preserves legacy CC meanings on overlap. It is not the
same as mutador's broader performance-CC interception on Global/Pch. A future
compact voice map must explicitly choose Global versus Voice priority before
implementation. Current tests describe current behavior, not that future map.

## Confirmed defect and correction

`midiParser_cc2voiceNr()` returns sound groups 1..6. The parser indexed
`midi_MidiChannels[voiceNr]`, whose voices begin at index 0. Consequently
BD1 CC2 used BD2's channel, BD2 CC3 used BD3's channel, through the shared
hi-hat CCs using open-hat track's channel. Global acceptance masked the error.

Changed the voice-specific channel lookup to `midi_MidiChannels[voiceNr - 1u]`.
The target-group table, parameter numbers, Global route and Pch overlap policy
are unchanged. Controllers relying on the old shifted assignment will need
their intended voice channel after installing this correction.

## Numeric conflicts and reservation rules

The complete current 0..127 numeric map is [P01_CC_MAP.csv](P01_CC_MAP.csv),
generated from the actual desktop enum and target-group helper. The symbol
identifies the parameter, not a guarantee that standard General MIDI semantics
apply. In particular CC120/123 are legacy LFO controls, not generic all-sound/
all-notes-off handling in this path.

| CC | Desktop legacy meaning | mutador performance meaning / next candidate |
| ---: | --- | --- |
| 1 | Mod wheel slot; no synth action in this handler | Master sample-rate reduction; mutador inverts input (`127-value`). Not implemented on desktop Pch. |
| 2 | BD1 waveform | Morph, implemented only on a dedicated desktop Pch. |
| 6 | NRPN data entry | Repeat chance; must not intercept on a legacy channel. |
| 7 / 8 / 9 | Cymbal wave / hi-hat wave / BD1 coarse pitch | Step chance / note chance / random velocity. |
| 10 | BD1 fine pitch | Step repeat amount, not delay chance. |
| 11..16 | BD2/BD3/snare tuning | Repeat sync/count, bounce, bounce exponent, delay pitch, delay mode. |
| 27 / 28 / 29 | Hi-hat wave / snare noise frequency / snare mix | Global pitch / decay / filter. |
| 37..43 | Mod oscillator gain / voice filter frequencies | Master filter/resonance/drive, shuffle and groove. |
| 53 | Voice 2 envelope decay | Performance gate enable. |
| 71..78 | Pitch EG / modulation amounts | Mute controls. |
| 80..83 | Pitch slopes / FM amount | Global scales. |
| 98 / 99 | NRPN selectors | Keep the NRPN route separate from any future compact map. |
| 115 | Master sample rate | Desktop's existing direct rate control, accepted on any configured legacy channel. |
| 125 / 126 | Snare / cymbal LFO amount | Repeat amount / velocity target. |

No control numbers are newly allocated by this audit. In particular, do not
put srt CC1 or the compact CC7-volume/CC10-pan map on Global without an
explicit migration choice. Before adding Pch CC1, define whether input follows
the srt display or mutador's inverse reduction amount.

## Executable checks

Run `python tools/check_midi_contract.py`. The tool extracts the actual
`midiParser_parseMidiMessage`, target-group, valid-channel, routing and filter
functions, compiles them with hardware/synth spies, and executes native C.
It does not reimplement the dispatcher in Python. On Windows it uses the
existing Visual Studio compiler; build output goes to `build/midi-audit/`.
The one-bit MIDI-source enum field is represented as unsigned in the host
harness to match ARM GCC rather than MSVC's signed one-bit enum behavior.

Before correction: failed `voice CC must use its own channel: 0 2 0`.
After correction: **147633 assertions passed**. Coverage includes all 128 CCs,
16 channels, dedicated Pch and all eight overlap assignments, RX C on/off,
both input source tags, all 128 Morph values, all six forwarding modes with
RX disabled, note fanout/deduplication and Pch versus Global Program Change.

DIN and USB share local dispatch. Forwarding runs before local filters and
channel checks, so `mrx=off` does not mute configured Thru. TX filtering is
outside this dispatcher test. Note/synthesis/storage/automation spy calls are
not tests of their downstream engines. The raw DIN byte decoder and USB cable
transport were not exercised here. Hardware loopback remains required.

## Build and next step

The corrected source is named Mutador 0.1.5. CMake release configuration
passed. The release build approval was rejected with `rejected by user` and
no further reason; no 0.1.5 image was produced. 0.1.4 remains the archived
device-tested image and does not include this channel-index correction.

Next: build 0.1.5, then test representative BD1 CC2, BD2 CC3 and hi-hat CC8
on their own channel and Global via DIN and USB. Test dedicated Pch CC2 and
an overlapping assignment. Only then extend the Pch map with CC1 srt.
