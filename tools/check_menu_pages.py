"""Pages that lead to further subpages must not end in TEXT_EMPTY.

menu_moveToMenuItem stops the encoder at TEXT_EMPTY, so it would never step past
the last slot. TEXT_SKIP is the spacer that lets it through.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    source = (ROOT / 'Core/Inc/menu/menuPages.h').read_text(errors='replace')
    source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    checks = 0
    for first in ('TEXT_BPM,\\s+TEXT_MIDI_CHAN_GLOBAL', 'TEXT_BPM,\\s+TEXT_ROLL_SPEED'):
        match = re.search(first + r'[^\n]*', source)
        assert match, first
        slots = [slot.strip() for slot in match.group(0).split(',') if slot.strip()]
        assert len(slots) == 8, slots
        assert slots[7] != 'TEXT_EMPTY', slots
        checks += 1
    print(f'MENU PAGES PASS {checks} pages')


if __name__ == '__main__':
    main()
