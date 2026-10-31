"""Scale active desktop LXR pattern velocities by 100/127, with a backed-up plan.

plan reads the card and writes original/staged copies under the repository.
apply accepts that plan, checks all hashes, writes only verified pattern files,
and can safely resume an interrupted application of the same plan.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def layout(relative, data):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe relative path: {relative}")
    if relative.parts[0] == "TMP" and relative.name.upper() == "TMP.PAT":
        if not data or data[0] >= 64:
            raise ValueError(f"Invalid TMP pattern slot: {relative}")
        header, version = 1, 3
    elif re.fullmatch(r"PROJ\d{2}", relative.parts[0]):
        if len(data) < 14 or data[8:14] not in (b"PatV02", b"PatV03"):
            raise ValueError(f"Unrecognized active pattern: {relative}")
        header, version = 14, int(chr(data[13]))
    else:
        raise ValueError(f"Outside active project/TMP scope: {relative}")
    stride = 64 * 7 + (64 if version == 3 else 0)
    end = header + 7 * stride + 7 * 4 * 2 + 1 + 7 + 1
    if len(data) not in (end, end + 6):
        raise ValueError(f"Unexpected length for {relative}: {len(data)}; expected {end}[+6]")
    if len(data) == end + 6:
        tail = data[end:]
        if tail[:4] != b"SCL2" or tail[4] not in (2, 4, 6, 8, 12, 16, 24, 32) or tail[5] != (tail[4] ^ 0xA5):
            raise ValueError(f"Invalid Scale trailer: {relative}")
    offsets = [header + track * stride + step * 7 for track in range(7) for step in range(64)]
    return version, header, offsets


def transform(relative, before):
    version, header, offsets = layout(relative, before)
    after = bytearray(before)
    for offset in offsets:
        after[offset] = (before[offset] & 0x80) | (((before[offset] & 0x7F) * 100 + 63) // 127)
    allowed = set(offsets)
    assert len(after) == len(before)
    assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(before, after)))
    assert all((before[i] & 0x80) == (after[i] & 0x80) for i in offsets)
    assert max(after[i] & 0x7F for i in offsets) <= 100
    return bytes(after), version, header, offsets


def plan(card, backup):
    card = card.resolve(strict=True)
    if not (card / "PROJ.IDX").is_file():
        raise ValueError("Expected mounted desktop LXR card with PROJ.IDX")
    backup.mkdir(parents=True, exist_ok=False)
    roots = sorted(p for p in card.iterdir() if p.is_dir() and re.fullmatch(r"PROJ\d{2}", p.name))
    if (card / "TMP").is_dir():
        roots.append(card / "TMP")
    files = sorted(p for root in roots for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".pat")
    if not files:
        raise ValueError("No active patterns found")
    entries = []
    before_hist, after_hist = Counter(), Counter()
    versions = Counter()
    changed_steps = 0
    for path in files:
        relative = path.relative_to(card)
        before = path.read_bytes()
        after, version, header, offsets = transform(relative, before)
        original = backup / "original" / relative
        staged = backup / "staged" / relative
        original.parent.mkdir(parents=True, exist_ok=True)
        staged.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(before)
        staged.write_bytes(after)
        if original.read_bytes() != before or staged.read_bytes() != after:
            raise OSError(f"Backup/staging verification failed: {relative}")
        changed = sum(before[i] != after[i] for i in offsets)
        changed_steps += changed
        before_hist.update(before[i] & 0x7F for i in offsets)
        after_hist.update(after[i] & 0x7F for i in offsets)
        versions[f"v{version}"] += 1
        entries.append({"path": str(relative), "bytes": len(before), "version": version,
                        "header": header, "slots": len(offsets), "changed_slots": changed,
                        "before": digest(before), "after": digest(after)})
    manifest = {"schema": 1, "card": str(card), "numerator": 100, "denominator": 127,
                "scope": "active PROJxx directories and TMP only",
                "project_index": digest((card / "PROJ.IDX").read_bytes()),
                "summary": {"files": len(entries), "changed_files": sum(e["before"] != e["after"] for e in entries),
                            "step_slots": sum(e["slots"] for e in entries), "changed_slots": changed_steps,
                            "formats": dict(versions), "before_histogram": dict(before_hist),
                            "after_histogram": dict(after_hist)},
                "files": entries}
    destination = backup / "plan.json"
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # Independent native-reader audit consumes these backed-up pairs before apply.
    with (backup / "audit.tsv").open("w", encoding="utf-8") as output:
        for entry in entries:
            output.write(f'{backup / "original" / entry["path"]}\t{backup / "staged" / entry["path"]}\t{entry["version"]}\t{entry["header"]}\n')
    print(json.dumps({k: v for k, v in manifest["summary"].items() if not k.endswith("histogram")}, indent=2))
    print(f"PLAN={destination}")


def apply(plan_path):
    plan_path = plan_path.resolve(strict=True)
    backup = plan_path.parent
    manifest = json.loads(plan_path.read_text(encoding="utf-8"))
    if manifest["schema"] != 1 or (manifest["numerator"], manifest["denominator"]) != (100, 127):
        raise ValueError("Unsupported plan")
    card = Path(manifest["card"]).resolve(strict=True)
    if digest((card / "PROJ.IDX").read_bytes()) != manifest["project_index"]:
        raise ValueError("Project index changed since planning")
    receipt = backup / "applied.json"
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        original = (backup / "original" / relative).read_bytes()
        staged = (backup / "staged" / relative).read_bytes()
        expected, _, _, _ = transform(relative, original)
        target = (card / relative).resolve(strict=True)
        if not target.is_relative_to(card):
            raise ValueError(f"Target outside card: {target}")
        if digest(original) != entry["before"] or digest(staged) != entry["after"] or staged != expected:
            raise ValueError(f"Backup/staging changed: {relative}")
        current = digest(target.read_bytes())
        if current not in (entry["before"], entry["after"]):
            raise ValueError(f"Card file changed since planning: {relative}")
        if receipt.exists() and current != entry["after"]:
            raise ValueError(f"Already-applied file changed: {relative}")
    written = []
    try:
        for entry in manifest["files"]:
            relative = Path(entry["path"])
            target = card / relative
            if digest(target.read_bytes()) == entry["after"]:
                continue
            written.append(relative)
            target.write_bytes((backup / "staged" / relative).read_bytes())
            if digest(target.read_bytes()) != entry["after"]:
                raise OSError(f"Readback failed: {relative}")
    except Exception:
        for relative in reversed(written):
            original = (backup / "original" / relative).read_bytes()
            (card / relative).write_bytes(original)
            if (card / relative).read_bytes() != original:
                raise OSError(f"Rollback failed: {relative}; backup at {backup}")
        raise
    receipt.write_text(json.dumps({"plan": str(plan_path), "written_this_run": len(written),
                                  "verified_files": len(manifest["files"]),
                                  "time_utc": datetime.now(timezone.utc).isoformat(),
                                  "summary": manifest["summary"]}, indent=2), encoding="utf-8")
    print(f'APPLIED_AND_VERIFIED files={len(manifest["files"])} written={len(written)} changed_slots={manifest["summary"]["changed_slots"]}')
    print(f"BACKUP={backup}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("plan")
    make.add_argument("card", type=Path)
    make.add_argument("backup", type=Path)
    write = commands.add_parser("apply")
    write.add_argument("plan", type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        plan(args.card, args.backup)
    else:
        apply(args.plan)
