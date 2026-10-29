# Session 005 — P00 baseline audit

Date: 2026-10-29
Branch: `docs/development-notes`
Target source: `main` `a43cd4fcda23ec3d577dc425261c3eb28bd5abff`
mutador source: `7319e19b1435dc5a127108367f812c4187f7c025`

## Goal

Build the untouched desktop source, check Euclid against official 1.71 and
map mutador features to desktop files, IDs, MIDI CCs and storage.

## Results

- `git diff main -- Core CMakeLists.txt CMakePresets.json cmake Drivers
  Middlewares USB_DEVICE_MIDI` was empty: firmware source on this docs branch
  matches main.
- Visual Studio CMake 3.31.6 and Ninja configured the release preset with
  DaisyToolchain ARM GCC 10.2.1. Compilation reached the link step, then
  failed on `.ARM.extab` in `STM32F765VGTX_FLASH.ld:86`. No `.img` produced.
- A local ARM GCC 14.3 compiler and an older source-build `.img` exist in
  `I:/Github/Lxr2rea/build/`. Reconfiguring this repository with GCC 14.3
  outside the sandbox was rejected by the command approval system. The
  commands and failure are in [BUILD_NOTES.md](../../BUILD_NOTES.md).
- Created the [source-to-target matrix](../MUTADOR_FEATURE_MATRIX.md).
- `Lxr2Menu`'s Rust path accelerates an exact firmware image in Unicorn. Its
  IMG-live mode is bound by SHA-256 to one older source-build 1.7 image; the
  official 1.71 image has a different hash. The existing UI test for Euclid
  uses `OfficialMenu` native C, not the two firmware images. Thus it cannot
  establish fix parity for this target without a new validated image/profile.

## Open

- [ ] Configure and build untouched desktop source with ARM GCC 14.3.
- [ ] Compare Euclid output of the resulting image with official 1.71 for
      several length/step/rotation cases, ideally through a validated emulator
      profile and then on the LXR V2.
- [ ] Hardware smoke test: boot, playback, project save/load, DIN/USB MIDI and
      analogue sync. Record image hash and SD backup first.
- [ ] Check exact numeric CC collisions before P01.
