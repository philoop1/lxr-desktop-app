# 016: Complete Mutador pitch and PERF controls

2026-10-29. User requested complete Mutador Pch note-to-pitch behavior,
including the previously disclosed differences, plus PERF display. They
requested the name gpt and explicitly omitted ntP. Source reference:
I:/Github/mutador at 7319e19b, Oscillator.c and MidiParser.c.

Copied osc_calcMidiNoteFrequency, base-note/recalc composition, global-pitch,
Pch-note and global/voice bend setters from Mutador. Frequencies interpolate
fractional semitones and extend by octaves outside MIDI 0..127. Added a
pitchBend member to OscInfo, not to serialized kit blocks. The composite is
kit coarse + played note relative to default + global base + Pch note offset
+ global bend + voice bend, with existing fine tuning applied afterward.

Copied Pch-note scaling (60 neutral, offset clamp -63..64), global CC27
mapping (61..66 neutral), and first-matching-voice bend scope. Global or Pch
bend takes precedence over Voice bend when channels overlap. Closed/open
hi-hat share their oscillator engine. Bend range clamps to 0..48, defaults
to 12; changing it reapplies global bend, as in Mutador. Existing per-voice
bend is rescaled on its next bend event, matching the source behavior.

Moved Pch Note On interception before forwarding and local RX filtering,
as explicitly requested by completing the previously disclosed differences.
Such notes are consumed and work with RX N off when Pch differs from Global.
Pch equal to Global uses the drum-map route. Note Off and zero-velocity leave
the pitch offset unchanged. Source filter/Thru behavior is now intentional.

PERF uses its free fields for gpt and pbr; ntP was removed. gpt is the editable
global base offset, not the sum including Pch notes and wheel positions.
The Pch-note latch and bends stay internal and live. Save globals/project to
persist gpt and pbr. Added their stored bytes after lsr and before CPU; old
stored indices and all kit/pattern formats remain unchanged. Old 30/34-byte
GLO.CFG files default to gpt=63 (display 0) and pbr=12. Values beyond valid
ranges in legacy project padding fall back to those defaults. The reusable
card-channel utility now accepts the expanded 36-byte globals layout too.

## Validation and build

Eight affected translation units passed ARM GCC syntax-only checks including
implicit-function errors. Native tests compare oscillator results against
the original Mutador functions for combinations of coarse pitch, base note,
Pch offsets, fractional global and voice bends; the actual desktop frequency
table is used. Existing note/CC/echo/filter/Thru tests were updated for the
explicitly imported Pch behavior. 334043 assertions passed after final rename.
These checks do not claim audible QA or a physical display test.

An initial release-build approval was rejected with `rejected by user` and
no reason. After the user explicitly requested writing the new image to the
card, a fresh approved build passed 35/35 steps with ARM GCC 14.3.rel1.

LXR_V2_V1.7_Mutador0.1.7.img: 278508 bytes including the 16-byte header.
SHA-256 76298CE0FAA7D6F01C48754E91A702A8B1A6D86A493EF852BA12D3D7D7B9E834.
ELF text=277628, data=856, bss=340708 bytes. Native test and archived image
are current after the gpt rename/removal of ntP.

Copied to F: (LXRO2/FAT32), verified the hash, backed up the prior 0.1.6
image under build/card-image-backups/20261029-184935 and removed only that old
root update image. Only 0.1.7 remains as a root LXR update. No project settings
were edited by this copy; Chan and the requested channel layout remain.

## Hardware checks pending

Install the image. On PERF, verify gpt=0, pbr=12; Pch16 notes 60/72/48 should
produce neutral/+12/-12. Combine with gpt, global/Pch wheel, a Voice wheel,
and kit/morph loads. Verify tones continue beyond the old MIDI limits and
that gpt/pbr save/reboot while note/wheel latches are live only. Verify the
documented early Pch consumption, and test both DIN and USB. No hardware
result has been recorded for 0.1.7.
