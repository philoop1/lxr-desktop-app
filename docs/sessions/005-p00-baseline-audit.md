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
  `I:/Github/Lxr2rea/build/`. An attempted agent-run reconfiguration was
  rejected by the command approval system. The user ran the documented
  PowerShell commands instead. The resulting `LXR_V2_V1.7.img` is 274,704
  bytes with SHA-256 `B34C0C3A946D02C5CEE624351A44C2597694B4832FDAA9CBAEB3627F84979AFE`;
  the CMake cache points at the GCC 14.3 toolchain.
- Created the [source-to-target matrix](../MUTADOR_FEATURE_MATRIX.md).
- `Lxr2Menu`'s Rust path accelerates an exact firmware image in Unicorn. The
  newly built image matches its validated 1.7 source-build hash exactly.
  `tools/probe_euclid_live.py` booted this image with the Rust accelerator:
  `LEN 16 / STP 5` generated five active steps, rotation changed the mask
  without changing the count, and `LEN 15` retained five. The official 1.71
  image has a different hash; the existing IMG-live address profile cannot
  establish fix parity without a separate validated 1.71 profile.

## Open

- [x] Configure and build untouched desktop source with ARM GCC 14.3.
- [ ] Compare Euclid output of the resulting image with official 1.71 for
      several length/step/rotation cases, ideally through a validated emulator
      profile and then on the LXR V2.
- [ ] Hardware smoke test: boot, playback, project save/load, DIN/USB MIDI and
      analogue sync. Record image hash and SD backup first.
- [ ] Check exact numeric CC collisions before P01.
