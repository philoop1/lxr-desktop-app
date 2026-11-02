# Session 033: Project transfer names, P+K and 0.2.13 release build

- Source already carried the 0.2.13 suffix, the double PROJECT shortcut, slot names and paired Pattern + Kit import, but no build record or archived image.
- Reviewed the dialog and `preset_copyProjectItem` / `preset_copyProjectPatternWithKit`. A kit import writes only `mainParameters[slot]` and resends the unchanged active parameters, so the active kit is not switched.

Fixed:

- Importing into the active pattern slot left the old pattern in `patternBackupBuffer`. The next pattern change restored it through `seq_copyBackupBufferToPattern`, so RAM reverted while the card held the new pattern. The backup is now refreshed after that import.
- `noFreeKit` was never cleared. After one full-project P+K failure, a later unrelated error showed `No free KIT` instead of its own message. It is now cleared when the result screen closes.

Verification: ARM GCC 14.3 release build passed with no compiler warnings. ITCM 14368/16384, DTCM 107672/131072, RAM 338188/393216, FLASH 285616/1015808 bytes. Host checks passed: performance 57227, pattern scale 1106, edit/scale/hat/storage 148257 assertions, plus trig storage, trig conditions, mod target, LFO step and LXR1 import. No host test covers the transfer dialog or either fix; both are checked by reading the code and by compiling only.

The MSVC checks run `contract.exe` from their build directory. In a shell with `NoDefaultCurrentDirectoryInExePath=1` they fail with "not found" and exit 1 without running any assertion. Clear that variable, or put `.` on PATH, before judging them.

Archived image: `LXR_V2_V1.7_Mutador0.2.13.img`, 336996 bytes, SHA256 `5E50B7C2AA635E899DE37CF28EF7A79FFE5CC56371AFBC900889FA485D30EE9A`. Copied to SD F: and SHA256 verified. The 0.2.12 card image matched its archive and was backed up under build/card-image-backups/20261101-mutador-0.2.13. Removing it from the card was blocked by a tool safety check, so it must be deleted by hand before updating.

Next step: install 0.2.13 and test on the device: KIT, PAT and P+K in both directions, replace confirmation, import into the active pattern slot followed by a pattern change, and a full-kit target project.

Follow-up 0.2.14: the user reported that the PROJECT double press does nothing. The 600 tick window was written as milliseconds, but `systick_ticks` runs at 4 kHz (TIM14: 108 MHz / 13501 / 2), giving 150 ms. `PROJECT_DOUBLE_PRESS_TICKS` is now 2400 ticks = 600 ms. No host test covers this window. Image `LXR_V2_V1.7_Mutador0.2.14.img`, 336996 bytes, SHA256 `905761062A2FAA68C36C11617084D8D57EB84589533798FD4C09658B393373A3`, archived. SD F: 0.2.14 copied and SHA256 verified. The user removed 0.2.12 by hand; 0.2.13 matched its archive, is backed up under build/card-image-backups/20261101-mutador-0.2.14/ and must be deleted by hand before updating, because a tool safety check blocks removal from F:.

Follow-up 0.2.15: added LXR1 performance import to the LOAD transfer dialog and found that PROJ63 holds PRF kits, not the 61 SND kits. Details and image hash are in BUILD_NOTES.md. Both are now on the card: image in the root, SND kits in PROJ62, PROJ63 unchanged. The old 0.2.14 image was renamed to .imm.
