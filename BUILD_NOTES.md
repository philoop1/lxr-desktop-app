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

The current archived build is Mutador 0.2.24; see the last entry of this
file for its hash and test state. Physical-device validation of the 0.2
series remains open.

The update image is written under `build/release/` as
`LXR_V2_V1.7_Mutador0.2.24.img`. The base version comes from
`project(VERSION ...)` in `CMakeLists.txt`; the fork suffix is set separately
there as `LXR_MUTADOR_VERSION`, which also sets the startup line. For a debug build, use the `debug` preset in both commands.

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

## 2026-10-30 — Mutador 0.1.14 import build

Branch `feature/global-load-switches`, based on `9c98ebe` with uncommitted earlier import work. Reference Mutador commit `7319e19b1435dc5a127108367f812c4187f7c025`. ARM GCC 14.3.rel1, release Ninja build: 5/5 after startup-display and menu-navigation edits. ELF text 303196, data 880, bss 342808 bytes; ITCM 13744/16384 bytes. The 304100-byte update image has SHA-256 `F2FA7E606D816036E2FCD58B12950177313E5539F0429F5C7985CA461949E3CD`.

Native tests: `check_audio_import.py` 10616322, `check_edit_scale_hat_storage.py` 127109, `check_midi_contract.py` 352168, `check_performance_import.py` 56858 assertions. Initial ARM build authorization rejected; later authorization granted and build passed. Prior card update 0.1.13 backed up under `build/card-image-backups/20261030-import-0.1.14`; card `LXRO2` now contains only the 0.1.14 root update image, SHA verified. No SD project/settings files changed. Hardware sound, CPU, timing and persistence still need testing. See session 022.

## 2026-10-30 — Mutador 0.1.15 voice and Clock Offset build

Same branch and source base, Mutador reference `7319e19b1435dc5a127108367f812c4187f7c025`. ARM GCC 14.3.rel1 release Ninja build passed 12/12 after DIN timestamp capture. ELF text 305324, data 884, bss 344176; ITCM 13928/16384 bytes. Update image 306232 bytes, SHA-256 `36197B8199EFBA75828AB720ACDE5DF636F0B12823D0302A3F3CCC417A2F0650`.

Native verification: voice import 2440 assertions, edit/scale/hat/storage 127112, MIDI 352168, performance/Clock 56866, project loader 5 cases. Kit tests cover old standalone and old padded project files, the new `SNE1` marker, corrupted marker fallback, Snare neutral controls and Ring blend. Clock tests cover predicted step, no duplicate on actual edge, zero-offset edge timing and 12-step eight-pulse timing. Device sound, MIDI jitter, CPU and save/reboot remain open. See session 023.

The old 0.1.14 card update was saved to `build/card-image-backups/20261030-voice-clock-0.1.15`; `LXRO2` now contains only the 0.1.15 update image in its root, with the archive SHA-256 verified. No project/configuration files on the card were edited.

## 2026-10-30 — Mutador 0.1.16 COPY, manual start and Snare Layer

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

## 2026-10-30 — Mutador 0.1.17 MIDI transport PLAY state

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

## 2026-10-31 � Mutador 0.1.20 Snare destinations

Appended destinations 229�235 for the seven Snare controls, preserving all
legacy target indices. Added parameter pointers and extended encoder/pot
selection and LFO voice-gap mapping. Wave and mode modulation use bounded
rounded selections. Release build passed. Native destination audit passed
49 assertions; voice/kit audit passed 2449. Hardware checks remain pending.
Mutador voice CC 112�118 mapping was identified but is not imported here.

## 2026-10-31 � Mutador 0.1.21 Snare voice CC

Imported Snare voice CC 112�118 with Mutador channel priority: dedicated
Snare voice channel only, excluding gch/Pch. Update sound, active parameter,
modulation base and automation target consistently; clamp Wave and Mode.
Release build passed. MIDI audit passed 357659 assertions, including all
128 input values for each alias on USB and DIN, channel overlaps and RX
filter checks. Hardware MIDI testing remains pending.

