# Performance controls

The main PERF page shows BPM, roll, Morph, master sample rate,
global pitch (`gpt`), global decay (`gdc`) and speed (`spd`).
`spd` offers /8, /4, /2, 1, *2 and *4 relative to the stored pattern rate. It starts at 1 and tops out at 64 steps a bar, or 48 on ternary rates. Pch CC 79-84 select it.
A pattern stores its own rate: 2/4/6/8/12/16/24/32 steps per 4/4 bar.
`pat` follows the scale saved with the current pattern. Hold LOAD for one
second to open its Scale window (PERFORMANCE before 0.2.52). Turn the encoder to preview, then click to confirm.
While running, the new division begins at
Step 1 on the next transport bar downbeat; while stopped it applies at once.
The window shows `click=OK` for an unconfirmed preview and `next 1` while a
confirmed change is pending. Leaving without confirming discards the preview.
LOAD retains its normal operation.

All 64 stored steps play at 2/4/6/8/16/24/32, at the selected speed. At 12,
each 16-step page plays slots 1�12, giving 48 played steps over four pages;
slots 13�16 remain stored. This replaces the old 12a/b/c skip patterns.

| Scale | MIDI clocks/step | Duration of a full 64-slot pattern |
|---|---:|---:|
| 2 | 48 | 32 bars |
| 4 | 24 | 16 bars |
| 6 | 16 | 10 2/3 bars |
| 8 | 12 | 8 bars |
| 12 | 8 | 4 bars (48 played steps) |
| 16 | 6 | 4 bars |
| 24 | 4 | 2 2/3 bars |
| 32 | 3 | 2 bars |

Track length still determines how many stored slots a track visits. Save the
pattern or project to retain Scale. Pattern copy and edit backup retain it.
A checked `SCL2` trailer stores the actual division after legacy PatV03 data;
older pattern files default to 16. Existing steps and automation are retained.
The 29-byte `MUTA.CFG` v3 sidecar marks the new global override numbering;
v1/v2 sidecars still load, translating old 16 to 16 and 12a/b/c to 12.
`pbr` moved to the third global settings page in Mutador 0.2.18.
SHIFT + Step 1 enters pattern selection from every mode and shows the first
PERF display. It cancels pending step-automation selection and COPY/CLEAR
selection before entering pattern selection.
SHIFT + Step 4 opens the Groove page: `shf`, `sh2`, `sh3`, `sh4`. From 0.2.54 `fil`, a temporary on/off Fill latch for Step conditions, sits on the first PERF page after `spd`.
The second half of the Groove page holds humanize (0.2.55): `hm1` to `hm4`
belong to the four steps of each group that `shf` to `sh4` shape. At 0 a step
plays on time; turning up moves every hit by a random amount, up to a quarter
step early or late at 127. Each voice on a step gets its own amount and every
pass is new, so a kick and a hat on the same step drift apart. Humanize also
works with `shf` at 0.
`shf` is the same master amount shown on the main PERF page. In each repeating
group of four steps, the first stays fixed. The other three controls move
their steps earlier (negative) or later (positive). Their displayed default
is 0; raw values 63 and 64 both have no effect. Set a nonzero shape as well
as a nonzero `shf` to hear the groove. For alternating swing, raise `sh2` and
`sh4`, keeping `sh3` at 0. Old projects with only a Shuffle amount start with
neutral shapes until these are set.

Groove follows each track's main-step position, including short track loops.
Notes, their automation and MIDI Delay repeats follow the shifted positions.
MIDI clock and pattern transport stay straight. From 0.1.13, the physical
clock output follows groove when `cko=16sh`: shuffled sixteenths, four pulses
per quarter. Other CKO divisions stay straight. The finer internal
192 PPQ grid preserves shifts that fall between the old 96 PPQ ticks.

All three shapes are saved with globals. With `lsh=off`, loading preserves
the current groove and the OFF setting; an incoming project cannot release
this hold. A project saved with `lsh=off` also leaves the current shapes alone.
With loading enabled on both sides, its saved shapes load. Pattern switches
use the same lsh choice for their stored Shuffle amount. Saving always writes
the current shapes, including while lsh is OFF.

The global settings have two four-field views: `cpu/cki/cko/scr`, then
`lki/lsh/lmp/lsr`. `lki` is the renamed kit-change mode, formerly `kcm`;
its behavior is unchanged. All four load controls show `off/aut`. On each
LCD view the labels are in the upper row and their values in the lower row.
The second PERF page contains random step (`rst`), previous-step repeat
(`csr`), Scarcity (`pSc`), global hit chance (`pst`), `cnt`, Random Velocity
(`rvl`), All Velocity (`avl`) and `sct`, in that order.
`cnt` scales the probability already stored on each step.

