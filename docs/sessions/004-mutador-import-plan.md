# Session 004 — mutador import plan

Date: 2026-10-29
Branch: `docs/development-notes`
Source project and commit: mutador `7319e19b1435dc5a127108367f812c4187f7c025`
Target main commit: `a43cd4fcda23ec3d577dc425261c3eb28bd5abff`

## Goal

Turn mutador's feature list into reviewable desktop-firmware sessions.

## Changes

- Added [the import plan](../IMPORT_MUTADOR_PLAN.md), with scope, dependencies,
  acceptance checks and an immediate baseline TODO.
- Identified existing desktop areas that must be compared before porting:
  MIDI, probability, shuffle, storage and FX.
- Kept Euclid 1.71 status open pending behavioral or binary comparison.

## Validation

- Planning documents only; no firmware source was changed.
- Firmware build and hardware test: not run for this planning session.

## Open questions and next step

Execute P00, then choose the first implementation session from the measured
feature matrix.
