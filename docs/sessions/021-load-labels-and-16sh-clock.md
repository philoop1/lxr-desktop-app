# 021: Load labels, global layout and 16sh clock

2026-10-30. User reported that the previous 0.1.12 works on the device.
This is a targeted hardware report, not a measured CPU/sync regression.

Renamed visible `kcm` to `lki` / Load Kit, preserving its parameter ID and
behavior. Swapped its menu slot with CPU: the first four-field view is
`cpu/cki/cko/scr`; the next is `lki/lsh/lmp/lsr`. These are successive
four-field views, not the LCD's two rows. Each view shows labels above values.
The three boolean load switches now display `off/aut` in overview and edit
mode. Other on/off controls keep their existing labels; lki also uses `aut`.

Appended CKO selector `16sh` at enum value 6, preserving the six existing
saved values. It emits shuffled sixteenth notes: four pulses per quarter,
following the four-point Groove. Existing 2/4/8/16/24/48 PPQ selections now
stay straight; only the explicit 16sh choice follows groove. With neutral
groove it emits straight sixteenths. This adapts Mutador's groove-following
clock behavior to an explicit desktop selector; 16sh is not 16 PPQ.

The overview uses all four characters of the CKO value cell; edit mode uses
the four rightmost LCD positions. The longer label is not truncated to 16s,
and the cell separator is cleared when changing back to a shorter value.
The Cortex parser recognizes the appended selector. No globals format or
field offsets changed. The prior lsh load hold remains in force.

`tools/check_groove.py` passed 1531942 assertions, including real output
functions and exact quarter-note edge positions for straight 4 PPQ versus
16sh with a non-neutral shape. ARM GCC 14.3 release build passed 9/9 final
steps after adding a missing clock header. An earlier build approval was
rejected with `rejected by user`; the later approved retry completed.
ELF text=294172, data=880, bss=341436 bytes; ITCM 15376/16384 bytes.

Image `LXR_V2_V1.7_Mutador0.1.13.img`: 295076 bytes including header.
SHA-256 `DCBF5B7176BA30D80DE17DA99E08C7E4C1FCA85C5CEDFC63E4B7F8FC5154BB07`.
Archived and copied to the verified LXRO2 volume F:, then hash-checked.
The old root image was backed up and verified under
`build/card-image-backups/20261030-clock-0.1.13` before removal. Only 0.1.13
remains as a root update. No project, kit, pattern or channel file was changed.
Device installation and the new LCD/physical-clock check remain pending.
