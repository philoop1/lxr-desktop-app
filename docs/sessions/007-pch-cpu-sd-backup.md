# Session 007 — Pch, CPU meter and SD-card backup

Date: 2026-10-29
Branch: `feature/pch-cpu`
Source: mutador Control-channel and CPU-meter implementations, adapted to the
desktop STM32F765 single-processor firmware.

## Changes

- Place `Pch` immediately after global `ch` on the first CONFIG page. Move
  screensaver (`ssv`) to the second page, next to the read-only `CPU` meter.
- Save `Pch` with global/project settings, default to channel 2 and accept
  older `GLO.CFG` files and project padding without changing their total size.
- Route CC 2 on a non-overlapping `Pch` to kit morph. More performance CCs
  remain a separate P01 import step.
- Measure peak audio-block processing time with the Cortex-M DWT cycle counter.
- Track the 1.6-era `SD-Card/` data backup, excluding the local
  `bootloader.img`. The firmware has `UPDATE_BOOTLOADER` set to 0.

## Validation

- ARM GCC 14.3 syntax checks passed for the changed C translation units.
- Full release build: ARM GCC 14.3, Ninja 34/34 steps after approval. The new
  `build/release/LXR_V2_V1.7_Mutador0.1.img` is 275,132 bytes, SHA-256
  `C5D2AE5C0F07C0A06AC888457AA051448B2380111373A7CA7E09D126853B983F`.
- MIDI behavior, CPU percentage and legacy SD loading on hardware: pending.

## Next step

Test Pch CC 2 on a MIDI channel distinct from all voice/global channels and
check the CPU display with an idle and busy kit.
