# Changelog

Changes in this fork relative to
[Erica Synths' lxr-desktop-app](https://github.com/erica-synths/lxr-desktop-app)
are recorded here. The upstream project keeps its own Git history.

## Unreleased

### Mutador 0.2.24 (hardware test pending)

- FX sends `s1`-`s6` and `sm` moved from the PERF pages to SHIFT + Step 5. Pressing it again switches between the two screens.
- The startup screen shows the real version again. It had stayed at 0.2.10.
- Four host checks that had been failing unnoticed run again; none found a firmware defect.

### Mutador 0.2.23 (hardware test pending)

- The Pch CCs from 0.2.22 now work only when Pch has a channel of its own. If Pch shares a channel with `ch` or a Voice, those numbers keep their existing meaning.

### Mutador 0.2.22 (hardware test pending)

- New Pch CCs: 54 Scarcity, 55 All Velocity, 56 Fill, 57 master filter enable, 58 pitch bend range, 59 FX send mode, 67 FX output mode, 68/69 clock offset, 92-97 PWM, 102-107 LFO slew, 108-113 LFO polarity, 114-119 random step LFO depth.
- The manual's Pch `spd` and `sct` section and the numeric CC table are up to date again.

### Mutador 0.2.21 (hardware test pending)

- Confirming rate 24 or 32 sets tracks on the default length to that rate, and returning to 16 or below restores 16. Hand-set lengths stay.
- PLAY on incoming MIDI Clock without MIDI START starts at once. The bar wait now applies only after MIDI START.

### Mutador 0.2.20 (hardware test pending)

- PERF `scl` is now `spd`: /8 /4 /2 1 *2 *4 relative to the stored pattern rate, so `pat` is gone and a ternary pattern stays ternary at any speed. It starts at 1 and changes at the bar. Speed tops out at 64 steps a bar, 48 on ternary rates.
- MIDI clock output no longer depends on the step length. Pch CC 79-84 select `spd`; 85-87 return to voice parameters.

### Mutador 0.2.19 (hardware test pending)

- A confirmed pattern rate now survives leaving or reselecting the pattern. The beat LED follows three-step groups on ternary rates.

### Mutador 0.2.18 (hardware test pending)

- sct is a live off/a/b/c control on PERF page 2 that follows the active rate: 4/3a/3b/3c on quaternary rates and 3/4a/4b/4c on ternary rates. It changes the step time as Mutador did, so a bar keeps its length, and each pair is an exact inverse. Old 12a is now 3c and old 12c is 3a.
- Changes apply on the next quarter or group edge without restarting. sct no longer writes to patterns and starts off.
- pbr moved to the third globals page. Pch CC 88-91 select sct off/a/b/c.

### Mutador 0.2.17 (hardware test pending)

- In pattern selection the encoder picks bank 1 to 4. Holding LOAD for one second opens the same view as SHIFT + Step 1.

### Mutador 0.2.16 (hardware test pending)

- Transfer imports now load from the project folder into the running project, so they survive Save Project and reboot. Older /tmp copies of a slot are dropped, and Replace and free-Kit checks count /tmp.

### Mutador 0.2.15 (hardware test pending)

- LOAD transfer adds LXR1 after PROJ63: imports a converted performance's eight patterns into an eight-slot block with its kit in the lowest free Kit slot. One Replace confirmation covers the block.

### Mutador 0.2.14 (hardware test pending)

- LOAD or SAVE + PROJECT pressed twice now works within 600 ms. The window was only about 150 ms in 0.2.13 because the system tick runs at 4 kHz.

### Mutador 0.2.13 (hardware test pending)

- Project transfer shows Kit and Pattern names, opens with LOAD or SAVE + PROJECT pressed twice, and adds P+K: a Pattern plus its linked Kit, placed in the lowest free Kit slot with the Pattern's kit link updated.
- Importing into the active pattern slot now keeps the new pattern after a pattern change. A failed P+K no longer leaves a false `No free KIT` on later errors.
- ARM build and host checks passed. The dialog has no host test; on-device copy tests are pending.

### Mutador 0.2 (hardware test pending)

- Added the rps LFO waveform: a played Step from the selected trigger voice changes the held random value once, independently of the target voice. A third and fourth LFO view expose trigger, destination, amount, offset, slew and Helicase-style neg/pos/bi polarity.
- Added per-Step fpr (Flam Probability). It gates the repeat hits after the main Step passes its normal probability; 0 leaves only the main hit and 100 preserves every Flam hit.
- New FLP1 Pattern and LFX1 Kit extensions retain these controls while older files load with compatible defaults. The new LFO extras are not morphed. ARM build and targeted host checks passed; device sound and save/load tests are pending.

### Mutador 0.1.28 (pattern selection hardware retest passed)

- Immediate kit loading now sends translated modulation destinations once. Its generic CC loop skips stored destination indices and LFO voice selectors, which the imported CC map otherwise interpreted as parameter IDs. This fixes a concrete kit-load encoding error associated with the ongoing freeze investigation. Production loader audit and ARM release build passed. The user confirmed pattern selection works again on the physical unit with 0.1.28; other changes need broader device checks.


- This import series adds performance load controls, MIDI pitch/CC routing, Groove/Delay/Accent, sequencer probability and scale controls, voice synthesis and modulation, external sends, VCAs and master filter. Membrane was not imported; Snare PWM remains.

### Mutador 0.1.27 (hardware retest pending)

- Guard modulation original-value refresh against null storage and invalid parameter IDs during kit loading. Native target checks and ARM build passed. Candidate image copied and hash-verified on SD. The bank-switch freeze is still awaiting hardware retest with lki=aut.


### Mutador 0.1.26 (hardware freeze retest pending)

- Prevent recursive UART MIDI dispatch during kit loading. Nested audio servicing leaves queued bytes for the outer dispatcher; sequencer interpolation waits until the pattern/kit transaction finishes.
- Fix CC0 original-value index underflow, which wrote 65536 bytes beyond the cache during immediate kit loading. Use cache slot 0 and legacy parameter 127; allocate all 256 CC/CC2 slots, including CC2 slot 255.
- Project loading shows Loading followed by its eight-character name, refreshed after reading prj.nfo.
- Regression tests reproduce the old CC0 write and recursive MIDI dispatch. Fixed bookkeeping passed 8486912 assertions; injected dispatch delivered 129 bytes in order at depth one; pattern switching passed 24576 assertions across 4096 source/destination pairs. MIDI 509607, Scale 1098 and Groove 1531942 checks passed. ARM release built. The reported instrument freeze needs the same hardware retest.

### Mutador 0.1.25 (hardware test pending)

- AVL now uses proportional gain across the full -100 to +100 percent range: +50 is x1.5 and +100 is x2, clipped at MIDI velocity 127. Soft notes retain their relative dynamics until clipping; zero remains zero. The control still runs after rvl for all sequencer voices, velocity modulation and MIDI output.
- Release build and 196491 native velocity/shortcut assertions passed. The image was copied to F: and hash-verified; 0.1.24 is backed up. The previously converted pattern files were not changed again.

### Mutador 0.1.24

- New/reset step velocity defaults to 100 instead of 127, providing headroom for positive AVL.
- Converted only the mounted card's active PROJ directories and TMP by 100/127, rounded. 1345 files/602560 slots were checked; 1281 files/573886 slots changed. All originals and staged results are backed up. Archived LXR material and Helicase were excluded; non-velocity bytes and step active bits were preserved.
- Production C loader audit passed 1262958 assertions across every original/staged file pair, including the default-reset check. Release build and card image hash verification passed. The new firmware does not automatically convert files on load.

### Mutador 0.1.23 (hardware test pending)

- Copied to SD card F: with SHA-256 verification; the former 0.1.22 image is backed up.

- SHIFT+Step 1 now enters pattern selection with the first PERF view from every mode, before COPY/CLEAR routing, and cancels pending step-automation selection.
- Added Mutador rvl behind cnt, then overall velocity avl; pbr moves to the last field. Rvl retains Mutador's Voice-1 sound/MIDI exception while randomizing its modulation velocity. AVL runs afterward for all seven sequencer voices and output MIDI: -100 percent gives velocity 0, neutral preserves it, +100 gives 127, including Flam/Delay repeats.
- MUTA.CFG v4 stores both controls in a 31-byte checked file while retaining the fixed legacy globals and previous extension fields. Versions 1-3 load with neutral defaults. Pch CC9 controls rvl as in Mutador; no external AVL CC is assigned.
- Release build passed. Native checks: velocity/any-mode shortcut 196491 assertions; MIDI dispatch 509607; performance/timing 56947; edit/scale/hat/storage 148256. Hardware sound/controller/save-reboot checks remain pending.

### Mutador 0.1.22 (hardware test pending)

- Copied the 317324-byte release image to SD card F: on 2026-10-31 and verified SHA-256. The old 0.1.19 image is backed up before removal from the card. README, manual, build and session records are updated.

- Added per-pattern Scale 2/4/6/8/12/16/24/32. Hold PERFORMANCE, preview with encoder, click to confirm; running playback restarts at Step 1 on the next transport bar, stopped playback applies immediately. Confirmation enables the pattern scale. LOAD behavior is retained.
- At /12 only the first 12 slots of each 16-step page play; all other rates retain all stored steps. Internal/MIDI clock stays straight. Pattern copy/backup retains scale, stored as a checked SCL2 trailer; old patterns default to /16. MUTA.CFG v3 preserves the new override numbering and migrates old 12a/b/c overrides to /12.
- Release build passed. Pattern/window/storage tests: 1098 assertions; performance/timing tests: 56947; edit/scale/hat/storage tests: 148249. On-device sound, timing and CPU remain to be checked.

- Added Stray (`str`) and Glide (`gld`) LFO shapes with Mutador random targets, interpolation, Offset bias and Retrigger behavior. Their output is normalized for the desktop modulation path. Frequency 0 stops the LFO; held random/Offset and retrigger match Mutador. Existing shape IDs are preserved.
- Imported the complete common Voice-CC map, excluding Membrane. Global/Pch priority and first-matching-voice behavior follow Mutador. Translated aliases update display, parameter base and automation; menu ranges bound discrete values. LFO/velocity destination CC handlers are connected.
- Native source comparisons passed: 450062 LFO assertions and 509589 MIDI mapping/dispatch assertions. Physical listening, MIDI controller and timing/CPU checks remain pending.


### Mutador 0.1.21 (hardware test pending)

- Added Mutador Snare voice CC 112�118: layer Wave/Mix/Frequency/Mode, then Noise Attack/Decay/Slope. These apply on the Snare voice channel, excluding global and performance channels, which retain their existing maps.
- Incoming CC updates sound, display and modulation base, and records the internal parameter on track 4. Wave and Mode clamp to valid selections.
- ARM release build and MIDI dispatch audit passed (357659 assertions). Hardware MIDI testing remains pending.

### Mutador 0.1.20 (hardware test pending)

- Added Snare Noise Attack/Decay/Slope and layer Wave/Mix/Frequency/Mode to LFO, velocity and step automation destinations. New targets are appended at indices 229–235; existing saved target indices remain valid.
- Destination selection handles the appended Snare range for encoder and pots, including LFO target-voice changes. Layer Wave and Mode use bounded, rounded modulation steps and retain their base value at zero depth.
- ARM release build, 49 native destination checks and 2449 Snare/kit checks passed. External voice CC 112–118 from Mutador remains a separate pending import.

### Mutador 0.1.19

- Restored Mutador Snare OSC/FM ordering and names, retaining PWM in place of Membrane. Pressing a different parameter button opens its first view; repeating the same button toggles its available views. Built and copied to the SD card with hash verification.

### Mutador 0.1.18

- Separated SHIFT+2/3/4 Accent/Delay/Groove navigation from regular PERF and hid the separate VCA view. Its initial Snare layout was corrected in 0.1.19. Built and copied to the SD card with hash verification.

### Mutador 0.1.17 (hardware test pending)

- Incoming MIDI START, CONTINUE and STOP now send transport state to the front panel, so PLAY and its LED agree with the sequencer. A local PLAY stop resets the step position. The next PLAY starts from Step 1 at the next MIDI Clock bar when the clock phase is known.
- The MIDI dispatch host test covers all three front-panel feedback messages. Instrument timing and button interaction remain to be checked.

### Mutador 0.1.16 (hardware test pending)

- Added a second Snare tonal oscillator with wave, amount, frequency ratio and Mix/FM/Ring mode. The neutral layer amount keeps the old sound. `SNE2` kit data preserves the `SNE1` noise-envelope values from 0.1.15 and defaults the new layer to off.
- Added COPY for one complete desktop step (including Flam/Shift), eight-step groups, and a track across all 64 pattern slots. Pattern copy also addresses all 64 slots.
- Manual PLAY under MIDI Clock waits for the next 96-pulse bar; when Clock Offset is set and the period is stable, it starts ahead of the confirming edge without doubling the first step. External analogue trigger and MIDI START retain their existing transport behavior.
- ARM release build and host contract tests passed; on-device sound, copy gestures, SD loading and transport timing remain to be checked.

### Mutador 0.1.15 (hardware test pending)

- Snare Noise Envelope: independent `nat`, `ndc`, `nsl` controls on the Snare's formerly empty FM page. Neutral 0/127/64 preserves the previous sound. New kit data carries an `SNE1` marker inside the reserved 512-byte kit block; old kits default safely. Morph interpolates the three values.
- Added drum oscillator `rng` (Ring) after FM/Mix without changing the old two mode values.
- Added Global MIDI Clock Offset: `cof` 0..80 in 0.1 ms and `cfn` 0..9 in 0.01 ms, displayed together as 0.00..−8.00 ms in detail view. Default is −5.00 ms. DIN Clock uses an interrupt-captured cycle timestamp; a predicted step is not replayed at the confirming MIDI edge. Twelve-step grids use eight incoming clocks per step.
- `MUTA.CFG` v2 stores the two clock values while accepting v1 files; explicit Save Globals/Project persists them. Build and native contract tests passed. Audio, timing and save/load on the instrument remain unverified.

### Mutador 0.1.14 (hardware test pending)

- Added held-chord multiple step editing, global `scl` grids (16/12a/12b/12c), exact same-tick half-closed hi-hat, external FX sends, seven independent VCAs, and a master low/high-pass filter.
- PERF now includes filter, send and VCA pages; Global has `mfl`, `fxs` and `fxo`. The startup display identifies Mutador 0.1.14.
- The 18 extra performance controls use a checked `MUTA.CFG` sidecar beside project globals. Existing global offsets and kit files remain unchanged. Save Globals or Project explicitly to persist them.
- Native source-comparison tests and ARM release build passed. Instrument sound, CPU, SD save/reload and clock timing still need testing.

### Mutador 0.1.13 (new controls: hardware test pending)

- Renamed `kcm` to `lki` (Load Kit) and swapped its menu slot with CPU.
  The two four-field global views are now `cpu/cki/cko/scr` and
  `lki/lsh/lmp/lsr`. The load switches display `off/aut`.
- Added `cko=16sh`: shuffled sixteenth-note pulses (4 per quarter). Existing
  clock divisions stay straight. The four-character value appears in full
  in both normal and edit views. Stored selector values remain compatible.
- Release build and groove/clock tests passed; card copy hash-verified.
  The user reported 0.1.12 works; new LCD and clock-output checks are pending.

### Mutador 0.1.12 (hardware test pending)

- Imported the four-point Mutador Groove on a 192 PPQ event grid. SHIFT +
  Step 4 opens `shf/sh2/sh3/sh4`; the main PERF `shf` controls the same master.
  Signed positions preserve the original rounding, deadband and fine offsets.
- Notes, automation and Delay follow the shifted event. Two neighbors on
  either side support combined Groove, Shift and Flam; probability and live
  source selection remain attached to that source. Neutral groove preserves
  the existing desktop dispatcher. MIDI transport/clock stay straight;
  the physical 2/4 PPQ clock output follows Groove.
- Save appends the three shapes to globals (61 stored bytes). `lsh=off`
  preserves the current groove on loading and stays OFF across project loads;
  saving still includes the values. Old projects default to neutral shapes.
- Pch CC40/41/42/43 control the master and three shapes. Includes the 0.1.11
  project-loading fixes. Release build and native reference/integration tests
  passed; physical sound, CPU, sync jitter and save/reboot checks remain open.

### Mutador 0.1.11 (local build; hardware test pending)

- Prefer a named project pattern or kit file when an old SD project contains
  both a blank-named and a named file for one slot. This prevents the empty
  `00-.PAT` in Beatsies from hiding its populated `00-LXR.PAT`.
- Refresh the pattern edit backup from the newly loaded project before the
  first pattern activation, so a prior project's backup cannot overwrite it.
- SHIFT + Step 4 opens the existing Shuffle field on PERF. The exact
  four-point Mutador groove remains separate unfinished timing work.
- GCC 14.3 release build, 399539 native assertions and five focused FAT
  selection cases passed. This
  image has not been copied to the card or tested on hardware.

### Mutador 0.1.10 (hardware test pending)

- SHIFT + Step 2 opens the Velocity/Accent PERF page; SHIFT + Step 3 opens
  MIDI Delay. On Delay, instrument buttons and LEDs edit its seven-voice input
  mask instead of mutes.
- Added Accent master `vlv` and seven destinations, MIDI Delay with chance
  `rpt`, repeat count, sync, bounce, velocity target, mono/poly, exponent and
  pitch, and `cnt` for scaling per-step probability.
- Corrected triplet delay rates to exact 96 PPQ periods after intermediate
  0.1.9. Source kits and automation remain editable; neutral Accent preserves
  active step automation. New stored globals fit the existing reserved block.
- GCC 14.3 release build and 399539 native assertions passed. Image was copied
  and hash-verified on F:. Device timing, sound, CPU and persistence remain to
  be checked.

### Mutador 0.1.8 (hardware test pending)

- Added master decay `gdc` directly beside `gpt` in PERF. It applies a neutral
  bipolar layer to all seven amp-decay destinations without changing kit or
  Morph endpoints; 0 is neutral, displayed range -63..64.
- Added a second PERF page with `rst` (random source step), `csr` (previous
  active step repeat), `pSc` (LXR2BC Scarcity) and `pst` (global hit probability).
  These live controls retain the existing probability stored on each step.
- Added 606-style live pattern ranges across the desktop's 64 slots: hold
  first and last pattern buttons; the inclusive range loops at pattern ends.
  Range LEDs remain lit and the playing pattern blinks. A single selection
  or project load clears the live range. Song mode retains precedence.
- Random/repeated sources carry their note, velocity, flam/shift and automation
  together. Planned neighbors preserve shifted-note lookahead. Scarcity drops
  a complete step including its flams; `pst` independently gates actual hits.
- Removed a duplicate sequencer MIDI output path and used the selected source
  velocity consistently for external MIDI.
- Pch CC5/6/7 control rst/csr/pst; CC28 controls gdc. Scarcity is currently
  menu-only to avoid colliding with reserved Mutador performance CCs.
- New controls save in appended globals; existing kit/pattern fields are
  unchanged. Live 606 ranges are not saved in this import.
- Release build passed; 350509 MIDI/GDC and 38002 performance assertions
  passed. Physical-device timing, CPU and save/reboot checks remain open.

### Mutador 0.1.7 (hardware test pending)

- Completed Mutador's oscillator pitch composition: global pitch, Pch-note
  offset, global bend and per-voice bend combine with kit/played pitch.
  Fractional semitones interpolate the frequency table; octaves continue
  below MIDI 0 and above 127 instead of clamping the resulting pitch.
- Added PERF `gpt` (editable global base pitch, -63..64) and `pbr` (bend range,
  0..48 semitones, default 12). No `ntP` display. These two settings are saved
  in the appended globals extension; old settings default to neutral/12.
- Pch CC27 uses Mutador's bipolar global-pitch mapping and neutral deadband.
  Pch notes now match Mutador's early consumption before RX filtering and
  port forwarding. Global/Pch pitchbend affects all oscillators; Voice bend
  affects the first matching voice, including its modulation oscillators.
- Release build passed 35/35 steps; 334043 native assertions passed,
  including comparison against unmodified Mutador pitch functions. Image
  copied to the SD card and hash-verified; device test remains pending.

### Mutador 0.1.6 (hardware test pending)

- Imported Mutador note routing: Global uses fixed `nte` assignments as a
  drum map at the default pitch; unmatched notes play the selected ANY voice
  chromatically. Duplicate fixed assignments trigger together. Global takes
  priority over overlapping voice channels.
- Dedicated voice channels accept every note chromatically, independent of
  `nte`, and can record without MIDI echo. Added a local-only sound trigger
  so the low-level trigger cannot produce a hidden echo; Global echoes once.
- Notes on a distinct Pch control master oscillator pitch: MIDI note 60 is
  neutral, offsets clamp to -63..64 semitones. Pch takes priority over a shared
  voice channel, while Global takes priority when Pch equals Global. RX N
  gates all three note routes. This offset is live and not saved in kits.
- Retained desktop step-note entry for the edited voice on the sequencer page.
- Includes the CC voice-channel correction from 0.1.5. ARM GCC 14.3 release
  build passed; 312125 native assertions passed. Device testing is pending.

### Mutador 0.1.5 (source correction; firmware build pending)

- Corrected a legacy CC channel lookup: voice-specific CCs now use their
  intended sound voice's channel instead of the next track's channel.
  Global-channel acceptance and the Pch overlap policy are unchanged.
- Added executable tests of the actual MIDI dispatcher and the complete
  numeric legacy CC table. 147633 assertions passed; hardware testing awaits
  a new image. The release-build approval was rejected; no 0.1.5 image exists.

### Mutador 0.1.4 (user device check passed, 2026-10-29)

- Added saved global `lsr` (Load Sample Rate) after `lmp`. With `lsr=off`,
  manual and automatic kit loads retain the current master `srt`; with `on`,
  they load the kit value. Defaults to on for compatibility with old settings.
- Master `srt` remains independent of the Morph target, as in 0.1.3.
- User reported that the resulting behavior works on the physical LXR V2.
  Persistence, old-project compatibility and every switch combination still
  require separate checks.

These performance corrections address behavior the project author says they
had reported to Erica Synths for years. `Pch` is a separate MIDI import feature
and is not included in that description.

### Mutador 0.1.3 (hardware test pending)

- PERF `srt` now controls the master sample rate across the entire Morph range.
  The target kit's stored master sample rate no longer overrides this control.
  Per-voice sample rates still morph between kits.
- Hardware feedback on 0.1.2 confirms that selecting another Morph kit works;
  the remaining reported issue was master sample-rate control at nonzero Morph.

### Mutador 0.1.2 (hardware test pending)

- Added `lsh` and `lmp` immediately after the CPU meter on the second CONFIG
  page. `lsh` chooses whether a pattern change loads that pattern's shuffle;
  `lmp` chooses whether loading a kit also selects its saved Morph target.
- Kept `KCM` as the existing kit-on-pattern-change switch; the proposed `lki`
  would have duplicated it and was omitted.
- Loading a Morph kit now marks the current kit as changed so its Morph-target
  slot can be saved with the kit/project.

### Mutador 0.1.1 (hardware retest pending)

- SHIFT + Step 1 enters pattern selection from PERF while keeping the PERF
  display with BPM and the other live settings visible. SHIFT + PATTERN still
  opens the dedicated pattern-selection display.
- Pattern selection requests Euclid data for the active voice, avoiding a
  menu-page index outside the voice range.
- Changed the morph update to use kit-load parameter order and skip placeholder
  CC 0 and non-morphable target selectors. This addresses code defects found
  after an on-device report that the Morph value changed but the sound did not.
- Archived the new `LXR_V2_V1.7_Mutador0.1.1.img` separately from 0.1 for
  straightforward rollback.

### CONFIG and SD card

- Added saved `Pch` beside global `ch` on the first CONFIG page. It defaults to
  MIDI channel 2 and accepts CC 2 for kit morph when its channel does not
  overlap a voice or global channel. Other performance CCs are still planned.
- Added a read-only CPU meter on the second CONFIG page. It shows the peak
  audio-block processing load over each half-second interval.
- Added the 1.6-era SD-card data backup to version control. The local
  `bootloader.img` is excluded from Git and is not part of this backup commit.
- Named the experimental update image `LXR_V2_V1.7_Mutador0.1.img` and archived
  it beside the unchanged 1.7 baseline image with SHA-256 hashes.

### Development workflow

- Added build notes, a fork changelog, and a numbered session log for planned
  work from LXR2BC and mutador.
- Added a chapter-based desktop manual, with unverified procedures clearly
  marked for later hardware checking.
- Expanded the MIDI and clock chapter using the current desktop menus and
  parser, including code-specific sync modes and routing choices.
- Added a staged mutador import plan with dependencies and validation gates.
- Recorded the P00 baseline build attempt and a source-to-target feature
  matrix.
- Verified a GCC 14.3 desktop baseline image and a Rust-accelerated Euclid
  emulator smoke test; official 1.71 parity and hardware testing remain open.
- Documented the mutador versus desktop MIDI contract and CC collision risks
  before any P01 firmware change.

The Pch/CPU work is an initial, experimental slice. Hardware validation is
still pending; see session 007.


## Mutador 0.2.1

- Explicit four-screen LFO navigation in Voice mode; extra screens remain excluded from PERF.
- Move fpr to Step screen 2 directly before flam.
- Hardware Flam report remains under investigation; host dispatch passes fpr=0/100 note-count checks.


## Mutador 0.2.2

- Random per Step shows trg (trigger voice), target voice, destination and amount. Wave selection remains on the normal LFO page.
- Encoder navigation now reaches all extra LFO parameters and returns to the normal LFO page.


## Mutador 0.2.3

- Stabilize the modulation destination read during live Random-per-Step edits. Restore the original LFO page 2 `rtg` label. Device freeze retest pending.


## Mutador 0.2.4

- Apply half-range bipolar Random per Step modulation. Keep LFO destination changes atomic with respect to audio interrupts. Hardware verification pending.


## Mutador 0.2.5

- Changing an LFO destination restores only that LFO's former target instead of resetting every modulation destination from inside MIDI message handling. Hardware freeze retest pending.

## Mutador 0.2.6

- Random per Step uses six separate modulators with independent trigger, target voice, destination, amount, offset, slew and polarity. The normal LFO stays independent and its older wav=rps mode still works.
- Kit and project kit storage include the new settings. Older kits receive safe defaults.


## Mutador 0.2.7

- Random per Step labels show trg and rds. Its destination shows only the parameter name and encoder selection stays within the voice chosen by voi. The click/transient pitch remains an available target.


## Mutador 0.2.8

- Random per Step destination no longer changes its selected voice. RDS remains within the voice chosen by VOI and retains an off position.


## Mutador 0.2.9

- Add per-Step trig conditions after probability: first/not-first track loop, Fill/not-Fill, and all A:B cycles through 8:8. Conditions gate shifted and flammed hits alongside the existing probability.
- Add a temporary Fill toggle to the Groove page. Conditions save in a versioned CND1 pattern extension; older patterns default to always. Step, track, pattern and edit-buffer copies include conditions.


## Mutador 0.2.10

- Add PRE/NEI/LST and inverse conditions. Resolve and retain condition outcomes at due events so lookahead does not alter history; Flam repeats reuse the outcome.
- Restore independent sct Pattern/16/12a/12b/12c with per-pattern storage and next-boundary switching. CND2 reads older CND1 patterns.


## Mutador 0.2.11

- Fix SHIFT + Step 4 so its second press opens the Groove page's second half with fil and sct; a third press returns to the first half.
- Add offline LXR1 Mutador conversion of eight one-bar LXR2 patterns plus a kit from .prf/.all (or separate .snd). Preserve supported Step automation and translate kit modulation target indices. Conversion limits are recorded per source file.

## Mutador 0.2.12

- Add LOAD + Step 7 import and SAVE + Step 7 export for a saved KIT or PATTERN between LXR2 projects. PROJECT returns to source/destination project selection.
- Require explicit encoder confirmation before every copy. A filled destination requires a second Replace confirmation. Copy through a temporary file, keep the old destination as a backup during replacement, and restore it if the new file cannot be renamed into place.
- Transfers require a stopped sequencer; imported slots are refreshed in RAM. Raw LXR1 files are still handled by the offline converter.
