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
`wmd` traverses mix, FM and rng. At zero modulation depth the base selection
is retained. Step automation uses the corresponding raw parameter values.
With `sla=0` the second oscillator is silent. The layer is saved with the
kit and interpolated by Morph. Old `SNE1` kits keep their noise envelope
and start with the layer off; new kits use the `SNE2` extension marker.

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