`rvl` ranges from 0 to 100 and is neutral at 100. It chooses a random
percentage between its value and 100 for each sequencer hit, including Flam
and MIDI Delay repeats. As in Mutador, Voice 1 retains its sound/MIDI
velocity while the randomized value feeds its velocity modulation; Voices
2-7 use the randomized velocity for both. The neutral value consumes no
random numbers, preserving existing probability/random-step sequences.

`avl` follows `rvl` and ranges from -100 to +100 percent, neutral at 0.
From 0.1.25 it applies proportional gain in both directions: -50 multiplies
velocity by 0.5, +50 by 1.5 and +100 by 2. Results round to the nearest MIDI
velocity and clip at 127. Zero stays zero. For example, velocity 40 becomes
60 at +50 and 80 at +100; velocity 80 becomes 120 at +50. Relative dynamics
are retained until a value reaches 127. -100 sets played-note velocity to 0;
0 preserves it. +100 no longer forces every soft note to 127.

This applies to all seven sequencer voices, their velocity modulation and
the sequencer's MIDI output, including Flam/Delay repeats. It does not create
notes on inactive steps or overwrite their stored velocities. Kit velocity
routing determines how velocity affects the sound; AVL controls velocity,
not the master VCA. Both controls persist with project settings.

From 0.1.24, newly initialized/reset steps default to velocity 100, giving
positive gain room to work. Existing files load their stored values as usual.
The mounted card's active PROJ directories and TMP were converted once by
100/127, with rounding: 127 becomes 100, 64 becomes 50. The active flags,
notes, automation, timing and pattern settings were preserved. Archived
LXR files and Helicase were excluded. Updating firmware does not repeat this
conversion. The proportional AVL correction in 0.1.25 changes no pattern data.

SHIFT + Step 2 opens the Velocity/Accent page. `vlv` is its live master level;
it returns to neutral after settings load. The seven saved destinations are
`vdc` amp decay, `vsr` sample rate, `vfi` filter cutoff, `vco` coarse pitch,
`vsl` amp slope, `vma` modulation amount and `vdr` filter drive. A depth of
63 is neutral; the master can invert the response. Accent uses the played
step's velocity. Neutral destinations leave current step automation intact.

SHIFT + Step 3 opens MIDI Delay. The eight controls are `rpt` chance,
`rcl` clock division, `rpn` repeat count, `bb` bounce, `vel` velocity target,
`pol` mono/poly, `bxp` bounce shape and `d2p` pitch per repeat. Both `rpt`
and `rpn` must be greater than zero to create repeats. `rcl` follows the
96 PPQ clock, with exact dotted and triplet divisions. Mono allows one
chain globally; poly allows up to four per voice. Repeats do not themselves
start more repeats.

While MIDI Delay is open, the seven instrument buttons toggle which voices
may enter the delay; their LEDs show the selection. Existing repeats finish
when a voice is deselected. Pattern changes and transport resets clear the
repeat queue. The ordinary mute settings are preserved. Delay input comes
from eligible sequencer hits, not manual rolls or incoming MIDI.

SHIFT + Step 5 opens the external sends `s1`–`s6` and `sm`; pressing it again
switches between the two screens.

SHIFT + Step 2, 3, 4 and 5 stay on their own pages; pressing PERF or scrolling
through its regular pages does not enter them. A further regular PERF page
contains master filter cutoff, resonance and drive. The seven VCAs remain active but are not shown as a
separate PERF page. Global `mfl` switches
the master filter on/off; `fxs` selects normal/AFL/PFL/CFL send routing and
`fxo` selects stereo/bipolar output routing. Sends use the physical output 2.
The master send is taken after the master filter. The existing internal FX
bus remains available. The six voice sends/VCAs share the two hi-hat voices.

In Step edit, hold the first step and press further step buttons to select a
group; release to keep it selected. The next unheld press starts a new group.
Edits to note, velocity, chance, flam, shift and automation apply to the
selected steps, including steps across visible bars.
From 0.2.53 holding a single step button for half a second sets or clears
that step; it stays selected for editing. A short press only selects.

The three new global switches use the remaining bytes of the existing
64-byte globals file. The 18 extra performance values, two Clock Offset digits and rvl/avl
are saved in a checked `MUTA.CFG` in the project folder (v4, 31 bytes; v5 with hm1..hm4, 35 bytes, from 0.2.55).
Version 1 (27 bytes) still loads with default Clock Offset. Save Globals or Project explicitly
and back up this file with the project. Older projects default safely.
The saved controls use the existing globals space. Older project globals
receive safe defaults. Physical-device tests of Groove/Accent/Delay timing,
CPU and save/reboot remain pending.

From 0.1.23, MUTA.CFG v4 adds rvl/avl after the previous payload. Versions
1-3 load with neutral rvl=100 and avl=0 percent. The raw stored avl byte is
0-200 with 100 neutral; the display shows -100 to +100 percent.
