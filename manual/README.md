# LXR V2 desktop — manual

This manual describes the experimental Mutador 0.1.26 desktop firmware. It is
being expanded as the fork develops. For changes specific to this fork, read
the [changelog](../CHANGELOG.md); for developer build records, read the
[build notes](../BUILD_NOTES.md).

## Chapters

1. [Device and firmware](chapters/01_device_and_firmware.md)
2. [Voices and sound parameters](chapters/02_voices_and_sound.md)
3. [Sequencer and patterns](chapters/03_sequencer_and_patterns.md)
4. [Saving and loading](chapters/04_saving_and_loading.md)
5. [MIDI and clock](chapters/05_midi_and_clock.md)
6. [Firmware update](chapters/06_firmware_update.md)
7. [Performance controls](chapters/07_performance.md)

The source code establishes which features exist, but exact button sequences
should be verified on an LXR V2 before they are added here. This manual
documents only features already present in this desktop source. The newest
controls still need physical-device verification.

## New controls in 0.1.22

- Hold PERFORMANCE for the per-pattern Scale window. Rotate to preview, click to confirm, then wait for the next bar while running. See [Performance controls](chapters/07_performance.md).
- Choose LFO `str` or `gld` for Stray/Glide; `ofs=63` is neutral. See [Voices and sound](chapters/02_voices_and_sound.md).
- Voice-channel CCs now use Mutador's common map, including the seven new Snare controls and LFO destination selection. See [MIDI and clock](chapters/05_midi_and_clock.md).

The documentation distinguishes the implemented controls from physical-device
validation, which is still open for this release.

## New controls in 0.1.23

SHIFT + Step 1 now opens pattern selection with the PERF display from every
mode. On the second PERF page, cnt is followed by rvl and avl, then pbr.
Rvl randomizes velocity as in Mutador. AVL follows it, applying -100 to +100
percent gain to sequencer velocity and MIDI output. From 0.1.25 the positive
range is proportional, with clipping at 127. See [Performance controls](chapters/07_performance.md).

## Velocity headroom in 0.1.24/0.1.25

New/reset steps default to 100. The mounted card's active projects and TMP
were proportionally converted once. AVL now multiplies soft and strong notes
by the same factor: +50 means x1.5, +100 means x2, clipped at 127. See the
Performance and Saving/Loading chapters for behavior and backup records.
