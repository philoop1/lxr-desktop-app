# Session 022 — step, scale and audio import

Date: 2026-10-30. Branch `feature/global-load-switches`, based on `9c98ebe` with previous uncommitted Mutador work. Reference: `I:/Github/mutador` at `7319e19b1435dc5a127108367f812c4187f7c025`.

## Implementation

- Imported Mutador's held multi-step selection gesture and applied it to desktop 64-step patterns. Notes, velocity, probability, flam, shift and both automation slots can be edited as a group.
- Imported global `scl` grids: 16, 12a, 12b and 12c. The 12-step modes skip one source step per group of four. Running changes queue to the pattern boundary. The desktop has no original per-pattern scale field, so `pat` uses the existing 16-step timing.
- Imported Mutador's same-tick half-closed hi-hat velocity and geometric-mean decay.
- Imported independent six-voice and master VCAs, CC20–26, plus seven external sends CC30–36. NORMAL/AFL/PFL/CFL and stereo/bipolar routing feed physical output 2. The master send taps the main sum after the master filter. The built-in FX bus still works.
- Imported the master LP/HP filter with cutoff CC37, resonance CC38, drive CC39, and Global `mfl` enable. `gfl` was intentionally excluded by request.
- Startup display reads `LXR2 Mutador` and `Mutador 0.1.14`.

## Storage and controls

`mfl`, `scl` and `fxs` use the last three slots in the legacy 64-byte globals block, leaving old offsets unchanged. Eighteen additional performance controls live in a 27-byte checked `MUTA.CFG` sidecar in the current project folder. Missing or damaged sidecars load neutral defaults. Saving Globals or Project writes it; simply leaving a page does not auto-save. Back up `MUTA.CFG` with project data. Global `fxo` and the additional PERF pages are described in the performance manual. Pch CC80–83 select the four explicit grids.

## Verification

GCC 14.3.rel1 release Ninja build passed 5/5 steps after the final display and navigation changes. ELF text 303196, data 880, bss 342808 bytes; ITCM 13744/16384. Image `LXR_V2_V1.7_Mutador0.1.14.img` is 304100 bytes, SHA-256 `F2FA7E606D816036E2FCD58B12950177313E5539F0429F5C7985CA461949E3CD`.

Native comparison tests passed: audio 10616322 assertions, step/scale/hat/storage 127109, MIDI 352168, performance 56858. An initial ARM build authorization was rejected; a later authorized build succeeded. Device sound, CPU headroom, timing, SD save/reboot and old-project reload still require hardware checks.

The prior 0.1.13 card image was backed up to `build/card-image-backups/20261030-import-0.1.14`. The `LXRO2` card now has only the 0.1.14 update image at its root; copied hash matches the archive. Project files on the card were untouched.

## Remaining imports

Mutador's LFO **Stray** and **Glide** waveforms, Snare noise envelope, and the third `rng` drum oscillator mix mode are still absent from this desktop port. The source also has Membrane body and further Snare layers. Import them separately with kit/morph compatibility tests. Official 1.71 Euclid parity and physical-device behavior remain open.
