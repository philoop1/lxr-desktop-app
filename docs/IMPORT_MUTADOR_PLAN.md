# mutador → LXR V2 desktop: import TODO

Status (2026-10-29): implementation has begun. P01 is partial; performance
corrections and load policies were implemented ahead of the larger import.
The [P00 feature matrix](MUTADOR_FEATURE_MATRIX.md) records the first
source-to-target comparison and its unresolved checks.
The [P01 MIDI comparison](P01_MIDI_COMPARISON.md) identifies channel,
note, CC and storage differences before implementation.

P00 progress (2026-10-29): source equivalence to target `main` confirmed.
GCC 10.2 failed at link; the user then built with GCC 14.3. The image hash,
size and basic Euclid behavior were checked in the Rust-accelerated IMG-live
emulator. Official 1.71 fix parity and physical hardware remain open. See
[build notes](../BUILD_NOTES.md) and
[session 005](sessions/005-p00-baseline-audit.md). Later fork images booted
on hardware, and the user reported 0.1.4 works. This does not complete the
baseline's MIDI, storage, sync or official Euclid comparison checks.

## Current implementation and next batch

- 0.1.8 implements the user's clarified batch: Mutador gdc next to gpt,
  rst and csr, BC Scarcity, global pst and a desktop 64-pattern 606 live range.
  P02/P06/P07 now have partial implementations; neither the larger MIDI delay
  nor optional 606 state persistence is included. Existing step probability
  remains active. Native scheduler/dispatcher/old-globals tests and release
  build passed; hardware validation is pending. See session 017.
- 0.1.10 adds the Velocity/Accent page, MIDI Delay page, `cnt`, instrument
  input-mask LEDs and shortcuts. Native tests and the release build passed;
  hardware timing/CPU and save/reboot remain open. See session 018. P05/P07
  are partially implemented.
- 2026-10-30 load audit found duplicate blank/named Pattern 00 files on the
  card and a stale edit backup on project activation. Source fixes are built
  locally as 0.1.11; hardware validation and exact Mutador four-point groove
  (`shf` plus SH2/SH3/SH4) remain open. See session 019.
- Follow-up 0.1.12 implements the four-point Groove on a 192 PPQ event grid,
  SHIFT+4, signed note/automation and repeat-lane timing, physical 2/4 PPQ
  groove clock and Pch CC40..43. Shapes save in appended globals; lsh OFF
  holds the live groove on load. Reference/native tests and release build
  passed. Hardware timing, CPU and save/reboot remain open. See session 020.
- 0.1.7 completes the requested Mutador pitch composition, adds PERF gpt/pbr,
  Pch CC27 and global/voice bend. Pch-note interception now matches Mutador's
  pre-filter/pre-Thru behavior. Native parity checks and release build passed;
  image copied to the card. Test this on hardware before the next P01 batch.
  Global/voice/overlap bend, old globals loading and PERF save/reboot remain
  device checks. No compact Voice CC map or Pch CC1 has been added.
- 0.1.6 implements the clarified Mutador note contract (not LXR2BC): Global
  fixed-note map/ANY fallback, chromatic Voice reception without echo, and
  Pch-note master transpose. Includes the CC channel-index correction. Release
  build and 312125 native assertions passed; DIN/USB hardware checks remain.
  See [session 014](sessions/014-mutador-note-routing.md). Next, test this
  image before extending Pch CC1 or adding the compact Voice CC map.
- Channel/CC audit: [results](P01_CHANNEL_AUDIT.md), complete numeric table
  and 147633 native assertions recorded. Corrected a legacy voice-channel
  index error in 0.1.5 source; firmware build and hardware test remain open.
  The user clarified the intended reference was Mutador; implemented in
  0.1.6 as recorded above. No new Pch CC1 was added.
- Implemented: initial `Pch` setting and Morph CC2 reception, CPU meter,
  PERF-preserving pattern shortcut, corrected Morph parameter updates,
  master `srt` independent of the Morph target, and `lsh`/`lmp`/`lsr` policies.
- User device feedback: 0.1.2 Morph target selection works; 0.1.4 reported
  working after the `srt` and `lsr` changes. No separate persistence or full
  MIDI/sync regression result has been recorded.
- `Pch` belongs to P01. It is separate from the performance issues the author
  reports having raised with Erica Synths for years.
- P03 load policy and P06 kit/Morph loading have partial groundwork only.
  Four-step groove was subsequently added in 0.1.12. Global scale and the
  larger pattern-loading work remain.

Recommended sequence:

1. Preserve 0.1.4 as the current device-tested checkpoint. Verify project
   save/reboot of `lsh`, `lmp` and `lsr`, manual/automatic kit changes and
   Morph 0/128/255, then commit the changes and records.
