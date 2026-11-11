"""0.2.104 peak diagnosis (d builds): the CPU note says what made the highest
block of each 0.5 s window. Host harness runs the real recording code
(extracted from AudioCodecManager.c) and the real note formats from menu.c;
the source contract checks the measuring points. --mutate shows the checks
bite."""
from pathlib import Path
import re, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
VS = r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat'
FILES = {'h': 'Core/Inc/Soundengine/cpuDiag.h', 'acmh': 'Core/Inc/Soundengine/AudioCodecManager.h',
         'acm': 'Core/Src/Soundengine/AudioCodecManager.c', 'se': 'Core/Src/Soundengine/Soundengine.c',
         'mix': 'Core/Src/Soundengine/DSPAudio/mixer.c', 'mf': 'Core/Src/Soundengine/DSPAudio/PerformanceMasterFilter.c',
         'menu': 'Core/Src/menu/menu.c', 'main': 'Core/Src/main.c'}


def load():
    return {k: (ROOT / v).read_text(encoding='latin-1').replace('\r\n', '\n') for k, v in FILES.items()}


def body(src, sig):
    start = src.find(sig)
    if start < 0:
        return ''
    i = src.index('{', start)
    depth = 0
    while True:
        depth += (src[i] == '{') - (src[i] == '}')
        if depth == 0:
            return src[start:i + 1]
        i += 1


def contract(s):
    p = []
    req = body(s['acmh'], 'static inline void audioCodec_blockRequested(void)')
    if 'if(bCurrentSampleValid != SAMPLE_VALID) CPU_DIAG_FLAG(CPU_DIAG_LATE);' not in req or 'CPU_DIAG_REQUEST();' not in req:
        p.append('the DMA request does not mark late blocks and the main loop place')
    if 'volatile int8_t checkMainLoc = 0;' not in s['main']:
        p.append('checkMainLoc must be visible to the diagnosis')
    end = body(s['acm'], 'void audioCodec_endCpuMeter(void)')
    f, r = end.find('cycles = render;'), end.find('cpuDiag_record(cycles, render, now);')
    if r < 0 or r < f:
        p.append('endCpuMeter must record after the first-block fallback')
    for fn in ('void soundengine_serviceAudio(void)', 'void soundengine_process()'):
        b = re.sub(r'//[^\n]*', '', body(s['se'], fn))
        if b.count('seq_tick();') != b.count('CPU_DIAG_SEQ_BEGIN();') or b.count('seq_tick();') != b.count('CPU_DIAG_SEQ_END();'):
            p.append(f'{fn}: seq_tick is not timed')
        if len(re.findall(r'CPU_DIAG_SEQ_BEGIN\(\);\s*seq_tick\(\);\s*CPU_DIAG_SEQ_END\(\);', b)) != b.count('seq_tick();'):
            p.append(f'{fn}: the seq timer must wrap seq_tick directly')
    mix = body(s['mix'], 'IN_ITCM_RAM void mixer_calcNextSampleBlock(')
    ms, fx, hat = mix.find('CPU_DIAG_MASTER_START();'), mix.find('FxBus_process('), mix.rfind('mixer_mixVoiceBlock(5,')
    if not (0 <= hat < ms < fx):
        p.append('the master stage mark must sit between the last voice and the FX bus')
    proc = body(s['mf'], 'void masterFilter_process(')
    st, fl = proc.find('masterFilter_steadyBlock('), proc.find('CPU_DIAG_FLAG(CPU_DIAG_FILTER);')
    if not (0 <= st < fl):
        p.append('the filter flag must mark only the fade/glide path')
    rep = body(s['menu'], 'void menu_processRepaint(void)')
    if rep.find('CPU_DIAG_FLAG(CPU_DIAG_REPAINT);') < rep.find('if(!menu_repaintPending) return;'):
        p.append('the repaint flag must be set only when a repaint runs')
    cpu = body(s['menu'], 'void menu_updateCpuUse(void)')
    if '(isLate || d.total >= 95) && (uint32_t)(systick_ticks - peakShown) >= MENU_CPU_NOTE_TICKS' not in cpu:
        p.append('the note must show late blocks and peaks from 95, one note per 6 s')
    if 'audioCodec_takePeakDiag(&d)' not in cpu:
        p.append('the window peak is not taken')
    if '#define MENU_CPU_NOTE_TICKS 24000u' not in cpu or 'menu_showNoteFor(line1, line2, MENU_CPU_NOTE_TICKS);' not in cpu:
        p.append('the diagnosis note must stay 6 s (readable)')
    h = s['h']
    if '#else' not in h or '#define CPU_DIAG_FLAG(f)\t\t\t((void)0)' not in h:
        p.append('the diagnosis must vanish in normal builds')
    return p


