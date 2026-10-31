# Build notes

This is the working build record for the `philoop1/lxr-desktop-app` fork. It
starts from the Erica Synths desktop firmware, version 1.7. Record measured
results here when porting features from LXR2BC or mutador; do not treat a
successful compile as proof that a feature works on hardware.

## Baseline

- Upstream: `erica-synths/lxr-desktop-app`, branch `main`.
- Current fork code: unchanged from upstream at the start of this log.
- Target: LXR V2 desktop, STM32F765VG.
- Toolchain and installation instructions: [README.md](README.md).

## Reproducible build

From the repository root:

```sh
cmake --preset release
cmake --build --preset release
```

The current archived build is Mutador 0.1.26. It retains the default step
velocity 100 from 0.1.24 and applies proportional AVL gain after rvl in both
directions (+50=x1.5, +100=x2, clipped at 127). Release build and the 196491
native velocity/shortcut checks passed. The card is hash-verified at 0.1.25.
The one-time card velocity migration has a complete original/staged backup
and passed 1262958 assertions through the production C pattern loader.
Physical-device sound/controller validation remains open.

The update image is written under `build/release/` as
`LXR_V2_V1.7_Mutador0.1.26.img`. The base version comes from
`project(VERSION ...)` in `CMakeLists.txt`; the fork suffix is set separately
there. For a debug build, use the `debug` preset in both commands.

### Exact Windows commands on this machine

The CMake and Ninja executables come from Visual Studio 2022. The locally
available ARM GNU Toolchain 14.3 is under `I:/Github/Lxr2rea/build/`.
PowerShell commands from `I:/Github/lxr2-Mutador`:

```powershell
$cmake = 'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
$ninjaDir = 'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja'
$armDir = 'I:\Github\Lxr2rea\build\arm-gnu-toolchain-14.3.rel1\bin'
$env:PATH = "$ninjaDir;$armDir;$env:PATH"

& $cmake --preset release --fresh -DARM_TOOLCHAIN_DIR='I:/Github/Lxr2rea/build/arm-gnu-toolchain-14.3.rel1/bin'
& $cmake --build --preset release
```

`--fresh` matters after switching compilers: CMake otherwise keeps the old
compiler recorded in `build/release/CMakeCache.txt`. Confirm the configure
output names GCC 14.3 before building. The `mkimage.py` step also needs a
working Python 3 on PATH; the build output shows which Python was selected.
These commands produced a release image on 2026-10-29. Keep the compiler
version and image hash with every later build; a different image needs its
own emulator-profile validation.

The BC/mutador build notes document separate AVR + STM32F4 binaries and a
combined `FIRMWARE.BIN`. Those commands, flash limits and output file are not
valid for the desktop STM32F765 image. For this repository use its CMake
presets and the resulting desktop `.img`.

## Build record