2. Continue P01 with a narrow channel-contract session: numeric CC collision
   table, Pch/global/voice overlap priority, DIN/USB and RX-filter tests.
   Add Control CC1 for the now-correct master `srt` beside existing CC2 Morph
   only after that priority is defined. Preserve legacy channel mappings.
3. Follow with P01 note routing/recording, then compact voice CCs in their
   own small batches. Keep MIDI delay in P05.
4. Complete the outstanding P00 Euclid 1.71 comparison and baseline tests
   before changes to sequencer timing, groove or clock behavior.

See [session 012](sessions/012-performance-checkpoint-and-plan.md) for the
hardware report and the distinction between fixes and MIDI import work.

Source snapshot: `I:/Github/mutador` at commit `7319e19b1435dc5a127108367f812c4187f7c025`.
Target baseline: `I:/Github/lxr2-Mutador` main at commit
`a43cd4fcda23ec3d577dc425261c3eb28bd5abff` (CMake version 1.7).
Refresh these commits before starting a session; do not silently change the
source snapshot in the middle of a port.

mutador targets the original LXR with an AVR front panel and STM32F4
mainboard. This repository targets the LXR V2 desktop on STM32F765. Port the
**behavior**, adapting its data flow, menu, MIDI, DSP and storage to the
desktop code. Copying source files wholesale would bypass that integration.

## Working rule for each implementation session

- Use a dedicated branch from an agreed integration base. Several small,
  related changes may share a branch when they can be reviewed and tested
  together; unrelated or high-risk changes get separate branches.
- Before editing, compare the existing desktop behavior and mutador source.
  Mark each candidate **already present**, **different**, **to port** or
  **deferred**. The desktop already has MIDI, step probability, shuffle,
  pattern/project storage and FX; do not reimplement them blindly.
- Define the exact user-visible behavior, data ranges, MIDI messages and
  file-format impact. Keep old desktop projects loadable where possible.
- Record a release build and image size in `BUILD_NOTES.md`; test the behavior
  and save/load on hardware before declaring the session complete.
- Update `CHANGELOG.md`, the relevant manual chapter and a numbered
  `docs/sessions/` record. A successful compile alone is not a feature test.

## Proposed sessions

The numbers below are **plan IDs**, not existing session-log numbers. Create
the next free numbered log file when work actually begins. Dependencies are
listed so work can be reordered without pretending it is complete.

| ID | Candidate branch | Scope and useful grouping | Depends on | Done when |
| --- | --- | --- | --- | --- |
| P00 | `audit/desktop-baseline` | Build unmodified desktop source; record compiler, image, SD backup and hardware smoke test. Compare Euclid behavior against official 1.71; its fix is currently unverified in this source. Inventory desktop menus, preset formats and parameter IDs. | — | Baseline image boots; play, save/load, MIDI and Euclid observations recorded. |
| P01 | `feature/midi-control` | Compare and port mutador's global/control/voice channel behavior, per-voice CC map, live note recording and pitch bend as one MIDI contract. Preserve the desktop's existing DIN/USB routing. | P00 | DIN and USB note/CC tests, recording and old MIDI behavior pass; manual MIDI table updated. |
| P02 | `feature/step-tools` | Add missing step probability extensions, repeat chance, random velocity and copy of tracks/main steps/substeps. Split the branch if the edit UI or storage format grows too large. Multiple-step selection was discussed separately but is not confirmed in mutador's changelog; keep it out of this import until its source is identified. | P00 | Edits play as shown by LEDs and survive pattern/project save/load. |
| P03 | `feature/groove-scale` | Compare desktop shuffle with mutador's four-step groove, `gsc` grid override and `shf` load policy. Keep pattern-local versus global settings explicit. | P00, P02 | Internal playback, pattern switches and saved projects reproduce the same groove/grid. |
| P04 | `feature/clock-sync` | Port only the missing predictive start, fine clock offset and groove-aware analogue clock outputs; preserve desktop `EXT`/`MID` semantics and existing PPQ options. | P00, P03 | Bench test DIN/USB/analogue sync, repeated starts and output pulse timing. |
| P05 | `feature/midi-delay` | Port performance MIDI delay with per-track sends, chance, pitch, repeat/bounce and mono/poly modes. Start with one working delay chain, then add the related controls in small commits. | P01, P03, P04 | Internal and external clock timing, simultaneous voices, note-off/gate behavior and save/load pass. |
| P06 | `feature/pattern-performance-load` | Port 606-style pattern linking, active-pattern restore, Quick Load feedback and bar-quantized kit/pattern publication. Avoid changing SD formats until the desktop layout is mapped. | P00, P03 | Playing loads switch together at the intended boundary; old projects still load. |
| P07 | `feature/performance-macros` | Port global pitch/decay, accent and velocity destinations, and held/smooth random LFO modes. Separate sound controls from MIDI mapping already handled in P01. | P01, P06 | Kit/morph changes, modulation and saved values match the displayed controls. |
| P08 | `feature/master-fx` | Port master LP/HP filter, bypass transitions, post-filter FX send and optional bipolar L2/R2 routing. Inspect existing desktop FX first. | P06, P07 | Audible routing, neutral positions, transitions and CPU headroom checked on all outputs. |
| P09 | `feature/voice-synthesis` | Evaluate half-open hi-hat, Membrane body and additional Snare layer/noise envelope as separate small feature branches if needed. Each changes synthesis and likely preset data. | P00, P07 | Each voice sounds correct, old kits load, new settings round-trip and CPU remains safe. |
| P10 | `perf/audio-optimization` | Evaluate silent-voice sleep, decimator fast paths and mixer optimizations only after a stable feature baseline. | P08, P09 | A/B listening and CPU measurements show no unwanted sound or timing change. |
| P11 | `release/desktop-preview` | Integrate accepted branches, update banner/version, complete manual and changelog, build image, test fresh/old projects and recovery path. | Selected completed sessions | Reproducible candidate image and signed-off hardware checklist. |

