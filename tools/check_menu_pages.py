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
    # 0.2.54: fil follows spd on the first PERF page, the Shuffle page keeps sh..sh4
    perf = re.search(r'TEXT_BPM,\s+TEXT_ROLL_SPEED[^\n]*\n\s*([^\n]*)', source)
    assert perf.group(0).split(',')[7].strip() == 'TEXT_PERF_FILL', perf.group(0)
    assert perf.group(1).split(',')[7].strip() == 'PAR_PERF_FILL', perf.group(1)
    assert source.count('TEXT_PERF_FILL') == 1 and source.count('PAR_PERF_FILL') == 1
    shuffle = re.search(r'TEXT_SHUFFLE,TEXT_GROOVE_SH2,TEXT_GROOVE_SH3,TEXT_GROOVE_SH4,([^\n]*)', source)
    assert shuffle and 'FILL' not in shuffle.group(1)
    checks += 1
    menu = (ROOT / 'Core/Src/menu/menu.c').read_text(encoding='utf-8')
    assert 'perf_formatVelocityGain(&editDisplayBuffer[1][i?4*i-1:0],curParmVal);' in menu
    assert 'if(parNr==PAR_SCALE_TRANSFORM) {' in menu
    print(f'MENU PAGES PASS {checks} pages')


if __name__ == '__main__':
    main()