| Date | Branch / commit | Command | Result | Hardware check |
| --- | --- | --- | --- | --- |
| 2026-10-30 | `feature/global-load-switches`, uncommitted; GCC 14.3.rel1 | 0.1.13 release rebuild | Initial approval rejected; approved retry found a missing TriggerOut include; corrected final build passed 9/9 steps. ELF text=294172, data=880, bss=341436. IMG 295076 bytes, SHA-256 `DCBF5B7176BA30D80DE17DA99E08C7E4C1FCA85C5CEDFC63E4B7F8FC5154BB07`. 1531942 Groove/clock assertions passed; F: copy hash-verified. | User reports 0.1.12 works; new 0.1.13 LCD/CKO check pending. |
| 2026-10-30 | `feature/global-load-switches`, uncommitted; GCC 14.3.rel1 | Final 0.1.12 Groove/Clock/lsh release rebuild | 7/7 steps. ELF text=293972, data=880, bss=341436. Actual IMG 294876 bytes, SHA-256 `14868D0050D68DD322AB7B550B298427758B3A0EDAC06AAC792395A1CDE8F621`. Native assertions: 1531928 Groove/reference/clock-output, 351790 MIDI, 56735 performance/clock/load, five FAT cases. See session 020. | Sound, CPU, MIDI/analog jitter and save/reboot pending. |
| 2026-10-30 | `feature/global-load-switches`, uncommitted; GCC 14.3.rel1 | Release build for local 0.1.11 project-loader fix and SHIFT+4 shortcut | 4/4 steps. ELF text=290924, data=880, bss=341348. Native suites: 351206 MIDI and 48333 performance assertions; five real-source FAT wildcard cases. | Not tested; not copied to F:. |
| 2026-10-29 | `feature/global-load-switches`, uncommitted; GCC 14.3.rel1 | Release build for 0.1.9 (intermediate) | 36/36 steps, then 3/3 after Accent automation correction. Image 291748 bytes, SHA-256 `410ACCC64D637874915FD7DA6962BCE7A1C12DD2C38A3EA3C0C09EFBAD1876B5`. | Not tested. |
| 2026-10-29 | Same branch; GCC 14.3.rel1 | Final release rebuild for 0.1.10 | 3/3 steps after exact 96 PPQ triplet correction. ELF text=290844, data=880, bss=341348. Image 291748 bytes, SHA-256 `3F0E6BA8BEEA1D5887615818959D004C2DFE60115D3D32810C5B5943AF7AB824`. Native contract tests: 351206 MIDI/Accent and 48333 performance/Delay assertions. F: copy hash-verified. | Sound, clock, CPU and save/reboot pending. |
| 2026-10-29 | `docs/development-notes` | Documentation setup only | Build not run for this change | Not run |
| 2026-10-29 | Firmware source identical to `main` `a43cd4f`; GCC 10.2.1 (DaisyToolchain) | Configure and release build | Configure passed; 120/122 compile steps passed; link failed at `.ARM.extab` with `non constant or forward reference address expression` in `STM32F765VGTX_FLASH.ld:86`. No image produced. | Not run |
| 2026-10-29 | Same source; ARM GCC 14.3.rel1 | User ran the fresh release configure/build from the PowerShell instructions above. CMake cache confirms the 14.3 toolchain; output verified locally. | `LXR_V2_V1.7.img`: 274,704 bytes, SHA-256 `B34C0C3A946D02C5CEE624351A44C2597694B4832FDAA9CBAEB3627F84979AFE`. ELF `text=273828`, `data=852`, `bss=340572` bytes. | IMG-live Euclid smoke test passed; physical device not tested. |
| 2026-10-29 | `feature/pch-cpu`; ARM GCC 14.3.rel1 | Six modified C translation units passed `-fsyntax-only`; release Ninja build completed 34/34 steps. The sandbox build stalled, then the approved build completed. | `LXR_V2_V1.7.img`: 275,132 bytes including 16-byte update header; SHA-256 `C5D2AE5C0F07C0A06AC888457AA051448B2380111373A7CA7E09D126853B983F`. ELF `text=274252`, `data=856`, `bss=340572` bytes. | Pch CC 2, CPU meter and old SD data have not been tested on hardware. |
| 2026-10-29 | `feature/pch-cpu` `af7feb3`; naming/archive | Reconfigured CMake and rebuilt 2/2 steps. The new name has the same image bytes as the Pch/CPU build above. | `LXR_V2_V1.7_Mutador0.1.img`: 275,132 bytes, SHA-256 `C5D2AE5C0F07C0A06AC888457AA051448B2380111373A7CA7E09D126853B983F`. Baseline and fork images are archived in `firmware-archive/`. | Not run. |
| 2026-10-29 | `fix/perf-pattern-morph`; GCC 14.3.rel1 | Changed button handler, morph walk and image suffix. Syntax checks passed; approved Ninja release build passed 4/4 steps, then a final 3/3 rebuild after correcting the Euclid request index. | `LXR_V2_V1.7_Mutador0.1.1.img`: 275,220 bytes, SHA-256 `047992BA5A9EEDEA29A05A33DA6E0D79C6C1D7268EE8A33A2CA59AE2DD18B9B8`; ELF `text=274340`, `data=856`, `bss=340564` bytes. | Awaiting hardware retest. 0.1 booted and showed 67% CPU, but Morph had no audible effect despite another kit being loaded and value changing. |
| 2026-10-29 | `feature/global-load-switches`; GCC 14.3.rel1 | ARM syntax checks passed; legacy global offsets confirmed. Approved Ninja release build passed 32/32 steps and a final 3/3 rebuild after marking loaded Morph targets dirty. | `LXR_V2_V1.7_Mutador0.1.2.img`: 275,588 bytes, SHA-256 `75CC47E9B862CB58F3F3492190BEA6356276D050F07D395BA5F5B64A41C50148`; ELF `text=274708`, `data=856`, `bss=340572` bytes. | `lsh`, `lmp` and Morph audio need hardware testing. |

