# LXR V2 firmware (desktop, STM32F765VG)

Firmware for the LXR V2 desktop drum machine: an STM32F765 (Cortex-M7, 216 MHz) running the
drum voices, FX bus, step sequencer, MIDI (DIN + USB), SD-card preset storage and the LCD/button UI.

This fork's development notes are in [BUILD_NOTES.md](BUILD_NOTES.md), its
user-facing changes in [CHANGELOG.md](CHANGELOG.md), and its numbered work
records in [docs/sessions](docs/sessions/README.md). The chapter-based
[manual](manual/README.md) describes the current desktop firmware.
The proposed [mutador import plan](docs/IMPORT_MUTADOR_PLAN.md) tracks future
work; its checkboxes do not claim that a feature has already been ported.

## Experimental Mutador changes

Current preview: **Mutador 0.2.62**, experimental and awaiting broader physical-device
checks of its new controls. The startup display identifies this version.

- **SHIFT+Step 1 from every mode:** opens pattern selection with the first PERF view.
- **Velocity headroom:** new/reset steps default to 100. The active projects and TMP on the mounted card were proportionally converted once, with verified backups.
- **rvl then avl after cnt:** Mutador Random Velocity plus a -100 to +100 percent proportional velocity gain for all sequencer voices and MIDI output: +50 is x1.5, +100 is x2, clipped at 127. Both persist with project settings; pbr moves to the last field.
- **Pattern Scale 2/4/6/8/12/16/24/32:** hold LOAD (from 0.2.52; PERFORMANCE before), turn the encoder to preview, then click to confirm. A running change starts Step 1 on the next transport bar; stopped changes apply immediately. Confirmation enables `scl=pat`. Save the pattern/project to retain it.
- At **12**, each 16-step page plays slots 1-12; slots 13-16 remain stored. Other divisions retain all 64 steps. At **32**, 64 steps take two bars; **6** and **24** provide triplet timing.
- **Random per played Step LFO (`rps`):** its `rtg` voice supplies triggers only from audible sequencer Steps; the target `voi` is independent. The third/fourth LFO views expose trigger, destination, amount, offset, slew and neg/pos/bi polarity. Kit storage has compatible defaults for old kits.
- **Step Flam Probability (`fpr`):** after the main Step passes `prob`, fpr decides whether its Flam repeats play. It is saved per Step; old patterns default to 100.
- **Stray/Glide LFOs** (`str`/`gld`), with smooth random motion, Offset bias and Retrigger behavior. `ofs=63` is neutral.
- **Common Voice-CC map** on the voice channels, including Snare CC112-118, LFO controls and destination selection. Global/Pch channels retain priority; the first matching voice wins on a shared channel.
- **Snare noise envelope and second oscillator** with Mix/FM/Ring, kit storage, Morph and LFO/velocity/step destinations. Snare OSC/FM names and ordering follow Mutador, retaining PWM in place of Membrane.
- Dedicated **SHIFT+2 Accent**, **SHIFT+3 MIDI Delay** and **SHIFT+4 Groove** windows stay out of regular PERF navigation. The separate VCA volume view is hidden; the VCAs remain active.

See the [Performance chapter](manual/chapters/07_performance.md),
[MIDI map](manual/chapters/05_midi_and_clock.md), and
[latest session](docs/sessions/031-random-step-lfo-flam-probability.md).
The release build and native source/timing/storage tests passed. This does
not establish sound, timing or CPU parity on the physical instrument.

The performance corrections through 0.1.4 cover Morph updates, master `srt`
across the full Morph range, the `lsh`/`lmp`/`lsr` load choices, and
SHIFT + Step 1 pattern selection while retaining the PERF display.
The user reported that 0.1.4 works on the physical LXR V2 on 2026-10-29.
This is a targeted device check, not validation of every setting or old project.

