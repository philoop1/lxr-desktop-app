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
as the main oscillator. Snare, Cymbal, Hihat and the snare layer keep the six
built-in waveforms.

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
`wmd` traverses mix, FM and rng; the Drum Voice mode traverses all five. At zero modulation depth the base selection
is retained. Step automation uses the corresponding raw parameter values.
With `sla=0` the second oscillator is silent. The layer is saved with the
kit and interpolated by Morph. Old `SNE1` kits keep their noise envelope
and start with the layer off; new kits use the `SNE2` extension marker.

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

## Random per played Step LFO (0.2)

Select the new LFO wave rps. Press the LFO parameter button repeatedly: the first two views are the existing controls; the third shows wave, rtg (source/trigger voice), voi (target voice) and dst; the fourth shows amount, ofs (value bias), slw (slew) and pol (neg, pos or bi). A random value is picked once when an active Step of rtg actually sounds. Empty, muted or probability-skipped Steps do not retrigger it. Open and closed hi-hat Steps both count as voice 6. slw=0 jumps immediately; higher values glide toward the new value. ofs=0 is neutral in rps mode. The LFO settings are saved with the kit. The new slew and polarity values do not morph between kits.
