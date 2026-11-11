# 3. Sequencer and patterns

The desktop firmware contains a step sequencer with seven tracks and up to
64 steps in its step storage. Its menus include pattern selection, pattern
settings and a Euclidean pattern generator. Track length can be set in the
voice pages.

Newly initialized or cleared steps default to velocity 100 from 0.1.24.
Track length determines the stored slots used by a track. Pattern Scale sets
how quickly those slots play. Hold LOAD for one second to open Scale (before
0.2.52: PERFORMANCE), turn the encoder
to preview and click to confirm. At 12, slots 1-12 of each 16-step page play;
the other slots are retained. All other divisions play all enabled stored
slots. See [Performance controls](07_performance.md) for divisions, bar
lengths and the confirmed switch on the next Takt-1/downbeat.

From every mode, **hold PERFORMANCE for half a second** to enter pattern
selection with the first PERF display (BPM, roll, Morph and sample rate), then
use the step buttons to choose a pattern. **SHIFT + PATTERN** (Step 16) opens
the dedicated pattern-selection display instead. From 0.1.23 to 0.2.70
SHIFT + Step 1 did the same; since 0.2.71 it opens the master compressor.

Hold a voice button for half a second to see which patterns are used: the
step LEDs light each pattern of the played bank that has a step on any track,
free patterns stay dark and the played pattern blinks. PAGE UP and PAGE DOWN
show the other banks while the voice is held. Release it to return. A short
press still selects the voice (0.2.52).

## Live performance variations (0.1.8)

The second PERF page contains:

| Control | Range / default | Behavior |
| --- | --- | --- |
| rst | 0..100 / 0 | Chance to read a random source step within the track length instead of the timeline step. Empty source steps remain empty. |
| csr | 0..127 / 0 | Chance to replay the previous active source step. 127 always repeats while a previous active source exists. |
| pSc | 0..100 / 100 | BC Scarcity: chance to retain a whole step, including all of its flams. 0 suppresses sequencer steps; 100 retains them. |
| pst | 0..100 / 100 | Independent chance that each eligible sequencer hit sounds. Flams can therefore be reduced individually. |

These controls are non-destructive. Source note, velocity, flam/shift and
automation travel together; existing per-step probability is still applied.
Shifted neighbors are planned in advance, so edits to rst/csr/pSc take effect
at the next timeline step. Moving csr to 127 remembers the previously selected active source, even if
another probability control suppressed its sound. Scarcity and probability do not gate manually played rolls
or incoming MIDI notes. Save the project to retain the four global controls.

## 606-style pattern range (0.1.8)

Enter pattern selection with SHIFT + PATTERN, or hold PERFORMANCE for half a
second, then release the buttons. Hold the first pattern button and press the last one.
The inclusive range loops in order, returning from its last pattern to its
first. For example, holding pattern buttons 2 and 5 links 2 → 3 → 4 → 5 → 2.
Only the range endpoints need to be held; intermediate patterns are included.
The existing bank buttons address all 64 desktop slots. Held pattern numbers
are absolute, so changing bank while holding an endpoint can span banks.

Patterns inside the visible part of the range remain lit; the playing pattern
blinks. A single pattern press after releasing the endpoints cancels the loop.
Running changes occur at the existing pattern-end boundary; stopped changes
apply immediately. Song mode has priority over a live range.

The range is a live selection: project load, reboot or a new single selection
clears it. This import does not add Mutador's optional 606 save/restore policy.
Normal pattern editing and stored pattern data are retained.

## Extended COPY in 0.1.16

Hold COPY while selecting source and destination. In voice editing, two Step
buttons copy one complete step, including note, velocity, probability,
automation, Flam, Shift and its on/off state. Switch bars between the two
presses to address all 64 steps. Two SELECT buttons copy one eight-step group;
SELECT 1–8 address groups 1–8 across the full 64-step pattern.

In pattern selection, two pattern buttons copy the whole source pattern to
the destination, including all tracks. For a single track across patterns,
hold COPY in pattern selection, press the source voice button, then the
destination pattern button. The source is the currently viewed pattern.
These RAM copies overwrite the destination; save the destination pattern
to the SD card if it should persist after power-off. The COPY button release
ends an incomplete operation. Pattern bank selection addresses all 64 slots.

[Previous: Voices and sound parameters](02_voices_and_sound.md) ·
[Next: Saving and loading](04_saving_and_loading.md)

## Flam Probability (0.2)

The Step screen now has fpr next to the ordinary Step probability, Flam and Shift controls. The normal probability first decides whether the Step sounds. If it does, fpr decides whether its Flam repeats also sound. fpr=0 leaves only the main hit; fpr=100 keeps the full Flam. This decision is shared by all repeats of that Step. fpr is copied with Steps and saved in an FLP1 trailer after the existing pattern scale; older patterns load with fpr=100.

## Flam 2+1 to 8+1 (0.2.48)

After x8 the Flam control offers 2+1, 3+1, 4+1, 6+1 and 8+1. The Step rolls like x2 to x8, and one more hit follows at the start of the next Step, with the note and velocity of the flammed Step. The extra hit plays only when the next Step has no note; a note there plays alone, even when its chance mutes it. On the last Step of the track the Flam stays normal and does not reach Step 1. Shift and groove move the extra hit with the Step, and fpr drops it together with the other repeats. Older firmware plays these values as off.

From 0.2.56 `fvl` after `shf` sets the velocity curve of the Flam, from -100 to +100 %. At 0 every hit has the Step velocity. Negative values fade the repeats: the first hit keeps the Step velocity and the last one plays at 100 % minus the amount, so -100 fades to silence. Positive values rise from 100 % minus the amount to the full Step velocity at the last hit. With 2+1 to 8+1 the extra hit is the last one of the curve. fvl is copied with Steps, can be set for a Step edit group and is saved in an FLV1 trailer; older patterns load with 0. From 0.2.61 fvl belongs to the Flam preset (see below).