## 2026-10-31 � Mutador 0.1.22 Stray/Glide and Voice CC

Imported smooth-random LFO trajectory/bias/retrigger code, adapting the
0�2 reference output to desktop 0�1 modulation. Kept existing waveform IDs;
new menu entries are str/gld (8/9). Integrated waveform/offset setters in
the MIDI parameter path. Frequency zero and held random follow Mutador.
Imported the source Voice-CC translator except Membrane 111, with dedicated
voice-channel priority, translated parameter state/automation and bounded
menu selections. Raw target CC 25/81 use sound-parameter IDs, not menu indices.
Native tests: 450061 deterministic LFO/reference assertions; 509499 MIDI
source-table and dispatch assertions. Device listening and timing remain open.

## 2026-10-31 � 0.1.22 per-pattern Scale and next-bar confirmation

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

## 2026-10-31 � 0.1.22 SD-card write and documentation update

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

## 2026-10-31 � 0.1.23 Random/overall Velocity and any-mode shortcut

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

## 2026-10-31 � 0.1.23 SD-card write

Copied LXR_V2_V1.7_Mutador0.1.23.img to F: and verified SHA-256
585F0CEDEC5C628A733E3434BA6EFA781EAE144BE80B14842913877D3F8CF616
(318284 bytes). The former 0.1.22 image matched its archive and was also
backed up under build/card-image-backups/20261031-mutador-0.1.23/.
Removed only the former root image after verifying the new copy. Device
installation and hardware testing remain pending.

## 2026-10-31 � 0.1.24 defaults and one-time card velocity migration

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

## 2026-10-31 � 0.1.25 proportional positive AVL

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

Mutador 0.2 candidate (2026-10-31): ARM GCC 14.3 release build passed with Random Step LFO, Flam Probability, LFX1 kit and FLP1 pattern extensions. Host checks: Pattern Scale/FLP1 1106, grouped Step editing 148257, performance/Flam 56951 assertions; LFO source routing passed. Memory ITCM 14400/16384, DTCM 107672/131072, RAM 305388/393216, FLASH 271688/1015808. Device testing pending.

Mutador 0.2 final image: 323084 bytes, SHA256 F58CF6793F27726F51FD504494E62571B41694213F0D7F837745DEE4A8A4D0AF. Copied and hash-verified as F:/LXR_V2_V1.7_Mutador0.2.img. The old card image 0.1.28 was hash-verified and backed up to build/card-image-backups/20261031-mutador-0.2/ before removal from the card. The card now has only the 0.2 LXR update image. Final build: ITCM 14400/16384, DTCM 107672/131072, RAM 305388/393216, FLASH 271672/1015808. Hardware installation and sound/save-load verification remain pending.


Mutador 0.2.1: explicit Voice-only four-screen LFO navigation; fpr moved before flam on Step screen 2. Release build passed; 57214 host assertions including actual Flam hit counts and all-voice LFO navigation passed. FLASH 271680 bytes; IMG 323092 bytes; SHA256 43016B34C3BDAB6316535F059889B628CA4A31FA2B0C2D820E895CFED05AB9AF. SD F: copied and SHA256 verified; previous update image backed up before removal. Hardware LFO/Flam retest pending. See session 032.


Mutador 0.2.2: ARM GCC 14.3 release build passed. IMG 323284 bytes, SHA256 095A1A96B6BCF0A8DF5E01317DD4E033DE46789C0CA174571D3B86E020530978. 57214 host performance assertions passed before the menu layout adjustment; hardware display check pending.


Mutador 0.2.3: ARM GCC 14.3 release build passed. Image 323348 bytes, SHA256 021569213D849D80AFE1A4A21BD621F5C4C600192C1417D27516CA232B50AD79. LFO STEP and 57214 performance host assertions passed. Hardware live-edit freeze retest pending.


Mutador 0.2.4: ARM GCC 14.3 release build passed. IMG 323420 bytes, SHA256 71641EF6B46EE127889E207C669D447BBBE355B0E271B7BF50E08A1581C7F2F8. Destination host contract 73 assertions and LFO STEP passed. Device destination-change and LFO audio retest pending.