| 2026-10-29 | `feature/global-load-switches`, based on `9c98ebe`; GCC 14.3.rel1 | CMake release configure and approved Ninja build, 3/3 steps passed. | `LXR_V2_V1.7_Mutador0.1.3.img`: 275,636 bytes, SHA-256 `9A886E68023BCFA486CFD78D7887398D4AA7B0F8F840A09E6FBD76D400F47508`; ELF `text=274772`, `data=856`, `bss=340572` bytes. | User confirmed Morph target selection works in 0.1.2. Master srt fix in 0.1.3 awaits hardware testing. |

| 2026-10-29 | Based on `9c98ebe`, plus srt and lsr changes; GCC 14.3.rel1 | CMake release configure; approved Ninja build passed 32/32 steps. | `LXR_V2_V1.7_Mutador0.1.4.img`: 275,772 bytes, SHA-256 `6864825660889E887FA162E2439DAE4294168429205BD69ED1AE6716825CD654`; ELF `text=274908`, `data=856`, `bss=340572` bytes. | User reported 0.1.4 works on the instrument; explicit persistence and full load-policy regression checks remain open. |

| 2026-10-29 | Current source based on `9c98ebe`; MIDI channel-index correction, 0.1.5 | Native MSVC dispatcher tests: 147633 assertions passed. CMake configure passed; release Ninja approval rejected (`rejected by user`, no further reason). | No 0.1.5 image produced. CMake source suffix is 0.1.5; archived device-tested image remains 0.1.4. | Pending ARM release build and DIN/USB device checks. |

| 2026-10-29 | Current source after `9c98ebe`; Mutador note routing and CC index correction | ARM GCC 14.3.rel1, CMake configure; approved Ninja release build passed 26/26 steps; native tests passed 312125 assertions. | `LXR_V2_V1.7_Mutador0.1.6.img`: 276,884 bytes, SHA-256 `3B6F171539FAD1A9E84ED1B0835E5C2D193FEC67C40EEEA287FC35A4D905D58D`; ELF `text=276004`, `data=856`, `bss=340580` bytes. | Device MIDI routing, recording/echo and Pch transpose tests pending. |

| 2026-10-29 | Current source after `9c98ebe`; full Mutador pitch and PERF gpt/pbr, 0.1.7 | Initial build approval rejected; after user requested SD copy, approved GCC 14.3.rel1 release Ninja build passed 35/35 steps. 8 ARM syntax checks and 334043 native assertions passed. | `LXR_V2_V1.7_Mutador0.1.7.img`: 278,508 bytes including header, SHA-256 `76298CE0FAA7D6F01C48754E91A702A8B1A6D86A493EF852BA12D3D7D7B9E834`; ELF `text=277628`, `data=856`, `bss=340708` bytes. | Copied to F: and hash verified. Physical-device pitch/PERF tests pending. |

| 2026-10-29 | Current source after `9c98ebe`; GDC, 606 live range, RST/CSR, BC Scarcity and PST, 0.1.8 | GCC 14.3.rel1 CMake/Ninja: 34/34 steps, then 3/3 after live CSR-history correction. Native MIDI/GDC 350509 and performance 38002 assertions passed. | `LXR_V2_V1.7_Mutador0.1.8.img`: 283,600 bytes including header, SHA-256 `F07720D86A87A9F0E849494A2FBFCD53EBA0F17911E0AB755B86DD8104108C01`; ELF `text=282708`, `data=868`, `bss=340884` bytes. | Copied to F: and hash verified. Hardware timing/CPU/save-reboot tests pending. |

