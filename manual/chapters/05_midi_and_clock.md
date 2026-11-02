# 5. MIDI and clock

This chapter describes the MIDI and clock settings in the current desktop
source. The LXR V2 has DIN MIDI IN/OUT, USB MIDI and analogue clock input/output.
The routing and sync combinations still need a check on the instrument.

## Open global settings

Press **SHIFT + CONFIG** (sequencer button 12). The CONFIG LED flashes. The
first global-settings page contains `bpm`, `shu`, `ch`, `Pch`, `mtx`, `mrx`,
`mrt` and `flw`. Pressing the same CONFIG combination again cycles to the
second page, which includes kit-load mode `lki`, `cki`, `cko`, `ssv`, `CPU`, `lsh`,
`lmp` and `lsr`.

Global settings, including `Pch`, are saved with the project. `CPU` is a live
read-only meter and is not saved. Save the project to the SD card
if you want the settings to survive a power cycle; see
[Saving and loading](04_saving_and_loading.md).

In 0.1.15 the third Global view adds `cof` (Clock Offset, 0â€“80 tenths of a
millisecond) and `cfn` (fine digit, 0â€“9 hundredths). Select either value to
see the combined offset from 0.00 to âˆ’8.00 ms in detail view. The default
is âˆ’5.00 ms. This advances sequencer steps relative to an incoming DIN/USB
MIDI Clock; 0 keeps the steps on the clock edge. The clock itself is not
advanced. DIN input is timestamped when the byte arrives. Save Globals or
Project explicitly to retain the offset. Older `MUTA.CFG` files load with
the default. External analogue clock is unaffected.

In 0.1.16, pressing PLAY while stopped and receiving MIDI Clock queues a
manual start for the next 96-pulse bar. With a stable incoming period and
nonzero `cof/cfn`, the first step is played early by the configured offset;
the confirming MIDI edge does not replay it. MIDI START and external
analogue trigger follow their existing transport paths. Only MIDI START sets a
bar phase. Without one, or after 1 s without clock, manual PLAY starts at once
and the next clock becomes the downbeat, without the early offset.

## Pattern and kit load settings

`lki` is the kit-change mode: `aut` loads a pattern's associated kit when
that pattern becomes active; `off` keeps the current kit. `lsh` controls a
separate choice: when `on` (the default), a pattern change also loads that
pattern's shuffle value. With `lsh=off`, the current shuffle is retained.

`lmp` controls what happens when a kit is loaded, whether manually or through
`lki=aut`. With `lmp=aut`, the kit's saved Morph-target slot is selected as the
Morph kit. With `lmp=off` (the default), the previously selected Morph kit is
kept. Use LOAD + MORPH to choose a target and save the source kit/project to
keep that association. These switches are global settings; older settings
files load with `lsh=on`, `lmp=off` and `lsr=on`.

`lsr` (Load Sample Rate) controls whether a manual or automatic kit load
loads the kit's master `srt`. With `lsr=off`, the current master sample rate
is retained; with `on` (the default), the kit value is loaded. This switch
does not affect the individual voice sample rates. Save the project to keep
the setting. Master `srt` still controls the whole Morph sound independently
of the target kit.

## MIDI channels and notes

Each of the seven tracks has a Voice MIDI channel (`ch`) and kit-note
assignment (`nte`). Channel values are 1..16; `nte=0` is displayed as ANY.
From Mutador 0.1.6, note reception follows these rules:

| Input | Result |
| --- | --- |
| Global `ch`, note matches a nonzero `nte` | Triggers each matching voice at its default pitch. |
| Global `ch`, no fixed assignment matches | Plays the selected voice chromatically only if its `nte` is ANY. |
| Dedicated Voice channel | Plays every incoming pitch on that voice, ignoring `nte`. Shared Voice channels trigger all matching voices. |
| Pch different from Global | Notes control master oscillator transpose, not drum triggers. MIDI note 60 is neutral; 72 is +12 semitones, 48 is -12. |

Global takes priority over an overlapping Voice channel. Pch takes priority
over a Voice channel when Pch differs from Global. If Pch equals Global,
the Global drum-map/ANY behavior applies. Duplicate fixed `nte` assignments
trigger together and suppress the ANY fallback. Muted voices do not sound.
Global and Voice note routes require `N` in `mrx`. From 0.1.7, Pch notes
match Mutador: they are consumed before RX filtering and port Thru, so they
work even with `N` disabled and are not forwarded. Zero-velocity Note On and Note Off do
not trigger a voice or reset master transpose. Normal note-release handling
is not added by this import.

