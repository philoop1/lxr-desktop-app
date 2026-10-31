"""Set project MIDI channels on a mounted desktop LXR SD card.

Defaults to a read-only plan. --apply first backs up every globals file under
build/card-midi-backups/. The project whose PRJ.NFO name is Chan is excluded.
Does not alter firmware, kits, patterns, sample data or the repository SD backup.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


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

    # Stored globals begin at PAR_BPM; derive offsets from the current enum.
    header = (ROOT / 'Core/Inc/Parameters.h').read_text()
    header = re.sub(r'/\*.*?\*/|//[^\n]*', '', header, flags=re.S)
    body = header.split('PAR_BPM = PAR_BEGINNING_OF_GLOBALS,', 1)[1]
    names = ['PAR_BPM'] + [x.strip() for x in body.split(',')]
    offsets = {n: i for i, n in enumerate(names) if re.fullmatch(r'PAR_\w+', n)}
    legacy_length = offsets['PAR_MIDI_CHAN_PC']
    stored_length = offsets['PAR_CPU_USE']
    assert legacy_length == 30 and stored_length == 64
    settings = {f'PAR_MIDI_CHAN_{v}': v for v in range(1, 7)}
    settings.update(PAR_MIDI_CHAN_7=6, PAR_MIDI_CHAN_GLOBAL=7, PAR_MIDI_CHAN_PC=16)
    projects = sorted(p for p in card.iterdir() if p.is_dir() and re.fullmatch(r'PROJ\d{2}', p.name))
    paths = [(card / 'GLO.CFG', '(root)', False)]
    for project in projects:
        name = (project / 'PRJ.NFO').read_bytes().decode('ascii').strip(' \x00')
        paths.append((project / 'GLO.CFG', name, name.casefold() == 'chan'))
    if sum(skip for _, _, skip in paths) != 1:
        raise RuntimeError('Expected exactly one project named Chan; refusing ambiguous plan')

    plan = []
    for path, name, skip in paths:
        before = path.read_bytes()
        if not legacy_length <= len(before) <= stored_length:
            raise RuntimeError(f'Unknown globals size: {path}: {len(before)}')
        after = bytearray(before)
        if not skip:
            defaults = [2, 1, 0, 1, 63, 12, 63, 0, 0, 100, 100, 100, 0, 6, 0, 63, 5, 0, 64, 64, 127, 63, 63, 63, 63, 63, 63, 63, 63, 63, 63, 0, 0, 0]  # Pch/load/pitch/step/delay/accent/groove/filter/scale/FX controls.
            after.extend(defaults[len(before)-legacy_length:])
            for key, value in settings.items():
                after[offsets[key]] = value
            allowed = {offsets[key] for key in settings}
            assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(before, after)))
        after = bytes(after)
        plan.append((path, name, skip, before, after))
        channels = [after[offsets[f'PAR_MIDI_CHAN_{v}']] for v in range(1, 8)]
        pch = after[offsets['PAR_MIDI_CHAN_PC']] if len(after) > legacy_length else '(default 2)'
        print(f'{path.relative_to(card)} [{name}]: {"KEEP" if skip else "SET"} '
              f'Global={after[offsets["PAR_MIDI_CHAN_GLOBAL"]]} Voices={channels} Pch={pch}')
    if not args.apply:
        print('Read-only plan; use --apply to back up and write.')
        return

    backup = ROOT / 'build/card-midi-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, exist_ok=False)
    manifest = {'card': str(card), 'settings': settings, 'files': []}
    for path, name, skip, before, after in plan:
        relative = path.relative_to(card)
        dest = backup / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(before)
        assert dest.read_bytes() == before
        manifest['files'].append({'path': str(relative), 'project': name, 'skipped': skip,
                                  'before': digest(before), 'after': digest(after)})
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    written = []
    try:
        for path, _, skip, before, after in plan:
            if path.read_bytes() != before:
                raise RuntimeError(f'File changed since planning: {path}')
            if not skip and before != after:
                written.append((path, before))
                path.write_bytes(after)
            if path.read_bytes() != after:
                raise RuntimeError(f'Readback differs: {path}')
    except Exception:
        for path, before in reversed(written):
            path.write_bytes(before)
        raise
    print(f'PASS: {len(written)} globals files updated and verified; Chan unchanged.')
    print(f'Backup: {backup}')


if __name__ == '__main__':
    main()
