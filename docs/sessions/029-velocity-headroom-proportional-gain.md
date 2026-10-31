# Session 029: Velocity headroom and proportional gain

Date: 2026-10-31. Final image: Mutador 0.1.25.

0.1.24 defaults new/reset Steps to velocity 100. The user requested a
one-time 100/127 proportional conversion of active PROJ directories and TMP,
excluding archived LXR material and Helicase. Original/staged copies, SHA-256
manifest and application receipt are in
build/card-velocity-backups/20261031-velocity-100/.
1345 files/602560 slots were checked; 1281 files/573886 slots changed.
The production C pattern loader audited all file pairs: 1262958 assertions.
Only velocity's low seven bits changed; active flags and every other field
were preserved. Firmware does not automatically migrate files on load.

The user then selected proportional positive AVL: +50=x1.5 and +100=x2,
clipped at 127. Negative gain, neutral point and Rvl/AVL order remain.
Velocity/shortcut tests: 196491 assertions. ARM build passed. 0.1.25 was
copied/hash-verified on F:; old images are backed up. Pattern conversion was
not repeated for this follow-up. Physical-device checks remain open.
