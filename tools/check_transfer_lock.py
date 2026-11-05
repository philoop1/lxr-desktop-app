"""Project transfer needs FatFs to allow two open files at once.

preset_copyItem() (presetManager.c) keeps the source file open while it
creates and writes the temporary target file. With _FS_LOCK 1, FatFs has one
lock entry, so creating the target returned FR_TOO_MANY_OPEN_FILES (18) and
every Kit, Pattern, P+K and LXR1 transfer showed "Copy failed".
The check counts the files preset_copyItem() holds open together and compares
that with _FS_LOCK in ffconf.h. It also checks that the transfer result screen
shows the FatFs code for unnamed errors, and that only a Kit transfer may run
while the sequencer plays (Patterns, P+K and LXR1 blocks may hit the running
or next pattern).
--mutate sets _FS_LOCK back to 1 and lets every transfer run while playing;
the check must then fail.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = failures = 0


def check(ok, name):
    global checks, failures
    checks += 1
    if not ok:
        failures += 1
        print('FAIL', name)


def function_body(source, name):
    start = source.index(name + '(')
    brace = source.index('{', start)
    depth = 0
    for i in range(brace, len(source)):
        depth += {'{': 1, '}': -1}.get(source[i], 0)
        if not depth:
            return source[brace:i + 1]
    raise AssertionError('no end of ' + name)


def max_open(body):
    """Largest number of FIL objects open at the same time, in source order.
    A close directly followed by return belongs to an error exit and is skipped."""
    body = re.sub(r'\bf_close\s*\(\s*&\w+\s*\)\s*;\s*return\b', 'return', body)
    open_files, most = set(), 0
    for match in re.finditer(r'\bf_(open|close)\s*\(\s*&(\w+)', body):
        if match.group(1) == 'open':
            open_files.add(match.group(2))
        else:
            open_files.discard(match.group(2))
        most = max(most, len(open_files))
    return most


def main():
    ffconf = (ROOT / 'FATFS/Target/ffconf.h').read_text(encoding='utf-8', errors='replace')
    if '--mutate' in sys.argv:
        ffconf, count = re.subn(r'(#define _FS_LOCK\s+)\d+', r'\g<1>1', ffconf)
        assert count == 1, 'mutation anchor'
    lock = int(re.search(r'#define _FS_LOCK\s+(\d+)', ffconf).group(1))
    preset = (ROOT / 'Core/Src/Preset/presetManager.c').read_text(encoding='utf-8', errors='replace')
    copy = function_body(preset, 'static FRESULT preset_copyItem')
    needed = max_open(copy)
    check(needed == 2, 'preset_copyItem holds source and temporary target open together')
    check(lock >= needed, f'_FS_LOCK {lock} allows the {needed} files a transfer copy opens')
    check(max_open('f_open(&a f_open(&b f_close(&a f_close(&b') == 2, 'the open-file counter counts overlap')
    check(max_open('f_open(&a f_close(&a f_open(&b f_close(&b') == 1, 'the open-file counter counts sequence')
    check(max_open('f_open(&a if(x){f_close(&a);return r;} f_open(&b') == 2, 'an error exit does not close the file')
    menu = (ROOT / 'Core/Src/menu/menu.c').read_text(encoding='utf-8', errors='replace')
    guard = 'if(seq_isRunning() && menu_transfer.pattern!=0)menu_transfer.result=FR_LOCKED;'
    if '--mutate' in sys.argv:
        assert menu.count(guard) == 1, 'mutation anchor'
        menu = menu.replace(guard, 'if(seq_isRunning())menu_transfer.result=FR_LOCKED;')
    transfer = function_body(menu, 'static void menu_handleTransferSd')  # 0.2.62: inside the SD window
    locks = re.findall(r'if\(seq_isRunning\(\)([^)]*)\)menu_transfer\.result=FR_LOCKED;', transfer)
    check(locks == [' && menu_transfer.pattern!=0'], 'only a Kit transfer (type 0) runs while the sequencer plays')
    check('"Copy failed %u",(unsigned)menu_transfer.result' in menu, 'Copy failed shows the FatFs code')
    check(len('Copy failed 255') <= 16, 'the longest code still fits the 16-character line')
    print(f"{'TRANSFER LOCK FAIL' if failures else 'TRANSFER LOCK PASS'} {checks} assertions")
    sys.exit(failures != 0)


if __name__ == '__main__':
    main()
