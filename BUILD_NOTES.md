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

The update image is written under `build/release/` as
`LXR_V2_V1.7_Mutador0.1.2.img`. The base version comes from
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
presets and the resulting `LXR_V2_V1.7_Mutador0.1.2.img`.

## Build record

| Date | Branch / commit | Command | Result | Hardware check |
| --- | --- | --- | --- | --- |
| 2026-10-29 | `docs/development-notes` | Documentation setup only | Build not run for this change | Not run |
| 2026-10-29 | Firmware source identical to `main` `a43cd4f`; GCC 10.2.1 (DaisyToolchain) | Configure and release build | Configure passed; 120/122 compile steps passed; link failed at `.ARM.extab` with `non constant or forward reference address expression` in `STM32F765VGTX_FLASH.ld:86`. No image produced. | Not run |
| 2026-10-29 | Same source; ARM GCC 14.3.rel1 | User ran the fresh release configure/build from the PowerShell instructions above. CMake cache confirms the 14.3 toolchain; output verified locally. | `LXR_V2_V1.7.img`: 274,704 bytes, SHA-256 `B34C0C3A946D02C5CEE624351A44C2597694B4832FDAA9CBAEB3627F84979AFE`. ELF `text=273828`, `data=852`, `bss=340572` bytes. | IMG-live Euclid smoke test passed; physical device not tested. |
| 2026-10-29 | `feature/pch-cpu`; ARM GCC 14.3.rel1 | Six modified C translation units passed `-fsyntax-only`; release Ninja build completed 34/34 steps. The sandbox build stalled, then the approved build completed. | `LXR_V2_V1.7.img`: 275,132 bytes including 16-byte update header; SHA-256 `C5D2AE5C0F07C0A06AC888457AA051448B2380111373A7CA7E09D126853B983F`. ELF `text=274252`, `data=856`, `bss=340572` bytes. | Pch CC 2, CPU meter and old SD data have not been tested on hardware. |
| 2026-10-29 | `feature/pch-cpu` `af7feb3`; naming/archive | Reconfigured CMake and rebuilt 2/2 steps. The new name has the same image bytes as the Pch/CPU build above. | `LXR_V2_V1.7_Mutador0.1.img`: 275,132 bytes, SHA-256 `C5D2AE5C0F07C0A06AC888457AA051448B2380111373A7CA7E09D126853B983F`. Baseline and fork images are archived in `firmware-archive/`. | Not run. |
| 2026-10-29 | `fix/perf-pattern-morph`; GCC 14.3.rel1 | Changed button handler, morph walk and image suffix. Syntax checks passed; approved Ninja release build passed 4/4 steps, then a final 3/3 rebuild after correcting the Euclid request index. | `LXR_V2_V1.7_Mutador0.1.1.img`: 275,220 bytes, SHA-256 `047992BA5A9EEDEA29A05A33DA6E0D79C6C1D7268EE8A33A2CA59AE2DD18B9B8`; ELF `text=274340`, `data=856`, `bss=340564` bytes. | Awaiting hardware retest. 0.1 booted and showed 67% CPU, but Morph had no audible effect despite another kit being loaded and value changing. |
| 2026-10-29 | `feature/global-load-switches`; GCC 14.3.rel1 | ARM syntax checks passed; legacy global offsets confirmed. Approved Ninja release build passed 32/32 steps and a final 3/3 rebuild after marking loaded Morph targets dirty. | `LXR_V2_V1.7_Mutador0.1.2.img`: 275,588 bytes, SHA-256 `75CC47E9B862CB58F3F3492190BEA6356276D050F07D395BA5F5B64A41C50148`; ELF `text=274708`, `data=856`, `bss=340572` bytes. | `lsh`, `lmp` and Morph audio need hardware testing. |

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
