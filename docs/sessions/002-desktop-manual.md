# Session 002 — Desktop manual

Date: 2026-10-29
Branch: `docs/development-notes`
Source project and commit: Erica Synths desktop firmware `a43cd4f`

## Goal

Give the desktop fork a chapter-based manual that can grow with each ported
feature.

## Changes

- Added manual contents and chapters for device, voices, sequencer, storage,
  MIDI/clock and firmware update.
- Linked the manual from the main README and recorded it in the changelog.
- Kept descriptions of current behavior separate from planned BC/mutador
  features. Exact control procedures await a hardware check.

## Validation

- Markdown links and Git whitespace: checked locally.
- Firmware build: not run; only documentation changed.
- Hardware test: not run.

## Open questions and next step

Verify page names and button sequences on the LXR V2, then expand the relevant
chapters when each firmware feature is ported.
