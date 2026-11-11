#!/usr/bin/env python3
"""Group the converted LXR1 library into complete LXR2 projects, eight performances each.

Block b of a project holds patterns b*8..b*8+7 linked to kit b. Every kit and
pattern slot gets a file, because the firmware keeps the previous project's RAM
for slots without one. Kits 8..63 repeat kit 7 as "Unused"; in a short last
project the remaining blocks repeat its last performance.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from import_lxr1_patterns import LXR2_PATTERN_BYTES

KIT_LINK_OFFSET = 3662  # TRANSFER_V3_KIT_OFFSET in presetManager.c
CND2_PATTERN_BYTES = 4574
KIT_BYTES = 328


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path, help="staged library containing Pxxx/LXR2")
    parser.add_argument("output", type=Path, help="new staging directory")
    parser.add_argument("--first-project", type=int, default=21)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new directory")
    folders = sorted(args.library.glob("P[0-9][0-9][0-9]"))
    if len(folders) != 61:
        parser.error(f"expected 61 performances, found {len(folders)}")

    files: dict[Path, bytes] = {}
    for group in range(0, len(folders), 8):
        project = args.first_project + group // 8
        members = folders[group:group + 8]
        last = int(members[-1].name[1:])
        root = args.output / f"PROJ{project:02d}"
        files[root / "PRJ.NFO"] = f"P{group:03d}-{last:03d}"[:8].encode("ascii")
        kits = []
        for block in range(8):
            folder = members[min(block, len(members) - 1)]
            kit = (folder / "LXR2" / "00-LXR1.SND").read_bytes()
            if len(kit) != KIT_BYTES:
                raise ValueError(f"{folder}: unexpected kit size")
            kits.append(kit)
            files[root / f"{block:02d}-{folder.name}.SND"] = kit
            for index in range(8):
                data = bytearray((folder / "LXR2" / f"{index:02d}-LXR1{index + 1}.PAT").read_bytes())
                if len(data) not in (CND2_PATTERN_BYTES, LXR2_PATTERN_BYTES) or data[8:14] != b"PatV03" or data[KIT_LINK_OFFSET] != 0:
                    raise ValueError(f"{folder}: unexpected pattern {index}")
                data[KIT_LINK_OFFSET] = block
                files[root / f"{block * 8 + index:02d}-{folder.name}.PAT"] = bytes(data)
        for slot in range(8, 64):
            files[root / f"{slot:02d}-UNUSE.SND"] = b"Unused  " + kits[7][8:]

    for path, data in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f"Wrote {len(files)} files to {args.output}")


if __name__ == "__main__":
    main()
