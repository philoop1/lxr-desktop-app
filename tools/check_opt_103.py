"""0.2.103 CPU work: drive 0 skips the distortion division, calcOnePole is an
inline float, control-rate setters leave ITCM for the steady master filter
loop, and menu_repaint only marks the page (drawn after the audio block).
Source contract plus a numeric test of the drive-0 skip; --mutate shows the
checks bite."""
from pathlib import Path
import re, sys

ROOT = Path(__file__).resolve().parents[1]
D = 'Core/Src/Soundengine/DSPAudio/'
FILES = {'dist': D + 'distortion.c', 'oph': 'Core/Inc/Soundengine/DSPAudio/1PoleLp.h',
         'opc': D + '1PoleLp.c', 'mf': D + 'PerformanceMasterFilter.c',
         'menu': 'Core/Src/menu/menu.c', 'menuh': 'Core/Inc/menu/menu.h', 'main': 'Core/Src/main.c',
         'decay': D + 'Decay.c', 'drum': D + 'DrumVoice.c', 'fxdist': D + 'FX/Distortion.c',
         'svf': D + 'ResonantFilter.c', 'slope': D + 'SlopeEg2.c', 'trans': D + 'transientGenerator.c',
         'param': 'Core/Src/Soundengine/MIDI/ParameterArray.c', 'seq': 'Core/Src/Soundengine/Sequencer/sequencer.c'}
OUT_OF_ITCM = {'decay': ['DecayEg_setSlope'], 'drum': ['setPan'],
               'fxdist': ['Distortion_setDrive', 'Distortion_setParam1', 'Distortion_setParam2', 'Distortion_setParam3'],
               'svf': ['SVF_setReso', 'SVF_setDrive'],
               'slope': ['slopeEg2_setAttack', 'slopeEg2_setDecay', 'slopeEg2_setSlope'],
               'trans': ['transient_setWaveform'], 'param': ['paramArray_setParameter'], 'seq': ['seq_nextStep']}


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


def shape_of(knob):
    """setDistortionShape with the MIDI value knob/127"""
    s = knob / 127.0 - 0.0078125
    return 2 * s / (1 - s)


def numeric(p):
    # only knob 0 gives a negative shape: the skip hits exactly that position
    neg = [k for k in range(128) if shape_of(k) < 0]
    if neg != [0]:
        p.append(f'negative drive shape at knobs {neg}, the skip would cut real drive')
    # what knob 0 did before: a near-linear curve, at most ~0.14 dB from passthrough
    s = shape_of(0)
    worst = 0.0
    for n in range(1, 32768, 7):
        x = n / 32767.0
        y = (1 + s) * x / (1 + s * abs(x))
        worst = max(worst, abs(y / x - 1))
    if worst > 0.017:
        p.append(f'drive 0 changed the level by {worst:.4f}: skipping it is audible')


