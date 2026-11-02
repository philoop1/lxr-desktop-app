#!/usr/bin/env python3
"""Convert the library's 61 LXR1 SND files to LXR2 kits for a kit-only project."""

from __future__ import annotations

import argparse
from pathlib import Path

from import_lxr1_patterns import convert_kit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path, help="staged library containing Pxxx/Pxxx.SND")
    parser.add_argument("output", type=Path, help="new directory for 00-SND.snd .. 60-SND.snd")
    parser.add_argument("--lxr1-source", type=Path,
                        default=Path(__file__).resolve().parents[2] / "mutador")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new directory")
    folders = sorted(args.library.glob("P[0-9][0-9][0-9]"))
    if len(folders) != 61:
        parser.error(f"expected 61 performances, found {len(folders)}")
    kits = []
    for folder in folders:
        data = (folder / f"{folder.name}.SND").read_bytes()
        kit, _ = convert_kit(data, ".snd", args.lxr1_source)
        if len(kit) != 328 or kit[:8] != data[:8]:
            raise ValueError(f"{folder}: unexpected converted kit")
        # The sound is the SND; the shown name follows the performance.
        name = (folder / f"{folder.name}.PRF").read_bytes()[:8]
        kits.append(name + kit[8:])
    args.output.mkdir(parents=True)
    for slot, kit in enumerate(kits):
        (args.output / f"{slot:02d}-SND.snd").write_bytes(kit)
    print(f"Converted {len(kits)} SND kits to {args.output}")


if __name__ == "__main__":
    main()
