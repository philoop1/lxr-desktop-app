# 013: MIDI channel priority and numeric CC audit

2026-10-29. Based on `9c98ebe` plus current 0.1.3/0.1.4 changes.

Audited actual desktop dispatch and mutador `7319e19b`. Added a native test
harness that extracts actual dispatch/filter/routing functions, using spies
for hardware and downstream synth/recording calls. It reproduces the legacy
voice-channel lookup defect before correction. After using target group minus
one as the channel-array index, 147633 assertions pass. Numeric CC0..127 output
is saved in docs/P01_CC_MAP.csv; details are in docs/P01_CHANNEL_AUDIT.md.

Pch overlap currently disables the Pch handler; dedicated Pch only implements
Morph CC2. Port forwarding precedes local receive filtering. Notes fan out on
shared channels; pitch bend and compact voice CCs are not implemented. No new
Pch CC1 behavior was added during the audit.

CMake configure succeeded for source version 0.1.5. The release-build approval
was rejected with `rejected by user`, without further reason. No 0.1.5 image
was created. The native parser test is not an ARM build or hardware test.

The user then requested LXR2BC note/channel behavior as the reference. Current
LXR2BC checkout c277507 has uncommitted changes and was read only. Its voice
channel menu accepts 1..16, not 0. Its note selector displays ANY at zero,
but voice-note matching uses a default note for zero. Clarification about
Voice ch=0 versus nte=0 is pending before porting that behavior.
