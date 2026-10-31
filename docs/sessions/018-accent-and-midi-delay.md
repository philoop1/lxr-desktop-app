# 018: Velocity Accent and MIDI Delay

2026-10-29. Source reference: `I:/Github/mutador` at `7319e19b`.
The desktop implementation follows its velocity depth, repeat timing, bounce,
pitch and chance behavior, adapted to the desktop sequencer's 96 PPQ clock.

SHIFT + Step 2 opens the Accent page (`vlv`, `vdc`, `vsr`, `vfi`, `vco`,
`vsl`, `vma`, `vdr`). SHIFT + Step 3 opens MIDI Delay (`rpt`, `rcl`, `rpn`,
`bb`, `vel`, `pol`, `bxp`, `d2p`). On the Delay page, the seven instrument
buttons and LEDs edit/show the delay input mask; they do not change mutes.
The probability PERF page gained `cnt`, scaling stored per-step chance.

Delay accepts eligible sequencer hits only. Mono holds one chain globally;
poly holds up to four chains per voice. Repeats do not feed back into Delay.
Changing pattern or resetting the playhead clears chains. A mask change stops
new input for that voice, while already scheduled repeats finish. `rpt=0` or
`rpn=0` disables new repeats by default. The final 0.1.10 rate table uses exact
96 PPQ values, including triplets; 0.1.9 was an intermediate rounded build.

Accent depths are saved in appended globals; the master `vlv` is live and
returns to neutral on settings load. Neutral depths leave step automation and
LFO values intact. The raw kit, Morph endpoints and MIDI CC cache remain
unchanged. Seven drum voices receive independent velocity; the two hats share
tone controls but keep independent amp decay.

The globals block now stores 58 bytes inside its reserved 64 bytes. Old
settings receive validated defaults, with existing field IDs unchanged.
The Pch CC map adds `cnt` (8), Delay controls (10–16, 126), Accent controls
(44, 46–52) and input-mask toggles (60–66).

ARM GCC 14.3 release build passed. Native MIDI/Accent contract tests passed
351206 assertions; sequencer/Delay/UI/storage tests passed 48333. Final image
`LXR_V2_V1.7_Mutador0.1.10.img` is 291748 bytes, SHA-256
`3F0E6BA8BEEA1D5887615818959D004C2DFE60115D3D32810C5B5943AF7AB824`.
It was copied to F: and hash-verified. The previous root image was backed up
under `build/card-image-backups/20261029-200214`. Hardware sound, clock,
CPU, save/reboot and old-project tests remain pending.