Mutador 0.2.5: ARM GCC 14.3 release build passed. IMG 323460 bytes, SHA256 2E21DEC9570ED5A2BA10B0D916FC14EFBD97B2DCB499E09C4034C582E863DFA5. Target-switch host check passed, 76 destination checks and 57216 performance checks passed. Physical dst-change freeze retest pending.

Mutador 0.2.6: ARM GCC 14.3 release build passed. IMG 325620 bytes, SHA256 FC0850C6E8B7A5F08B38CC13D1D2D982C23B9B5C930D084B04804544D300FE8F. LFO step and kit checks, modulation target switch and performance checks passed. Hardware test of simultaneous LFO and Random per Step pending.


Mutador 0.2.7: ARM GCC 14.3 release build passed. IMG 326012 bytes, SHA256 DE49DF14FB7E7307E06C85208AB0DAA0F0D8AFA8C8BD580098B2204916FA0DB9. Target-switch host check passed. Hardware UI verification pending.


Mutador 0.2.8: ARM GCC 14.3 release build passed. IMG 326036 bytes, SHA256 4DA1BD027AC65AFD05B8BA85476119594011B0FC4D9DAA7DFB56634642A31D32. LFO step, kit storage and mod target checks passed. Hardware RDS/VOI test pending.


Mutador 0.2.9: ARM GCC 14.3 release build passed. IMG 326660 bytes, SHA256 4D5C4E0691B50F14BE2CE10AD7B9205A13CF8D768D4A2981D12C3DC285D346AD. Trig condition, CND1 storage, performance, edit/scale/hat/storage native checks passed. Hardware test pending.


Mutador 0.2.10: ARM GCC 14.3 release passed. IMG 331220 bytes SHA256 D5795706CB70BD5667B17F228E86D4349ABC8E5C891E42989EC78370B8C44A1E. Native condition/SCT, CND1/CND2 storage, 1106 pattern-scale and 57227 performance assertions passed. Hardware validation pending.


Mutador 0.2.11: ARM GCC 14.3 release passed. Actual IMG 331300 bytes, SHA256 0421C3E632DF2806ADA1C3D4BF4C62F25B7EAC3D718BEE69A287ED64306B6A6D. ITCM 14368/16384, DTCM 107672/131072, RAM 338148/393216, FLASH 279920/1015808. Offline LXR1 timing/kit/automation tests passed; real Mutador v12 performance converted to eight 4574-byte patterns and one 328-byte kit. Copied to SD F: and hash verified; archived 0.2.10 image hash checked before removal. SCT menu hardware check pending.

Mutador 0.2.12: ARM GCC 14.3 release passed with no compiler warnings. Transfer dialog and transactional project kit/pattern copy compiled. Actual IMG 334820 bytes, SHA256 61CBBCA7D922443F38DECEDBF58CD239FACA3C77F14FD75EFDCE84A548AB5341. ITCM 14368/16384, DTCM 107672/131072, RAM 338156/393216, FLASH 283440/1015808. On-device FAT copy and overwrite confirmation test pending.
SD F: 0.2.12 copied and SHA256 verified; previous 0.2.11 image matched the local archive before removal. Physical copy/replace test remains open.

2026-11-01 LXR1 SD library: staged all 61 Pxxx.PRF performances from I:/Github/mutador/SDcard, copied 44 matching original SND files, reconstructed 17 missing SND files from embedded PRF kits, and generated eight one-bar PAT files plus one LXR2 kit per performance. F:/LXR1 now contains 61 folders and 734 files (5,437,555 bytes); every file SHA256 matched staging after copy. Individual NOTES.TXT files mark conversion approximations. The existing F: projects and 0.2.12 update image were not changed. Firmware 0.2.12 does not browse F:/LXR1 yet.

2026-11-01 sound access: F:/LXR1/SOUNDS/LXR1 holds 61 LXR1 SND files (44 copied originals, 17 reconstructed from PRF); F:/LXR1/SOUNDS/LXR2 holds 61 converted LXR2 kits. F:/PROJ63 is a kit-only library with 61 files in slots 00..60 for 0.2.12 project-transfer UI. All 122 central sound copies and all 61 PROJ63 kit copies were SHA256-verified against the per-performance originals. Existing PROJ00..PROJ20 directories were not touched.

