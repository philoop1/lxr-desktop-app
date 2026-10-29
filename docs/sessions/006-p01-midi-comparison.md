# Session 006 — P01 MIDI comparison

Date: 2026-10-29
Branch: `audit/midi-contract`
Source commits: mutador `7319e19b`, desktop main `a43cd4f`

## Goal

Compare MIDI behavior before porting mutador features to the desktop fork.

## Changes

- Added [P01 comparison](../P01_MIDI_COMPARISON.md) for channels, notes,
  recording, CC collisions, routing, filters, clock and saved settings.
- Split P01 into channel, note, Voice CC and Control CC/bend slices.

## Validation

- Findings checked in both code trees; no firmware code changed.
- Build/hardware test: not applicable to this documentation-only audit.

## Next step

Implement the saved Control/PC channel and channel precedence in a separate
feature branch, then run focused MIDI tests before changing note behavior.
