# 017: GDC, step variations and 606 pattern range

2026-10-29. User clarified: gdc directly beside gpt; rnd repeat means Mutador
CSR (previous active step), not MIDI delay; Scarcity comes from LXR2BC; pst
is global probability in addition to stored per-step probability.

Sources: Mutador 7319e19b (GDC bipolar depth, RST/CSR, 606 endpoint gesture),
LXR2BC c277507 sequencer Scarcity behavior. Desktop source builds on current
uncommitted changes after 9c98ebe. GDC does not import additional Snare or
velocity layers absent from the desktop; it affects the seven existing amp
decays. Applied after fresh kit/Morph parameter writes and updates modulation
node originals, without changing raw source CCs or saved kit endpoints.

## Desktop adaptations

Added a pure PerformanceSteps module. RST chooses a source within each track's
1..64 main-step length. CSR tracks active sources using Mutador's logic.
Prev/current/next choices, per-step probability draws and BC Scarcity decisions
are planned together so desktop's shifted/flammed neighbors remain valid.
Live source-control changes preserve the currently playing event and replan
at the next boundary, remembering the source actually selected for the previous timeline step for CSR.

BC Scarcity samples once per main step and drops all its sub-events. PST is
an independent gate on each actual sequencer hit. Existing stored probability
still uses its own 1..100 draw, including 0=never and 100=always. RST source
note/velocity/automation are consistent even for shifted neighbors. Manual
rolls and incoming MIDI are outside these sequencer-only gates.

The actual desktop seq_triggerVoice emitted MIDI both through the normal
voice trigger and its explicit outgoing-note path. Changed it to use the
local-only trigger and one explicit MIDI send, preserving external note
override while using the selected source's velocity instead of timeline
velocity. Integration tests exercise that exact trigger code.

606 gesture uses held absolute pattern numbers, covering all 64 slots and
bank-spanning ranges. Single selection clears the range. Song mode takes
precedence. LEDs show the visible range and blink the playing pattern.
Project load clears the live range. No 606 state persistence was requested;
Mutador's optional 606 save/restore switch is not imported here.

## Controls and storage

Main PERF: BPM / roll / morph / srt / shuffle / gpt / gdc / pbr.
Second PERF page: rst / csr / pSc / pst. Appended global IDs, in order:
gdc, rst, csr, pSc, pst. Defaults: 63 (display 0), 0, 0, 100, 100. Stored
globals grow from 36 to 41 bytes, still within the existing 64-byte reserved
project section. Existing field offsets and kit/pattern layout stay unchanged.
Old 30..40-byte globals and 0xFF padding receive validated defaults.

Pch CC5/6/7 are rst/csr/pst; CC28 is gdc using the existing bipolar mapping.
On Pch these take precedence over legacy CC meanings, as CC27 already does.
Legacy Global/Voice channels retain their map unless also assigned to Pch.
CC2 keeps its earlier distinct-Pch-only overlap rule. Scarcity is menu-only;
BC's CC25 collides with reserved Mutador performance controls and was not
copied blindly. Core CC table updated accordingly.

## Validation

tools/check_midi_contract.py: 350509 assertions passed, including all GDC
base/depth pairs against Mutador's original full-depth formula, raw-cache
preservation and restoring seven independent decays, plus new Pch controls.

tools/check_performance_import.py compiles the actual scheduler, flam/shift
dispatcher, source-aware trigger, 606 button helper, LED function and globals
loader with hardware spies. 38002 assertions passed: all track lengths,
wraps, random bounds, CSR endpoints/live knob changes, Scarcity/PST endpoints,
source note/velocity/automation, single MIDI emission, negative shifts,
per-step probability, all banks, live loop cancellation/song priority, and
old/new globals. These tests are not a hardware timing/CPU measurement.

GCC 14.3.rel1 CMake/Ninja release build passed 34/34 steps, then 3/3 after
the final live CSR-history correction. ELF text=282708, data=868, bss=340884.
Image LXR_V2_V1.7_Mutador0.1.8.img: 283600 bytes including its header.
SHA-256 F07720D86A87A9F0E849494A2FBFCD53EBA0F17911E0AB755B86DD8104108C01.

Hardware tests pending: neutral A/B with 0.1.7, all gdc voices/Morph, CSR
on/off while playing, rests and shifted/flammed notes under RST/Scarcity/PST,
64-pattern range changes with KCM, MIDI echo/velocity, CPU and project save/
reboot. Broad P02/P06/P07 work remains partial.

## SD update

Copied the final 0.1.8 to F: (LXRO2/FAT32), verified SHA-256 and backed up
0.1.7 under build/card-image-backups/20261029-191730 before removing its root
update image. Only 0.1.8 remains as a root LXR update. No project settings,
channel assignments, Chan project, kit or sample data were changed by this
copy. Installation on the instrument remains the user's next step.
