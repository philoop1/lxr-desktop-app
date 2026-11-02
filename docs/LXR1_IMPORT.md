# LXR1 Mutador pattern import (offline preview)

`tools/import_lxr1_patterns.py` reads an LXR1 `.pat`, `.prf` or `.all` file,
including Mutador performance version 12, and writes **eight** LXR2 Mutador
`PatV03` patterns. Performances also produce an LXR2 `.snd` kit; a `.pat`
can be paired with `--kit-source PATH_TO_SND`. Keep LXR1 card files in a
separate `LXR1` folder. The
converter never changes its source or an existing LXR2 project.

```powershell
python tools/import_lxr1_patterns.py I:\LXR1\P021.PRF I:\Github\lxr2-Mutador\build\import-P021 --start-slot 16
```

The output directory must not exist yet. Inspect `IMPORT_NOTES.txt` before
copying the eight `.pat` files into the chosen LXR2 `PROJxx` directory. Slots
16 through 23 are used in the example. Existing files in those slots must be
backed up and removed separately because the firmware can find two files for
the same slot. To import eight LXR1 performances into 64 LXR2 slots, convert
them with start slots 0, 8, 16, 24, 32, 40, 48 and 56.

Each LXR1 pattern's 16 main steps stay a single bar by default. Bars 2–4 are
empty and each track keeps its original length. `--repeat` explicitly repeats
the bar over four bars. A track's rotation is baked into the generated step
order. A single substep hit
uses LXR2 shift; evenly spaced x2/x4/x8 hits use flam. Irregular hit groups
retain the first hit and are listed in the notes. Probabilities are scaled
from 0–127 to 0–100. The kit association defaults to `--start-slot / 8` and
can be changed with `--kit-slot`.

The old parameter IDs 0–220 are unchanged in LXR2; supported automation
targets are carried over, while unsupported targets are listed and omitted.
Kit modulation target indices are remapped through the two firmware target
tables. Kit sound parameters and Mutador's snare noise/layer extras are
copied. Membrane settings have no LXR2 equivalent and are reported.
Project settings, LXR1 next-pattern chains and live browser selection are
**not yet imported**. The converter is a safe offline stage. Import from
another LXR2 project is described in [PROJECT_TRANSFER.md](PROJECT_TRANSFER.md).

On the device, `sct` is on the second PERF page from Mutador 0.2.18.