Example: Global `ch=10`, snare Voice `ch=3`, snare `nte=38`, Pch on another
channel. Note 38 on channel 10 plays the snare at its default pitch. Any note
on channel 3 plays the snare chromatically. If another voice is selected with
ANY, an unmapped note on channel 10 plays that selected voice chromatically.

Global input can record and echoes once to the destination Voice channel.
Voice input can record without echoing to that channel. Configured port Thru
is separate and can still forward the original message. On the sequencer
step page, input for the currently edited voice sets the selected step's note;
other mapped voices sound normally.

Program Change still uses Global `ch` and selects desktop patterns 0..63.
`Pch` means performance control, not Program Change. Pch defaults to channel
2. CC2 controls Morph only when Pch differs from Global and all Voice channels;
CC overlap retains the legacy mapping. That CC policy differs from Pch note
priority above. RX `C` is required. Pch CC27 now controls global pitch with Mutador's mapping: CC values 61..66
are neutral, 0 is -63 and 127 is +64 semitones. It has Pch precedence even
on overlapping channels, unlike the legacy-preserving Morph CC2 rule.
Pch CC1 srt is not imported. The common Voice CC map is implemented from 0.1.22; see below.

Pch-note transpose is live, stays through kit loads, and is not saved.
Send note 60 on Pch to reset it; power-on starts neutral. It changes oscillator
pitch, not the MIDI note numbers sent by the sequencer.

PERF also provides **gpt** (editable global base pitch, -63..64 semitones,
0 neutral) and **pbr** (pitchbend range, 0..48 semitones, default 12). Save the
project to retain them. gpt shows the base offset; Pch-note and bend offsets
are added internally and do not replace its displayed value. There is no ntP
field.

Pitchbend on Global or Pch affects all main and modulation oscillators.
On a dedicated Voice channel it affects the first matching voice; both hats
share their oscillator engine. Global/Pch takes priority on overlap. As in
Mutador, bend is handled independently of the N/C/P receive-filter bits.

The combined pitch is kit coarse tuning + played note relative to the default
+ gpt + Pch-note transpose + global bend + Voice bend, with fine tuning applied
afterward. Fractional semitones interpolate the frequency table; frequencies
continue by octaves below MIDI 0 and above 127. Changing pbr reapplies global
bend immediately; a Voice bend uses the new range on its next wheel message.

0.1.6 also includes the legacy CC-index correction: voice-specific sound CCs
use their own sound voice's channel or Global, instead of the next track's
channel. The archived 0.1.4 image predates that correction. See the
[channel audit](../../docs/P01_CHANNEL_AUDIT.md),
[complete numeric CC table](../../docs/P01_CC_MAP.csv) and
[note-import record](../../docs/sessions/014-mutador-note-routing.md).

From 0.1.8, Pch also accepts CC5 (rst, scaled 0..100), CC6 (csr, 0..127),
CC7 (pst, scaled 0..100), and CC28 (gdc, bipolar mapping with a center
neutral zone). These controls require RX C and take Pch precedence on
channel overlap, like CC27. On Global/Voice channels distinct from Pch,
the legacy CC meanings remain. The BC Scarcity control pSc uses Pch CC54 from 0.2.22; its BC CC25
assignment conflicts with the Mutador performance map. See the [numeric CC table](../../docs/P01_CC_MAP.csv).

The `CPU` value shows the peak audio-block calculation time as a percentage
of the available block time, sampled every 500 ms. It does not include all
background work and is not a complete measure of total MCU usage.

The current Pch map also includes CC8 (`cnt`), CC10..16 and CC126 (MIDI
Delay), CC44 and CC46..52 (Accent), and CC60..66 (Delay input toggles when
value is at least 64). From 0.1.12, CC40 is Shuffle master and CC41/42/43
are `sh2/sh3/sh4`. Groove values are 0..127, with CC64 mapped to neutral 63
for the signed shapes. These mappings require RX C and take the same Pch
priority on overlapping channels. See the [Performance chapter](07_performance.md).

## Receive and transmit filters

`mrx` filters received messages; `mtx` filters transmitted messages. The
display shows a combination of these letters:

| Letter | Message class |
| --- | --- |
| `N` | Note On/Off |
| `R` | Realtime messages, including MIDI clock and start/stop |
| `C` | Control Change (CC) |
| `P` | Program Change |