Mutador 0.2.13: ARM GCC 14.3 release passed with no compiler warnings. Adds slot names, double PROJECT shortcut and P+K transfer; fixes the stale pattern backup after importing into the active slot and the stale No free KIT message. IMG 336996 bytes, SHA256 5E50B7C2AA635E899DE37CF28EF7A79FFE5CC56371AFBC900889FA485D30EE9A. ITCM 14368/16384, DTCM 107672/131072, RAM 338188/393216, FLASH 285616/1015808. Host checks passed: performance 57227, pattern scale 1106, edit/scale/hat/storage 148257, trig storage/conditions, mod target, LFO step, LXR1 import. The transfer dialog has no host test. Archived and hash verified. SD F: 0.2.13 copied and SHA256 verified; the 0.2.12 card image matched its archive and was backed up under build/card-image-backups/20261101-mutador-0.2.13/. Its removal from the card was blocked by a tool safety check, so F: holds both images until 0.2.12 is deleted by hand. Device installation and on-device copy test pending. See session 033.

Mutador 0.2.14: user reports the PROJECT double press does nothing. Cause: its 600 tick window assumed milliseconds, but systick_ticks runs at 4 kHz (TIM14: 108 MHz / 13501 / 2), so the window was 150 ms. Now 2400 ticks = 600 ms. ARM GCC 14.3 release passed with no compiler warnings. IMG 336996 bytes, SHA256 905761062A2FAA68C36C11617084D8D57EB84589533798FD4C09658B393373A3. ITCM 14368/16384, DTCM 107672/131072, RAM 338188/393216, FLASH 285616/1015808. Host checks passed: performance 57227, pattern scale 1106, edit/scale/hat/storage 148257; none covers this window. Archived and hash verified. SD F: 0.2.14 copied and SHA256 verified. The user removed 0.2.12 by hand; 0.2.13 matched its archive, is backed up under build/card-image-backups/20261101-mutador-0.2.14/ and must be deleted by hand before updating, because a tool safety check blocks removal from F:. Device retest pending.

Mutador 0.2.15: LOAD transfer gains LXR1 after PROJ63: choose a performance and an eight-slot pattern block, kit goes to the lowest free slot, one Replace confirmation covers all eight. Sources must be /LXR1/Pxxx/LXR2/00-LXR1.SND and 00..07-LXR1n.PAT. A failure after the first pattern leaves the patterns already copied, with their kit. ARM GCC 14.3 release passed with no compiler warnings. IMG 338300 bytes, SHA256 FB924EE519640BA145CD7C8DDF465ACF2041C3D361E2339EEF1C54A326E1CAC4. FLASH 286920/1015808, RAM 338188/393216. Host checks passed: performance 57227, pattern scale 1106, edit/scale/hat/storage 148257; none covers transfer or performance import. Archived, hash verified; not on SD, card absent.

2026-11-01 PROJ63 finding: its kits came from PRF embedded kits, not the SND files. 44 of 61 SND files hold a different kit from their PRF; the other 17 were reconstructed from it. tools/prepare_snd_kit_library.py converted all 61 SND files to build/lxr1-snd-kits-20261101. PROJ63 was left unchanged; see the card entry below. Performance import keeps using the PRF kit, which belongs to its patterns.

2026-11-01 card: F: 0.2.15 copied and SHA256 verified. The former 0.2.14 image matched its archive and was renamed to LXR_V2_V1.7_Mutador0.2.14.imm, so it is no longer an update image. New F:/PROJ62 holds the 61 SND-derived LXR2 kits as NN-Pxxx.SND, each SHA256 verified against build/lxr1-snd-kits-20261101. PROJ63 stays the PRF kit library. All 183 sampled paths under /LXR1/Pxxx/LXR2 exist. PROJ64 is not usable: projects end at 63. Device installation and test pending.

