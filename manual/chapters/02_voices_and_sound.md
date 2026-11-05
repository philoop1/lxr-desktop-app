# 2. Voices and sound parameters

The firmware has seven sequencer tracks. The sound pages expose parameters
such as volume, pan, sample-rate reduction, drive, audio output, track length,
MIDI channel and MIDI note. The available synthesis parameters depend on the
selected voice; consult the display while editing a voice.

In Mutador 0.1.3, PERF `srt` controls the master sample rate at every Morph
position, including 255. The Morph kit's stored master sample rate is ignored
while morphing. Each voice's own sample-rate parameter still morphs between
the source and target kits. At `srt=0`, the master decimation stops advancing
regardless of the Morph amount.

From 0.1.8, PERF **gdc** sits directly beside **gpt**. It is a master amp-decay
depth: display 0 is neutral, -63 moves all seven amp decays toward their
minimum, and +64 moves them toward their maximum. The closed/open hi-hat
decays remain independent. Changing a kit or Morph amount supplies fresh
source decays beneath this layer; returning gdc to 0 restores those source
values. Kit endpoints are not overwritten. Save the project to retain gdc.

This chapter will gain parameter descriptions and verified control steps as
the desktop fork develops. A change to a sound parameter should be saved if
you want to keep it after switching or restarting; see
[Saving and loading](04_saving_and_loading.md).

In 0.1.15 the Snare's formerly empty FM page contains `nat` (Noise Attack),
`ndc` (Noise Decay) and `nsl` (Noise Slope). Their neutral values are
0/127/64; with all three at neutral the prior Snare signal path is used.
Changing any of them gives the noise its own envelope. Save the kit to keep
them. Old kits load with neutral values. New kit and project files include
these values and an `SNE1` marker in the reserved kit area; Morph blends them.
Drum Voices 1â€“3 now offer `rng` after FM and Mix. This is Ring modulation,
with the existing modulation amount controlling the dry/ring blend.

From 0.2.25 the same selector adds two modes for Drum Voices 1â€“3. Both follow
the FM amount and the pitch EG, as FM does, so the sound changes as the EG
falls.

- `exp` is exponential FM. The modulator bends the pitch by up to 4 octaves,
  like a pitch input on an analog oscillator, and the note rises with depth.
  Sine stays cleanest; Saw, Rec and PWM alias at high depths.
- `pd` is Casio style phase distortion. The FM amount acts as DCW, from a
  plain sine at 0 to close to a saw at full amount. It always uses a sine, so
  Waveform has no effect unless a user wavetable is selected, which then
  plays plain. The modulator is unused.

From 0.2.36 Drum Voices 1-3 can play user wavetables. Their Waveform list
continues after `PWM` with up to 32 tables (12 before 0.2.41), named by the first three letters
of the file (two letters and a number where several files share them, for
example `CE1`, `CE2`).

1. Collect up to 32 sources on the computer. A source is one wavetable:
   - a Serum WAV (frames of 2048 samples, or the size in its `clm ` chunk),
   - a Surge WAV (frame size in its `srge` chunk) or a Surge `.wt` file,
   - a single-cycle WAV (one frame),
   - a folder of single-cycle WAVs: one wavetable, one frame per file in name
     order.
   WAV files may be 8 to 32 bit or float, mono or stereo.
2. Run `python tools/make_wavetables.py <source> [<source> ...] <SD card>`.
   `python tools/make_wavetables.py --each <folder> <SD card>` makes every
   file of the folder its own wavetable instead, so each wave gets its own
   name in the Waveform list. The tool writes
   `WAVES/WAVES.BIN` on the card and lists the slots, names and frames.
3. Boot the LXR with the card. The display shows "Loading waves" with the
   percent done, then the number of tables. A new or changed file takes up to
   a minute the first time; later boots only compare it.

From 0.2.37 PWM scans the tables. At 0 the voice plays the selected table;
turning PWM up blends smoothly through the following tables, and full PWM
plays the last one. Select the first table and PWM moves through all of
them; select a later one and PWM covers the rest. An LFO, velocity, Morph or
automation on PWM moves through the tables while the note plays. On the
built-in waveforms PWM keeps its old meaning (it only changes `PWM`).

