# Session 032: LFO page navigation and Step Flam layout

- User reports the third LFO click returns to the first screen in Voice mode.
- Make the four-screen LFO cycle explicit in `menu_cycleVoiceLfo`, before generic two-screen wrapping; resolve the selected voice independently of the visible page number.
- Invoke extra LFO navigation only in Voice mode. PERF keeps its existing behavior.
- Step screen 1: velocity, note, probability. Screen 2: fpr, flam, shift.
- Version: Mutador 0.2.1.

Verification: 57214 performance assertions passed, including repeated four-screen LFO navigation for all seven voices, exit to another voice parameter page, and exclusion of PERF. Actual Flam dispatch emits eight notes at x8/fpr=100 and one main note at fpr=0. These host results do not reproduce or explain the reported hardware Flam failure; device retest is pending.

ARM GCC 14.3 release build passed. ITCM 14400/16384, DTCM 107672/131072, RAM 305388/393216, FLASH 271680/1015808 bytes.

Archived image: `LXR_V2_V1.7_Mutador0.2.1.img`, 323092 bytes, SHA256 `43016B34C3BDAB6316535F059889B628CA4A31FA2B0C2D820E895CFED05AB9AF`. Copied to SD F: and SHA256 verified. The previous 0.2 image was backed up under build/card-image-backups/20261031-mutador-0.2.1 before removal. Device retest pending.