## Immediate TODO

- [x] P00: build the untouched desktop baseline with GCC 14.3 and run an
      emulator Euclid smoke test. Physical hardware testing is still open.
- [ ] P00: determine whether the Euclid fix from official 1.71 is present;
      do not infer this from the `1.7` version label alone.
- [x] P00: create a first source-to-target feature matrix with concrete
      files, symbolic parameter IDs, MIDI CC ranges and storage fields.
- [ ] P00: validate the matrix's unknown behavior and numeric CC collisions
      before choosing P01/P02.
- [x] First feature batch started: P01 has an initial Pch/Morph CC2 slice.
- [ ] Stabilize and commit the 0.1.4 performance checkpoint after persistence
      and kit-change checks; keep Pch listed as separate P01 scope.
- [ ] Next P01 batch: complete channel precedence and numeric collision tests
      before extending the control map or changing note routing.

## Scope guard

The mutador changelog is a feature inventory, not evidence that those
features run on LXR V2 desktop. Its existing `.BIN` image and AVR/STM32F4
build steps are not desktop update artifacts. No box in this plan should be
checked off without desktop-source and hardware evidence.
# 2026-10-30 checkpoint: image 0.1.14

Session [022](sessions/022-step-scale-audio-import.md) completes the source import of held multi-step selection, global 12-step grids, same-tick half-closed hi-hat, external FX sends, independent VCAs and master filter. The 0.1.14 image was built and copied to the LXRO2 card. Device verification is pending. The older planning rows below are historical and may describe those items as open.

The next synthesis candidates are LFO Stray/Glide, Snare noise envelope, and the `rng` drum oscillator mode. Membrane body and extra Snare layers remain separate candidates. Importing any kit parameter requires explicit old-kit and Morph compatibility checks.

## 0.1.15 follow-up

Session [023](sessions/023-snare-ring-clock.md) imports Snare Noise Envelope, `rng` Ring mode and the confirmed MIDI Clock Offset with coarse/fine Global display. Session [024](sessions/024-copy-start-snare-layer.md) adds desktop-adapted COPY, predictive manual MIDI Clock bar start and the second Snare oscillator. Physical sound, DIN/USB timing and saved-kit checks remain open. LFO Stray/Glide and Membrane remain separate candidates.

## 0.1.22 current checkpoint

Stray/Glide and the complete common Voice-CC table (excluding Membrane)
are now imported. The preceding candidate lists are historical. Random
Velocity, quarter-position scl commit, and per-pattern scale remain open.
See session 026 and the manual for normalized desktop LFO behavior and CC
channel priorities. Hardware parity has not been established by native tests.

## Current Scale update in 0.1.22

Session 027 implements per-pattern 2/4/6/8/12/16/24/32, long PERFORMANCE,
encoder preview/confirmation and next-bar Step-1 switching. This supersedes
the preceding open scale items and 12a/b/c planning. Random Velocity and
Membrane remain absent; hardware verification remains open.

## 0.1.23 velocity checkpoint

Random Velocity is now imported, together with the new AVL control applied
after it, and SHIFT+Step 1 from every mode. See session 028. This supersedes
the earlier missing-Random-Velocity lists. Hardware verification remains open;
Membrane is still intentionally excluded.