From 0.2.38 a wavetable can have several frames, as Serum wavetables do: a
WAV file whose length is a multiple of 2048 samples is split into frames of
2048. Waveform then picks the wavetable and PWM scans only its frames, from
the first at 0 to the last at full PWM. A single-cycle file is a wavetable
with one frame. From 0.2.42 PWM on such a single wave scans on through the
single waves in the slots after it, from the selected one at 0 to the last at
full PWM (it stops before a wavetable with several frames). So waves built
with `--each` can be picked by name and still scanned. PWM glides to its
value over about 15 ms, and the octave levels fade into each other while the
pitch moves, so pitch envelopes and PWM changes do not click. All wavetables together may hold 284
frames (56 before 0.2.40), at most 255 per wavetable; the generator thins out
the largest ones evenly and lists how many frames each one keeps. Files from
0.2.36 to 0.2.40 must be built again for 0.2.41.

The tables stay in flash when the card has no `WAVES.BIN`. A broken file
shows "WAVES.BIN error" and keeps the tables already there. A firmware
update can erase them; the next boot with the card copies them again. A kit
that uses a table plays silence on that voice while no table is in that slot.
From 0.2.45 the modulator of Drum Voices 1-3 offers the wavetables too, so
a wavetable can drive FM, Mix, ring and expo FM; it scans with the same PWM
as the main oscillator. From 0.2.49 the main waveform of Snare, Cymbal and
Hihat offers the wavetables too; from 0.2.51 the snare layer and the Cymbal
and Hihat modulators do as well.

### User samples (0.2.51)

After the wavetables the Wave menus list one-shot samples. Build the bank on
a computer and copy it to the card:

    python tools/make_samples.py F:/SAMPLES my_samples_folder
    python tools/make_samples.py F:/SAMPLES --mutador ../mutador

The first form takes WAV files (8, 16 or 24 bit, 32 bit float, mono or
stereo, 8 to 96 kHz) in name order; `--list` takes `name|file` lines and
`--crash` adds the LXR1 crash. The second builds the LXR1 Mutador set: its 16
samples and the crash. `SAMPLES.TXT` beside the bank lists the samples.

At boot the display shows "Loading samples". The firmware copies
`SAMPLES/SAMPLES.BIN` into flash behind the wavetables, only when the file
changed. A bank fills at most 1 MB behind one sector of wavetables; larger
wavetables leave less ("No sample space").

Waveform numbers stay fixed: 0 to 5 built-in, 6 to 37 wavetables, 38 and up
samples. Empty wavetable slots are skipped when turning the encoder. A sample
starts on each trigger and plays once. Coarse 0 (note 60) plays it at its own
pitch; each semitone of coarse or note is a semitone, fine tunes within a
semitone, and the pitch envelope and modulation work as for the
oscillators. After the last frame the sample stays silent until the next
trigger. FM moves the read point; exp and pd play a sample without
modulation.

LXR1 kits from the LXR1 folder use the sample numbers of the Mutador set.
Their waveforms 6 and up become 38 and up, the crash 5 becomes 54, and
coarse and fine move so each sample plays at its LXR1 pitch (about 31
semitones up). The snare layer keeps its LXR2 pitch.

In 0.1.16 the same Snare page adds `slw` (second oscillator waveform),
`sla` (layer amount), `slf` (frequency ratio) and `slm` (Mix/FM/Ring).
From 0.1.19 the Snare layout follows Mutador: OSC first shows Coarse,
Fine, layer Frequency and layer Mix. Press OSC again for Wave Mode (`wmd`),
PWM, main waveform and layer waveform. PWM is retained in place of Mutador's
Membrane, which is not imported. FM first shows Noise/Osc Mix, Attack,
Decay and Slope; the second FM view shows Noise Frequency. Changing to a
different parameter button starts on its first view; pressing the same
button again toggles its two views. The ordinary MIX page keeps its controls.

From 0.1.20, Noise Attack/Decay/Slope and layer Wave/Mix/Frequency/Mode are
also destinations for LFO, velocity and step automation. Select target voice
4 for Snare when using an LFO. The seven new targets follow the legacy Snare
targets in its target selector; existing target numbers remain unchanged.
For example, select layer Mix as LFO destination and raise the LFO amount.
Wave and Wave Mixer (`wmd`) modulation selects discrete valid values;
`wmd` traverses mix, FM, rng, exp and pd; the Drum Voice mode traverses all five. At zero modulation depth the base selection
is retained. Step automation uses the corresponding raw parameter values.
With `sla=0` the second oscillator is silent. The layer is saved with the
kit and interpolated by Morph. Old `SNE1` kits keep their noise envelope
and start with the layer off; new kits use the `SNE2` extension marker.

### Snare exp and pd (0.2.49)

