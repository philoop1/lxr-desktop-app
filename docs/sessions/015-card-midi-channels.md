# 015: SD-card MIDI channel configuration

2026-10-29. User requested Global 7, Voice 1..6 on 1..6, Pch 16,
excluding the Chan project. They confirmed both hi-hat tracks share channel 6.

Windows reported the card mounted as F:, label LXRO2, FAT32, 7.8 GB,
Generic SD/MMC USB disk 2. No mount/format/repair operation was required.
Read the project names from PRJ.NFO and identified Chan as PROJ17.

Ran tools/set_card_midi_channels.py F:\ --apply after user approval.
Updated and read back 20 GLO.CFG files: root plus 19 projects. Values are
Global=7, Voice channels=[1,2,3,4,5,6,6], Pch=16. PROJ17/GLO.CFG was
verified byte-identical. Notes, other existing settings and project contents
were not edited. Old 30-byte globals gained the missing extension defaults
(lsh=1, lmp=0, lsr=1) along with the requested Pch=16.

Original globals and before/after hashes were saved under:
build/card-midi-backups/20261029-184000-147730/manifest.json.
That local backup is ignored by Git. The repository's historical SD-Card
snapshot was not changed. No firmware file was copied or installed in this
card-configuration operation. The new 0.1.6 note behavior requires that
firmware to be installed on the instrument.

Follow-up, explicitly requested by the user: copied 0.1.6 to F: and verified
SHA-256 3B6F171539FAD1A9E84ED1B0835E5C2D193FEC67C40EEEA287FC35A4D905D58D.
The complete file is 276884 bytes (the build tool reports payload length
276868 before its 16-byte header). Backed up the old 0.1.4 image under
build/card-image-backups/20261029-184155, verified the backup hash and deleted
only that old root LXR update image. Root now contains only the 0.1.6 LXR
update image. Installation on the instrument has not been performed here.
