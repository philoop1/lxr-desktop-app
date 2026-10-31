# Session 030: Pattern selection bank freeze investigation

Date: 2026-10-31. Reported firmware: current card image Mutador 0.1.25.

The user reports a freeze after increasing the bank in the new pattern
selection mode. Exact trigger remains to be established: bank button alone
versus selecting a pattern in the higher bank. The subsequent investigation below produced candidate image 0.1.26;
hardware retest is pending.

The bank-button branch only increments/decrements the bank within 0..3
and calls `led_initPatternSelectLeds`; it does not load a kit or pattern.
`tools/check_pattern_banks.py` exercises the production LED functions with
MSVC runtime checks: 262144 refreshes across all four banks, all played and
viewed pattern slots, with and without a pattern loop, passed. This is a
native logic check, not a hardware reproduction or proof that the firmware
is free of the reported fault.

All 1345 backed-up staged PROJ/TMP pattern files have valid kit-slot
references (0..63). These checks do not reproduce live audio/interrupt load,
GPIO/SPI behavior, or the complete kit-switching path on the device.

Initial investigation awaited trigger clarification; subsequent findings follow.


## 2026-10-31 - 0.1.26 MIDI-running pattern-switch investigation

User reproduction: SHIFT+Step 1, bank up, choose pattern; freeze only while
running with MIDI Clock. Exact project and slot were not identified.
Confirmed code defects: CC0 underflow wrote at cache offset 65536; recursive
UART dispatch via kit loading -> soundengine_process -> uart_processMidi.
Fixed cache indices/size, UART dispatch reentry and sequencer interpolation
during incomplete pattern switching. Loading display now shows project name.

Old CC storage regression failed; fixed passed 8486912 assertions.
Old injected UART dispatch reached depth 128; fixed dispatched all 129 bytes
in order at depth one. Production pattern switching: 24576 assertions across
4096 old/new slots, injecting nested MIDI/sequence callbacks during kit load.
MIDI dispatch 509607, Scale 1098 and Groove 1531942 checks passed.
ARM release: ITCM 14304/16384, DTCM 107664/131072,
RAM 274884/393216, FLASH 266944/1015808 bytes.
Image LXR_V2_V1.7_Mutador0.1.26.img: 318260 bytes.
SHA256 462432BA7278419494974FA9181EBB23D009E3837726A298711A31E924443E8E.
Archived locally. F: was absent; no SD files were changed.
These tests identify and repair concrete defects; they do not prove that
all causes of the user's hardware freeze have been eliminated. Device
retest with the original gesture and external MIDI Clock remains open.


## Device retest: freeze persists in 0.1.26

User explicitly confirmed startup version 0.1.26. In MayengA (last card
project index 14), selecting a pattern after increasing the bank freezes
immediately during MIDI-clock playback. Thus 0.1.26 must not be considered
a complete fix. Higher slots have valid kit references; several legacy
patterns contain out-of-range track lengths, already clamped in most new
playback paths. Requested device comparison with lki=off to isolate the
automatic kit transaction from selection and pattern playback. No new
firmware or card-data changes were made in this follow-up.


## 0.1.27 candidate after lki comparison

User confirmed: with lki=off the same bank/pattern change works; failure
is associated with automatic kit loading in 0.1.26. Added bounds and null
storage checks in modNode_setOriginalValueChanged before accessing the
parameter table. Empty/off targets can have TYPE_UINT8 with a null pointer.
A native extracted-function audit passed all 65536 empty/invalid IDs and
a valid byte target. ARM release passed. This repairs a concrete unchecked
access; hardware confirmation of the reported freeze remains pending.
Image 0.1.27: 318084 bytes, SHA256
10A5980FD81A1B2C2A4B9C2C88C5BD63EF738DD16BBBA38FB65B9A44F0929EF1.
Copied/hash-verified on F:, former 0.1.26 image backed up under
build/card-image-backups/20261031-mutador-0.1.27/.


## 0.1.28: immediate kit loader selector encoding

User reports 0.1.27 still freezes, also in normal pattern selection.
lki=off works. Immediate kit loading translates destination indices through
modTargets and sends them, then its generic parameterOrder loop sent the
raw indices again through the newly imported CC selector handlers. These
handlers interpret bytes as parameter IDs, corrupting destinations and
allowing selector/reset recursion. Skip VEL_DEST, VOICE_LFO and TARGET_LFO
selectors in the generic loop, as the existing morph path already does.
Also skip NONE and Bank Change placeholders. Production immediate-loader
and parameterOrder harness passed 256 complete kit-value sweeps: all twelve
translated target messages sent, no raw selector CCs. ARM build passed.
Candidate 0.1.28 archived, SHA256
08FD79C072EE4B068913E5563CD70565689DC028C3596879E278564715325C03.
Card F: absent during follow-up, no card write. Device retest remains open.

0.1.28 card write completed: F:/LXR_V2_V1.7_Mutador0.1.28.img,
318108 bytes, SHA256 verified as
08FD79C072EE4B068913E5563CD70565689DC028C3596879E278564715325C03.
Previous 0.1.27 image backed up and hash-verified before removing only
that old root image. Device installation and lki=aut retest pending.

## Device result and session close

After installing 0.1.28, the user reported pattern selection works again. This is a targeted device retest of the kit-load fix, not a full regression pass. Membrane was not imported; Snare PWM remains.

Release memory: ITCM 14328/16384 (2056 bytes free), DTCM 107664/131072 (23408 free), RAM 274884/393216 (118332 free), FLASH 266768/1015808 (749040 bytes free).
