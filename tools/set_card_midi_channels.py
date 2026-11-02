"""Set the MIDI channels in GLO.CFG on a mounted LXR SD card.

Voices 1-6 on channels 1-6, track 7 on channel 6 with the Hi-Hat, Global ch 7 and
Pch 16, in the root file and every project except the ones named with --skip.
Defaults to a read-only plan. --apply backs up every changed file under
build/card-midi-backups/ and restores them if a readback differs.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# GLO.CFG offsets; each byte holds the displayed channel number
CHANNELS = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 12: 6, 21: 7, 30: 16}
SMALLEST = max(CHANNELS) + 1


def project_name(folder):
    path = folder / 'PRJ.NFO'
    return path.read_bytes().decode('ascii', 'replace').strip(' \x00') if path.exists() else ''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('card', type=Path)
    parser.add_argument('--skip', action='append', default=[], help='project name to leave alone')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    card = args.card.resolve(strict=True)
    if not (card / 'PROJ.IDX').is_file():
        raise RuntimeError('Expected an LXR card with PROJ.IDX')

    changes = []
    for path in [card / 'GLO.CFG'] + sorted(card.glob('PROJ??/GLO.CFG')):
        name = project_name(path.parent) if path.parent != card else '(root)'
        label = f'{path.relative_to(card)} [{name}]'
        if name in args.skip:
            print(f'{label}: SKIP')
            continue
        before = path.read_bytes()
        if len(before) < SMALLEST:
            raise RuntimeError(f'{label}: only {len(before)} bytes')
        after = bytearray(before)
        for offset, value in CHANNELS.items():
            after[offset] = value
        after = bytes(after)
        moved = [offset for offset in CHANNELS if before[offset] != after[offset]]
        print(f'{label}: ' + (f'CHANGE bytes {moved}' if moved else 'already set'))
        if moved:
            changes.append((path, before, after))
    if not args.apply:
        print('Read-only plan; use --apply to back up and write.')
        return

    backup = ROOT / 'build/card-midi-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for number, (path, before, _) in enumerate(changes):
        (backup / f'{number:02d}.CFG').write_bytes(before)
        manifest[f'{number:02d}.CFG'] = str(path.relative_to(card))
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    written = []
    try:
        for path, before, after in changes:
            written.append((path, before))
            path.write_bytes(after)
            if path.read_bytes() != after:
                raise RuntimeError(f'Readback differs: {path}')
    except Exception:
        for path, before in reversed(written):
            path.write_bytes(before)
        raise
    print(f'PASS: {len(changes)} files changed and verified.')
    print(f'Backup: {backup}')


if __name__ == '__main__':
    main()
