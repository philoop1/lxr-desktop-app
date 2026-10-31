# Session 025 — MIDI transport and local PLAY

Date: 2026-10-30. Branch `feature/global-load-switches`, with earlier
uncommitted import work. Mutador reference
`7319e19b1435dc5a127108367f812c4187f7c025`.

## Behavior audit

Mutador MIDI START resets the global 96-pulse bar phase and starts on the
following MIDI Clock. Local PLAY stop resets the voice step positions. A
following local PLAY request during the bar waits for the next global bar
boundary: Step 1 is fired there, or by the configured Clock Offset just
before it. At bar phase 0 or before a valid phase has been received, Mutador
starts immediately. MIDI CONTINUE starts without resetting the bar phase.

The Desktop import already has that manual bar-start path. Its front-panel
PLAY state was not updated by incoming MIDI START/CONTINUE/STOP, however.
The sound CPU could run while the front panel still believed it was stopped,
making the next PLAY press choose the wrong action. The MIDI receiver now
sends `FRONT_SEQ_RUN_STOP` with the current state after each accepted
transport message; the existing front-panel handler updates the button state
and LED without issuing another transport command.

## Verification

MIDI host dispatch test: 352171 assertions, including exact three-byte
front-panel messages for START, CONTINUE and STOP. The existing Performance
host test checks a queued manual start before the 96th pulse, confirmation
without duplicate Step 1, and zero-offset start on the 96th pulse (56872
assertions). ARM GNU 14.3.rel1 release Ninja build passed. ELF text 309548,
data 888, bss 344536 bytes; ITCM 13976/16384 bytes.

Archived `LXR_V2_V1.7_Mutador0.1.17.img`: 310460 bytes; SHA-256
`013EE2DC1404661A4EF51D316F22C639D75A7B12AA1E69BB027C70F23EF0294C`.
The firmware payload reported by Ninja is 310444 bytes; the update file adds
a 16-byte `LXRV2IMG` header. Device behavior remains to be tested.

The previous 0.1.16 card update was hash checked and saved under
`build/card-image-backups/20261030-midi-transport-0.1.17`. The 0.1.17 image
on F: matched the archive hash; only then was the 0.1.16 root update removed.
Projects, samples and configuration files were not changed.
