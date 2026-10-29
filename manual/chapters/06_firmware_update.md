# 6. Firmware update

The built-in updater installs a desktop firmware image from a FAT32 SD card.
The complete build instructions and error-message table are in the
[repository README](../../README.md#updating-your-lxr).

1. Build the firmware with `cmake --preset release` followed by
   `cmake --build --preset release`.
2. Copy `build/release/LXR_V2_V1.7_Mutador0.1.img` to the top folder of the SD
   card. Remove older `LXR*.img` update files from the card.
3. Turn the LXR off, insert the card, hold the encoder button and turn it on.
   Keep holding until `LXR Updater` appears.
4. Wait for `Update OK!` and the automatic restart.

Before installing a development build, back up important SD-card data. Record
the exact image, build result and on-device test in
[BUILD_NOTES.md](../../BUILD_NOTES.md).

[Previous: MIDI and clock](05_midi_and_clock.md) · [Manual contents](../README.md)
