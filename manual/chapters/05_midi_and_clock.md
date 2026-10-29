# 5. MIDI and clock

This chapter describes the MIDI and clock settings in the current desktop
source. The LXR V2 has DIN MIDI IN/OUT, USB MIDI and analogue clock input/output.
The routing and sync combinations still need a check on the instrument.

## Open global settings

Press **SHIFT + CONFIG** (sequencer button 12). The CONFIG LED flashes. The
first global-settings page contains `bpm`, `shu`, `ch`, `Pch`, `mtx`, `mrx`,
`mrt` and `flw`. Pressing the same CONFIG combination again cycles to the
second page, which includes pattern mode, `cki`, `cko`, `ssv` and `CPU`.

Global settings, including `Pch`, are saved with the project. `CPU` is a live
read-only meter and is not saved. Save the project to the SD card
if you want the settings to survive a power cycle; see
[Saving and loading](04_saving_and_loading.md).

## MIDI channels and notes

Each of the seven tracks has a MIDI channel (`ch`) and MIDI note (`nte`) in
its voice settings. A Note On on the track's channel triggers that voice.
With a specific `nte` selected, only that note triggers it; with the note
setting at zero, incoming notes can play the voice at their received pitch.
The note's velocity is passed to the voice. A muted track does not sound.

The global `ch` on the CONFIG page is separate from the track channels.
Incoming notes on the global channel play the currently selected voice.
Program Change on this channel selects a pattern; the new pattern is queued
when the sequencer is playing. MIDI CC messages can control parameters when
the receive filter permits CC. Channel numbers shown in the menu run from
1 to 16.

`Pch` is a separate performance-control channel (default: 2). On this first
import slice, CC 2 on `Pch` controls kit morph from 0 to 255. This applies
only when `Pch` is distinct from every voice channel and the global `ch`;
overlapping channels retain the existing MIDI mapping. The receive filter
must include `C`. Other mutador performance controls are not imported yet.

The `CPU` value shows the peak audio-block calculation time as a percentage
of the available block time, sampled every 500 ms. It does not include all
background work and is not a complete measure of total MCU usage.

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

- **No sound from MIDI notes:** check the cable/port, `mrx` includes `N`,
  the track or global channel, the track's `nte` setting and whether the
  track is muted.
- **No MIDI clock sync:** select `MID`, include `R` in `mrx`, and confirm
  that the sender transmits MIDI Clock and Start/Continue.
- **No analogue clock sync:** select `EXT`, then match `cki` to the incoming
  pulse rate.
- **No port forwarding:** check `mrt`; `off` forwards nothing. Test with a
  MIDI monitor at the destination port.

MIDI-delay experiments from LXR2BC or mutador have **not yet been ported**
to this desktop fork. Any future behavior should be documented only after
its code and hardware test are recorded in the
[changelog](../../CHANGELOG.md) and [build notes](../../BUILD_NOTES.md).

[Previous: Saving and loading](04_saving_and_loading.md) ·
[Next: Firmware update](06_firmware_update.md)
