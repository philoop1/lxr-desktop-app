# 019: Shuffle port and project-load audit

Follow-up: the groove integration is implemented in [session 020](020-four-point-groove.md).

2026-10-30. User asked for Mutador's exact Shuffle behavior in PERF, a
SHIFT + Step 4 shortcut, and diagnosis of projects that load but do not play.
Yesterday's 0.1.10 work is recorded separately in [session 018](018-accent-and-midi-delay.md).

## Verified card evidence

The SD card has 20 project folders. `PROJ06` is mayengo; `PROJ13` is Next.
Most `GLO.CFG` files store BPM `0` (external clock), including those two, so
that byte alone does not explain the user's different playback result.
Several other Pattern 00 files contain active steps and their linked kit
files exist. No data was changed on the card in this investigation.

`PROJ00` (Beatsies) contains both `00-.PAT` and `00-LXR.PAT`. The blank-named
file has zero active steps; the named one has 34. The loader's wildcard search
selected the first FAT directory match, which could silently choose the empty
file. It now prefers a named match and retains the blank-named file as a
fallback. A second load flaw was that the previous project's edit backup could
overwrite a freshly loaded pattern during activation. The backup now refreshes
from the newly loaded project before that activation.

## Shuffle comparison

Mutador has `shf` plus signed `SH2/SH3/SH4` groove shapes and a fine timing
grid. This desktop tree only has the legacy single Shuffle value and a
different 96 PPQ scheduler. SHIFT + Step 4 now opens the existing Shuffle
field in the second half of the main PERF page; SHIFT + Step 3 still opens
MIDI Delay. The three groove shapes and their exact note, repeat and external
clock timing remain to be ported and tested. The temporary UI shortcut must
move to the complete groove page when that exists.

## Validation and next step

ARM GCC 14.3 release build passed 4/4 steps for the current 0.1.11 source.
The existing native suites passed 351206 MIDI and 48333 performance assertions.
A new real-source FAT wildcard test passed five directory-order cases,
including the two-file Beatsies case. The suites do not yet simulate the
complete project load sequence. The 0.1.11 image is a local build only; the last archived and
card-verified image remains 0.1.10. Next: port Mutador's four-point groove on the desktop clock without changing
old project files, then validate the affected projects and timing on hardware.
