# Wavetable plan

Status: phase 1 is in Mutador 0.2.36 (hardware test pending), in a changed
form; see "Phase 1 as built" at the end. Phase 2 (scanning) is not started
and needs the user's go-ahead.

## Goal

Eight wavetables as new oscillator waveforms for the drum voices, with smooth
scanning between neighbouring tables. The idea comes from Helicase (looped
user samples plus wave interpolation), but Helicase's licence is
non-commercial and does not fit GPL-3.0. So no Helicase code is used: the
tables and the code are new.

Not in scope: user samples or loops from the SD card in flash (Helicase
Load > Samples). That needs flash erase and programming with audio stopped,
an installer, a menu and guarded metadata. It is a separate project and can
follow later on top of the same oscillator code.

## What exists today

- `Oscillator.c` already plays band-limited tables: `sawTable`, `triTable` and
  `recTable` are `int16_t [11][1024]`, one table per octave
  (`osc_calcWavetableFreq` picks `tableOffset` from the pitch), read with
  linear interpolation in `calcWavetableOscBlock`. That is about 22 KB of
  flash per waveform.
- The waveforms are `Sin Tri Saw Rec Noi PWM` (0..5). `menu_getWaveformMax()`
  is `5 + menu_numSamples`, and user samples are compiled out (`#if 0`).
- The waveform is a modulation target. With a float modulator, MidiParser
  already computes a continuous position
  (`NUM_OSC_WAVEFORMS * value.flt`) and then rounds it. That is the hook for
  scanning.
- Kit files store raw parameter bytes plus appended extension blocks (snare
  extension, LFO extras, RPS extras). New per-voice values can go into one
  more block the same way.

## Budget

| Resource | free now | wavetables need |
|---|---|---|
| CPU | user measured 67 % on 0.2.35 | about 1 % for three voices scanning (two table reads and one lerp per sample) |
| Flash | about 700 KB (linker 992 KB) | 8 x 11 x 1024 x 2 B = 176 KB with octave tables |
| RAM / DTCM | 54 KB / 23 KB | a few bytes per voice |
| ITCM | 1.5 KB | none: the new code runs from flash; it must not displace ITCM code |

A smaller option is 8 x 6 octave levels (96 KB), with the top levels shared.

## Phase 1: tables and plain playback

1. `tools/gen_wavetables.py` generates `Core/Src/Soundengine/DSPAudio/WavetableBank.c`
   with `const int16_t wtBank[8][11][1024]`. Each level is built additively
   with only the partials that stay below Nyquist for the top note of its
   octave, the same way the saw and square tables are.
2. Eight tables, ordered so that neighbours morph well (a proposal; the user
   picks):
   1. `Sft` soft: sine plus a weak 2nd and 3rd
   2. `Org` organ: drawbar 8' 4' 2 2/3'
   3. `Hol` hollow: odd partials with a tilt
   4. `Vox` formant "ooh"
   5. `Vo2` formant "aah"
   6. `Res` CZ-like resonance snapshot
   7. `FM` 1:2 FM snapshot, index about 3
   8. `Syn` hard-sync saw snapshot
3. New waveform values 6..13 after `PWM`, shown as the names above. The
   waveform menus, `menu_getWaveformMax()`, the MIDI clamps and the mod scaling
   grow to 14 entries.
4. The oscillator uses a `calcWavetableOscBlock` variant on `wtBank[n]`, both
   in normal and in FM mode, as for Saw.
5. Voices: Drum 1-3 main oscillator first. Snare, the snare layer, and the
   Cymbal and Hihat oscillators only after a CPU measurement.

Compatibility: an older firmware plays a kit that uses waveform 6..13 as
silence. That needs a note in the manual.

## Phase 2: scanning

1. A new per-voice parameter `scn` (0..127) on the Drum 1-3 pages. It crossfades
   from the selected table towards the next one. 127 reaches the next table;
   above table 8 it stays there.
2. Store it in a new kit extension block (`WTB1`, 3 bytes and a checksum),
   like the LFO and RPS extras, so old kits load with 0.
3. Add `scn` as a modulation target at the end of the target list, so LFO,
   velocity and Morph move it. Saved targets keep their indices.
4. Optionally, a float modulator on the waveform target scans too, instead of
   jumping.
5. The oscillator reads two tables at the same phase and blends them. It costs
   one extra lookup and lerp per sample, and nothing when `scn` is 0.

## Tests (host, like the other checks)

- `check_wavetables.py`: the generator is deterministic. A DFT of each level
  shows no partial above Nyquist for its octave's top note. The peak stays at
  full scale without clipping.
- The real oscillator code compiled on the host: `scn` 0 equals the plain
  table, 127 equals the next table, the path between is continuous, and FM and
  plain mode agree at zero FM.
- Kit round trip: a saved `WTB1` block reloads, an old kit loads `scn` 0, and a
  bad checksum is ignored.
- Mutation runs as before (for example, a missing octave selection must fail
  the alias check).
