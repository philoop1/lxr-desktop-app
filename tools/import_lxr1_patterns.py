#!/usr/bin/env python3
"""Convert one LXR1/Mutador performance into LXR2 kit and PAT files.

This is an offline, non-destructive first step toward an on-device LXR1 browser.
The output is staged in a fresh directory; existing project files are never edited.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import struct

TRACKS = 7
LXR1_PATTERNS = 8
LXR1_STEPS = 128
LXR2_STEPS = 64
STEP_BYTES = 7
LXR1_PATTERN_BYTES = TRACKS * LXR1_PATTERNS * LXR1_STEPS * STEP_BYTES + 112 + 16 + 1 + 56
ROLLS = {(0, 4): 1, (0, 2, 4, 6): 3, tuple(range(8)): 5}
DEFAULT_STEP = bytes((100, 100, 60, 255, 0, 255, 0))
LXR1_KIT_BYTES = 228


def enum_values(header: Path) -> dict[str, int]:
    text = header.read_text(encoding="utf-8")
    body = text[text.index("PAR_NONE,"):text.index("END_OF_SOUND_PARAMETERS,")]
    body = re.sub(r"/\*.*?\*/|//[^\n]*", "", body, flags=re.S)
    values: dict[str, int] = {}
    number = -1
    for item in body.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            name, expr = (part.strip() for part in item.split("=", 1))
            number = sum(values.get(term.strip(), int(term.strip(), 0) if term.strip().lstrip("-").isdigit() else 0)
                         for term in expr.split("+"))
        else:
            name = item
            number += 1
        values[name] = number
    return values


def mod_targets(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
    body = text[text.index("modTargets[]"):]
    body = body[:body.index("};")]
    return re.findall(r"\{\s*TEXT_[A-Z0-9_]+\s*,\s*(PAR_[A-Z0-9_]+)\s*\}", body)


def parameter_maps(lxr1_source: Path) -> tuple[dict[int, int], set[int], int]:
    repo = Path(__file__).resolve().parents[1]
    old = mod_targets(lxr1_source / "front/LxrAvr/Menu/Cc2Text.c")
    new = mod_targets(repo / "Core/Src/menu/Cc2Text.c")
    enum = enum_values(repo / "Core/Inc/Parameters.h")
    if enum["PAR_AUDIO_OUT6"] != 220 or len(old) < 150 or len(new) < 150:
        raise ValueError("unexpected source or destination modulation table")
    index_by_name = {name: index for index, name in enumerate(new)}
    target_map = {index: index_by_name[name] for index, name in enumerate(old)
                  if name in index_by_name}
    valid_ids = {enum[name] for name in new if name in enum}
    return target_map, valid_ids, max(enum.values()) + 1


def source_kit(data: bytes, suffix: str) -> bytes | None:
    if suffix == ".snd":
        if len(data) < 8 + LXR1_KIT_BYTES:
            raise ValueError("truncated LXR1 kit")
        return data[8:8 + LXR1_KIT_BYTES]
    if suffix in (".prf", ".all"):
        offset = source_offset(data, suffix) - 512
        return data[offset:offset + LXR1_KIT_BYTES]
    return None


def convert_kit(data: bytes, suffix: str, lxr1_source: Path) -> tuple[bytes, list[str]]:
    raw = source_kit(data, suffix)
    if raw is None:
        raise ValueError(".pat has no kit; supply a matching .snd separately")
    target_map, _, new_count = parameter_maps(lxr1_source)
    kit = bytearray(new_count)
    kit[:221] = raw[:221]
    notes: list[str] = []
    # Both lists contain parameter IDs, but added PWM/modulation entries move
    # the menu indices. Preserve the addressed parameter rather than the index.
    for start in (149, 167):  # PAR_VEL_DEST_1 and PAR_TARGET_LFO1
        for voice in range(6):
            old_index = raw[start + voice]
            if old_index in target_map:
                kit[start + voice] = target_map[old_index]
            else:
                kit[start + voice] = 0
                notes.append(f"voice {voice + 1}: unsupported modulation target {old_index}")
    # Old LXR1 performance data stores the first snare noise parameters in
    # the 512-byte kit block. Sound defaults remain safe for older files.
    enum = enum_values(Path(__file__).resolve().parents[1] / "Core/Inc/Parameters.h")
    kit[enum["PAR_SNARE_NOISE_DECAY"]] = 127
    kit[enum["PAR_SNARE_NOISE_SLOPE"]] = 64
    kit[enum["PAR_SNARE_LAYER_FREQ"]] = 25
    extra_offset = (8 + LXR1_KIT_BYTES) if suffix == ".snd" else source_offset(data, suffix) - 512 + LXR1_KIT_BYTES
    extras_old = data[extra_offset:extra_offset + 12]
    if suffix in (".prf", ".all") and data[8] < 10:
        notes.append("older performance snare extension not mapped; using safe defaults")
    elif len(extras_old) >= 12:
        for name, position in (("PAR_SNARE_NOISE_ATTACK", 2), ("PAR_SNARE_NOISE_DECAY", 3),
                               ("PAR_SNARE_NOISE_SLOPE", 4), ("PAR_SNARE_LAYER_WAVE", 6),
                               ("PAR_SNARE_LAYER_AMOUNT", 7), ("PAR_SNARE_LAYER_FREQ", 8),
                               ("PAR_SNARE_LAYER_MODE", 9)):
            kit[enum[name]] = extras_old[position]
        if any(extras_old[index] for index in (0, 5, 10, 11)):
            notes.append("LXR1 membrane parameters have no LXR2 equivalent")
    extras = b"SNE2" + b"LFX1" + bytes(6) + bytes((2,)) * 6
    rps = bytearray(42)
    for voice in range(6):
        rps[voice] = voice + 1
        rps[6 + voice] = voice + 1
        rps[36 + voice] = 2
    extras += b"RPS2" + rps
    name = data[:8].ljust(8, b" ")[:8]
    return name + kit + extras, notes


def source_offset(data: bytes, suffix: str) -> int:
    if suffix == ".pat":
        return 8
    if suffix not in (".all", ".prf"):
        raise ValueError("source must be .pat, .all or .prf")
    if len(data) < 9 or not 1 <= data[8] <= 12:
        raise ValueError("unsupported or missing LXR1 performance version")
    return 9 + (1 if suffix == ".prf" and data[8] == 1 else 64) + 512


def convert(data: bytes, suffix: str, repeat: bool = False,
            valid_automation: set[int] | None = None,
            kit_slot: int = 0) -> tuple[list[bytes], list[str]]:
    offset = source_offset(data, suffix)
    if len(data) < offset + LXR1_PATTERN_BYTES:
        raise ValueError(f"truncated LXR1 pattern block: {len(data)} bytes")
    raw = memoryview(data)[offset:offset + LXR1_PATTERN_BYTES]
    step_bytes = TRACKS * LXR1_PATTERNS * LXR1_STEPS * STEP_BYTES
    masks = struct.unpack_from("<56H", raw, step_bytes)
    shuffle = raw[step_bytes + 112 + 16]
    lengths = raw[step_bytes + 112 + 16 + 1:step_bytes + 112 + 16 + 1 + 56]
    name = data[:8].decode("latin1", errors="replace").strip(" \x00") or "LXR1"
    warnings: list[str] = []
    outputs: list[bytes] = []
    for pat in range(LXR1_PATTERNS):
        payload = bytearray()
        main = [[0] * TRACKS for _ in range(4)]
        track_lengths = []
        for track in range(TRACKS):
            packed = lengths[pat * TRACKS + track]
            length = (packed & 15) or 16
            rotation = (packed >> 4) % length
            track_lengths.append(64 if repeat else length)
            steps = bytearray()
            timing = bytearray()
            for bar in range(4 if repeat else 1):
                for j in range(16):
                    source_main = ((j % length) + rotation) % length
                    base = (((track * LXR1_PATTERNS + pat) * LXR1_STEPS) + source_main * 8) * STEP_BYTES
                    hits = []
                    if masks[pat * TRACKS + track] & (1 << source_main):
                        for k in range(8):
                            raw_step = bytes(raw[base + k * STEP_BYTES:base + (k + 1) * STEP_BYTES])
                            if raw_step[0] & 128:
                                hits.append((k, raw_step))
                    if not hits:
                        steps.extend(DEFAULT_STEP)
                        timing.append(7 << 4)
                        continue
                    first_k, first = hits[0]
                    positions = tuple(k for k, _ in hits)
                    flam = ROLLS.get(positions, 0)
                    shift = 7 + first_k if len(hits) == 1 else 7
                    if bar == 0 and len(hits) > 1 and not flam:
                        warnings.append(f"pattern {pat + 1}, voice {track + 1}, step {j + 1}: irregular substeps {positions}; kept first hit")
                    if bar == 0 and len(hits) > 1 and any(s[1:7] != first[1:7] or (s[0] & 127) != (first[0] & 127) for _, s in hits[1:]):
                        warnings.append(f"pattern {pat + 1}, voice {track + 1}, step {j + 1}: differing substep values; kept first")
                    automation = []
                    for dest, value in ((first[3], first[4]), (first[5], first[6])):
                        if dest in (0, 255):
                            automation.extend((255, 0))
                        elif valid_automation is not None and dest in valid_automation and dest < 221:
                            automation.extend((dest, value & 127))
                        else:
                            automation.extend((255, 0))
                            if bar == 0:
                                warnings.append(f"pattern {pat + 1}, voice {track + 1}, step {j + 1}: unsupported automation target {dest}")
                    probability = min(100, round((first[1] & 127) * 100 / 127))
                    steps.extend((first[0], probability, first[2] & 127, *automation))
                    timing.append((shift << 4) | flam)
                    main[bar][track] |= 1 << j
            if not repeat:
                steps.extend(DEFAULT_STEP * 48)
                timing.extend(bytes((7 << 4,)) * 48)
            payload.extend(steps)
            payload.extend(timing)
        for track in range(TRACKS):
            for bar in range(4):
                payload.extend(struct.pack("<H", main[bar][track]))
        payload.append(shuffle & 127)
        payload.extend(track_lengths)
        payload.append(kit_slot)
        payload.extend(b"SCL2" + bytes((16, 16 ^ 0xA5)))
        payload.extend(b"FLP1" + bytes((100,)) * (TRACKS * LXR2_STEPS))
        payload.extend(b"CND2" + bytes((0,)) * (1 + TRACKS * LXR2_STEPS))
        header = f"{name[:6]}{pat + 1:02d}"[:8].ljust(8).encode("ascii", errors="replace")
        image = header + b"PatV03" + payload
        if len(image) != 4574:
            raise AssertionError(f"unexpected LXR2 PAT size: {len(image)}")
        outputs.append(image)
    return outputs, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="LXR1 .pat/.all/.prf")
    parser.add_argument("output", type=Path, help="new, empty staging directory")
    parser.add_argument("--start-slot", type=int, default=0, help="LXR2 slot 0..56; eight consecutive slots")
    parser.add_argument("--repeat", action="store_true", help="repeat the LXR1 bar through all four LXR2 bars")
    parser.add_argument("--kit-slot", type=int, help="LXR2 kit slot 0..63 (default: start-slot / 8)")
    parser.add_argument("--kit-source", type=Path, help="matching LXR1 .snd when source is .pat")
    parser.add_argument("--lxr1-source", type=Path, default=Path(__file__).resolve().parents[2] / "mutador",
                        help="LXR1 Mutador source tree for modulation target mapping")
    args = parser.parse_args()
    if not 0 <= args.start_slot <= 56:
        parser.error("start slot must be 0..56")
    kit_slot = args.kit_slot if args.kit_slot is not None else args.start_slot // 8
    if not 0 <= kit_slot <= 63:
        parser.error("kit slot must be 0..63")
    if args.output.exists():
        parser.error("output directory already exists; choose a fresh staging directory")
    source = args.source.read_bytes()
    suffix = args.source.suffix.lower()
    _, valid_ids, _ = parameter_maps(args.lxr1_source)
    images, warnings = convert(source, suffix, args.repeat, valid_ids, kit_slot)
    kit_data = None
    if args.kit_source is not None:
        kit_data, kit_notes = convert_kit(args.kit_source.read_bytes(), args.kit_source.suffix.lower(), args.lxr1_source)
        warnings.extend(kit_notes)
    elif suffix in (".all", ".prf"):
        kit_data, kit_notes = convert_kit(source, suffix, args.lxr1_source)
        warnings.extend(kit_notes)
    args.output.mkdir(parents=True)
    for index, image in enumerate(images):
        slot = args.start_slot + index
        (args.output / f"{slot:02d}-LXR1{index + 1}.pat").write_bytes(image)
    if kit_data is not None:
        (args.output / f"{kit_slot:02d}-LXR1.snd").write_bytes(kit_data)
    (args.output / "IMPORT_NOTES.txt").write_text(
        "Source: " + str(args.source) + "\n"
        "LXR2 patterns: " + str(args.start_slot) + ".." + str(args.start_slot + 7) + "\n"
        "Kit slot: " + str(kit_slot) + (" (converted)\n" if kit_data else " (supply matching kit separately)\n") +
        "Warnings:\n" + ("\n".join(warnings) if warnings else "none") + "\n",
        encoding="utf-8")
    print(f"Wrote eight PAT files to {args.output}; {len(warnings)} conversion notes")


if __name__ == "__main__":
    main()
