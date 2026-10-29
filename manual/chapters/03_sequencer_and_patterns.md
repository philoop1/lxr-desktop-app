# 3. Sequencer and patterns

The desktop firmware contains a step sequencer with seven tracks and up to
64 steps in its step storage. Its menus include pattern selection, pattern
settings and a Euclidean pattern generator. Track length can be set in the
voice pages.

The number of steps used during playback depends on the pattern settings.
Exact editing gestures, pattern switching behavior and any timing edge cases
still need a hardware check before this chapter gives instructions for them.

From the PERF page, **SHIFT + Step 1** enters pattern selection while keeping
the PERF display (BPM, roll, morph and other settings) visible. Release SHIFT,
then use the step buttons to choose a pattern. **SHIFT + PATTERN** opens the
dedicated pattern-selection display instead. The SHIFT + Step 1 shortcut is
new in Mutador 0.1.1 and still needs an on-device check.

Features discussed for LXR2BC or mutador, such as multiple-step selection or
slide note length, are **not yet present in this desktop fork**. Their arrival
will be recorded in the [changelog](../../CHANGELOG.md).

[Previous: Voices and sound parameters](02_voices_and_sound.md) ·
[Next: Saving and loading](04_saving_and_loading.md)