The GCC 14.3 build image exactly matches the SHA-256 of the previously
validated 1.7 source image used by `Lxr2Menu` IMG-live. With its optional
Rust accelerator enabled, the current image booted in the emulator. The
Euclid page showed `LEN 16 / STP 4 / ROT 0`; raising `STP` to 5 generated
five active steps, rotating by one changed the mask while retaining five,
and reducing `LEN` to 15 retained five. This is a smoke test of generator
operation, not proof that the official 1.71 Euclid fix is identical. The
official 1.71 image has a different hash and cannot be substituted into
this emulator's source-build profile without validating its addresses.

For each firmware change, add the exact commit, toolchain version, build
result, image filename and size, and any test performed on the instrument.
Keep failed attempts in the record so later sessions can see what happened.

## 2026-10-30 â€” Mutador 0.1.14 import build

Branch `feature/global-load-switches`, based on `9c98ebe` with uncommitted earlier import work. Reference Mutador commit `7319e19b1435dc5a127108367f812c4187f7c025`. ARM GCC 14.3.rel1, release Ninja build: 5/5 after startup-display and menu-navigation edits. ELF text 303196, data 880, bss 342808 bytes; ITCM 13744/16384 bytes. The 304100-byte update image has SHA-256 `F2FA7E606D816036E2FCD58B12950177313E5539F0429F5C7985CA461949E3CD`.

Native tests: `check_audio_import.py` 10616322, `check_edit_scale_hat_storage.py` 127109, `check_midi_contract.py` 352168, `check_performance_import.py` 56858 assertions. Initial ARM build authorization rejected; later authorization granted and build passed. Prior card update 0.1.13 backed up under `build/card-image-backups/20261030-import-0.1.14`; card `LXRO2` now contains only the 0.1.14 root update image, SHA verified. No SD project/settings files changed. Hardware sound, CPU, timing and persistence still need testing. See session 022.

## 2026-10-30 â€” Mutador 0.1.15 voice and Clock Offset build

Same branch and source base, Mutador reference `7319e19b1435dc5a127108367f812c4187f7c025`. ARM GCC 14.3.rel1 release Ninja build passed 12/12 after DIN timestamp capture. ELF text 305324, data 884, bss 344176; ITCM 13928/16384 bytes. Update image 306232 bytes, SHA-256 `36197B8199EFBA75828AB720ACDE5DF636F0B12823D0302A3F3CCC417A2F0650`.

Native verification: voice import 2440 assertions, edit/scale/hat/storage 127112, MIDI 352168, performance/Clock 56866, project loader 5 cases. Kit tests cover old standalone and old padded project files, the new `SNE1` marker, corrupted marker fallback, Snare neutral controls and Ring blend. Clock tests cover predicted step, no duplicate on actual edge, zero-offset edge timing and 12-step eight-pulse timing. Device sound, MIDI jitter, CPU and save/reboot remain open. See session 023.

The old 0.1.14 card update was saved to `build/card-image-backups/20261030-voice-clock-0.1.15`; `LXRO2` now contains only the 0.1.15 update image in its root, with the archive SHA-256 verified. No project/configuration files on the card were edited.

## 2026-10-30 â€” Mutador 0.1.16 COPY, manual start and Snare Layer

Reference Mutador commit `7319e19b1435dc5a127108367f812c4187f7c025`.
ARM GNU 14.3.rel1, release Ninja build passed. ELF text 309508, data 888,
bss 344536; ITCM 13976/16384 bytes. Final archive image 310420 bytes,
SHA-256 `FCC35C9BC4DC5D0584167E292ACC19F84A5CEB2C10ADC39B65BF25B253619DF1`.
The Ninja size line reports the firmware payload; the update file adds a
16-byte `LXRV2IMG` header.

