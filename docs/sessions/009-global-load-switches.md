# Session 009 — Shuffle and Morph load switches

Date: 2026-10-29
Branch: `feature/global-load-switches`

## Decision

`KCM` already selects whether pattern changes automatically load associated
kits, so `lki` would be redundant and was not added. The requested `lsh` and
`lmp` controls are placed after the CPU meter on CONFIG page 2.

## Behavior

- `lsh=on` (default): a pattern activation loads its stored shuffle value.
  `lsh=off`: preserve the current shuffle.
- `lmp=on`: loading a source kit also activates the Morph-target slot stored
  in that kit. `lmp=off` (default): preserve the current Morph target.
- LOAD + MORPH sets the source kit's Morph-target slot and marks the kit dirty
  for the existing save flow.
- The new switches are stored after `Pch` in globals. Older `GLO.CFG` files
  remain readable, and old project padding is sanitized to the defaults.

## Validation

- ARM GCC 14.3 syntax checks passed for the modified code.
- Static parameter-offset assertions confirmed the old 30-byte globals,
  `Pch` at offset 30, `lsh` at 31, `lmp` at 32 and CPU outside stored globals.
- Approved Ninja release build passed 32/32 steps, then 3/3 after the final
  Morph-target dirty-state change. The 275,588-byte image has SHA-256
  `75CC47E9B862CB58F3F3492190BEA6356276D050F07D395BA5F5B64A41C50148`.
- Physical hardware behavior: pending.

## Device check

1. Set `lsh=off`, set a distinct shuffle value, switch patterns and confirm
   the value stays. Set `lsh=on` and confirm the pattern's value returns.
2. Load source kit A, then a distinct Morph kit B via LOAD + MORPH. Save the
   source kit/project, enable `lmp`, load A again and verify B is selected as
   the Morph target. Move Morph across its range and listen for a change.