2026-11-01 card projects: tools/prepare_lxr1_projects.py grouped the 61 performances into PROJ21..PROJ28, eight per project: block b holds patterns b*8..b*8+7 linked to kit b. Every project has 64 kits and 64 patterns because project load keeps old RAM for missing slots; kits 8..63 are named Unused, and PROJ28 repeats P060 in its last three blocks. No songs or GLO.CFG were written, so song slots and globals stay as they were in RAM. All 1032 files matched staging by SHA256. Added PRJ.NFO to PROJ62 (SND KITS) and PROJ63 (PERFKITS); project load fails without it. Existing projects unchanged. Not loaded on the device yet.

Firmware defect, fixed in 0.2.16: the transfer writes to /projNN but the firmware works in /tmp. The RAM reload after an import reads /tmp, so the import does not reach the running project, and Save Project empties /projNN and writes RAM back, losing the import. No *IMPRT* file was found on the card. Source fix: reload from the project folder, return to /tmp, drop stale slot files, refresh the edit backup and tmp.pat when the active slot changes, count /tmp in Replace and free-kit checks, create a missing project folder. 0.2.15 still has the defect.

Mutador 0.2.16: ARM GCC 14.3 release passed with no compiler warnings. IMG 339164 bytes, SHA256 CB9EFED3A4C72944FF2F11E2CE0CC7B3C25F78A6BEFAA9F26A27C26EFB9528C1. ITCM 14368/16384, DTCM 107672/131072, RAM 338188/393216, FLASH 287784/1015808. Host checks passed: performance 57227, pattern scale 1106, edit/scale/hat/storage 148257; none covers transfer or /tmp handling. Archived; SD F: copied and SHA256 verified, former 0.2.15 image matched its archive and was renamed to .imm. Device installation and transfer tests pending.

2026-11-01 LXR1 converter defect: user reported PROJ21..28 show only voice 1 and sometimes voice 2. The converter wrote main-step words by bar then track, while firmware reads and writes track then bar, so tracks 1-4 became the four bars of voice 1 and tracks 5-7 went to voice 2. Fixed in tools/import_lxr1_patterns.py; check_lxr1_import.py now checks every track. Regenerated build/lxr1-library-20261101b and build/lxr1-projects-20261101b: 381 of 488 patterns changed, only the 56 main-step bytes differ; the other 107 have at most voice 1 hits or none, and 102 are empty. All PAT files converted before this fix are wrong, including those on F: under /LXR1 and PROJ21..28. Card PROJ21..28 and /LXR1 matched the old staging exactly, so nothing the user saved was replaced; corrected PAT files were written and read back byte-identical. Device listening test pending.

Mutador 0.2.17: in pattern selection the encoder picks bank 1..4 outside edit mode, except on the pattern save page. Holding LOAD for 1 s alone opens the SHIFT + Step 1 pattern shortcut; any other button or release cancels it, and the transfer dialog ignores it. ARM GCC 14.3 release passed with no compiler warnings. IMG 339348 bytes, SHA256 4B9C9FA1EA5F55B517E2EA223F74F1EE1945BCFF0B1352CCA4B50BE0748AEEC1. FLASH 287968/1015808, RAM 338196/393216. Host checks: performance 57227, pattern scale 1111 including five long LOAD cases, edit/scale/hat/storage 148257. No host test covers the encoder bank branch. SD F: copied and SHA256 verified; 0.2.16 matched its archive and was renamed to .imm. PROJ62 kit names now follow the PRF names; sound bytes unchanged. User reports pattern chaining works on 0.2.16. Device test of 0.2.17 pending.

2026-11-01 card: renamed PROJ62 and PROJ63 kit files to the firmware scheme NN-NAME.SND, using the first five sanitized characters of each kit name, so names are visible in a file browser. Content hashes unchanged; 61 unique slots in each.