Native tests: Voice Import 2449, MIDI 352168, Edit/Scale/Hat/Storage 127112,
Performance 56872, Project Loader 5. The separate COPY source contract
passes 25 assertions on cross-bar Step timing, group bits and slot 64.
Hardware is pending. The prior 0.1.15 card image was hash checked, backed up
under `build/card-image-backups/20261030-copy-start-snare-0.1.16`, and removed
from the card only after the new 0.1.16 root image matched the archive hash.
No project, sample or configuration file was changed.
See [session 024](docs/sessions/024-copy-start-snare-layer.md).

## 2026-10-30 â€” Mutador 0.1.17 MIDI transport PLAY state

Compared the local STOP/PLAY flow to Mutador's 96-clock bar phase. Accepted
MIDI START, CONTINUE and STOP now update the front-panel run state so the
next PLAY press has the correct meaning. Host MIDI contract test 352171;
Performance start test 56872. ARM GNU 14.3.rel1 release Ninja build passed.
ELF text 309548, data 888, bss 344536; ITCM 13976/16384 bytes. Final image
310460 bytes, SHA-256
`013EE2DC1404661A4EF51D316F22C639D75A7B12AA1E69BB027C70F23EF0294C`.
See [session 025](docs/sessions/025-midi-transport-play-state.md).

The prior 0.1.16 card image was hash checked and backed up under
`build/card-image-backups/20261030-midi-transport-0.1.17`. The new 0.1.17
root update matched the archive hash before 0.1.16 was removed. No project,
sample or configuration file was changed.

## 2026-10-31 — Mutador 0.1.20 Snare destinations

Appended destinations 229–235 for the seven Snare controls, preserving all
legacy target indices. Added parameter pointers and extended encoder/pot
selection and LFO voice-gap mapping. Wave and mode modulation use bounded
rounded selections. Release build passed. Native destination audit passed
49 assertions; voice/kit audit passed 2449. Hardware checks remain pending.
Mutador voice CC 112–118 mapping was identified but is not imported here.

## 2026-10-31 — Mutador 0.1.21 Snare voice CC

Imported Snare voice CC 112–118 with Mutador channel priority: dedicated
Snare voice channel only, excluding gch/Pch. Update sound, active parameter,
modulation base and automation target consistently; clamp Wave and Mode.
Release build passed. MIDI audit passed 357659 assertions, including all
128 input values for each alias on USB and DIN, channel overlaps and RX
filter checks. Hardware MIDI testing remains pending.

## 2026-10-31 — Mutador 0.1.22 Stray/Glide and Voice CC

Imported smooth-random LFO trajectory/bias/retrigger code, adapting the
0–2 reference output to desktop 0–1 modulation. Kept existing waveform IDs;
new menu entries are str/gld (8/9). Integrated waveform/offset setters in
the MIDI parameter path. Frequency zero and held random follow Mutador.
Imported the source Voice-CC translator except Membrane 111, with dedicated
voice-channel priority, translated parameter state/automation and bounded
menu selections. Raw target CC 25/81 use sound-parameter IDs, not menu indices.
Native tests: 450061 deterministic LFO/reference assertions; 509499 MIDI
source-table and dispatch assertions. Device listening and timing remain open.

## 2026-10-31 — 0.1.22 per-pattern Scale and next-bar confirmation

Replaced 12a/b/c with eight musical divisions, 2/4/6/8/12/16/24/32.
/12 visits only the first twelve slots of each sixteen-slot page. The other
rates keep all 64 slots. Fine event frames are resampled over the true step
interval, covering every Flam/Groove frame even for /24 and /32. MIDI clock
stays 24 PPQ. A confirmed change is queued to the internal or MIDI transport
downbeat and restarts Step 1 once, suppressing an accidental auto-pattern
advance. The existing MIDI lead path can commit before the confirming edge
without duplicating Step 1. Long PERFORMANCE opens an independent preview;
LOAD is unaffected. Confirming activates per-pattern playback.

Storage: checked six-byte SCL2 pattern trailer; old patterns default to 16.
Pattern copy and edit backup include the scale. MUTA.CFG v3 has the same
29-byte payload size and marks new override indices; v1/v2 convert old 16
and 12a/b/c settings. Native Pattern Scale audit: 1098 assertions;
performance/timing: 56947; edit/scale/hat/storage: 148249. ARM build passed.

