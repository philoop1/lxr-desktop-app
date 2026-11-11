"""0.2.103 the screensaver writes the LCD directly while the menu interrupt
sends text nibble by nibble. Two writers at once lose a nibble and the
4-bit LCD stays out of sync (strange characters, page changes do not help).
Contract: nothing queues text under the screensaver, the interrupt starts no
new transfer, the screensaver only starts between transfers, the late-block
note waits for the wake. --mutate shows the checks bite."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = {'menu': 'Core/Src/menu/menu.c', 'ss': 'Core/Src/menu/screensaver.c'}


def load():
    return {k: (ROOT / v).read_text(encoding='latin-1').replace('\r\n', '\n') for k, v in FILES.items()}


def body(src, sig):
    start = src.index(sig)
    i = src.index('{', start)
    depth = 0
    while True:
        depth += (src[i] == '{') - (src[i] == '}')
        if depth == 0:
            return src[start:i + 1]
        i += 1


def contract(s):
    p = []
    rep = body(s['menu'], 'static void menu_repaintNow(void)\n{')  # 0.2.103 deferred: this body draws
    first = rep.find('if(screensaver_Active) return;')
    for q in ('menu_lockWarnActive', 'menu_noteActive', 'buttonHandler_lockMemoryFull', 'display_needs_refresh'):
        j = rep.find(q)
        if first < 0 or (j >= 0 and j < first):
            p.append(f'menu_repaint queues text ({q}) before the screensaver check')
            break
    tick = body(s['menu'], 'void menu_tick()\n{')
    g = tick.find('if(screensaver_Active && display_refresh_state == 0) return;')
    if g < 0 or g > tick.find('if(display_needs_clear_all') or g > tick.find('sendDisplayBuffer();'):
        p.append('the menu interrupt can start a transfer under the screensaver')
    chk = body(s['ss'], 'void screensaver_check()')
    a, b, c = chk.find('__disable_irq();'), chk.find('if(display_refresh_state == 0)'), chk.find('screensaver_Active = 1;')
    if not (0 <= a < b < c) or chk.find('__enable_irq();') < c:
        p.append('the screensaver can start in the middle of a display transfer')
    cpu = body(s['menu'], 'void menu_updateCpuUse(void)')
    if 'if(any && !screensaver_Active &&' not in cpu:  # 0.2.104 the peak note carries late blocks
        p.append('the late-block note does not wait for the screensaver to end')
    return p


MUTATIONS = {
    'repaint-late-check': ('menu', '\tif(screensaver_Active) return;\n    if(menu_lockWarnActive) {', '    if(menu_lockWarnActive) {'),
    'tick-no-guard': ('menu', '\tif(screensaver_Active && display_refresh_state == 0) return;\n', ''),
    'start-anytime': ('ss', '\t\t\t\tif(display_refresh_state == 0)\n', '\t\t\t\tif(1)\n'),
    'start-no-irq-lock': ('ss', '\t\t\t\t__disable_irq();\n', ''),
    'note-under-saver': ('menu', 'if(any && !screensaver_Active &&', 'if(any &&'),
}

src = load()
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        m = dict(src)
        assert m[key].count(old) == 1, name
        m[key] = m[key].replace(old, new)
        hit = bool(contract(m))
        caught += hit
        print(name, 'caught' if hit else 'MISSED')
    print(f'{caught}/{len(MUTATIONS)} mutations caught')
    sys.exit(0 if caught == len(MUTATIONS) else 1)

found = contract(src)
for f in found:
    print('FAIL', f)
if found:
    sys.exit(1)
print('DISPLAY SCREENSAVER PASS')
