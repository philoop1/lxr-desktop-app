"""Give the converted LXR1 projects PROJ21..28 MIDI sync on a mounted LXR SD card.

Each project gets GLO.CFG copied from the card root with bpm set to MID (1).
Defaults to a read-only plan. --apply records a manifest and the root file under
build/card-midi-backups/ and refuses to replace an existing project GLO.CFG.
Does not alter the root GLO.CFG, kits, patterns or any other project.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = {21: 'P000-007', 22: 'P008-015', 23: 'P016-023', 24: 'P024-031',
            25: 'P032-039', 26: 'P040-047', 27: 'P048-055', 28: 'P056-060'}
BPM_MIDI = 1  # bpm is the first stored global: 0 EXT, 1 MID, 2+ internal tempo


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('card', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    card = args.card.resolve(strict=True)
    if not (card / 'PROJ.IDX').is_file():
        raise RuntimeError('Expected an LXR card with PROJ.IDX')
    source = (card / 'GLO.CFG').read_bytes()
    if not 30 <= len(source) <= 64:
        raise RuntimeError(f'Unknown globals size: {len(source)}')
    after = bytes([BPM_MIDI]) + source[1:]

    paths = []
    for number, expected in PROJECTS.items():
        project = card / f'PROJ{number:02d}'
        name = (project / 'PRJ.NFO').read_bytes().decode('ascii').strip(' \x00')
        if name != expected:
            raise RuntimeError(f'{project.name} is named {name!r}, expected {expected!r}')
        path = project / 'GLO.CFG'
        if path.exists():
            raise RuntimeError(f'Refusing to replace {path}')
        paths.append(path)
        print(f'{path.relative_to(card)} [{name}]: CREATE {len(after)} bytes, bpm MID')
    print(f'Root GLO.CFG stays unchanged: bpm {source[0]}, SHA256 {digest(source)}')
    if not args.apply:
        print('Read-only plan; use --apply to back up and write.')
        return

    backup = ROOT / 'build/card-midi-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, exist_ok=False)
    (backup / 'GLO.CFG').write_bytes(source)
    manifest = {'card': str(card), 'root': digest(source), 'after': digest(after),
                'created': [str(path.relative_to(card)) for path in paths]}
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    written = []
    try:
        for path in paths:
            written.append(path)
            path.write_bytes(after)
            if path.read_bytes() != after:
                raise RuntimeError(f'Readback differs: {path}')
    except Exception:
        for path in reversed(written):
            path.unlink(missing_ok=True)
        raise
    print(f'PASS: {len(paths)} project globals created and verified.')
    print(f'Backup: {backup}')


if __name__ == '__main__':
    main()