`wmd` adds `exp` and `pd`. With `exp` the layer oscillator bends the rate of
the Snare oscillator in octaves, like the Drum mode `exp`; `slw` and `slf`
choose its wave and ratio. With `pd` the Snare oscillator warps its own sine,
from sine towards saw (Casio phase distortion); the layer oscillator is not
used. In both modes the depth is the layer amount `sla` times the Snare pitch
envelope, so the sound is brightest at the attack. `sla=0` keeps the plain
Snare. Older firmware plays these two modes as rng.

Up to 0.2.49 `wmd=FM` had no depth and sounded like the plain Snare. From
0.2.50 the layer oscillator modulates the phase of the Snare oscillator, and
the layer amount `sla` sets the depth.

FX Dry/Wet is a destination for LFO, velocity and
step automation on every voice; it comes last in each voice's list.

From 0.2.31 FX Type offers `tpe`, a tape delay that always follows the tempo.
`typ` picks `nrm` (mono) or `pp` (ping pong: first echo left, next right).
`rte` picks the note division, shown in the repeat names (`8` is an eighth,
`8d` a dotted eighth, `6` a quarter triplet). A division that does not fit
the buffer at the current tempo falls to the next shorter one, and the page
shows the one that plays: mono holds 0.74 s, ping pong 0.37 s per side.
`fin` moves the time by up to 20 % either way. Time changes glide over about
150 ms and bend the pitch like tape. `ton` darkens the repeats, `fbk` sets
how many come back.
On MIDI clock the delay follows whole beats and smooths them, so a jittery
clock does not wobble the echo pitch (from 0.2.33).
`fbk` shows percent and goes to 125: above 100 the repeats grow into a soft
tape saturation and keep ringing (from 0.2.34).

[Previous: Device and firmware](01_device_and_firmware.md) Â·
[Next: Sequencer and patterns](03_sequencer_and_patterns.md)

## Stray and Glide LFOs (0.1.22)

The LFO Wave menu adds `str` and `gld` after the eight existing shapes.
Stray chooses bounded random-walk targets, moving at most 0.35 per cycle
and reflecting at either end. Glide chooses a new target across the whole
0–1 range. Both use smoothstep interpolation between targets. Frequency
and Sync set the movement speed. Offset (`ofs`) biases the random range;
63 is neutral. Retrigger restarts their phase at zero; Offset acts as bias
rather than the retrigger phase for these two shapes.

Their random curves and bias follow Mutador, normalized to the desktop's
0–1 modulation input. Destination response uses the desktop's existing
modulation path. Frequency 0 now stops the LFO, as in Mutador. For `rnd`
at Frequency 0, Offset sets the held random value and a configured retrigger
chooses another random value. Existing waveform IDs and kit fields are
unchanged; the new shapes are stored as IDs 8 and 9 in the existing field.

## One-shot LFOs and xtr (0.2.49)

After `gld` the LFO Wave menu has `xtr`, an exponential triangle: it rises
like `xup` and falls like `xdn`. Then follow one-shot versions of the
shapes: `si1`, `tr1`, `su1`, `sd1`, `sq1`, `rn1`, `xu1`, `xd1` and `xt1`.
A one-shot starts when its retrigger voice (`rtg`) plays, runs one cycle at
the set Frequency or Sync and then holds the end value: `su1` stays at the
top, `sd1` at the bottom. Offset (`ofs`) is a start delay of up to one cycle
for the one-shots, not the start phase. `sq1` is on first and off after half
a cycle; during the delay it is off. `rn1` takes one new random value per
trigger and holds it. Choosing a one-shot runs it once; without a retrigger
voice it then stays still. `xtr` takes the slot of the former `rps`; kits
that used `rps` now play `xtr`.

## Random per played Step LFO (0.2)

From 0.2.49 rps is no longer an LFO wave (see One-shot LFOs below); the six
Random per Step modulators on the third and fourth LFO views remain. The
original 0.2 text follows. Select the new LFO wave rps. Press the LFO parameter button repeatedly: the first two views are the existing controls; the third shows wave, rtg (source/trigger voice), voi (target voice) and dst; the fourth shows amount, ofs (value bias), slw (slew) and pol (neg, pos or bi). A random value is picked once when an active Step of rtg actually sounds. Empty, muted or probability-skipped Steps do not retrigger it. Open and closed hi-hat Steps both count as voice 6. slw=0 jumps immediately; higher values glide toward the new value. ofs=0 is neutral in rps mode. The LFO settings are saved with the kit. The new slew and polarity values do not morph between kits.