Mutador 0.2.18: live sct rebuilt. Mutador and LXR2BC change the step time in 12a/b/c, which the local port had lost. sct is now off/a/b/c, chosen by the active rate: rates 2/4/8/16/32 are quaternary and show 4/3a/3b/3c (drop index 3/1/2, step time 4/3); rates 6/12/24 are ternary and show 3/4a/4b/4c (step time 3/4, all tracks pause one gap slot at index 3/1/2). Each pair is an exact inverse; old 12a is now 3c and old 12c is 3a. sct no longer writes the pattern; the stored transform byte stays in files and is ignored; sct is not persisted and starts off. Changes commit on the next group edge without restart: every quarter at rates 12 and up, half note at 6/8, bar at 2/4. seq_prescaleCounter is 16 bit because rate 2 with 3x needs 256 ticks. sct moved to PERF page 2 in the old pbr slot; pbr moved to the third globals page. Pch CC 88..91 select off/a/b/c and no longer reach voice parameters on that channel. ARM GCC 14.3 release passed with no compiler warnings. IMG 338028 bytes, SHA256 703EC9754E072CC558E8125AFB11DBB9F01997168F3DE1BF0A56ABDD147B1CE6. FLASH 286648/1015808, RAM 338196/393216. Host checks: new check_sct 595 against the production scale code, performance 57227, MIDI 509679, pattern scale 1111, edit/scale/hat/storage 148257, trig conditions/storage, mod target, LFO step, LXR1 import. The sequencer paths for gap slots and live switching, Flam/Groove in a gap and MIDI clock sync have no host test. SD F: copied and SHA256 verified; 0.2.17 matched its archive and was renamed to .imm. Device listening test pending.

Mutador 0.2.19: user reports a pattern set to rate 12 plays no triplets. seq_setPatternScale changed the pattern but not patternBackupBuffer, so leaving or reselecting the pattern restored the old rate. The backup is now updated. The beat LED now follows three-step groups on ternary rates. check_pattern_scale gained a regression case that fails without the fix and passes with it, 1112 assertions. ARM GCC 14.3 release passed with no compiler warnings. IMG 338092 bytes, SHA256 80A18D336FD1B53F623A31FCDF37BB16BF18DC391303D2C7388E74077EB99F5B. FLASH 286656/1015808, RAM 338196/393216. Host checks passed: sct 595, performance 57227, MIDI 509679, edit/scale/hat/storage 148257, trig conditions. Whether this is what the user heard is not confirmed; device retest pending.

Mutador 0.2.20: PERF scl becomes spd, /8 /4 /2 1 *2 *4 relative to the stored pattern rate; pat and absolute overrides are gone. spd is live only, always starts at 1 and still commits at the bar with a restart. Step time is computed in ticks with a floor of six: 64 steps a bar, 48 on ternary rates, so *4 on rate 32 stops at 64 and on rate 24 at 48. Ternary detection and the 13-16 slot rule use the stored rate. Internal MIDI clock and clock-out counting moved from the step counter to the bar frame, because a six-tick step does not divide the clock. External MIDI sync alternates one and two clocks for six-tick steps. Pch CC 79-84 select spd; 85-87 return to voice parameters. The confirmed pattern rate no longer touches spd. The user was unsure about live sct switching on the quarter: 64 random switch sequences over 8 bars through the real seq_tick and seq_applyPendingTransform found no position error; removing the group alignment or the clock alternation makes the new checks fail. That harness stubs seq_nextStep, so gap slots through the full step path remain untested. ARM GCC 14.3 release passed with no compiler warnings. IMG 338308 bytes, SHA256 2C17F4482B3228387CA468F5C510F88531C685AC031BF81529B72370C70F094B. ITCM 14424/16384, DTCM 107672/131072, RAM 338196/393216, FLASH 286872/1015808. Host checks: sct 620, performance 61324, pattern scale 1110, edit/scale/hat/storage 148257, MIDI 509625, trig conditions/storage, mod target, LFO step, LXR1 import. SD F: copied and SHA256 verified; 0.2.19 matched its archive and was renamed to .imm. Device test pending.

