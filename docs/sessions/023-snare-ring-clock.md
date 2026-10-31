# Session 023 — Snare envelope, Ring and MIDI Clock Offset

Date: 2026-10-30. Branch `feature/global-load-switches`, based on `9c98ebe` with prior uncommitted import work. Mutador reference `7319e19b1435dc5a127108367f812c4187f7c025`. User confirmed Clock Offset/Vorlauf as the requested Clock fix.

## Source import

- Added the three Mutador Snare noise-envelope controls Attack, Decay and Slope as `nat/ndc/nsl` on the Snare's free fourth page. The legacy neutral 0/127/64 bypasses the separate envelope. The noise envelope can continue after the body envelope ends. `Snare_calcSyncBlock` retains the old calculation path at neutral.
- Added `rng` as the third Drum Voice 1–3 FM/Mix mode. Mutador's DSP calls it Ring; the previous FM=0 and Mix=1 IDs are retained and Ring=2. The existing modulation amount crossfades between dry body and ring product.
- New sound IDs follow the original 228-byte sound block. `SNE1` follows the three new values. Old `.snd` files and older project files with 0xFF kit padding receive neutral defaults. New project kit blocks remain 512 bytes, and old sound IDs keep their positions. The new values participate in kit save/load, RAM slots and Morph interpolation. Old firmware can ignore the appended bytes.
- Global `cof` and `cfn` set 0.1 ms and 0.01 ms MIDI Clock Offset, with the combined negative millisecond value in detail view. The default is 50/0 = −5.00 ms; maximum 80/0 = −8.00 ms. A 216 MHz DWT timestamp is recorded for each received DIN Clock byte. The receiver averages actual cycle intervals; after the last clock before a step, it predicts an early deadline and plays once. The confirming MIDI Clock does not replay the step. USB uses its dispatch timestamp. A 12-step grid takes eight MIDI Clock pulses per step; the 16-step grid takes six.
- `MUTA.CFG` v2 contains 20 performance bytes plus header/checksum, 29 bytes total. It accepts the prior v1 27-byte file and defaults only the two added clock digits. Save Globals or Project explicitly. Analogue EXT timing is unchanged.

## Verification

ARM GNU 14.3.rel1 release Ninja build passed after the DIN timestamp changes. Image `LXR_V2_V1.7_Mutador0.1.15.img`, 306232 bytes, SHA-256 `36197B8199EFBA75828AB720ACDE5DF636F0B12823D0302A3F3CCC417A2F0650`; ELF text 305324, data 884, bss 344176; ITCM 13928/16384 bytes.

Native tests passed: voice import 2440 assertions against actual kit reader/writer, envelope setters and Ring branch; edit/scale/hat/storage 127112; MIDI 352168; performance/Clock 56866; project loader 5 cases. The Clock test verifies early play exactly once, zero-offset edge play, max/fine clamp and eight-pulse 12-grid timing. Physical audio, DIN/USB jitter, CPU, Morph and save/reload still require instrument testing.

The `LXRO2` card's previous 0.1.14 root update was hash-checked and backed up under `build/card-image-backups/20261030-voice-clock-0.1.15`. The card now contains only the 0.1.15 root update image; its SHA-256 matches the archive. Project and configuration files on the card were not changed.

## Limits and next checks

Clock Offset advances sequencer step events; it does not change MIDI Clock transmission or external analogue clock. The displayed hundredth-millisecond setting is finer than the audio service interval, so actual advance and jitter need measurement on hardware. Predictive manual start on the next global bar and other Mutador staging behaviors were not part of this narrow Clock Offset import.