def contract(s):
    p = []
    cd = body(s['dist'], 'IN_ITCM_RAM void calcDistBlock(')
    g = cd.find('if(dist->shape < 0.f) return;')
    if g < 0 or g > cd.find('for(i=0;i<size;i++)'):
        p.append('calcDistBlock: drive 0 does not pass the block before the loop')
    cf = body(s['dist'], 'void calcDistBlockFiltered(')
    sm, sk, dv = cf.find('calcOnePole( &dist->DriveParamFilter'), cf.find('if(shape < 0.f) continue;'), cf.find('float x = buf[i]/32767.f;')
    if not (0 <= sm < sk < dv):
        p.append('calcDistBlockFiltered: the skip must come after the drive smoothing and before the division')
    h = s['oph']
    if not re.search(r'typedef struct OnePoleStruct\s*\{\s*float r;\s*float b;\s*\} OnePoleFilter;', h):
        p.append('OnePoleFilter state is not float')
    if 'static inline float calcOnePole(OnePoleFilter* filter, float input)' not in h or \
            'filter->b = fmaf(filter->r, input - filter->b, filter->b);' not in h:
        p.append('calcOnePole is not the inline float one-pole')
    if re.search(r'float calcOnePole\(', s['opc']):
        p.append('1PoleLp.c still defines calcOnePole (a call per sample)')
    for k, names in OUT_OF_ITCM.items():
        for n in names:
            if re.search(r'^\s*IN_ITCM_RAM[^\n]*\b' + n + r'\(', s[k], re.M):
                p.append(f'{n} still takes ITCM (control rate)')
    mf = s['mf']
    if not re.search(r'IN_ITCM_RAM static __attribute__\(\(noinline\)\) void masterFilter_steadyBlock\(', mf):
        p.append('the steady master filter loop is not in ITCM')
    proc = body(mf, 'void masterFilter_process(')
    if 'masterFilter_steadyBlock(output, frames, mixer_masterFilterMode == FILTER_HP);\n\t\treturn;' not in proc:
        p.append('masterFilter_process does not hand the steady state to the ITCM loop')
    steady = body(mf, 'IN_ITCM_RAM static __attribute__((noinline)) void masterFilter_steadyBlock(')
    if 'if(hp)' not in steady or '(xL - lowL)' not in steady or '(lowL * FILTER_GAIN)' not in steady:
        p.append('the ITCM master filter loop lost its HP or LP branch')
    rep = body(s['menu'], 'void menu_repaint()\n{')
    if rep.replace(' ', '').replace('\t', '').replace('\n', '') != 'voidmenu_repaint(){menu_repaintPending=1;}':
        p.append('menu_repaint draws at once again (it must only mark the page)')
    pr = body(s['menu'], 'void menu_processRepaint(void)')
    a, b, c = pr.find('if(!menu_repaintPending) return;'), pr.find('menu_repaintPending = 0;'), pr.find('menu_repaintNow();')
    if not (0 <= a < b < c):
        p.append('menu_processRepaint must clear the mark before drawing (a repaint asked meanwhile is kept)')
    tick = body(s['menu'], 'void menu_tick()\n{')
    clr = tick[tick.find('if(display_needs_clear_all'):]
    if 'menu_repaintNow();' not in clr[:clr.find('sendDisplayBuffer();')]:
        p.append('the clear-all path must draw at once (buffers were just cleared)')
    if 'void menu_processRepaint(void);' not in s['menuh']:
        p.append('menu_processRepaint not declared')
    m = s['main']
    e = m.find('menu_parseEncoder(encode_read4(),encode_readButton());')
    sa = m.find('soundengine_serviceAudio();', e)
    r = m.find('menu_processRepaint();', e)
    if e < 0 or not (sa < r < e + 250):
        p.append('main loop: the repaint is not drawn right after the audio block that follows the encoder')
    return p


MUTATIONS = {
    'dist-no-skip': ('dist', '\tif(dist->shape < 0.f) return;\n', ''),
    'dist-skip-wrong-sign': ('dist', 'if(dist->shape < 0.f) return;', 'if(dist->shape <= 0.1f) return;'),
    'filtered-skip-before-smooth': ('dist', '\t\t\tif(shape < 0.f) continue;\t// 0.2.103 drive knob at 0, see calcDistBlock\n', ''),
    'onepole-double': ('oph', '\tfloat r;\n\tfloat b;\n} OnePoleFilter;', '\tdouble r;\n\tdouble b;\n} OnePoleFilter;'),
    'onepole-call': ('oph', 'static inline float calcOnePole(OnePoleFilter* filter, float input)', 'static inline float calcOnePole(OnePoleFilter* filter, double input)'),
    'setter-back-in-itcm': ('svf', '/*IN_ITCM_RAM 0.2.103 control rate, flash*/ void SVF_setReso(', 'IN_ITCM_RAM void SVF_setReso('),
    'nextstep-back-in-itcm': ('seq', '/*IN_ITCM_RAM 0.2.103 control rate, flash*/ void seq_nextStep(', 'IN_ITCM_RAM void seq_nextStep('),
    'mf-steady-flash': ('mf', 'IN_ITCM_RAM static __attribute__((noinline)) void masterFilter_steadyBlock(', 'static __attribute__((noinline)) void masterFilter_steadyBlock('),
    'mf-steady-unused': ('mf', '\t\tmasterFilter_steadyBlock(output, frames, mixer_masterFilterMode == FILTER_HP);\n\t\treturn;\n', '\t\treturn;\n'),
    'repaint-immediate': ('menu', 'void menu_repaint()\n{\n\tmenu_repaintPending = 1;\n}', 'void menu_repaint()\n{\n\tmenu_repaintNow();\n}'),
    'process-clear-late': ('menu', '\tmenu_repaintPending = 0;\n\tmenu_repaintNow();\n', '\tmenu_repaintNow();\n\tmenu_repaintPending = 0;\n'),
    'clearall-deferred': ('menu', '\t\tmenu_repaintNow();\t// 0.2.103', '\t\tmenu_repaint();\t// 0.2.103'),
    'main-no-process': ('main', '\t  menu_processRepaint(); // 0.2.103 the repaint asked for this pass, after the audio block\n', ''),
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
numeric(found)
for f in found:
    print('FAIL', f)
if found:
    sys.exit(1)
print('OPT 103 PASS')
