# Session 028: Random/overall Velocity and any-mode pattern shortcut

Date: 2026-10-31. Image: Mutador 0.1.23.

SHIFT+Step 1 takes priority from every mode and COPY/CLEAR selection, cancels
pending automation selection and opens pattern selection with PERF page 1.
The second PERF page is rst/csr/pSc/pst/cnt/rvl/avl/pbr.

Rvl uses Mutador random attenuation and its Voice-1 modulation-only exception.
AVL follows rvl for all sequencer voices and MIDI output, including repeats:
-100 percent sets velocity 0, 0 preserves it, +100 sets 127. The signed field
uses four LCD cells. New controls are appended IDs with neutral startup values.
MUTA.CFG v4 extends v3 by two explicit bytes, preserving old field locations;
v1-v3 files load with neutral velocity controls. Pch CC9 controls rvl.

ARM release build passed. Native checks: velocity/shortcut 196491, MIDI
509607, performance/timing 56947 and edit/scale/hat/storage 148256 assertions.
Hardware sound/controller/save-reboot checks remain pending. This image was
archived locally and subsequently copied to F: with hash verification.
The former 0.1.22 image was backed up before removal from the card.
