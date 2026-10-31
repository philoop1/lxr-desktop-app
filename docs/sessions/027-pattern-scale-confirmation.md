# Session 027: Pattern Scale and confirmed downbeat switching

Date: 2026-10-31. Image: Mutador 0.1.22.

Long PERFORMANCE opens the current pattern Scale window. Encoder rotation
only previews; click confirms and enables scl=pat. A running change starts
Step 1 once on the next transport bar; stopped changes apply immediately.
The choices are 2/4/6/8/12/16/24/32. All 64 stored slots remain active except
/12, which plays slots 1–12 of each page and preserves the remaining slots.
/32 plays all 64 steps in two bars. /6 and /24 are genuine triplet timing.

Pattern copy/backup and checked SCL2 trailers retain the actual division.
Old patterns default to 16. MUTA.CFG v3 marks new global scale indices and
migrates v1/v2 overrides; the payload size remains 29 bytes.

ARM release build passed. Native tests: Pattern/window/storage 1098,
performance/timing 56947, edit/scale/hat/storage 148249 assertions. The full
Voice-CC audit passed 509589 assertions and LFO reference audit 450062.
Hardware listening, controller use, analogue sync, save/reboot and CPU
remain to be verified. The image was subsequently copied to F: on 2026-10-31 and hash-verified.
The old 0.1.19 image was backed up before removal; see BUILD_NOTES.md.
