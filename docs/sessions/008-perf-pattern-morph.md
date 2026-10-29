# Session 008 — PERF pattern shortcut and morph correction

Date: 2026-10-29
Branch: `fix/perf-pattern-morph`
Source image tested on hardware: `LXR_V2_V1.7_Mutador0.1.img`

## Device report

- The 0.1 image booted; CPU meter showed 67% in the reported state.
- A different Morph kit was loaded and the Morph value changed, but there was
  no audible morph effect.
- Desired gesture: SHIFT + Step 1 enters pattern selection while the PERF
  display with BPM remains. SHIFT + PATTERN keeps its dedicated pattern page.

## Changes

- SHIFT + Step 1 sets pattern-selection mode from PERF without changing the
  menu page; pattern LEDs are initialized. Releasing SHIFT then pressing a
  step button selects a pattern. Other SHIFT + Step 1 contexts are unchanged.
- Pattern selection now requests Euclid parameters for the active voice rather
  than using the menu page number, which could be outside the voice range.
- The nonblocking morph walk now follows `parameterOrder`, as full kit loading
  does. It skips `PAR_BANK_CHANGE` (which previously wrapped to CC 0), empty
  placeholders, morph target selectors and the Morph-kit destination field.
  Audio routing remains sourced from the current kit.
- Bumped the image filename suffix to `Mutador0.1.1` and archived the 0.1.1
  image separately from the 0.1 rollback image.

## Validation

- ARM GCC 14.3 syntax checks passed for the changed C files.
- Release Ninja build passed 4/4 steps, then a final 3/3 rebuild after the
  pattern-index correction. Image size: 275,220 bytes; SHA-256:
  `047992BA5A9EEDEA29A05A33DA6E0D79C6C1D7268EE8A33A2CA59AE2DD18B9B8`.
- Hardware retest of pattern selection and Morph audio: pending.

## Next step

On the device, keep a known audible source kit, load a clearly different
Morph kit through LOAD + MORPH, then move Morph from 0 to 255. Also test SHIFT
+ Step 1 from PERF, release SHIFT and select a pattern while BPM stays visible.
