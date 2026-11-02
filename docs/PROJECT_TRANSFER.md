# Kit and pattern transfer between LXR2 projects

Mutador 0.2.13 adds names and a paired Pattern + Kit import to the
on-device copy dialog for saved LXR2 kits and patterns. Use 0.2.14 or later:
in 0.2.13 the double press only worked within about 150 ms.
Stop the sequencer before using it.

1. Hold **LOAD** and press **PROJECT (Step 11) twice** within 600 ms to import
   into the current project. With **SAVE + PROJECT twice**, export from it.
   The old LOAD/SAVE + Step 7 shortcut remains available.
2. Turn the encoder to select the other `PROJxx` folder; project numbers wrap
   from 63 to 00. Click the encoder.
3. Choose **KIT**, **PAT**, or **P+K** (Pattern + Kit) with the encoder and click.
   The KIT and PATTERN keys also select those two types directly. PROJECT
   returns to project selection.
4. Select the source slot while reading its eight-character name; click.
   Select the Pattern/Kit destination slot and click. Its current name is shown
   too. For **P+K**, the firmware finds the lowest free Kit slot automatically.
5. Check the displayed slot numbers, including the automatically chosen Kit
   slot for P+K. Click to confirm the copy.
   A used destination asks `Replace?` and requires another click. Press VOICE
   to leave without replacing it.

The current project stays active. After an import, the copied slot is also
loaded into RAM; the playing pattern or active kit is not switched. Importing
into the active pattern's own slot replaces that pattern's content. The copy
uses a temporary file and backs up the previous destination during a replace.
If a slot contains more than one matching file, the transfer refuses to guess
which one to replace. P+K supports PatV02 and PatV03 files and updates the
copied Pattern's kit link to the new Kit slot. If no free Kit slot exists,
nothing is written.

From Mutador 0.2.15, LOAD + PROJECT twice also offers `LXR1 PRF` after PROJ63:
choose a performance, then the first slot of an eight-slot Pattern block. Its
Kit goes to the lowest free slot. `Replace` covers the whole block. This needs
the converted library in `/LXR1/Pxxx/LXR2` on the card.

Raw LXR1 `.prf`, `.all`,
`.pat` and `.snd` files still need `tools/import_lxr1_patterns.py` on a PC;
the on-device LXR1 reader and selection are a separate step.
