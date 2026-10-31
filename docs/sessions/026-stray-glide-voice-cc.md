# Session 026: Stray/Glide and common Voice CC

Date: 2026-10-31. Build: Mutador 0.1.22.

Imported Mutador LFO Stray/Glide trajectories, offset bias, waveform setters,
zero-frequency held random and retrigger behavior. Output is normalized for
the desktop modulation path; this does not claim identical response of all
DSP destinations across the two hardware versions.

Imported the common Voice-CC translator, excluding Membrane. Global and
performance channels retain their existing maps. First matching voice wins
on shared channels. Values update sound, display, baseline and recorded
internal automation target. Destination CCs use raw sound-parameter IDs.

Native LFO/reference test: 450062 assertions. MIDI map/dispatch test: 509589
assertions including all source mapper entries and values. Hardware listening,
MIDI controller checks, storage/reboot and CPU verification remain pending.