According to the project author, these performance issues had been reported
to Erica Synths over several years. This fork records that account and the
current fixes; it does not establish the history or status of upstream reports.
The additional `Pch` MIDI control channel is separate import work under P01,
and is not part of these longstanding performance corrections.

> **Licence and trademarks:** the firmware source code is free software under the GNU GPL version 3
> ([LICENSE](LICENSE)). You're welcome to study, change and share it, for example to write your own
> updates for your LXR. The names **"Erica Synths" and "LXR"** and the **LXR hardware** are the property
> of Erica Synths and are **not** covered by this licence. Building and installing your own firmware is
> at your own risk: Erica Synths provides no support for self-built or modified firmware. See
> [Licence, trademarks and hardware](#licence-trademarks-and-hardware) below and [NOTICE.md](NOTICE.md).

0.1.6 additionally imports Mutador's Global drum-map/ANY fallback, chromatic
Voice input without echo and live Pch-note master transpose. It includes the
CC channel-index correction. Build and native tests pass; device testing is
pending. See the [MIDI chapter](manual/chapters/05_midi_and_clock.md).

0.1.7 completes the Mutador pitch calculation and adds PERF **gpt** and **pbr**.
It is built and copied to the SD card; hardware validation is pending.

0.1.8 adds PERF **gdc** next to **gpt**, plus **rst**, **csr**, BC **pSc**,
and global **pst** on the next PERF page. Hold first/last pattern buttons
to form a 606-style live loop. Source patterns remain editable and unchanged.
The image is built, tested natively and copied to the card; hardware checks
remain open. See the [sequencer chapter](manual/chapters/03_sequencer_and_patterns.md).

0.1.10 adds the Velocity/Accent page (SHIFT + Step 2), MIDI Delay page
(SHIFT + Step 3) and per-step chance scaling `cnt`. On the Delay page the
instrument buttons and LEDs select incoming voices. The image passed the
release build and native tests and was copied to the SD card. Hardware tests
remain open; see [session 018](docs/sessions/018-accent-and-midi-delay.md).

0.1.12 adds Mutador's four-point Groove with exact fine positions, source
automation and Delay follow-up timing. SHIFT + Step 4 opens `shf/sh2/sh3/sh4`.
The shapes are saved, while `lsh=off` preserves the live groove during loading.
It also includes the project file-selection and edit-backup fixes from the
local 0.1.11 build. Release and native tests passed; physical-device checks
remain open. See [session 020](docs/sessions/020-four-point-groove.md).

## Updating your LXR

Mutador 0.1.17 synchronizes the PLAY button and its LED with incoming MIDI
START, CONTINUE and STOP. A local PLAY stop resets the step position; the
next PLAY begins at Step 1 on the next MIDI Clock bar. See
[session 025](docs/sessions/025-midi-transport-play-state.md).

Mutador 0.1.16 adds Snare Layer (`slw/sla/slf/slm`), COPY gestures for
individual steps, eight-step groups and tracks across patterns, plus a
manual PLAY that can start at the next MIDI Clock bar boundary. Device tests
for these changes are still pending; see [session 024](docs/sessions/024-copy-start-snare-layer.md).

Mutador 0.1.15 adds the Snare Noise Envelope, Ring mode for Drum Voices 1–3,
and adjustable MIDI Clock Offset in Global. The release image and native
tests passed; sound and timing on the physical LXR still need testing. See
[session 023](docs/sessions/023-snare-ring-clock.md).

0.1.13 renames `kcm` to `lki`, groups the four load controls together and
adds the explicit `cko=16sh` output for shuffled sixteenths. The user reported
that 0.1.12 works; 0.1.13 passed the release build and clock tests and was
copied to the card with hash verification. Its new display/output controls
still need a device check. See [session 021](docs/sessions/021-load-labels-and-16sh-clock.md).

Every LXR has a built-in updater (the bootloader) that installs new firmware from the SD card. You
don't need any extra hardware:

1. [Build the firmware](#building-the-firmware). The latest archived image is `LXR_V2_V1.7_Mutador0.1.26.img`.
2. [Copy it to the SD card and install it](#installing-the-update) on the LXR.

### Building the firmware

You need [CMake](https://cmake.org/download/) 3.21 or newer, [Ninja](https://ninja-build.org/),
the [Arm GNU Toolchain](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads)
(`arm-none-eabi-gcc`, tested with 14.3.rel1 and 11.3.rel1) and [Python 3](https://www.python.org/downloads/)
(to create the `.img` update file). The build finds them on `PATH`.

**1. Install the tools (once)**

*macOS* (Apple Silicon and Intel), with [Homebrew](https://brew.sh):

```sh
brew install cmake ninja
brew install --cask gcc-arm-embedded
```

Use exactly this `--cask gcc-arm-embedded` package, the official Arm toolchain. The similarly named
`brew install arm-none-eabi-gcc` does **not** include the C library the firmware needs, and the build
fails with it. Python 3 comes with the Xcode Command Line Tools, which Homebrew installs.
If you installed the toolchain with Arm's own `.pkg` installer instead, it isn't on `PATH`: add
`-DARM_TOOLCHAIN_DIR=/Applications/ArmGNUToolchain/<version>/arm-none-eabi/bin` to the first `cmake`
command below.

*Windows:* install CMake, Ninja and Python 3 (e.g. `winget install Kitware.CMake Ninja-build.Ninja
Python.Python.3.12`) and the Arm GNU Toolchain with its Windows installer. On the installer's last page,
tick "Add path to environment variable".

*Linux:* install CMake, Ninja and Python 3 with your package manager (e.g.
`sudo apt install cmake ninja-build python3`) and the Arm GNU Toolchain from Arm's download page, then
add its `bin` folder to `PATH`.

**2. Build**

Open a terminal (Terminal on macOS, PowerShell on Windows) in this folder and run:

```sh
cmake --preset release
cmake --build --preset release
```

When the build has finished it shows where the update file is and how to install it:

```
======================================================================
  Firmware update file:
    .../lxr2-Mutador/build/release/LXR_V2_V1.7_Mutador0.2.62.img
  ...
```

The base version `1.7` comes from `project(VERSION ...)` in
[CMakeLists.txt](CMakeLists.txt). `LXR_MUTADOR_VERSION` in the same file sets the
`Mutador0.2.62` suffix of this experimental fork image and the `Mutador 0.2.62`
line on the startup screen.
Verified build artifacts and their hashes are in the
[firmware image archive](firmware-archive/README.md).

### Installing the update

1. Copy `LXR_V2_V1.7_Mutador0.1.26.img` from `build/release/` to the top folder of the SD card. Delete any
   older `LXR*.img` files from the card: the updater installs the first one it finds.
   On a Mac, eject the card in Finder before you take it out. Finder also leaves hidden files starting
   with `._` on the card; the updater ignores them.
2. Switch the LXR off and put the card in.
3. Hold down the encoder button and switch the LXR on. Keep holding the button until
   "LXR Updater" appears on the display.
4. The display shows "Checking Firmware...", then "Loading Firmware" with the progress in percent.
5. When it shows "Update OK!" the LXR restarts by itself with the new firmware.

The updater itself is never changed by an update. If an update fails or is interrupted (for example by
a power cut), the LXR can always be updated again the same way.

### Troubleshooting

If the updater stops with one of these messages, switch the LXR off, fix the cause and try again:

| Display | Cause |
|---|---|
| `can't mount` / `SD Card` | No SD card, or the card can't be read. The card must be formatted as FAT32. Cards larger than 32 GB usually come formatted as exFAT, which the updater can't read. On a Mac, reformat the card in Disk Utility with the format "MS-DOS (FAT)". |
| `LXRE*.img` / `Not Found!` | No update file in the top folder of the card. The file name must start with `LXR` and end with `.img`. |
| `Can't open` / `LXRE*.img!` | The update file couldn't be read. Copy it to the card again. |
| `LXR*.img` / `Not Valid!` | The file isn't an update for the desktop LXR (for example a Eurorack module update, or a damaged file). |
| `LXR*.img` / `Wrong Size!`, `Wrong` / `Checksum!` | The file is damaged or incomplete. Build it again or copy it to the card again. |
| `Can't erase` / `Flash!`, `Flash write` / `Error!` | Writing the firmware to the LXR's memory failed. Switch the LXR off and try the update again. |

## Build options

| Option | Effect |
|---|---|
| `cmake --preset debug` | Debug build: `-O3 -g3` with `DEBUG` defined, output in `build/debug/`. The release build uses `-O3 -g0`. Both need `-O3` for the audio engine to keep up in real time. |
| `-DARM_TOOLCHAIN_DIR=<bin folder>` | Use a toolchain that isn't on `PATH`, e.g. `/Applications/ArmGNUToolchain/14.3.rel1/arm-none-eabi/bin` (macOS) or `C:/toolchain_arm-none-eabi/11.3rel1/bin` (Windows) |
| `-DLXR_ITCM_OPT=<flag>` | Optimisation for the code in the fast ITCM memory, see [Memory map](#memory-map) (default `-O2`) |
| `-DLXR_GENERATE_LISTING=ON` | Also write a disassembly listing (`.list`) |

Options are passed when configuring, e.g. `cmake --preset release -DLXR_GENERATE_LISTING=ON`.
The toolchain file and the CMake modules and tools are in the `cmake/` folder.

All files the build creates (in `build/<preset>/`):

| File                     | Purpose                                                        |
|--------------------------|----------------------------------------------------------------|
| `LXR_V2_V1.7_Mutador0.1.26.img` | **Update file for the SD card** (see [Installing the update](#installing-the-update)) |
| `LXR_V2_STM32F765.elf`   | Firmware with debug information, for a debugger               |
| `LXR_V2_STM32F765.bin`   | Raw firmware image (from 0x08008000)                          |
| `LXR_V2_STM32F765.hex`   | Intel HEX of the same                                         |
| `LXR_V2_STM32F765.map`   | Linker map                                                    |

## Cleaning the build

**Remove the compiled files** (including the `.img`) but keep the settings. The next build then
compiles everything again:

```sh
cmake --build --preset release --target clean
```

Use `--preset debug` to clean the debug build.

**Start completely from scratch:** delete the build folder, which also forgets all settings such as
`-DARM_TOOLCHAIN_DIR` or `-DLXR_BOOTLOADER_HEX`, then configure and build again:

```sh
rm -rf build                        # Linux, macOS, Git Bash
Remove-Item -Recurse -Force build   # Windows PowerShell
rmdir /s /q build                   # Windows Command Prompt

cmake --preset release
cmake --build --preset release
```

Start from scratch when you switch to a different compiler (another `ARM_TOOLCHAIN_DIR`, or a
different `arm-none-eabi-gcc` on `PATH`), because an existing build folder keeps using the compiler it
was first set up with. Do the same if the build behaves strangely after updating the sources.
With CMake 3.24 or newer, `cmake --preset release --fresh` redoes the setup without deleting the folder.

The `build/` folder is never committed to git.

## Memory map

| Region   | Address                   | Size   | Contents                                              |
|----------|---------------------------|--------|-------------------------------------------------------|
| FLASH    | 0x08000000 Ã¢â‚¬â€œ 0x08007FFF   | 32 KB  | Bootloader (`LXR_V2_STM32F765_Bootloader`)            |
| FLASH    | 0x08008000 Ã¢â‚¬â€œ              | 992 KB | This firmware (`VECT_TAB_OFFSET` 0x8000)              |
| ITCM     | 0x00000000                | 16 KB  | `IN_ITCM_RAM` hot DSP code, copied there by `main()`  |
| DTCM     | 0x20000000                | 128 KB | `INDTCM`/`INDTCMZ` data, DMA buffers, the stack       |
| RAM      | 0x20020000                | 384 KB | `.data`, `.bss`, heap                                 |

The ITCM is tight. Current GCC releases generate too much code at `-O3` for it, so the translation
units that contain ITCM code are compiled with `LXR_ITCM_OPT` (default `-O2`). The linker prints
region usage after every build.

## Source layout and CMake targets

The project was originally generated with STM32CubeMX/STM32CubeIDE, which explains the directory
layout and the `USER CODE BEGIN/END` comments. It no longer depends on either tool: the CubeMX project
(`.ioc`) was removed because regenerating code from it overwrites application code in `main.c`.
Pins, clocks and peripherals are configured in `Core/Inc/main.h`, `Core/Src/main.c`
(`SystemClock_Config`, `MX_*_Init`) and `Core/Src/stm32f7xx_hal_msp.c`; edit them there.

Every component is an OBJECT library linked into `LXR_V2_STM32F765`:

| Target          | Sources                                         | Contents                                              |
|-----------------|-------------------------------------------------|-------------------------------------------------------|
| `stm32f7_hal`   | `Drivers/`                                      | ST HAL + CMSIS                                         |
| `fatfs`         | `Middlewares/Third_Party/FatFs`, `FATFS/`       | FatFs and the SD card glue                            |
| `usb_midi`      | `Middlewares/JS`, `USB_DEVICE_MIDI/`            | USB device stack with the custom USB-MIDI class       |
| `lxr_platform`  | `Core/Startup`, `Core/Src/main.c`, ...          | Startup, clocks, peripheral init, interrupts          |
| `lxr_io`        | `Core/Src/IO`                                   | Button/LED shift registers, pots and faders           |
| `lxr_ui`        | `Core/Src/menu`, `lcd.c`, `buttonHandler.c`, ...| LCD, encoder, buttons, LEDs, menu pages               |
| `lxr_preset`    | `Core/Src/Preset`                               | Kit/pattern/project load & save on SD                 |
| `lxr_dsp`       | `Core/Src/Soundengine/DSPAudio`                 | Oscillators, filters, envelopes, voices, master FX    |
| `lxr_engine`    | `Core/Src/Soundengine/*.c`                      | Codec/I2S DMA, sample block rendering, FX bus, clock in/out |
| `lxr_midi`      | `Core/Src/Soundengine/MIDI`                     | MIDI UART, parsers, parameter mapping                 |
| `lxr_sequencer` | `Core/Src/Soundengine/Sequencer`                | Step sequencer, Euclidean generator, clock sync       |
| `lxr_usb_app`   | `Core/Src/Soundengine/USB`                      | USB-MIDI message queue                                |

Source files are listed explicitly in the `CMakeLists.txt` files. Add new files there.

## Advanced: programming with a debug probe

Not needed for updates: use the [SD card](#installing-the-update) for that. This section is for
development, factory programming and repairs, with an ST-Link debug probe connected to the LXR's
debug header and [OpenOCD](https://openocd.org/) installed (the build finds it on `PATH`; on macOS:
`brew install open-ocd`).

**Firmware only.** Writes just the firmware; the bootloader is left alone:

```sh
cmake --build --preset release --target flash
```

**Blank devices (bootloader + firmware).** A blank device, or replacing the bootloader on purpose,
needs the bootloader as well. The bootloader is a separate project, so by default the build doesn't
include it. Tell the build where to find it in one of two ways:

```sh
# A: a prebuilt bootloader .hex (e.g. from a bootloader release)
cmake --preset release -DLXR_BOOTLOADER_HEX=path/to/LXR_V2_STM32F765_Bootloader.hex

# B: the bootloader source code, which is then built together with the firmware
cmake --preset release -DLXR_BOOTLOADER_DIR=path/to/LXR_V2_STM32F765_Bootloader
```

The build checks that the bootloader is valid for this device: it must fit in the 32 KB bootloader
sector and accept desktop (`LXRV2IMG`) update images, so the firmware, a full image or the Eurorack
bootloader are rejected. It then also writes `LXR_V2_V<version>_full.hex`/`.bin` (bootloader +
firmware, the whole flash from 0x08000000) and enables:

```sh
cmake --build --preset release --target flash_full
```

The same `.hex`/`.bin` can also be loaded with STM32CubeProgrammer (the `.bin` goes to 0x08000000).
To go back to a firmware-only build, clear the setting: `-DLXR_BOOTLOADER_HEX=` or `-DLXR_BOOTLOADER_DIR=`.

> **Warning:** `flash_full` overwrites the bootloader. If that is interrupted, the device can no longer
> update itself from the SD card and has to be recovered with a debug probe. The target therefore
> prints a warning and only continues after you type `yes`; without an interactive terminal (e.g. a
> build started from an IDE) it refuses. For scripts and factory programming, set the environment
> variable `LXR_CONFIRM_BOOTLOADER_OVERWRITE=yes` to skip the question.

The bootloader write-protects its own flash sector (sector 0) every time it boots, so on a unit that
has run before, sector 0 cannot simply be erased. `flash_full` therefore clears that protection first;
the new bootloader sets it again on its first boot. Other programming tools need the same step
(in STM32CubeProgrammer: Option bytes Ã¢â€ â€™ Write protection Ã¢â€ â€™ uncheck nWRP0).

The OpenOCD settings can be changed with `LXR_OPENOCD_INTERFACE`, `LXR_OPENOCD_TRANSPORT`,
`LXR_OPENOCD_SPEED` (default 1000 kHz) and `LXR_OPENOCD_WORKAREA` (default 0x8000). The defaults are
deliberately conservative: with a 64 KB work area at the faster default clock, an ST-Link V2 (firmware
V2J29) failed half-way through programming.

## Licence, trademarks and hardware

Copyright (C) 2012-2026 Erica Synths.

**Firmware licence.** The firmware, the bootloader and the build system are licensed under the
[GNU General Public License version 3](LICENSE) (GPL-3.0-only), with an additional permission for
the STMicroelectronics libraries and the additional terms in [NOTICE.md](NOTICE.md). In short:

- You may use, study and change the firmware, for example to build your own updates for your device.
- If you share or distribute the firmware, or a modified version of it, including pre-installed on a
  device, you must provide the complete source code under the same licence, and the people you give it
  to may install their own modified versions.
- Modified firmware must be marked as modified (its start-up screen must show this, e.g. with a
  different name or version text) and must not be presented as official Erica Synths firmware.
- The firmware comes **without any warranty**. Building and installing your own or modified firmware is
  entirely at your own risk, and Erica Synths provides no support for it.

**Trademarks.** "Erica Synths", "LXR" and "LXR-02" and the associated logos are trademarks of
Erica Synths. The GPL licence does **not** grant any right to use them. They may not be used for any
product, firmware release, service or commercial activity without prior written permission from
Erica Synths. Truthful references such as "custom firmware for the Erica Synths LXR-02" are fine.

**Hardware.** The LXR hardware (schematics, circuit board layouts, front panel, enclosure and industrial
design) is the intellectual property of Erica Synths and is protected by copyright and design rights.
It is **not** part of this repository and is **not** licensed under the GPL or any other licence. It may
not be copied, manufactured or sold, in whole or in part, without prior written permission from
Erica Synths.

**Third-party code.** The repository includes components from STMicroelectronics, Arm and ChaN (FatFs)
under their own licences. See [NOTICE.md](NOTICE.md#third-party-components).


<sup>
Use code OPENLXR15 on the Erica Synths website for a discount on the LXR (active for 1 week since open-source announcment) :)
</sup>