HARNESS = r'''
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#define LXR_FREEZE_DIAG 1
static void __disable_irq(void){}
static void __enable_irq(void){}
#define CPU_DIAG_STEP 0x01u
#define CPU_DIAG_REPAINT 0x02u
#define CPU_DIAG_FILTER 0x04u
#define CPU_DIAG_LATE 0x08u
typedef struct { uint8_t total, wait, seq, render, voices, master; int8_t loc; uint8_t flags; } CpuPeakDiag;
static uint32_t cpuBlockBudget = 1000;
volatile int8_t checkMainLoc;
@DECLS@
@FUNCS@
static int fails, checks;
#define CHECK(c,msg) do{checks++; if(!(c)){fails++; printf("FAIL %s\n",msg);}}while(0)
/* one block: request at 0, seq inside the wait, render, master part of it */
static void block(uint32_t wait, uint32_t seq, uint32_t render, uint32_t master, uint8_t flags, int8_t loc)
{
	cpuDiag_flags |= flags; cpuDiag_seqCycles += seq; cpuDiag_locAtRequest = loc;
	const uint32_t now = 100000u + wait + render;
	cpuDiag_masterStart = now - master;
	cpuDiag_record(wait + render, render, now);
}
int main(void)
{
	CpuPeakDiag d;
	block(100, 50, 700, 200, CPU_DIAG_STEP, -12);
	block(150, 80, 800, 300, CPU_DIAG_REPAINT, -10);
	block(50, 0, 600, 100, 0, -9);
	CHECK(audioCodec_takePeakDiag(&d), "window has a block");
	CHECK(d.total == 95, "peak is the highest block");
	CHECK(d.seq == 8 && d.wait == 7 && d.render == 80, "wait/seq/render of the peak");
	CHECK(d.voices == 50 && d.master == 30, "voices/master split");
	CHECK(d.wait + d.seq + d.render == d.total, "parts add up");
	CHECK(d.loc == -10 && d.flags == CPU_DIAG_REPAINT, "place and flags of the peak block only");
	CHECK(!audioCodec_takePeakDiag(&d), "taking starts an empty window");
	block(20, 0, 500, 100, CPU_DIAG_LATE, -7);
	block(200, 0, 790, 100, 0, -11);
	audioCodec_takePeakDiag(&d);
	CHECK(d.flags & CPU_DIAG_LATE, "a late block wins over a higher one");
	CHECK(d.total == 52, "the late block's own numbers");
	block(10, 500, 400, 50, 0, -8);
	audioCodec_takePeakDiag(&d);
	CHECK(d.seq == 1 && d.wait == 0, "seq before the request is not counted");
	block(10, 0, 400, 900, 0, -8);
	audioCodec_takePeakDiag(&d);
	CHECK(d.master == 40 && d.voices == 0, "master never larger than render");
	block(5000, 0, 400, 50, 0, -8);
	audioCodec_takePeakDiag(&d);
	CHECK(d.total == 255, "no wrap above 255 %");
	/* the note lines must fit 16 characters with the worst values */
	char line1[17], line2[17];
	unsigned late = 999; d.wait = d.seq = d.render = 99; d.voices = d.master = 99; d.loc = -128;
	CHECK(snprintf(line1, sizeof(line1), @F1@, late, 99u, 99u, 99u) <= 16, "late line fits");
	CHECK(snprintf(line1, sizeof(line1), @F2@, 99u, 99u, 99u, 99u) <= 16, "peak line fits");
	CHECK(snprintf(line2, sizeof(line2), @F3@, 99u, 99u, (int)(d.loc < -99 ? -99 : d.loc), 'S', 'R', 'F') <= 16, "second line fits");
	printf("%s %d assertions\n", fails ? "CPU PEAK DIAG FAIL" : "CPU PEAK DIAG PASS", checks);
	return fails != 0;
}
'''


def harness(s):
    acm = s['acm']
    a = acm.index('#if LXR_FREEZE_DIAG\nvolatile uint8_t cpuDiag_flags;')
    b = acm.index('#endif', a)
    block = acm[a + len('#if LXR_FREEZE_DIAG\n'):b]
    decls = block[:block.index('static uint8_t cpuDiag_percent(')]
    funcs = block[len(decls):]
    cpu = body(s['menu'], 'void menu_updateCpuUse(void)')
    fmts = re.findall(r'snprintf\(line[12], sizeof\(line[12]\), ("[^"]*")', cpu)
    if len(fmts) != 3:
        return ['note formats not found']
    c = HARNESS.replace('@DECLS@', decls).replace('@FUNCS@', funcs)
    c = c.replace('@F1@', fmts[0]).replace('@F2@', fmts[1]).replace('@F3@', fmts[2])
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        (Path(folder) / 'h.c').write_text(c, encoding='utf-8')
        r = subprocess.run(f'call "{VS}" -arch=x64 >nul && cl /nologo /W3 /TC h.c >nul && h.exe',
                           shell=True, cwd=folder, capture_output=True, text=True, errors='replace')
        out = r.stdout.strip()
        if r.returncode != 0 or 'PASS' not in out:
            return ['harness: ' + (out or r.stderr.strip())[-400:]]
        return [], out


