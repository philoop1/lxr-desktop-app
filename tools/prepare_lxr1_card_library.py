#!/usr/bin/env python3
"""Stage every LXR1 PRF with its SND and converted LXR2 kit/patterns."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from import_lxr1_patterns import convert, convert_kit, parameter_maps, source_offset


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="LXR1 card backup containing Pxxx.PRF")
    parser.add_argument("output", type=Path, help="new staging directory")
    parser.add_argument("--lxr1-source", type=Path,
                        default=Path(__file__).resolve().parents[2] / "mutador")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new directory")
    performances = sorted(args.source.glob("P[0-9][0-9][0-9].PRF"))
    if not performances:
        parser.error("no Pxxx.PRF files found")
    _, valid_automation, _ = parameter_maps(args.lxr1_source)
    prepared: list[tuple[str, bytes, bytes, list[bytes], list[str], bool, int]] = []
    for source in performances:
        data = source.read_bytes()
        images, warnings = convert(data, ".prf", False, valid_automation, 0)
        kit, kit_notes = convert_kit(data, ".prf", args.lxr1_source)
        warnings.extend(kit_notes)
        snd_path = args.source / (source.stem + ".SND")
        existing = snd_path.is_file()
        if existing:
            snd = snd_path.read_bytes()
            if len(snd) < 236:
                raise ValueError(f"{snd_path}: truncated SND")
        else:
            kit_offset = source_offset(data, ".prf") - 512
            extra = data[kit_offset + 228:kit_offset + 240] if data[8] >= 10 else b""
            snd = data[:8] + data[kit_offset:kit_offset + 228] + extra
            warnings.append("Original SND missing; SND extracted from this PRF")
        if len(images) != 8 or any(len(image) != 4574 for image in images) or len(kit) != 328:
            raise ValueError(f"{source}: unexpected converted file size")
        prepared.append((source.stem, data, snd, images, warnings, existing, data[8]))

    args.output.mkdir(parents=True)
    rows = []
    for stem, data, snd, images, warnings, existing, version in prepared:
        folder = args.output / stem
        converted = folder / "LXR2"
        converted.mkdir(parents=True)
        (folder / f"{stem}.PRF").write_bytes(data)
        (folder / f"{stem}.SND").write_bytes(snd)
        (converted / "00-LXR1.SND").write_bytes(convert_kit(data, ".prf", args.lxr1_source)[0])
        for slot, image in enumerate(images):
            (converted / f"{slot:02d}-LXR1{slot + 1}.PAT").write_bytes(image)
        (folder / "NOTES.TXT").write_text(
            f"{stem}.PRF: version {version}; SHA256 {sha256(data)}\n"
            f"{stem}.SND: {'original file' if existing else 'extracted from PRF'}; SHA256 {sha256(snd)}\n"
            "LXR2: eight one-bar patterns, kit slot 00.\n"
            "Conversion notes:\n" + ("\n".join(warnings) if warnings else "none") + "\n",
            encoding="utf-8")
        rows.append((stem, version, "original" if existing else "extracted", len(warnings), sha256(data), sha256(snd)))
    with (args.output / "INDEX.CSV").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("performance", "version", "snd", "notes", "prf_sha256", "snd_sha256"))
        writer.writerows(rows)
    (args.output / "README.TXT").write_text(
        "LXR1 Mutador library. Pxxx/ contains the original PRF and matching SND; "
        "Pxxx/LXR2/ contains eight converted one-bar LXR2 patterns and one kit. "
        "An SND marked 'extracted' was reconstructed from its PRF because no "
        "separate SND existed. Read NOTES.TXT for approximations. These folders "
        "are a library; firmware 0.2.12 cannot browse them directly yet.\n",
        encoding="utf-8")
    print(f"Staged {len(rows)} performances, {sum(row[2]=='original' for row in rows)} original SND, "
          f"{sum(row[2]=='extracted' for row in rows)} extracted SND, "
          f"{sum(row[3] for row in rows)} conversion notes at {args.output}")


if __name__ == "__main__":
    main()
