# Changelog

Changes in this fork relative to
[Erica Synths' lxr-desktop-app](https://github.com/erica-synths/lxr-desktop-app)
are recorded here. The upstream project keeps its own Git history.

## Unreleased

### Mutador 0.1.2 (hardware test pending)

- Added `lsh` and `lmp` immediately after the CPU meter on the second CONFIG
  page. `lsh` chooses whether a pattern change loads that pattern's shuffle;
  `lmp` chooses whether loading a kit also selects its saved Morph target.
- Kept `KCM` as the existing kit-on-pattern-change switch; the proposed `lki`
  would have duplicated it and was omitted.
- Loading a Morph kit now marks the current kit as changed so its Morph-target
  slot can be saved with the kit/project.

### Mutador 0.1.1 (hardware retest pending)

- SHIFT + Step 1 enters pattern selection from PERF while keeping the PERF
  display with BPM and the other live settings visible. SHIFT + PATTERN still
  opens the dedicated pattern-selection display.
- Pattern selection requests Euclid data for the active voice, avoiding a
  menu-page index outside the voice range.
- Changed the morph update to use kit-load parameter order and skip placeholder
  CC 0 and non-morphable target selectors. This addresses code defects found
  after an on-device report that the Morph value changed but the sound did not.
- Archived the new `LXR_V2_V1.7_Mutador0.1.1.img` separately from 0.1 for
  straightforward rollback.

### CONFIG and SD card

- Added saved `Pch` beside global `ch` on the first CONFIG page. It defaults to
  MIDI channel 2 and accepts CC 2 for kit morph when its channel does not
  overlap a voice or global channel. Other performance CCs are still planned.
- Added a read-only CPU meter on the second CONFIG page. It shows the peak
  audio-block processing load over each half-second interval.
- Added the 1.6-era SD-card data backup to version control. The local
  `bootloader.img` is excluded from Git and is not part of this backup commit.
- Named the experimental update image `LXR_V2_V1.7_Mutador0.1.img` and archived
  it beside the unchanged 1.7 baseline image with SHA-256 hashes.

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
