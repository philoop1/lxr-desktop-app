# 4. Saving and loading

The firmware has SD-card storage for kits, patterns and projects. Keep a copy
of important SD-card files on your computer before testing a modified
firmware. The [firmware update](06_firmware_update.md) also uses the SD card,
but its `.img` file is an update image, not a kit or pattern file.

This chapter needs hardware-verified instructions for the load/save menus,
file locations and compatibility between firmware versions. In particular,
LXR1/LXR2 import behavior discussed in other projects has **not** been
implemented in this desktop fork.

[Previous: Sequencer and patterns](03_sequencer_and_patterns.md) ·
[Next: MIDI and clock](05_midi_and_clock.md)

## Unsaved pattern edits (0.2.66)

A pattern change keeps what you recorded or edited in a pattern; switching
back shows it again. The edits live in RAM until SAVE Project writes them to
the card, so without saving they are gone after power off. Saving a pattern to
another slot copies the edits there and puts the source slot back to the state
it had when you entered it. Up to 0.2.65 every pattern change discarded
unsaved edits.

## High Pitch Damp (0.2.66)

Global `hpd` (third global page) makes high pitched drum voices quieter, as
the LXR1 Mutador did: voice 1 above 120 Hz, voices 2 and 3 and (from 0.2.67)
the snare above 1 kHz. 0 is
off, 100 is the full LXR1 Mutador damping. Samples are not damped. The value
is kept in MUTA.CFG with the other global extras.

## Pattern Scale and the new sound controls

Encoder confirmation in the Scale window sets the pattern's scale in memory;
it does not replace explicitly saving the pattern or project to SD. An
unconfirmed preview is discarded when leaving the window. Pattern copy and
edit backup retain the scale. Older patterns without scale data load at 16.
At 12, unused page slots 13-16 retain their notes and automation, so changing
back to 16 restores their playback.

Save the kit to retain the Snare noise envelope, second-oscillator settings
and new LFO wave selections. Old kits default the added Snare layer to off
and the independent noise envelope to its neutral values. The new Stray/Glide
shapes use the existing LFO waveform field. Project copies should include
`MUTA.CFG`: version 4 keeps the updated scale override choices and adds rvl/avl.
Versions 1-3 still load, with the new velocity controls neutral.

## One-time velocity conversion on the mounted card

On 2026-10-31, active PROJ directories and TMP were backed up and their step
velocities scaled by 100/127, rounded to integers. 1,345 files were checked;
1,281 changed, affecting 573,886 of 602,560 stored step slots. Step active
flags, notes, automation, timing and pattern settings were preserved.
The Lxr2openmytake archives and Helicase directory were excluded.

The complete originals, staged results, hashes and application receipt are
under `build/card-velocity-backups/20261031-velocity-100` in the repository.
This is a separate migration, not a firmware load operation. The same plan
can resume safely without scaling an already-converted file a second time.
Do not make another fresh scaling plan to repeat this conversion.
