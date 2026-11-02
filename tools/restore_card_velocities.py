"""Restore pre-migration step velocities while retaining later pattern trailers.

Requires the original/staged SHA-256 manifest from the 100/127 card migration.
Only files matching the staged bytes (optionally plus a validated scale trailer)
are eligible. The changed TMP.PAT is intentionally left untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scale_card_velocities import layout


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card", type=Path)
    parser.add_argument("migration_backup", type=Path)
    parser.add_argument("restore_backup", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    card = args.card.resolve(strict=True)
    source = args.migration_backup.resolve(strict=True)
    target_backup = args.restore_backup.resolve()
    if not (card / "PROJ.IDX").is_file():
        raise ValueError("Not the expected LXR card")
    if target_backup.exists():
        raise FileExistsError(f"Restore backup already exists: {target_backup}")
    manifest = json.loads((source / "plan.json").read_text(encoding="utf-8"))
    if sha((card / "PROJ.IDX").read_bytes()) != manifest["project_index"]:
        raise ValueError("Project index differs from migration plan")
    changes = []
    skipped = []
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        path = (card / relative).resolve(strict=True)
        if not path.is_relative_to(card):
            raise ValueError(f"Outside card: {path}")
        original = (source / "original" / relative).read_bytes()
        staged = (source / "staged" / relative).read_bytes()
        if sha(original) != entry["before"] or sha(staged) != entry["after"]:
            raise ValueError(f"Migration backup changed: {relative}")
        current = path.read_bytes()
        if relative.as_posix().upper() == "TMP/TMP.PAT" and current != staged:
            skipped.append(str(relative))
            continue
        if not current.startswith(staged):
            raise ValueError(f"Pattern changed since migration: {relative}")
        if len(current) != len(staged):
            layout(relative, current)  # validates the later scale trailer
        _, _, offsets = layout(relative, staged)
        after = bytearray(current)
        for offset in offsets:
            if current[offset] != staged[offset]:
                raise ValueError(f"Velocity changed since migration: {relative}")
            after[offset] = original[offset]
        if bytes(after) != current:
            changes.append((relative, current, bytes(after)))
    print(f"verified={len(manifest['files'])} restore={len(changes)} skipped={skipped}")
    if not args.apply:
        return
    target_backup.mkdir(parents=True)
    for relative, before, _ in changes:
        dest = target_backup / "card-before" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(before)
        if dest.read_bytes() != before:
            raise OSError(f"Backup verification failed: {relative}")
    written = []
    try:
        for relative, before, after in changes:
            path = card / relative
            if path.read_bytes() != before:
                raise ValueError(f"Card changed during restore: {relative}")
            written.append((path, before))
            path.write_bytes(after)
            if path.read_bytes() != after:
                raise OSError(f"Readback failed: {relative}")
    except Exception:
        for path, before in reversed(written):
            path.write_bytes(before)
            if path.read_bytes() != before:
                raise OSError(f"Rollback failed: {path}; backup is {target_backup}")
        raise
    (target_backup / "receipt.json").write_text(json.dumps({
        "source_plan": str(source / "plan.json"),
        "restored_files": len(changes),
        "skipped": skipped,
        "files": [{"path": str(relative), "before": sha(before), "after": sha(after)}
                  for relative, before, after in changes],
    }, indent=2), encoding="utf-8")
    print(f"RESTORED_AND_VERIFIED={len(changes)} BACKUP={target_backup}")


if __name__ == "__main__":
    main()
