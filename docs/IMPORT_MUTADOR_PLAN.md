# mutador → LXR V2 desktop: import TODO

Status: planning only. No mutador firmware feature has been ported here.
The [P00 feature matrix](MUTADOR_FEATURE_MATRIX.md) records the first
source-to-target comparison and its unresolved checks.

P00 progress (2026-10-29): source equivalence to target `main` confirmed;
GCC 10.2 compiled the sources but failed at the linker script. A GCC 14.3
retry was rejected by the command approval system. No baseline image or
hardware result is available yet. See [build notes](../BUILD_NOTES.md) and
[session 005](sessions/005-p00-baseline-audit.md).

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

- [ ] P00: build and test the untouched desktop baseline.
- [ ] P00: determine whether the Euclid fix from official 1.71 is present;
      do not infer this from the `1.7` version label alone.
- [x] P00: create a first source-to-target feature matrix with concrete
      files, symbolic parameter IDs, MIDI CC ranges and storage fields.
- [ ] P00: validate the matrix's unknown behavior and numeric CC collisions
      before choosing P01/P02.
- [ ] Decide the first feature batch after that matrix. P01 (MIDI contract)
      or a narrowed P02 (step tools) are reasonable starting points.

## Scope guard

The mutador changelog is a feature inventory, not evidence that those
features run on LXR V2 desktop. Its existing `.BIN` image and AVR/STM32F4
build steps are not desktop update artifacts. No box in this plan should be
checked off without desktop-source and hardware evidence.
