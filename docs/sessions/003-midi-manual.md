# Session 003 — MIDI and clock manual

Date: 2026-10-29
Branch: `docs/development-notes`
Source project and commit: Erica Synths desktop firmware `a43cd4f`

## Goal

Expand the MIDI chapter from a placeholder to a usable guide for the current
desktop fork.

## Changes

- Compared the provided LXR-02 manual's global settings with the desktop
  menu, MIDI parser, sequencer and analogue clock input.
- Documented channels, note triggering, filters, routing, sync modes, PPQ
  options and basic troubleshooting.
- Called out the code-specific `MID` tempo mode and `M2A` routing option,
  which are not described in the provided manual's table.

## Validation

- Checked setting names and behavior against source code.
- Firmware build: not run; only documentation changed.
- Hardware test: not run. Routing and synchronization remain to be checked.

## Open questions and next step

On the desktop unit, verify `EXT` versus `MID`, USB/DIN routing (especially
`M2A`) and whether the transmit CC filter applies to all outgoing CCs.
