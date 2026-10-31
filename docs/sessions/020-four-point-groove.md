# 020: Four-point Mutador groove on desktop

Follow-up: the user reported 0.1.12 works. In 0.1.13, groove clock output
moves to the explicit `16sh` selector; ordinary PPQ modes are straight.
See [session 021](021-load-labels-and-16sh-clock.md).

2026-10-30. Continues [019](019-shuffle-and-project-load-audit.md).
Reference: Mutador `7319e19b`, original `seq_centerGrooveValue`,
`seq_recalcGrooveOffsets`, groove event/clock and repeat-lane behavior.

## Controls and load policy

SHIFT + Step 4 opens a PERF page with `shf`, `sh2`, `sh3`, `sh4`.
The main PERF Shuffle field controls the same master amount. Step 1 of each
four-step group stays fixed. The other three signed controls move their
positions earlier or later. Raw 63/64 are neutral, with the original Mutador
rounding, deadband and maximum offset. All three default to neutral; an old
project's single Shuffle value now acts as the groove master and requires
non-neutral shapes to produce swing. This is an intentional behavior change.

All three shapes are saved at globals offsets 58..60. The reserved 64-byte
block now stores 61 bytes, with prior stored fields unchanged. The transient
CPU/VLV fields remain excluded. Old files and invalid padding use neutral
defaults. Pch CC40 controls the master, CC41/42/43 the shapes, including the
original CC64-to-neutral mapping. Existing channel and RX priority applies.

User clarified that save always includes groove, but `lsh=off` must prevent
loading it. A live OFF setting preserves the three shapes across globals/
project loads and remains OFF even if the incoming project saved ON. An
incoming OFF setting also preserves the live shapes. With both permissions
ON the stored shapes load. Pattern activation continues to gate the stored
Shuffle master through lsh. Thus a project cannot silently unlock a live
groove hold. This does not change kit or Morph load policies.

## Timing integration

The desktop's existing 96 PPQ event positions are retained on even frames of
a 192 PPQ clock. A Mutador fine groove unit is represented by three such
frames; odd offsets are not rounded back to 96 PPQ. Internal transport,
external-clock anchors and outgoing MIDI clock remain straight. The former
odd-step transport delay is removed. Notes, automation and eligible Delay
input follow the moved source event. With neutral groove the existing desktop
Flam/Shift dispatcher runs on even frames without double triggers.

Combined groove and desktop per-step Shift can reach across two neighbors.
The performance planner now keeps previous-two through next-two metadata so
RST, CSR, per-step chance, Scarcity and PST remain associated with the chosen
source. Newer timeline events retain desktop priority if hits collide on one
voice. This is a desktop adaptation rather than a wholesale scheduler copy.

Delay chains run at 192 PPQ and remember their actual input groove lane.
Periods of a main step or longer add the target-minus-current lane offset,
using Mutador's lane advance rounding and minimum fine period. Existing
exact desktop triplet rates and bounded bounce arithmetic remain. Repeats do
not feed themselves back. The legacy 96 PPQ Delay test API advances two fine
frames; production advances one. Pattern/reset operations clear chains.

MIDI and analog clock boundaries start frame zero on the external edge.
Interpolation stops at the next expected step when no clock arrives. The
MIDI tempo estimator now averages only valid intervals during startup rather
than zero-filled samples; elapsed time is unsigned for systick wrap. The
desktop's single clock output follows groove at 2/4 PPQ, with Mutador's
one-substep pulse width. Faster output divisions retain their straight rate.
Incoming-pattern pre-roll is not scheduled before that pattern is activated,
matching the active-pattern scope of the source implementation.

## Validation

- `tools/check_groove.py`: 1531928 assertions against extracted original
  Mutador functions, signed event positions, repeat lanes and real TriggerOut
  code, including negative/floored periods.
- `tools/check_performance_import.py`: 56735 assertions. Includes actual fine
  dispatcher and clock functions, positive/negative/half-tick events, combined
  Shift/Flam tails across two steps, probability gates, neutral equivalence,
  Delay follow-up positions, internal/external quarter timing, cold clock
  startup, clock loss, old globals, lsh hold and SHIFT+4 access.
- `tools/check_midi_contract.py`: 351790 assertions including Pch CC40..43.
- `tools/check_project_loader.py`: five real-source FAT selection cases.

ARM GCC 14.3 release build passed after one missing TriggerOut declaration
was corrected. Final rebuild: 7/7 steps. ELF text=293972, data=880,
bss=341436. ITCM 15376/16384, DTCM 107512, RAM 271804, FLASH 242488 bytes.
`LXR_V2_V1.7_Mutador0.1.12.img`: 294876 bytes including the 16-byte header,
SHA-256 `14868D0050D68DD322AB7B550B298427758B3A0EDAC06AAC792395A1CDE8F621`.

Physical sound, MIDI/analog jitter, CPU use and project save/reboot checks
remain pending. Native tests do not measure real audio timing or CPU load.

## SD update

Copied the archived 0.1.12 to F: (verified LXRO2 volume) and verified its
SHA-256 against the archive. The previous 0.1.10 root update was backed up
and checked under `build/card-image-backups/20261030-groove-0.1.12` before
removal. Only 0.1.12 remains as a root update image. Project, kit, pattern,
sample and channel files were not modified. Installation on the device is
pending.
