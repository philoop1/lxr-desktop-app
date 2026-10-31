# Session 024 — COPY, manual bar start and Snare Layer

Date: 2026-10-30. Branch `feature/global-load-switches`, carrying earlier
uncommitted import work. Mutador reference
`7319e19b1435dc5a127108367f812c4187f7c025`.

## Source and adaptation

- Mutador has separate COPY operations for a track across patterns, a full
  main step and an individual substep. Desktop stores 64 linear Steps per
  pattern, each with its own Flam/Shift timing. COPY now handles an individual
  complete desktop Step, a group of eight, a full pattern and a single track
  into any of 64 pattern slots. A track copy includes note/velocity/probability,
  two automation lanes, Flam/Shift, main-step bits and track length. It leaves
  the destination pattern's kit and shuffle assignment intact.
- Under MIDI Clock, manual PLAY while stopped arms for the next 96-pulse bar.
  It uses the configured Clock Offset to predict the first step before the
  actual bar edge when a stable incoming period exists. That edge confirms
  the start without playing step 1 twice. MIDI START and analogue EXT retain
  their prior handling; if no MIDI phase has been received, PLAY starts
  immediately. This is separate from the ordinary step Clock Offset.
- The Snare adds a second tonal oscillator with `slw` wave, `sla` amount,
  `slf` frequency ratio and `slm` Mix/FM/Ring. `sla=0` preserves the legacy
  oscillator path. Mix blends tonal oscillators, FM runs the main oscillator
  through the existing FM block, and Ring blends the main signal with the
  oscillator product. The new controls are on the Snare's fourth page beside
  the Noise Envelope.
- Four new sound IDs are appended; existing IDs are unchanged. New kit data
  uses an `SNE2` marker inside the fixed 512-byte project kit block. Existing
  `SNE1` kits retain their three Noise Envelope values and default the layer
  to wave 0, amount 0, ratio control 25 and Mix mode. Earlier kits default
  both extensions. Morph and normal kit transmission include the new IDs.

## Verification and image

ARM GNU 14.3.rel1 release Ninja build passed. ELF text 309508, data 888,
bss 344536 bytes; ITCM 13976/16384, DTCM 107624/131072. Final archived
`LXR_V2_V1.7_Mutador0.1.16.img` is 310420 bytes with SHA-256
`FCC35C9BC4DC5D0584167E292ACC19F84A5CEB2C10ADC39B65BF25B253619DF1`.
The build prints the 310404-byte firmware payload; the update file adds a
16-byte `LXRV2IMG` header. The archive and finished build output were hash
compared.

Native source contract tests: Voice Import 2449 assertions, MIDI 352168,
Edit/Scale/Hat/Storage 127112, Performance 56872 including predictive
manual start without a duplicate step, Project Loader 5. COPY test checks
Step data, Flam/Shift, on/off bits across bars, eight-step groups and a
track copied into slot 64 (25 assertions).

The prior 0.1.15 card image was hash checked and backed up under
`build/card-image-backups/20261030-copy-start-snare-0.1.16`. The 0.1.16
image was copied to F: and verified against the archive; only then was the
old root update removed. The card root now contains the 0.1.16 update.
No project, sample or configuration file was changed. On-device sound,
CPU, COPY button behavior, old/new kit save and Morph, and MIDI Clock timing
still require instrument checks.