- On the device: CPU value with three scanning voices and Tape delay, compared
  with the 67 % today.

## Open questions for the user

- Which eight tables, or the proposal above?
- Drum 1-3 only, or Snare and the layer as well?
- `scn` on the voice page: which slot may it take?
- 11 octave levels (176 KB) or 6 (96 KB)?

## Phase 1 as built (0.2.36)

The user chose user tables instead of eight built-in ones:

- `tools/make_wavetables.py` turns up to 12 single-cycle WAV files into
  `WAVES/WAVES.BIN` (128-byte header with magic `LXRWT001`, names and a zlib
  CRC-32, then `int16 [count][10][1024]`). It removes DC, takes the spectrum
  and builds 10 octave levels; level j keeps the harmonics below 20 kHz at
  55 Hz * 2^j (at most 511). One gain per table brings the loudest level to
  32000. Names are three letters of the file name, with automatic numbers on
  collisions.
- The linker gives the image 736 KB (sectors 1 to 6). `WaveBank.c` keeps the
  tables in sector 7 (0x080C0000, 256 KB; 12 tables need 240 KB).
- At boot, after the SD mount and before the kits load, `main.c` shows
  "Loading waves" and calls `waveBank_installFromSd()`: it skips an equal
  header, checks the whole file's CRC before it erases, writes the data and
  the header last, and `waveBank_init()` checks the CRC over the flash.
- The waveform values 6 to 6+count-1 play the tables through the existing
  `calcWavetableOscBlock` and `calcFmBlock`; expo FM reads them with
  `osc_readTable`; PD plays them plain. Only Drum 1-3 main oscillators offer
  them (menu `MENU_WAVEFORM_WT`).
- `tools/check_wavebank.py` tests the generator and the real `WaveBank.c`
  with RAM as NOR flash.

## Phase 2 as built (0.2.37)

The user chose the existing PWM parameter for scanning instead of a new `scn`
parameter. PWM is a per-voice float that kits store, Morph blends and LFO,
velocity and automation reach, so no kit block or new target was needed.
`osc_waveBankScan()` maps PWM 0..1 from the selected table to the last one;
`osc_readScan()` reads the two neighbouring tables at the same phase and
level and blends them (Q15). Plain, FM, ring, expo FM and PD all scan. The
0.2.36 plain mode was silent because the default case of
`calcNextOscSampleBlock` was still the empty sample stub; it now calls
`calcWaveBankBlock`. `tools/check_osc_modes.py` runs the real dispatchers on
a fake bank of 3 tables.

## Serum frames (0.2.38)

The user wanted PWM to scan inside one wavetable, as in Serum, instead of
across all tables. `KRC Sampler Serum` holds 127 Serum files with 4, 7, 8, 16
or 64 frames of 2048 samples. With 20 KB per frame only 12 frames fit, so the
levels got short: level j has 1024, 512, 256, 128 and then 64 samples
(2304 samples, 4.6 KB per frame), which keeps about 2.8 samples per kept
partial on levels 0 to 4. 56 frames fit in sector 7. Format `LXRWT002` adds a
frame count per wavetable to the header (covered by the CRC). The oscillator
reads a level with `osc_readLevel` (length 2^bits) and blends two frames.

## Sectors 7 to 11 (0.2.40)

0.2.39 showed "2048 single" on the device: 2 MB, single bank, sectors 8 to 11
of 256 KB exist. The bank now spans sectors 7 to 11 (1280 KB, 284 frames of
2304 samples, up to 255 per wavetable). Install erases only the sectors the
file needs, one by one, with a progress callback; the header is still written
last. `waveBank_available()` reads the flash size register and refuses a bank
past the chip. The generator takes file and folder sources (Serum `clm `,
Surge `srge`, Surge `.wt`, folders of single cycles as in Helicase) and
`--each`. Risk: the LXR bootloader may erase sectors 8 to 11 on a firmware
update; the CRC fails then and the next boot with the card writes them again.

## 32 slots (0.2.41)

The user wants single waves picked by name, like a Casio, so a folder built
with `--each` needs more than 12 slots. `WAVEBANK_MAX` is 32, the header 256
bytes (names at 24, frames at 152, padding from 184), format `LXRWT003`. The
frame budget stays 284. Next idea under discussion: crossfade the kit's and the
morph kit's waveform live with the morph value instead of stepping the index.

## Slot scan and level blend (0.2.42)

The user heard slight clicks and wants Casio-style named waves that can still
be scanned. PWM on a single-frame slot scans the run of single-frame slots
after it (stopping at a multi-frame wavetable or the count); a multi-frame
slot scans its frames. `osc_levelMix()` gives the share of the next octave
level (level j fades into j+1 from 27.5 Hz * 2^j to 55 Hz * 2^j), so a pitch
envelope no longer switches partials at once; `OscInfo.scanPos` glides to
PWM by `OSC_SCAN_GLIDE` (0.1) per block. A read now costs up to four
interpolated level reads.
