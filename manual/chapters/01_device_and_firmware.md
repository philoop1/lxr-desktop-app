# 1. Device and firmware

The LXR V2 desktop is a drum machine with a sound engine, step sequencer,
effects, MIDI connections and SD-card storage. This repository builds firmware
for the desktop unit's STM32F765 processor. Do not use its update image for
the LXR Eurorack module.

The firmware version is defined in `CMakeLists.txt`. This fork currently
starts from Erica Synths' version 1.7 code. See the [changelog](../../CHANGELOG.md)
for the changes made in this fork. The current preview identifies itself as
`Mutador 0.1.26` on startup.

## Finding your way around

The instrument's display presents pages for sound parameters, pattern
settings, MIDI and clock. The current menu definitions live in
`Core/Inc/menu/menuPages.h`; the names shown on the display are defined in
`Core/Inc/menu/MenuText.h`. Detailed button-by-button instructions will be
added after checking them on the desktop hardware.

[Next: Voices and sound parameters](02_voices_and_sound.md)
