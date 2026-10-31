# 011: Load Sample Rate switch

2026-10-29. Based on 9c98ebe plus the uncommitted 0.1.3 changes.

User requested global lsr because master srt is also loaded with kits.
Added PAR_LOAD_SAMPLE_RATE before the transient CPU parameter. Existing
stored global indices remain unchanged. Global serialization already ends
before CPU, so the appended switch is saved automatically. Missing values
and old project 0xFF padding default to on, preserving previous behavior.

The second CONFIG page now ends with CPU / lsh / lmp / lsr. With lsr off,
preset_loadDrumsetRam retains master decimation while loading the rest of the
source kit. This applies to manual kit loads and KCM automatic kit loads.
Morph-target loads never change the live master rate. Per-voice rates are
unaffected. Menu initialization seeds master srt at 127 so retaining it on
first boot does not retain a zero-initialized silent value.

Built with ARM GCC 14.3.rel1, CMake and Ninja: 32/32 steps passed.
Archived LXR_V2_V1.7_Mutador0.1.4.img: 275772 bytes, SHA-256
6864825660889E887FA162E2439DAE4294168429205BD69ED1AE6716825CD654.
ELF text=274908, data=856, bss=340572 bytes.

Hardware tests pending: lsr off retains srt across manual and KCM auto kit
loads; lsr on loads the stored rate; project save/reboot retains the switch;
Morph sweep leaves master srt unchanged. No hardware result claimed.

Follow-up 2026-10-29: user reported 0.1.4 works on the instrument. The
individual save/reboot and load-policy cases above were not separately
reported; see session 012.
