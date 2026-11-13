# 8. Cheat sheet: button combinations

Firmware: Mutador 0.2.73. All combinations below were read from the source code
(`Core/Src/buttonHandler.c`, `Core/Src/menu/menu.c`). Most still need checking on
the device; the chapters linked at the end of each section explain the details.

**Names used here.** Step 1-16 are the 16 sequencer buttons. The four mode
buttons are VOICE (mode 1), PERF, LOAD and SAVE. "Hold" without a time means
keep the first button down while you press the second. A long press is 0.5 s
unless another time is given.

## SHIFT + Step

| Combination | Function |
|---|---|
| SHIFT + Step 1 | Master compressor (Global page 4): on, ratio, attack, release, threshold, gain, mix (0.2.71) |
| SHIFT + Step 2 | Groove page: `shf`, `sh2`, `sh3`, `sh4` (Step 4 until 0.2.67) |
| SHIFT + Step 3 | MIDI Delay page (`rpt` and the delay controls) |
| SHIFT + Step 4 | Velocity/Accent page, `vlv` live level (Step 2 until 0.2.67) |
| SHIFT + Step 5 | External sends `s1`-`s6`, `sm` |
| SHIFT + Step 6 | Internal FX sends `i1`-`i6` (0.2.68); stored per pattern from 0.2.70 |
| SHIFT + Step 10 | Song mode |
| SHIFT + Step 12 | CONFIG: Global and MIDI pages |
| SHIFT + Step 13 | Reload: the current kit returns to its state in the project (last save or load; unsaved sound edits are lost). The current pattern only restarts (at its next start while running); step edits stay. Other kits, patterns and the project are not reloaded |
| SHIFT + Step 14 | Last step: set the track length with a Step button; press again for all tracks |
| SHIFT + Step 15 | FX page of the selected FX type (off, dst, rng, cmp, del, tpe, rev) |
| SHIFT + Step 16 | Pattern selection display |

Steps 7, 8, 9 and 11 have no SHIFT function.
[Performance controls](07_performance.md)

## LOAD + Step and SAVE + Step

| Combination | Function |
|---|---|
| LOAD + Step 7 | Transfer import: a KIT or PATTERN from another project (also LXR1 performances) |
| SAVE + Step 7 | Transfer export to another project |
| LOAD / SAVE + Step 8 | Kit |
| LOAD / SAVE + Step 9 | Morph target (SAVE stores the kit you hear at the current Morph position) |
| LOAD / SAVE + Step 10 | Song |
| LOAD / SAVE + Step 11 | Project; press Step 11 twice within 0.6 s for project transfer |
| LOAD + Step 16 | Pattern selection |
| SAVE + Step 16 | Pattern save; the next Step button chooses the slot |

[Saving and loading](04_saving_and_loading.md)

## Long presses

| Combination | Function |
|---|---|
| Hold PERF (0.5 s) | Pattern selection with the first PERF display |
| Hold LOAD (1 s) | Pattern Scale window: turn the encoder to preview, click to confirm |
| Hold a voice button (0.5 s) | Shows used patterns of the bank (lit = used, blinking = playing); PAGE UP/DOWN change the bank while held |
| Hold a Step in Step edit (0.5 s) | Sets or clears the step; it stays selected for editing |
| Turn on while holding the encoder | Firmware update from the SD card |

## Steps, locks and pages

| Combination | Function |
|---|---|
| VOICE twice | Voice edit, then Step edit |
| Hold a Step for 0.5 s (voice mode) + turn a knob or the encoder | Parameter lock on that step, up to 16 per step (0.2.72) |
| Hold a Step + encoder click | Removes the lock of the selected parameter |
| Step edit: hold first Step + press more | Selects a group of steps; release to keep it |
| Step edit: press the selected Step again | Step screens, then automation, then Flam presets |
| SHIFT + PAGE UP / DOWN | Changes bar and sets the track length to that bar |
| COPY + PAGE UP | Copies the current bar into the next and extends the track |
| PAGE UP / DOWN in pattern selection or song | Changes the pattern bank (4 banks of 16) |

[Sequencer and patterns](03_sequencer_and_patterns.md)

## Patterns

| Combination | Function |
|---|---|
| Pattern selection: Step | Switches to that pattern |
| Pattern selection: hold first + press last | Loops the range of patterns |
| Song mode: Step | Adds the pattern to the song |
| Song mode: COPY / SHIFT + COPY | Inserts / deletes a song row |

## Copy and clear

| Combination | Function |
|---|---|
| Hold COPY + Step, Step | Copies a step (voice mode) |
| Hold COPY + voice, voice | Copies a track |
| Pattern selection: hold COPY + Step, Step | Copies a pattern |
| Pattern selection: hold COPY + voice, then a pattern | Copies one track into another pattern |
| SHIFT + COPY | Arms clear; press COPY again while SHIFT is held to clear, release SHIFT to cancel |
| SHIFT + COPY while recording and running | Erases while held |

## Transport, mute and PERF

| Combination | Function |
|---|---|
| PLAY | Start / stop |
| SHIFT + PLAY | Start / stop in song mode |
| REC | Live recording on/off |
| SHIFT + REC | Recording settings page |
| SHIFT + voice | Mute / unmute (outside PERF) |
| PERF: voice | Mute / unmute |
| PERF: SHIFT + voice | Unmutes all voices up to this one |
| PERF: Step 1-8 | Manual roll |
| MIDI Delay page: voice | Adds or removes the voice as a delay input |
| Hold SHIFT | Voice LEDs show the mutes |

[Previous: Performance controls](07_performance.md)
