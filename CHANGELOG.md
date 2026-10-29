# Changelog

Changes in this fork relative to
[Erica Synths' lxr-desktop-app](https://github.com/erica-synths/lxr-desktop-app)
are recorded here. The upstream project keeps its own Git history.

## Unreleased

### Development workflow

- Added build notes, a fork changelog, and a numbered session log for planned
  work from LXR2BC and mutador.
- Added a chapter-based desktop manual, with unverified procedures clearly
  marked for later hardware checking.
- Expanded the MIDI and clock chapter using the current desktop menus and
  parser, including code-specific sync modes and routing choices.
- Added a staged mutador import plan with dependencies and validation gates.
- Recorded the P00 baseline build attempt and a source-to-target feature
  matrix; no mutador firmware feature has been imported.
- Verified a GCC 14.3 desktop baseline image and a Rust-accelerated Euclid
  emulator smoke test; official 1.71 parity and hardware testing remain open.
- Documented the mutador versus desktop MIDI contract and CC collision risks
  before any P01 firmware change.

No LXR2BC or mutador firmware feature has been imported into this fork yet.
When one is merged, describe its user-visible behavior here and link the
relevant session record and validation.
