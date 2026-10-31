# 010: Master sample rate across the Morph range

2026-10-29. Based on `9c98ebe`, branch `feature/global-load-switches`.

The user tested 0.1.2 with lmp off and ultimately confirmed that loading a
different Morph kit works. The remaining issue was PERF srt: at high Morph
amounts, interpolation selected the target kit's stored master sample rate
instead of the live control value.

The LXR1 AVR Morph function walks individual voice masks. LXR2BC and desktop
Morph walk all sound parameters, including master decimation. Desktop also
interpolates edited sound parameters before sending them, so excluding master
decimation only from the background Morph walk would leave live edits broken.

`preset_getMorphValue()` now returns the active master decimation unchanged.
The background Morph walk uses that same getter. Both live editing and Morph
updates therefore retain PERF srt; per-voice decimation still interpolates.
No kit format or kit-load behavior changed.

Release build: ARM GCC 14.3.rel1, Visual Studio CMake/Ninja; 3/3 steps passed.
Image: `LXR_V2_V1.7_Mutador0.1.3.img`, 275636 bytes, SHA-256
`9A886E68023BCFA486CFD78D7887398D4AA7B0F8F840A09E6FBD76D400F47508`.
ELF text=274772, data=856, bss=340572 bytes. Archived separately from 0.1.2.

Hardware retest pending: choose two distinct kits, test srt at Morph 0,
128 and 255, turn srt to zero and back, then sweep Morph again and confirm
the master sample rate remains controlled by srt.