def run(s):
    p = contract(s)
    h = harness(s)
    if isinstance(h, tuple):
        return p, h[1]
    return p + h, ''


MUTATIONS = {
    'no-late-flag': ('acmh', '\tif(bCurrentSampleValid != SAMPLE_VALID) CPU_DIAG_FLAG(CPU_DIAG_LATE);\t// 0.2.104\n', ''),
    'record-before-fallback': ('acm', '\tif(cycles < render || cycles > cpuBlockBudget * 4u) cycles = render; // first block, interrupt mode\n#if LXR_FREEZE_DIAG\n\tcpuDiag_record(cycles, render, now);\n#endif\n',
                               '#if LXR_FREEZE_DIAG\n\tcpuDiag_record(cycles, render, now);\n#endif\n\tif(cycles < render || cycles > cpuBlockBudget * 4u) cycles = render; // first block, interrupt mode\n'),
    'late-not-first': ('acm', "((flags & CPU_DIAG_LATE) ? 256u : 0u)", "0u"),
    'flags-kept': ('acm', '\tcpuDiag_flags = 0;\n\tcpuDiag_seqCycles = 0;\n', '\tcpuDiag_seqCycles = 0;\n'),
    'seq-unclamped': ('acm', '\tif(seq > wait) seq = wait;', '\t'),
    'wait-includes-seq': ('acm', 'cpuDiag_percent(wait - seq)', 'cpuDiag_percent(wait)'),
    'take-no-reset': ('acm', '\tcpuDiag_peakKey = 0;\n\t__enable_irq();', '\t__enable_irq();'),
    'percent-wraps': ('acm', 'return (uint8_t)(p > 255u ? 255u : p);', 'return (uint8_t)p;'),
    'seq-untimed': ('se', '\t{ CPU_DIAG_SEQ_BEGIN(); // 0.2.104 peak diagnosis (d builds)\n\tseq_tick();\n\tCPU_DIAG_SEQ_END(); }\n\t__HAL_TIM_SetCounter(&htim2, 1950);\n\t__HAL_TIM_ENABLE_IT',
                    '\tseq_tick();\n\t__HAL_TIM_SetCounter(&htim2, 1950);\n\t__HAL_TIM_ENABLE_IT'),
    'master-mark-late': ('mix', '\tCPU_DIAG_MASTER_START();\t// 0.2.104 voices done, master stage starts\n\tFxBus_process(', '\tFxBus_process('),
    'filter-flag-steady': ('mf', '\tCPU_DIAG_FLAG(CPU_DIAG_FILTER);\t// 0.2.104 the fade/glide loop (flash)\n', ''),
    'repaint-flag-always': ('menu', '\tif(!menu_repaintPending) return;\n\tmenu_repaintPending = 0;\n\tCPU_DIAG_FLAG(CPU_DIAG_REPAINT);',
                            '\tCPU_DIAG_FLAG(CPU_DIAG_REPAINT);\n\tif(!menu_repaintPending) return;\n\tmenu_repaintPending = 0;'),
    'peak-note-spam': ('menu', '(isLate || d.total >= 95) && (uint32_t)(systick_ticks - peakShown) >= MENU_CPU_NOTE_TICKS', '(isLate || d.total >= 95)'),
    'note-short': ('menu', '		menu_showNoteFor(line1, line2, MENU_CPU_NOTE_TICKS);', '		menu_showNote(line1, line2);'),
    'threshold-low': ('menu', '(isLate || d.total >= 95)', '(isLate || d.total >= 93)'),
    'line-too-long': ('menu', '"Sp%2u W%2u S%2u R%2u"', '"Spitze%2u W%2u S%2u R%2u"'),
}

src = load()
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        m = dict(src)
        assert m[key].count(old) == 1, name
        m[key] = m[key].replace(old, new)
        hit = bool(run(m)[0])
        caught += hit
        print(name, 'caught' if hit else 'MISSED')
    print(f'{caught}/{len(MUTATIONS)} mutations caught')
    sys.exit(0 if caught == len(MUTATIONS) else 1)

found, out = run(src)
for f in found:
    print('FAIL', f)
if found:
    sys.exit(1)
print(out)
