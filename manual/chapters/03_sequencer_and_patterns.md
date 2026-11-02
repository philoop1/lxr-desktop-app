# 3. Sequencer and patterns

The desktop firmware contains a step sequencer with seven tracks and up to
64 steps in its step storage. Its menus include pattern selection, pattern
settings and a Euclidean pattern generator. Track length can be set in the
voice pages.

Newly initialized or cleared steps default to velocity 100 from 0.1.24.
Track length determines the stored slots used by a track. Pattern Scale sets
how quickly those slots play. Hold PERFORMANCE to open Scale, turn the encoder
to preview and click to confirm. At 12, slots 1-12 of each 16-step page play;
the other slots are retained. All other divisions play all enabled stored
slots. See [Performance controls](07_performance.md) for divisions, bar
lengths and the confirmed switch on the next Takt-1/downbeat.

From every mode, **SHIFT + Step 1** enters pattern selection and shows the
first PERF display (BPM, roll, Morph and sample rate). Release SHIFT,
then use the step buttons to choose a pattern. **SHIFT + PATTERN** opens the
dedicated pattern-selection display instead. The SHIFT + Step 1 shortcut is
available from every mode in Mutador 0.1.23; device testing remains open.

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

Enter pattern selection with SHIFT + PATTERN, or SHIFT + Step 1 from PERF,
then release SHIFT. Hold the first pattern button and press the last one.
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

## Trig Conditions (0.2.9)

`cnd` follows `prob` on the first Step screen. A Step sounds only when its condition is true and its existing probability passes. Available conditions are `---` (always), `1st` (first track loop only), `n1s` (every loop except the first), `fil` (Fill on), `nfl` (Fill off), and every `A:B` combination from `1:1` through `8:8` where A is at most B. `1:2` plays on loops 1, 3, 5, ...; `2:4` on loops 2, 6, 10, ... . Each track counts its own loops and resets on transport restart or pattern change. Shifted Steps use their source position's loop. Flam repeats share the Step's condition.

Fill is currently a latched `fil` on/off control on the second half of the SHIFT + Step 4 Groove page. It defaults to off and is not saved. A dedicated Fill button may be added later. Since 0.2.10, `pre`/`npr` follow the most recent evaluated condition on the same track, ignoring PRE variants as history sources. `nei`/`nne` follow the preceding track (track 1 has no neighbor). A failed Step probability counts as false. A result is retained for the whole Flam group. `lst`/`nls` test whether this pattern is due to leave at its next boundary, including a queued change, Song end/next entry or the performance pattern loop. A change queued after a Step has passed cannot affect that earlier Step.

Conditions are copied with Steps, tracks and patterns. New pattern saves append a `CND1` block after the Flam Probability data; older patterns load with `cnd=---` for every Step.

## Scale Transform (0.2.10)

`sct` is a live control on the second PERF page (Mutador 0.2.18). It reads the active rate: on 2/4/8/16/32 it offers `4 3a 3b 3c`, on 6/12/24 it offers `3 4a 4b 4c`. `3a/3b/3c` leave out step 4, 2 or 3 of each four and play the rest as triplets, so `1 2 3`, `1 3 4` or `1 2 4`. `4a/4b/4c` play three stored steps across four slots as `1 2 3 -`, `1 - 2 3` or `1 2 - 3`. Each pair is an exact inverse and a bar keeps its length. A change applies on the next quarter from rate 12 upward, on the next half note at 6 and 8 and on the next bar at 2 and 4, without restarting. `sct` is not stored and starts on `4`/`3`. Pch CC 88-91 select its four positions.