`off` disables all four classes and `all` enables them all. Other menu
choices combine letters, for example `RN` or `PCR`. In the current parser,
received clock/start/stop are acted on only when `R` is enabled and an
external sync mode is selected. The source comments say the transmit `C`
filter is not fully applied, so treat `mtx` CC filtering as unverified.

## MIDI routing (`mrt`)

Routing passes messages between the physical MIDI ports; it does not replace
the receive filter used for the LXR's own sound and sequencer control.

| Display | Routing |
| --- | --- |
| `off` | No port forwarding |
| `U2M` | USB MIDI input to DIN MIDI OUT |
| `M2M` | DIN MIDI IN to DIN MIDI OUT (soft thru) |
| `A2M` | USB MIDI input and DIN MIDI IN to DIN MIDI OUT |
| `M2U` | DIN MIDI IN to USB MIDI output |
| `M2A` | DIN MIDI IN to both DIN MIDI OUT and USB MIDI output |

`M2A` is present in this fork's source even though it is absent from the
provided LXR-02 manual's routing table. Test forwarding with the intended
ports before depending on it in a live setup.

## Tempo and clock synchronization

The `bpm` setting has three kinds of value in this desktop source:

| Display/value | Clock source |
| --- | --- |
| `EXT` / 0 | Analogue clock input |
| `MID` / 1 | Incoming MIDI clock |
| 2 or higher | Internal tempo in BPM |

For MIDI synchronization, select `MID` and allow `R` in `mrx`; connect a
clock source to DIN MIDI IN or USB MIDI. The parser handles MIDI Clock,
Start, Continue and Stop. MIDI Song Position Pointer is explicitly marked
unimplemented in the current source. With internal tempo selected, the
sequencer sends its own MIDI clock; with external sync selected, it does not
generate that internal MIDI clock.

For analogue synchronization, select `EXT`. `cki` sets the incoming pulse
resolution to **4** or **24 PPQ** (pulses per quarter note). `cko` selects
the analogue clock output resolution: **2, 4, 8, 16, 24 or 48 PPQ**. Match
these values to the connected device. The provided LXR-02 manual describes
`bpm = 0` more generally as external sync; the `EXT`/`MID` distinction above
comes from this desktop firmware's code and needs an on-device check.

## Troubleshooting

From 0.1.13, `cko` appends `16sh` after the existing straight PPQ divisions.
It sends shuffled sixteenth notes, four pulses per quarter, following the
Groove page. Ordinary `16` still means 16 straight pulses per quarter.
With neutral Groove, `16sh` gives straight sixteenths.

- **No sound from MIDI notes:** check the cable/port, `mrx` includes `N`,
  the track or global channel, the track's `nte` setting and whether the
  track is muted.
- **No MIDI clock sync:** select `MID`, include `R` in `mrx`, and confirm
  that the sender transmits MIDI Clock and Start/Continue.
- **No analogue clock sync:** select `EXT`, then match `cki` to the incoming
  pulse rate.
- **No port forwarding:** check `mrt`; `off` forwards nothing. Test with a
  MIDI monitor at the destination port.

MIDI Delay, Accent and Groove are now implemented and tested natively.
Hardware sound, CPU and real sync timing remain to be verified; see the
[changelog](../../CHANGELOG.md) and [build notes](../../BUILD_NOTES.md).

[Previous: Saving and loading](04_saving_and_loading.md) Â·
[Next: Firmware update](06_firmware_update.md)

## Snare voice CC aliases (0.1.21)

On the configured Snare voice channel, Mutador CC 112–118 provide:

| CC | Parameter | Values |
|---|---|---|
| 112 | Layer Wave | 0–5 synthesized waves, then loaded samples |
| 113 | Layer Mix | 0–127 |
| 114 | Layer Frequency | 0–127 |
| 115 | Wave Mixer | 0=mix, 1=FM, 2=rng |
| 116 | Noise Attack | 0–127 |
| 117 | Noise Decay | 0–127 |
| 118 | Noise Slope | 0–127 |

Values above the available Wave or Mode range clamp to the last valid choice.
As in Mutador, these voice aliases do not apply if the Snare channel equals
`gch` or `Pch`. Those channels retain their existing CC maps. Enable CC receive
in the MIDI RX filter. DIN and USB use the same mapping. Incoming changes
update the display and modulation base and can record automation on Snare
track 4. Save the kit to retain the settings.