## Flam presets (0.2.61)

The Flam control of a Step now picks one of 15 Flam presets of the project, `F1` to `F15`. F1 to F10 start as the former x2, x3, x4, x6, x8 and 2+1 to 8+1, so existing patterns sound the same. F11 to F15 start as examples: F11 speeds up, F12 slows down, F13 rises two semitones per hit, F14 fades out on the x8 grid, F15 plays three quick hits.

Press the selected Step again to go from the Step screens to the automation screen and on to the Flam preset screens; since 0.2.63 the encoder also scrolls there past the empty places. The screens edit the preset of the Step you selected last, the one its `flm` shows:

| Control | Range | Function |
|---|---|---|
| rep | 1..64 | Number of hits including the main hit. The hits stay inside the flam length, so the grid limits them (x4 and stp 1: at most 4, x4 and stp 2: at most 8). |
| res | /3, t4, /2, t8, 1, t16, x2, x3, x4, x6, x8, x12 | Grid of the hits. x2 to x12 are hits per Step. From 0.2.65 the slower grids: `1` one hit per Step, `/2` and `/3` one hit every 2 or 3 Steps, `t16`, `t8` and `t4` sixteenth, eighth and quarter triplets (3 hits over 2, 4 or 8 Steps). They need a matching `stp`: `res t8`, `rep 3`, `stp 4` plays one quarter of eighth triplets. |
| fvl | -100..+100 % | Velocity curve, as before, now for every Step using the preset. |
| fpt | -12..+12 | Pitch step per hit in semitones; the notes stop at 0 and 127. The +1 hit continues the steps. |
| +1 | off/on | One more hit at the start of the following empty Step, like 2+1 to 8+1. |
| bb | -100..+100 % | Accelerate or brake. Positive values make the gaps shorter towards the end, negative values longer; 0 keeps them even. |
| stp | 1..16 | Length of the flam in Steps (0.2.63). 1 is the flam inside its Step as before. |

From `stp` 2 on the preset is a long flam: the hits run on the `res` grid over `stp` Steps, `bb`, `fvl` and `fpt` run over the whole length and `+1` plays on the first Step after it. A long flam has priority over its track: notes of the same track that fall into it are skipped, also when another long flam would start there. At the end of the track it continues into the next loop; stop and a pattern change end it. Shift and groove move the start hit, the other hits keep their distance to it. Until 0.2.62 a `fla` control chose the edited preset; it is gone, and older projects load with `stp` 1.

Flam probability (`fpr`) stays per Step. Edits apply at once to every Step using the preset and are kept two seconds later in the tmp folder; SAVE Project stores the presets in the project (prj.nfo, after the name). Loading or creating a project starts from the factory presets, older projects keep them. Patterns saved by 0.2.56 to 0.2.60 still hold a velocity per Step: on loading, a Step with its own velocity points at a preset with the same Flam and that velocity, which takes a free place from F15 down to F11. When no place is free, the preset with the nearest velocity is used. The per-Step velocity table is gone, which frees about 28 KB of RAM. A pattern copied into another project uses the presets of that project.

## Trig Conditions (0.2.9)

`cnd` follows `prob` on the first Step screen. A Step sounds only when its condition is true and its existing probability passes. Available conditions are `---` (always), `1st` (first track loop only), `n1s` (every loop except the first), `fil` (Fill on), `nfl` (Fill off), and every `A:B` combination from `1:1` through `8:8` where A is at most B. `1:2` plays on loops 1, 3, 5, ...; `2:4` on loops 2, 6, 10, ... . Each track counts its own loops and resets on transport restart or pattern change. Shifted Steps use their source position's loop. Flam repeats share the Step's condition.

Fill is currently a latched `fil` on/off control on the first PERF page, after `spd` (on the SHIFT + Step 4, now Step 2, Groove page before 0.2.54). It defaults to off and is not saved. A dedicated Fill button may be added later. Since 0.2.10, `pre`/`npr` follow the most recent evaluated condition on the same track, ignoring PRE variants as history sources. `nei`/`nne` follow the preceding track (track 1 has no neighbor). A failed Step probability counts as false. A result is retained for the whole Flam group. `lst`/`nls` test whether this pattern is due to leave at its next boundary, including a queued change, Song end/next entry or the performance pattern loop. A change queued after a Step has passed cannot affect that earlier Step.

Conditions are copied with Steps, tracks and patterns. New pattern saves append a `CND3` block after the Flam Probability data. It stores the pattern transform and six bits per Step for conditions. The firmware also reads `CND1` and `CND2`. Patterns without condition data use `cnd=---` for every Step. Earlier firmware reads the main pattern but defaults CND3 conditions and the transform when loading a new save.

## Scale Transform (0.2.10)

`sct` is a live control on the second PERF page (Mutador 0.2.18). It reads the active rate: on 2/4/8/16/32 it offers `4 3a 3b 3c`, on 6/12/24 it offers `3 4a 4b 4c`. `3a/3b/3c` leave out step 4, 2 or 3 of each four and play the rest as triplets, so `1 2 3`, `1 3 4` or `1 2 4`. `4a/4b/4c` play three stored steps across four slots as `1 2 3 -`, `1 - 2 3` or `1 2 - 3`. Each pair is an exact inverse and a bar keeps its length. A change applies on the next quarter from rate 12 upward, on the next half note at 6 and 8 and on the next bar at 2 and 4, without restarting. `sct` is not stored and starts on `4`/`3`. Pch CC 88-91 select its four positions.

