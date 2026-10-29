# Changelog

Changes in this fork relative to
[Erica Synths' lxr-desktop-app](https://github.com/erica-synths/lxr-desktop-app)
are recorded here. The upstream project keeps its own Git history.

## Unreleased

### CONFIG and SD card

- Added saved `Pch` beside global `ch` on the first CONFIG page. It defaults to
  MIDI channel 2 and accepts CC 2 for kit morph when its channel does not
  overlap a voice or global channel. Other performance CCs are still planned.
- Added a read-only CPU meter on the second CONFIG page. It shows the peak
  audio-block processing load over each half-second interval.
- Added the 1.6-era SD-card data backup to version control. The local
  `bootloader.img` is excluded from Git and is not part of this backup commit.

### Development workflow

- Added build notes, a fork changelog, and a numbered session log for planned
  work from LXR2BC and mutador.
- Added a chapter-based desktop manual, with unverified procedures clearly
  marked for later hardware checking.
- Expanded the MIDI and clock chapter using the current desktop menus and
  parser, including code-specific sync modes and routing choices.
- Added a staged mutador import plan with dependencies and validation gates.
- Recorded the P00 baseline build attempt and a source-to-target feature
  matrix.
- Verified a GCC 14.3 desktop baseline image and a Rust-accelerated Euclid
  emulator smoke test; official 1.71 parity and hardware testing remain open.
- Documented the mutador versus desktop MIDI contract and CC collision risks
  before any P01 firmware change.

The Pch/CPU work is an initial, experimental slice. Hardware validation is
still pending; see session 007.
