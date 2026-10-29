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

## Build record

| Date | Branch / commit | Command | Result | Hardware check |
| --- | --- | --- | --- | --- |
| 2026-10-29 | `docs/development-notes` | Documentation setup only | Build not run for this change | Not run |

For each firmware change, add the exact commit, toolchain version, build
result, image filename and size, and any test performed on the instrument.
Keep failed attempts in the record so later sessions can see what happened.
