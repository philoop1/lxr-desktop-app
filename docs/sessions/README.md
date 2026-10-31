# Session log

Numbered notes track experiments and decisions for this fork. They complement
Git commits and the user-facing [changelog](../../CHANGELOG.md). The full
source context remains in the LXR2BC and mutador repositories; their old
session logs are not history of this fork.

| Session | Date | Topic |
| --- | --- | --- |
| [001](001-development-workflow.md) | 2026-10-29 | Set up development documentation |
| [002](002-desktop-manual.md) | 2026-10-29 | Add chapter-based desktop manual |
| [003](003-midi-manual.md) | 2026-10-29 | Expand MIDI and clock chapter |
| [004](004-mutador-import-plan.md) | 2026-10-29 | Plan mutador import sessions |
| [005](005-p00-baseline-audit.md) | 2026-10-29 | P00 build attempt and feature matrix |
| [006](006-p01-midi-comparison.md) | 2026-10-29 | Compare mutador and desktop MIDI contracts |
| [007](007-pch-cpu-sd-backup.md) | 2026-10-29 | Add Pch, CPU meter and SD-card data backup |
| [008](008-perf-pattern-morph.md) | 2026-10-29 | PERF pattern shortcut and morph correction |
| [009](009-global-load-switches.md) | 2026-10-29 | Shuffle and Morph load switches |
| [010](010-morph-master-sample-rate.md) | 2026-10-29 | Master sample rate across the Morph range |
| [011](011-load-sample-rate.md) | 2026-10-29 | Global lsr switch for master sample rate |
| [012](012-performance-checkpoint-and-plan.md) | 2026-10-29 | User hardware confirmation and next import batch |
| [013](013-midi-channel-audit.md) | 2026-10-29 | Channel priority, CC table and parser regression tests |
| [014](014-mutador-note-routing.md) | 2026-10-29 | Mutador drum-map, Voice note routing and Pch transpose |
| [015](015-card-midi-channels.md) | 2026-10-29 | SD-card channel configuration; Chan excluded |
| [016](016-complete-pitch-and-perf.md) | 2026-10-29 | Complete Mutador pitch, PERF gpt/pbr and SD update |
| [017](017-performance-variations-and-link.md) | 2026-10-29 | GDC, RST/CSR, BC Scarcity, PST and 606 pattern range |
| [018](018-accent-and-midi-delay.md) | 2026-10-29 | Velocity Accent, MIDI Delay, CNT, shortcuts and image 0.1.10 |
| [019](019-shuffle-and-project-load-audit.md) | 2026-10-30 | Shuffle timing comparison, SHIFT+4 and project-load diagnosis |
| [020](020-four-point-groove.md) | 2026-10-30 | Four-point Groove, 192 PPQ events, Delay/Clock and lsh hold |
| [021](021-load-labels-and-16sh-clock.md) | 2026-10-30 | lki/aut labels, CPU slot swap and explicit 16sh clock |
| [022](022-step-scale-audio-import.md) | 2026-10-30 | Step groups, global grid, half-closed hi-hat, sends, VCAs, filter and image 0.1.14 |
| [023](023-snare-ring-clock.md) | 2026-10-30 | Snare Noise Envelope, Ring mode, MIDI Clock Offset and image 0.1.15 |
| [024](024-copy-start-snare-layer.md) | 2026-10-30 | Extended COPY, manual MIDI Clock bar start, Snare Layer and image 0.1.16 |
| [025](025-midi-transport-play-state.md) | 2026-10-30 | MIDI START/CONTINUE/STOP front-panel state and image 0.1.17 |
| [026](026-stray-glide-voice-cc.md) | 2026-10-31 | Stray/Glide and full common Voice-CC map |
| [027](027-pattern-scale-confirmation.md) | 2026-10-31 | Eight per-pattern scales, long PERFORMANCE and encoder-confirmed downbeat switch |
| [028](028-velocity-and-any-mode-shortcut.md) | 2026-10-31 | Any-mode SHIFT+1, rvl/avl and versioned persistence |
| [029](029-velocity-headroom-proportional-gain.md) | 2026-10-31 | Default 100, backed-up card migration and proportional positive AVL |
| [030](030-pattern-bank-freeze-investigation.md) | 2026-10-31 | MIDI-running pattern freeze fixed in 0.1.28; targeted device retest passed |

For each new session, copy [TEMPLATE.md](TEMPLATE.md), use the next number,
and record the source commit or branch, changed files, build result, hardware
test, open questions, and next step. Keep observed results separate from ideas
or expectations.