## 2026-10-31 — 0.1.22 SD-card write and documentation update

Copied firmware-archive/LXR_V2_V1.7_Mutador0.1.22.img to F: and verified
SHA-256 088D3C994528BB06B71549802068C5A0FFB77E49E72774517F92974B4180705F
(317324 bytes). Only after verification, removed the old root 0.1.19 image.
The actual former card image was verified against the archive and copied to
build/card-image-backups/20261031-mutador-0.1.22/. Other card files were not
changed. Installation/boot on the instrument is not implied by copying.

Updated the README's current feature summary and firmware filenames, Manual
index/device/sequencer/save chapters, Changelog (including the 0.1.18/19 UI
history), sessions and archive record. No firmware source changed in this
card/documentation task; the previously built and tested image was used.

## 2026-10-31 — 0.1.23 Random/overall Velocity and any-mode shortcut

SHIFT+Step 1 now has priority over mode-dependent COPY/CLEAR and opens the
first PERF display with pattern selection from every mode. Pending automation
arming is cancelled. Rvl's integer arithmetic and Voice-1 exception follow
Mutador. AVL is applied once afterward to sound/modulation velocities and
sequencer MIDI output; incoming MIDI note handling retains its original path.
AVL raw 0-200 displays -100 to +100 percent; endpoints force 0/127 and neutral
is exact. The signed display occupies four cells, including both endpoints.

Appended parameter IDs preserve previous IDs. The fixed 20-byte extension
block remains unchanged; v4 adds two explicit velocity bytes after it, avoiding
the intervening UI-only Pattern Scale parameter. Legacy v1/v2/v3 settings
load neutral. MIDI Pch CC9 scales rvl to 0-100. Release build and native tests
passed (196491 / 509607 / 56947 / 148256 assertions). Device validation is open.

## 2026-10-31 — 0.1.23 SD-card write

Copied LXR_V2_V1.7_Mutador0.1.23.img to F: and verified SHA-256
585F0CEDEC5C628A733E3434BA6EFA781EAE144BE80B14842913877D3F8CF616
(318284 bytes). The former 0.1.22 image matched its archive and was also
backed up under build/card-image-backups/20261031-mutador-0.1.23/.
Removed only the former root image after verifying the new copy. Device
installation and hardware testing remain pending.

## 2026-10-31 — 0.1.24 defaults and one-time card velocity migration

Changed seq_resetNote to SEQ_DEFAULT_VELOCITY=100. Identified active PROJxx
and TMP layouts: 1153 v3/TMP patterns and 192 PatV02 files, total 1345.
The user excluded Lxr2openmytake and Helicase archives. Scaled only each
Step.volume's low seven bits with (v*100+63)/127; preserved its active flag.
Pattern versions, all other step bytes, timing, main-step flags, lengths,
shuffle, kit and Scale trailers remained unchanged. Original/staged copies,
SHA-256 hashes and receipt are under
build/card-velocity-backups/20261031-velocity-100/.

The independent audit uses the actual production C pattern loader to compare
every original/staged file and the new reset default: 1345 files, 602560
slots, 573886 changed slots, 1262958 assertions passed. Applied and readback-
verified 1281 changed files. The application can resume using the same plan
without double scaling. Build 0.1.24 passed and was copied/hash-verified on
F: before the proportional-gain follow-up below.

## 2026-10-31 — 0.1.25 proportional positive AVL

On request, changed positive AVL from filling the remaining distance to 127
to the same multiplicative rule as attenuation: round(velocity*gain/100),
clipped at 127. UI/storage remain -100..+100 percent, raw 0..200; Rvl/AVL
order and Voice-1 Rvl exception remain. Native velocity/shortcut checks pass
196491 assertions. ARM release build passed. The pattern migration was not
repeated. Updated manual, changelog and archive records.

