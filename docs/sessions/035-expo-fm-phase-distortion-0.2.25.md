# Session 035: exponential FM and phase distortion in 0.2.25

Date: 2026-11-02
Branch: adding-to-mutador (uncommitted, on top of 86620b5)

The drum `FM` mode has always been phase modulation: the modulator offsets the read index and `phaseInc` stays untouched. A mode named PM would have sounded the same, so the two new modes add what the voices did not have.

- Mode 3 `exp`: the modulator acts in octaves on `phaseInc`, up to +/-4 octaves, like a V/Oct input. The mean pitch rises with depth. Depth follows `osc.fmMod`, so the FM amount and the pitch EG set it as they do for FM. The rate stops at half the sample rate. `osc_expoRatio` stays within 0.1% of 2^x and is exact at whole octaves, so no modulation keeps the tuning.
- Mode 4 `pd`: Casio style phase warp of one sine cycle, with the same `osc.fmMod` as DCW. Zero reads the plain sine, full amount is close to a saw. The steep part always spans at least two samples. The modulator is not calculated. User samples play unwarped, since they run on another phase scale.

Modulated `wmd` now maps 0..1 onto the five modes. Before, a modulator scaled it to 0..127 and the clamp left only FM, Mix and rng.

Only Drum 1-3 have the new modes. The Snare `slm` keeps its three.

`exp` reads table waves through the base pitch table, so high depths alias on Saw, Rec and PWM. Sine aliases least.

Validation: ARM GCC 14.3 release passed with no compiler warnings; ITCM is at 96.63%. All 25 checks that were run passed, including the new `tools/check_osc_modes.py` with 163643 assertions on the production blocks. Its `--mutate` run fails as intended. `check_card_velocity_plan` needs a plan argument and was not run.

Image `LXR_V2_V1.7_Mutador0.2.25.img`, 341100 bytes, SHA256 `3B11345DFC9072D017B80EF4656BB1021C68F6B930CF3C67ED547EB51E1F5543`, archived and on card F: with its hash verified; 0.2.24 on the card is now `.imm`.

0.2.26 adds Pch CC70-72 for the Drum mode, scaled over the five modes, and CC73-75 for the Drum FM amount. Both need a Pch channel of its own. `check_midi_contract` covers every value on all three voices and passes 510507 assertions; all 25 checks were rerun and passed. Image `LXR_V2_V1.7_Mutador0.2.26.img`, 341236 bytes, SHA256 `04C403114F49E8D2367C226FDEB10BD08574825D1641AF29523B00B3A70EBBB2`, archived and on card F: with its hash verified; 0.2.25 on the card is now `.imm`.

Reverb: a throwaway build with `USE_REVERB 1` linked with ITCM at 98.34% and DTCM at 82.54%. `Reverb_process` runs from flash and only four setters are in ITCM. It uses the same `FX_BUFFER` as Delay, and `rev` is not in the menu. CPU load was not measured.

Open: sound, CPU load with all voices in `exp` and the device reports from session 034.

0.2.27:

- Reverb enabled as FX type `rev`. `FxBus_prepareFxChange` now clears `FX_BUFFER` when switching to or from Reverb, because both effects use it. `USE_REVERB` also turns on the cheaper filter for Snare, Cymbal and Hi-Hat while `rev` is active.
- FX Dry/Wet was the one sound parameter worth modulating that had no target. Indices 236..241 hold it once per voice, appended so stored indices stay valid. The modulated value caps at 100, since `dryWet` divides by 100.
- `shu` removed from the Global page and the main PERF page; the SHIFT + Step Groove page keeps it. The controls after it moved up one slot.
- ITCM: `Reverb_process`, `AllpassDelay_process`, `AllpassModDelay_process`, `VerbDelay_process`, `VerbModDelay_setModValue`, `SineCosine_calc` and `TiltEq_process` moved in. Reverb setters, `FxBus_updateParameter`, `FxBus_setParameter`, `modNode_resetTargets`, `modNode_reassignVeloMod`, `preset_sendDrumsetParametersImmediate` and `seq_setPendingPatternActive` moved out. Double constants in the active Reverb path became float.

Validation: ARM GCC 14.3 release passed with no compiler warnings; ITCM 92.53%, DTCM 82.54%. All 25 host checks that were run passed; none exercises Reverb audio. Image `LXR_V2_V1.7_Mutador0.2.27.img`, 345764 bytes, SHA256 `51C9AD20A5CA6ED2ECF83EB6D1166BD1B608FAFE42E5100A685A9CA12ED1B0AB`, archived and on card F: with its hash verified; 0.2.26 on the card is now `.imm`.

Open: Reverb sound and CPU load on the device, read from the Global `cpu` value.

0.2.28: the device report on 0.2.27 showed missing Global parameters. `menu_moveToMenuItem` refuses TEXT_EMPTY, so the empty slot 7 left by removing `shu` blocked the step to the next subpage on Global and main PERF. Slot 7 is now TEXT_SKIP. New `tools/check_menu_pages.py` failed before the fix and passes after it. Image `LXR_V2_V1.7_Mutador0.2.28.img`, 345764 bytes, SHA256 `57B16CCFAC941BACDC173BCCA93BAB53F4DB13F08005A43B917FB243E4764CFC`, archived and on card F: with its hash verified; 0.2.27 on the card is now `.imm`.

Also reported on 0.2.27: the sequencer does not start. Cause not found. The PRF projects are on `bpm` MID since session 034 and then need a running MIDI clock.

0.2.29: the device showed CPU 96 with the reverb on 0.2.28. The reverb tank now runs on every second sample with all delay lengths and taps halved, so times stay the same and the sound is darker. Input is averaged and output interpolated between tank samples. Early taps use fixed offsets instead of a float division. VerbDelay read, write and tap plus VerbModDelay read, write and calcLength moved to ITCM. New `tools/check_reverb.py` compiles the real sources on the host; its `--mutate` run fails as intended. The real saving is unmeasured until the device reports CPU. `apDelay[1]` is processed twice per step and `apDelay[0]` never, as inherited; left as is because it shapes the sound. Image `LXR_V2_V1.7_Mutador0.2.29.img`, 345636 bytes, SHA256 `D13245BBFBFF057062EC933046A5851BDCB9D1614160C20333E9DE7EA03B90A0`.

0.2.29 on the device: CPU 74 with the reverb, down from 96 on 0.2.28.

0.2.30: the user dropped the reverb after the CPU test. `USE_REVERB` is 0 again, `rev` is out of the menu, and Reverb, VerbTools, sinCos and TiltEq are back to HEAD, so the half-rate tank, the reverb ITCM moves, the FX_BUFFER clear and `tools/check_reverb.py` are gone. Kept: FxBus_updateParameter, FxBus_setParameter, modNode_resetTargets, modNode_reassignVeloMod, preset_sendDrumsetParametersImmediate and seq_setPendingPatternActive outside ITCM, and FX Dry/Wet as a modulation target. CC2_FX_TYPE above FX_DELAY now maps to off, for kits saved with `rev`. ITCM 84.91%, DTCM 82.15%. Image `LXR_V2_V1.7_Mutador0.2.30.img`, 341164 bytes, SHA256 `736BABA5F0C40C8B48797581F71BAE4D73126BFAD6994DAD76CE27FE38086AB9`.
