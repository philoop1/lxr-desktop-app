# 9. Making your own samples and wavetables

Firmware: Mutador 0.2.107. This chapter shows step by step how to turn WAV
files into the two bank files the LXR reads from the SD card:

| File on the card | What it holds | Built with |
|---|---|---|
| `WAVES/WAVES.BIN` | up to 32 wavetables for the oscillators | `tools/make_wavetables.py` |
| `SAMPLES/SAMPLES.BIN` | up to 48 one-shot samples | `tools/make_samples.py` |

The ready-made card in [`SD-Card/`](../../SD-Card) already contains both
files. You only need this chapter for your own sounds. The details of how the
voices play them are in [Voices and sound](02_voices_and_sound.md).

## 1. What you need

- A computer with **Python 3** (python.org; on Windows tick "Add python.exe
  to PATH" during the install). No extra packages are needed.
- This repository on the computer: "Code" -> "Download ZIP" on GitHub and
  unpack it, or `git clone`.
- The SD card of the LXR in a card reader. The examples use `F:` as the card
  drive; use your own drive letter (macOS: `/Volumes/<name>`).

Open a terminal (Windows: PowerShell or cmd) **in the repository folder**, the
folder that contains `tools/`. Check Python with:

```bash
python --version
```

On macOS and Linux the command may be `python3` instead of `python`.

## 2. Wavetables

### Which files work

Every *source* becomes one wavetable:

- **a Serum WAV**: a wavetable with frames of 2048 samples (or the size its
  `clm ` chunk names). Most "Serum/Vital" wavetable packs are this kind.
- **a Surge WAV** (frame size in its `srge` chunk) or a **Surge `.wt`** file.
- **any other WAV**: one single cycle, a wavetable with one frame.
- **a folder** of WAV/.wt files: one wavetable, all files in name order, each
  adding its frames. A folder of single cycles becomes one table you can scan.

WAV files may be 8, 16, 24 or 32 bit or 32-bit float, mono or stereo (stereo
is mixed to mono).

### Build the file

Put the sources you want into one folder on the computer, for example
`my_waves/`, then choose one of the two forms:

```bash
python tools/make_wavetables.py my_waves/bell.wav my_waves/pad.wav my_waves/glass F:/
```

lists each source and gives it its own wavetable (here three). The last
argument is the **card root**: the tool creates `WAVES/WAVES.BIN` there itself.

```bash
python tools/make_wavetables.py --each my_waves F:/
```

makes **every file** of the folder its own wavetable, so each one gets its own
name in the Waveform list. This is the easy way for a folder of Serum
wavetables or single cycles.

The tool prints the slots, the three-letter names and the frames each table
keeps, and the size of the file. You can also build into a folder on the
computer first (for example `out/`) and copy `out/WAVES/WAVES.BIN` to the card
later.

### Limits

- at most **32 wavetables**, at most **255 frames** per table and **284
  frames** together. Where there are more, the tool keeps evenly spaced frames
  (first and last included) and says so in its list.
- names are the first three letters of the file or folder name; where several
  share them, two letters and a number (`KR1`, `KR2`, ...). Rename the files
  before building if you want other names.
- **space for samples:** wavetables and samples share the flash. Up to **56
  frames** of wavetables fit in the first 256 KB sector and leave the full
  1 MB for samples. Every further 56 or so frames of wavetables take 256 KB
  from the samples.

## 3. Samples

### Which files work

WAV files, 8, 16 or 24 bit or 32-bit float, mono or stereo (mixed to mono),
**8 to 96 kHz**. The sample rate stays as it is: coarse 0 plays a sample at its
own pitch. The end of each sample fades out over 64 frames so it does not
click.

### Build the file

The first argument is the **SAMPLES folder on the card**, then the WAV files
or folders:

```bash
python tools/make_samples.py F:/SAMPLES my_samples
```

takes all WAV files of `my_samples/` in name order. Names are the first three
letters of the file name. For your own names write a list file, one
`name|file` per line (paths relative to the list file, `#` starts a comment):

```text
# my_samples/list.txt
kik|kick 01.wav
snr|snare dry.wav
cow|808 cowbell.wav
```

```bash
python tools/make_samples.py F:/SAMPLES --list my_samples/list.txt
```

`--crash` adds the 909-style crash of the LXR1 as the last sample.

Next to `SAMPLES.BIN` the tool writes `SAMPLES.TXT`: each sample with its
waveform number, name, length and rate.

### Limits

- at most **48 samples**.
- all together about **1 MB** (about 11.9 s at 44.1 kHz, 23.8 s at 22.05 kHz),
  less when the wavetables need more than one sector (see above). The tool
  refuses a bank over 1 MB; with large wavetables the LXR shows "No sample
  space".
- Lower sample rates save room: 22.05 kHz halves the size of a 44.1 kHz
  sample.

## 4. On the LXR

1. Put the card into the LXR and switch it on.
2. The display shows **"Loading waves"** and/or **"Loading samples"**, then
   the number of tables or samples ("12 wavetables", "17 samples"). Copying
   happens only when a file is new or changed and can take up to a minute;
   later boots only compare.
3. Pick a sound in a voice's **Waveform** menu. The numbers stay fixed:
   0 to 5 built-in waves, 6 to 37 wavetables, 38 and up samples. Empty
   wavetable slots are skipped.
4. On a wavetable, **PWM** scans through its frames (or through the following
   single waves).

The banks stay in the LXR's flash when the card has no new file. A firmware
update can erase them; the next boot with the card copies them again.
"WAVES.BIN error" or "SAMPLES.BIN err" means a broken file: the LXR keeps the
banks it already had. "No sample space" means the samples do not fit behind
the wavetables: use fewer wavetable frames or shorter samples.

**Kits remember the waveform number.** If you build a new bank with the sounds
in another order, kits that used a slot play whatever sits there now. Keep the
order (add new sounds at the end) if your kits should keep sounding the same.

## 5. Example: the free KRC Mathwaves pack

The wavetables on the ready-made card come from the free collection of KRC
Mathwaves by Kevin R. Crosley (https://www.wavetables.lol/l/free, see
[`SD-Card/WAVES/CREDITS.md`](../../SD-Card/WAVES/CREDITS.md)).

1. Download the free pack and unpack it.
2. Find its folder of Serum/Vital `.wav` wavetables and copy up to 32 tables
   you like into a new folder, for example `krc_pick/`. Keep the total frames
   small (around 56) if you also want the full 1 MB for samples.
3. Build and copy in one step:

   ```bash
   python tools/make_wavetables.py --each krc_pick F:/
   ```

4. Boot the LXR with the card.

Please get the wavetables from the author's page yourself rather than passing
the files on.
