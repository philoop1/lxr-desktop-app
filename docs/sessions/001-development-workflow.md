# Session 001 — Development workflow

Date: 2026-10-29
Branch: `docs/development-notes`
Source project and commit: Erica Synths desktop firmware `a43cd4f`

## Goal

Prepare a clear record for gradually porting features from LXR2BC and mutador
into this desktop firmware fork.

## Changes

- Created `BUILD_NOTES.md` for exact build and hardware-test results.
- Created `CHANGELOG.md` for changes visible to users of this fork.
- Created this numbered session log and a template for later work.
- Kept the upstream README as the authoritative build and installation guide.

## Validation

- Documentation links checked locally; `git diff --check` passed.
- Firmware build: not run; no firmware source changed.
- Hardware test: not run.

## Open questions and next step

Choose one small feature to port first. Compare its LXR2BC or mutador source
with the desktop firmware, implement it on a dedicated branch, then record
the build and on-device behavior before merging.
