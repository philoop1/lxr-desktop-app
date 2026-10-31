# Session 031: Mutador 0.2 random step LFO and Flam Probability

Date: 2026-10-31. Branch: `adding-to-mutador`, based on the completed
0.1.28 import at `00b9280`.

## Changes

- LFO wave `rps` holds a random value until the selected `rtg` voice has a
  step that actually sounds. The selection is independent of the `voi`/`dst`
  destination. Open and closed hi-hat steps both count as source voice 6.
  Muted, inactive and probability-skipped steps do not change the random
  value. One played Flam group makes one random decision.
- Repeated LFO-button presses cycle its original two screens, then a third
  screen showing wave, trigger voice, destination voice and destination,
  then a fourth showing amount, value offset, slew and polarity. `slw=0`
  snaps to the new random value; larger values glide up to roughly two
  seconds. `pol` offers `neg`, `pos`, `bi` as in Helicase. `bi` preserves
  the former bipolar destination response. For `rps`, `ofs=0` is neutral;
  other values bias and clamp the generated random value.
- New `fpr` Step control (0..100) decides whether an already accepted main
  step also plays its Flam repeats. At 0 only the main hit remains; at 100
  all Flam hits remain. One decision applies to the whole Flam group.
  Group editing, step/track/pattern copies and pattern backup include `fpr`.
- Existing packed Step/StepTiming bytes are unchanged. Pattern files append
  an `FLP1` block with 448 probability bytes after `SCL2`. Older patterns
  load with `fpr=100`. Kits append an `LFX1` block with six slew and six
  polarity bytes after `SNE2`, within the reserved project kit block. Older
  kits default to `slw=0`, `pol=bi`. The new LFO extras belong to the source
  kit and are not interpolated by Morph.
- Startup and update-image name advance to Mutador 0.2.

## Verification

The ARM GCC 14.3 release built. Host checks: Pattern Scale/FLP1 1106
assertions; grouped Step editing 148257 assertions; performance/Flam/played
trigger 56952 assertions; source voice random LFO and kit-extension native
checks passed. Physical
sound, kit round-trip and timing remain to be checked on the LXR V2.

0.2 build memory: ITCM 14400/16384, DTCM 107672/131072,
RAM 305388/393216, FLASH 271672/1015808 bytes. The final 323084-byte
update image has SHA-256
`F58CF6793F27726F51FD504494E62571B41694213F0D7F837745DEE4A8A4D0AF`.
It is archived and hash-verified on the SD card as
`F:/LXR_V2_V1.7_Mutador0.2.img`. The 0.1.28 card image was hash-verified
and backed up before removal. Installation and sound testing on the unit
remain pending.