## Common voice CC map (0.1.22)

Mutador's common voice map applies on the configured voice channels. `gch`
and `Pch` take priority and retain their maps. On shared voice channels the
first voice supporting that CC wins, in voice order 1–7. Unsupported aliases
fall through to the existing desktop CC map. CC receive filtering applies
to USB and DIN. Membrane CC 111 is not imported.

| CC | Common voice control |
|---|---|
| 7 | Volume |
| 9 | Main oscillator waveform |
| 10 | Pan (63/64 center) |
| 12 / 13 / 14 | Sample rate / Drive / Coarse pitch |
| 16 / 17 / 18 / 19 | Filter cutoff / Resonance / Drive / Type |
| 20 / 21 | Snare Noise/Osc Mix / Noise frequency |
| 22 | Drum voices 1–3 FM/Mix/Ring/Expo/PD mode, values 0-4 |
| 23 / 24 / 25 | Velocity-to-volume enable / Velocity amount / Destination |
| 26 / 27 / 28 | Transient level / Wave / Frequency |
| 46 | Fine pitch (63/64 center) |
| 70 | Snare/Cymbal repeat |
| 72 | Open hi-hat decay |
| 73 / 74 / 75 | Amp Attack / Slope / Decay |
| 76 / 77 / 78 | LFO Frequency / Amount / Offset |
| 79 / 80 / 81 | LFO Wave / Target voice / Destination |
| 82 / 83 | LFO Retrigger voice / Sync |
| 84 / 85 / 86 | Drum/Snare pitch-envelope Decay / Amount / Slope |
| 89 | Audio output routing |
| 102 / 103 / 104 | Drum FM Wave / Frequency / Amount |
| 105 / 106 / 107 | Cymbal/Hi-hat second oscillator Wave / Gain / Frequency |
| 108 / 109 / 110 | Cymbal/Hi-hat third oscillator Wave / Gain / Frequency |
| 112–118 | Snare layer and noise controls, listed above |

Discrete values use the menu's indices and clamp at its last valid choice.
CC 79 selects LFO shapes 0–9: sin, tri, sup, sdn, sqr, rnd, xup, xdn,
str, gld. CC 80 accepts target voice 0–5 (shown as 1–6 in the menu).
As in Mutador, CC 25 and 81 carry a raw sound-parameter ID, not a
Destination-list index; 0 is off. Their seven-bit values address IDs 0–127.
The full destination list, including the new Snare targets, remains available
from the menu. Incoming aliases update the sound and display and use their
translated internal parameter when recording automation.

Pch CC79-84 select `spd` /8, /4, /2, 1, *2 and *4, and Pch CC88-91 select
`sct` off, a, b and c. Values 0 or 64-127 select; values 1-63 are ignored.
Running changes wait for the bar (`spd`) or the group edge (`sct`). These Pch
shortcuts are separate from the voice-channel aliases using the same numbers.

## Further Pch controls (0.2.23)

| CC | Control | Values |
|---|---|---|
| 54 | Scarcity (`pSc`) | scaled 0-100 |
| 55 | All Velocity (`avl`) | scaled 0-200 |
| 56 | Fill | 64-127 on |
| 57 | Master filter enable | 64-127 on |
| 58 | Pitch bend range | 0-48 semitones, higher clamps |
| 59 | FX send mode | scaled 0-3 |
| 67 | FX output mode | 64-127 second mode; resets the sends |
| 68 / 69 | Clock offset / fine | scaled 0-80 / 0-9 |
| 70-72 | Drum 1-3 mode (FM, Mix, rng, exp, pd) | scaled 0-4 |
| 73-75 | Drum 1-3 FM amount, `exp` depth, `pd` DCW | 0-127 |
| 92-97 | Voice PWM 1-6 | 0-127 |
| 102-107 | LFO slew 1-6 | 0-127 |
| 108-113 | LFO polarity 1-6 | scaled 0-2 |
| 114-119 | Random step LFO depth 1-6 | 0-127 |

The other random step LFO settings stay menu-only. Like Morph CC2, these controls need a Pch
of its own: if Pch equals `ch` or a Voice channel, these numbers keep their
existing meaning.

From 0.1.23, Pch CC9 controls rvl, scaling MIDI 0-127 to 0-100 percent as in
Mutador. Voice-channel CC9 still selects the oscillator waveform. AVL has Pch CC55 from 0.2.22.
