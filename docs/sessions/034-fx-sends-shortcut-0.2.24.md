# Session 034: FX sends on SHIFT + Step 5, version line and host check repair

Date: 2026-11-02
Branch: adding-to-mutador (uncommitted, on top of 72c445f)

- The startup screen still showed `Mutador 0.2.10` through every build up to 0.2.23. `LXR_MUTADOR_VERSION` in CMakeLists.txt now sets both the image name and the startup line.
- PERF sends `s1`-`s6` and `sm` moved to SHIFT + Step 5, as a dedicated page like SHIFT + Step 2, 3 and 4. Pressing it again switches between its two screens. The regular PERF cycle is now first page, second page, master filter. CC, storage and parameters are unchanged.

Host checks: running every `tools/check_*.py` showed four that had been failing unnoticed, and none of them pointed at a firmware defect:

- `check_copy_import`, `check_velocity_controls` and `check_voice_import` no longer compiled or linked, because their stubs lacked Flam Probability/Trig Condition, the LFO event IDs, the transfer functions and the LFO/rps kit extras. They run again. `check_copy_import` now also asserts that Flam Probability and Trig Condition are copied. The stubbed LFO/rps extras are not exercised by `check_voice_import`.
- `check_lfo_import` compared `rps` with a Mutador reference that has no such wave. It now stops before `rps`, which `check_lfo_step` covers, and prints the failing wave.
- `check_sct` sometimes exited 1 after its PASS line because Windows still held the temp folder. Cleanup errors are now ignored.

Run the checks with `NoDefaultCurrentDirectoryInExePath` cleared (session 033). `check_card_velocity_plan` needs a plan argument and was not run.

Validation: ARM GCC 14.3 release passed with no compiler warnings. All 23 checks that were run passed; `check_sct` needed the separate rerun above. Image `LXR_V2_V1.7_Mutador0.2.24.img`, 339708 bytes, SHA256 `FE0D3C60554B80188A5303FDB4EE7927154EC7D62B126EA9892C4608CFA9C019`, archived. SD F: 0.2.24 copied and SHA256 verified; 0.2.23 matched its archive and was renamed to .imm. Hardware test pending.

Card: PROJ21..28 had no `GLO.CFG`. `tools/set_card_prf_midi_sync.py` created one in each from the root file with `bpm` (first byte) set to `MID` (1). All eight were read back; `mrx` is `all`. The root file, other projects, PROJ62 and PROJ63 are unchanged. Backup and manifest: build/card-midi-backups/20261102-184434-131412. Not yet tried on the device.

Gap slots: new `tools/check_sct_step_path.py` runs the real `seq_nextStep` with the production PerformanceScale.c on rates 6, 12 and 24, sct off/a/b/c and lengths 3 to 64: 1451594 assertions passed, no firmware defect. `--mutate` removes the gap guard and produces 948417 failures. Everything `seq_nextStep` calls is stubbed, so Flam/Groove in a gap, `seq_tick` timing and MIDI clock sync through gap slots remain untested.

Open: the spd/sct/Pch CC/SHIFT + Step 5 device report and the LFO 2 report.
