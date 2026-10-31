# 012: Performance checkpoint and import-plan update

2026-10-29. Documentation only; firmware remains the archived 0.1.4 image.

The user reported that 0.1.4 works on the instrument after adding lsr. Earlier
feedback confirmed another Morph target works in 0.1.2. Record these as user
device observations; persistence and a full regression test were not reported.

The user describes the performance issues as ones they had reported to Erica
Synths for years. This is attributed project history, not an independently
verified upstream issue trail. Pch was explicitly excluded by the user from
that group of longstanding corrections. It remains a separate P01 MIDI feature;
the request is documentation, not removal of its implementation.

README and changelog now distinguish the performance work from Pch. Updated
the stale planning-only status: initial P01 work and parts of P03/P06 exist,
but none of those broad sessions is complete. Next: preserve 0.1.4, check
save/reboot and load policies, commit the checkpoint, then finish P01 channel
priority and numeric CC checks before expanding control CCs and note routing.
Official Euclid 1.71 parity and baseline storage/MIDI/sync checks remain open.

No rebuild: only documentation changed. Existing 0.1.4 artifact remains
275772 bytes, SHA-256
6864825660889E887FA162E2439DAE4294168429205BD69ED1AE6716825CD654.
