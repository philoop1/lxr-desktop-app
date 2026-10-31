# 014: Mutador note routing

2026-10-29. Based on current changes after desktop commit 9c98ebe. Source
reference: I:/Github/mutador at 7319e19b, MidiParser.c note routing and
scaleGlobalPitchNote. The user clarified that Mutador, not LXR2BC, was intended.

## Implemented behavior

- Global Note On checks every nonzero kit nte. Every match triggers that
  voice at SEQ_DEFAULT_NOTE (60); matches suppress the ANY fallback.
- When no fixed note matches and the selected voice has nte=0, that voice
  plays the received pitch. A fixed-note selected voice has no fallback.
- A dedicated Voice channel plays every note chromatically, ignoring nte.
  Shared Voice channels play all matching voices. Recording remains enabled
  but no input echo is generated. Global has precedence on overlap.
- A Pch distinct from Global uses Note On as live master transpose, with
  MIDI note 60 neutral and offset -63..64. It takes priority over an overlapping
  Voice channel. If Pch equals Global, Global drum-map semantics win.
- RX N gates these note routes. Unlike Mutador's early Pch interception, the
  desktop forwarding path still runs before local filtering, preserving its
  port-routing contract. Zero-velocity/Note Off leave the transpose unchanged;
  baseline voice-release handling remains unchanged.

The normal desktop voiceControl_noteOn already sends MIDI. Calling it and
then adding parser echo would duplicate output and make a supposedly silent
Voice path echo. Refactored its existing sound/LED path into a common helper
and added voiceControl_noteOnNoEcho. Incoming MIDI uses that helper and owns
echo explicitly; existing sequencer triggers keep their MIDI output.

Kept desktop step-note editing on SEQ_PAGE for the currently edited voice.
Other mapped voices sound normally rather than writing the selected voice's
step. This desktop adaptation is tested explicitly.

Added a live oscillator note offset, applied in both base-note and frequency
recalculation paths, clamped before frequency-table access. Pch notes recalc
all three drum main/mod oscillators, snare, cymbal main/two mods, and hi-hat
main/two mods, matching Mutador's recalc scope. Offset persists through kit
loads but is not stored; MIDI note 60 resets it and boot starts neutral.
No stored parameter IDs or file formats changed for this note import.

## Validation

tools/check_midi_contract.py now compiles actual dispatcher, input-note,
low-level trigger and oscillator pitch functions with boundary spies. Both
port tags, all 128 nte values and 128 incoming pitches, duplicate mappings,
ANY suppression, Voice fanout, Global/Pch priority, mute, RX filters,
step entry, recording, one Global echo/no Voice echo and oscillator index
clamping are covered alongside the prior CC matrix. 312125 assertions passed.
Frequency-index tests use a synthetic table and do not claim audible DSP QA.

ARM GCC 14.3.rel1 release: configure and Ninja 26/26 steps passed.
Image LXR_V2_V1.7_Mutador0.1.6.img: 276884 bytes, SHA-256
3B6F171539FAD1A9E84ED1B0835E5C2D193FEC67C40EEEA287FC35A4D905D58D.
ELF text=276004, data=856, bss=340580 bytes. Archived independently of 0.1.4.
Includes the earlier CC channel-index correction; no standalone 0.1.5 image
was produced after its build approval was rejected.

Hardware checks pending: Global drum notes and ANY, chromatic Voice notes,
recording/echo loopback, shared channel priorities, Pch 60/72/48, kit/morph
changes, step entry and old projects via DIN and USB. Pch CC1 and compact
Voice CC mapping are not part of this change.