Copied 0.1.25 to F: (318260 bytes), SHA-256
6DFB73370CAD9E8EC5E87C05F6E8B74EA29CD7D800917F1851C3B4A214D0F492.
The old 0.1.24 image is archived and backed up under
build/card-image-backups/20261031-mutador-0.1.25/. Hardware testing is open.


## 2026-10-31 - 0.1.26 MIDI-running pattern-switch investigation

User reproduction: SHIFT+Step 1, bank up, choose pattern; freeze only while
running with MIDI Clock. Exact project and slot were not identified.
Confirmed code defects: CC0 underflow wrote at cache offset 65536; recursive
UART dispatch via kit loading -> soundengine_process -> uart_processMidi.
Fixed cache indices/size, UART dispatch reentry and sequencer interpolation
during incomplete pattern switching. Loading display now shows project name.

Old CC storage regression failed; fixed passed 8486912 assertions.
Old injected UART dispatch reached depth 128; fixed dispatched all 129 bytes
in order at depth one. Production pattern switching: 24576 assertions across
4096 old/new slots, injecting nested MIDI/sequence callbacks during kit load.
MIDI dispatch 509607, Scale 1098 and Groove 1531942 checks passed.
ARM release: ITCM 14304/16384, DTCM 107664/131072,
RAM 274884/393216, FLASH 266944/1015808 bytes.
Image LXR_V2_V1.7_Mutador0.1.26.img: 318260 bytes.
SHA256 462432BA7278419494974FA9181EBB23D009E3837726A298711A31E924443E8E.
Archived locally. F: was absent; no SD files were changed.
These tests identify and repair concrete defects; they do not prove that
all causes of the user's hardware freeze have been eliminated. Device
retest with the original gesture and external MIDI Clock remains open.


## 0.1.27 candidate after lki comparison

User confirmed: with lki=off the same bank/pattern change works; failure
is associated with automatic kit loading in 0.1.26. Added bounds and null
storage checks in modNode_setOriginalValueChanged before accessing the
parameter table. Empty/off targets can have TYPE_UINT8 with a null pointer.
A native extracted-function audit passed all 65536 empty/invalid IDs and
a valid byte target. ARM release passed. This repairs a concrete unchecked
access; hardware confirmation of the reported freeze remains pending.
Image 0.1.27: 318084 bytes, SHA256
10A5980FD81A1B2C2A4B9C2C88C5BD63EF738DD16BBBA38FB65B9A44F0929EF1.
Copied/hash-verified on F:, former 0.1.26 image backed up under
build/card-image-backups/20261031-mutador-0.1.27/.


## 0.1.28: immediate kit loader selector encoding

User reports 0.1.27 still freezes, also in normal pattern selection.
lki=off works. Immediate kit loading translates destination indices through
modTargets and sends them, then its generic parameterOrder loop sent the
raw indices again through the newly imported CC selector handlers. These
handlers interpret bytes as parameter IDs, corrupting destinations and
allowing selector/reset recursion. Skip VEL_DEST, VOICE_LFO and TARGET_LFO
selectors in the generic loop, as the existing morph path already does.
Also skip NONE and Bank Change placeholders. Production immediate-loader
and parameterOrder harness passed 256 complete kit-value sweeps: all twelve
translated target messages sent, no raw selector CCs. ARM build passed.
Candidate 0.1.28 archived, SHA256
08FD79C072EE4B068913E5563CD70565689DC028C3596879E278564715325C03.
Card F: absent during follow-up, no card write. Device retest remains open.

0.1.28 card write completed: F:/LXR_V2_V1.7_Mutador0.1.28.img,
318108 bytes, SHA256 verified as
08FD79C072EE4B068913E5563CD70565689DC028C3596879E278564715325C03.
Previous 0.1.27 image backed up and hash-verified before removing only
that old root image. Device installation and lki=aut retest pending.

0.1.28 device result (2026-10-31): user reports pattern selection works again after installing the verified image. This confirms the targeted kit-load freeze retest; other imported functions still need broader testing. Membrane was not imported. Release headroom: FLASH 749040 bytes, ITCM 2056 bytes, DTCM 23408 bytes, RAM 118332 bytes.
