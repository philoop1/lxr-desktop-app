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
`LXR_V2_V<version>.img`. The version comes from `project(VERSION ...)` in
`CMakeLists.txt`. For a debug build, use the `debug` preset in both commands.

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
presets and the resulting `LXR_V2_V1.7.img`.

## Build record

| Date | Branch / commit | Command | Result | Hardware check |
| --- | --- | --- | --- | --- |
| 2026-10-29 | `docs/development-notes` | Documentation setup only | Build not run for this change | Not run |
| 2026-10-29 | Firmware source identical to `main` `a43cd4f`; GCC 10.2.1 (DaisyToolchain) | Configure and release build | Configure passed; 120/122 compile steps passed; link failed at `.ARM.extab` with `non constant or forward reference address expression` in `STM32F765VGTX_FLASH.ld:86`. No image produced. | Not run |
| 2026-10-29 | Same source; ARM GCC 14.3.rel1 | User ran the fresh release configure/build from the PowerShell instructions above. CMake cache confirms the 14.3 toolchain; output verified locally. | `LXR_V2_V1.7.img`: 274,704 bytes, SHA-256 `B34C0C3A946D02C5CEE624351A44C2597694B4832FDAA9CBAEB3627F84979AFE`. ELF `text=273828`, `data=852`, `bss=340572` bytes. | IMG-live Euclid smoke test passed; physical device not tested. |

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