Mutador 0.2.21: confirming pattern rate 24 or 32 sets tracks on the default length to that rate, and returning to 16 or below restores 16; hand-set lengths stay. PLAY with MIDI clock but no MIDI START now starts at once and makes the next clock the downbeat. Only MIDI START places the bar, and over 1 s without clock forgets it. The clock-offset lead does not apply to this immediate start. ARM GCC 14.3 release passed with no compiler warnings. IMG 338812 bytes, SHA256 9FE652FDDC384965DE6D534EF091A4823D5DFB32C18E814A5F348265B28BD9C1. FLASH 287376/1015808, RAM 338204/393216. Host checks: sct 620, performance 61327, pattern scale 1115, edit/scale/hat/storage 148257, MIDI 509625, trig conditions. Archived, not copied to SD: F: holds 0.2.20. Device test pending.

Mutador 0.2.22: new Pch CCs. 54 pSc, 55 avl, 56 Fill, 57 master filter enable, 58 pitch bend range, 59 FX send mode, 67 FX output mode, 68/69 clock offset and fine, 92-97 PWM, 102-107 LFO slew, 108-113 LFO polarity, 114-119 random step LFO depth. CC 1, 3, 4, 17-19, 29, 45, 53 and 71-78 stay free for the Mutador numbers; 98-101 and 120-127 are avoided as NRPN/RPN and channel mode numbers. The other random step LFO settings stay menu-only. Not changed: CC 25/81 still address IDs 0-127, so 112 of 235 destinations stay menu-only, and an LFO on Vel Dst still writes activeParameters while modulating. Manual and docs/P01_CC_MAP.csv corrected. ARM GCC 14.3 release passed with no compiler warnings. IMG 339628 bytes, SHA256 B958AE11784F9628F7AA9FC40067D2F90AA1363B89D038A104A5CD92176D42F3. Host checks: MIDI 510252, sct 620, performance 61327, pattern scale 1115, edit/scale/hat/storage 148257, snare destinations 76, LFO step. Archived, not copied to SD: F: holds 0.2.20. Device test pending.

Mutador 0.2.23: the Pch CCs added in 0.2.22 need a Pch of their own, as Morph CC2 does. If Pch equals gch or a Voice channel, those numbers keep their legacy meaning; 0.2.22 would have replaced them. Removing the guard makes the CC route check fail. LFO 2 report: no voice-specific defect in the code. CC 123 (LFO 2 depth on the global map) cannot be sent from Live's MIDI Ctrl list, and Voice 2 on channel 2 overlaps the default Pch; the user's channel settings were not read. ARM GCC 14.3 release passed with no compiler warnings. IMG 339748 bytes, SHA256 F83C5EC848C37C2A9514418D4B8D292A544A3BB2C25256E45BBEF4D23E33C71D. FLASH 288312. Host checks: MIDI 509724, sct 620, performance 61327, pattern scale 1115, edit/scale/hat/storage 148257, snare destinations 76, LFO step. SD F: copied and SHA256 verified; 0.2.20 matched its archive and was renamed to .imm. Device test pending.

Mutador 0.2.24: FX sends moved to SHIFT + Step 5 and left the regular PERF cycle. LXR_MUTADOR_VERSION now sets the image name and the startup line, which had stayed at 0.2.10. check_copy_import, check_velocity_controls, check_voice_import and check_lfo_import had been failing unnoticed on stale harnesses and were repaired; no firmware defect found. ARM GCC 14.3 release passed with no compiler warnings. IMG 339708 bytes, SHA256 FE0D3C60554B80188A5303FDB4EE7927154EC7D62B126EA9892C4608CFA9C019. ITCM 14424/16384, DTCM 107672/131072, RAM 338204/393216, FLASH 288272/1015808. Host checks: performance 61326, MIDI 509724, sct 620, pattern scale 1115, edit/scale/hat/storage 148257, LFO import 450062, velocity 196491, voice 2449, copy 29, and the remaining checks passed. SD F: 0.2.24 copied and SHA256 verified; 0.2.23 matched its archive and was renamed to .imm. New check_sct_step_path: 1451594 assertions through the real seq_nextStep, gap guard mutation fails. PROJ21..28 got GLO.CFG from the root file with bpm MID; backup under build/card-midi-backups/20261102-184434-131412. Device test pending. See session 034.
