"""0.2.87 full-wave FM for drum voices 1-3.

The original FM code converted the phase offset (modulator * fmMod, a float
that can be negative) to uint32_t; the Cortex-M7 FPU saturates negative values
to 0, so FM only used the positive half of the modulator (the official v1.71
binary has the same vcvt.u32). OSC_FM_OFFSET keeps that with fmFloor 0
(cymbal, hi-hat, snare) and uses the full wave with a negative floor, which
the drum voices 1-3 set. Runs the production calcFmSineBlock on the host;
--mutate shows the checks bite."""
from pathlib import Path
import os, re, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root / 'build/fm-full-wave'
out.mkdir(parents=True, exist_ok=True)
OSC = root / 'Core/Src/Soundengine/DSPAudio/Oscillator.c'
DRUM = root / 'Core/Src/Soundengine/DSPAudio/DrumVoice.c'


def load():
    return {'osc': OSC.read_text(encoding='latin-1').replace('\r\n', '\n'),
            'drum': DRUM.read_text(encoding='latin-1').replace('\r\n', '\n')}


def function(src, name):
    m = re.search(r'\n(?:IN_ITCM_RAM )?void ' + name + r'\(', src)
    start = m.start() + 1
    depth = 0
    i = src.index('{', start)
    while True:
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1].replace('IN_ITCM_RAM ', '')
        i += 1


def contract(src):
    p = []
    o = src['osc']
    if re.search(r'\(uint32_t\)\((?:modBuffer\[i\]|modOsc->output)\*osc->fmMod\)', o):
        p.append('an FM phase offset still uses the unsigned conversion')
    if o.count('OSC_FM_OFFSET(osc,mod') != 8:
        p.append('not every FM phase offset uses OSC_FM_OFFSET')
    if 'voiceArray[i].osc.fmFloor = -65536.f;' not in src['drum']:
        p.append('drum voices 1-3 do not select full-wave FM')
    return p


def harness(src):
    o = src['osc']
    macro = re.search(r'#define OSC_FM_OFFSET\(osc,x\)[^\n]*\n', o).group(0)
    return r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#define INTERPOLATE_FM_OSC 1
typedef struct {uint32_t phase,phaseInc;int16_t output;float fmMod,fmFloor;} OscInfo;
static int16_t sine_table[4097];
''' + macro + function(o, 'calcFmSineBlock') + r'''
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
static int16_t run(float floor,int16_t mod){OscInfo osc={0};osc.fmMod=1.f;osc.fmFloor=floor;
 int16_t mb[1]={mod},b[1];calcFmSineBlock(&osc,mb,b,1,1.f);return b[0];}
int main(void){
 for(int i=0;i<4097;i++)sine_table[i]=(int16_t)(i&4095);
 /* positive modulator: both modes move the phase forward the same */
 check(run(0.f,8192)==1024&&run(-65536.f,8192)==1024,"positive half unchanged");
 /* negative modulator: the original drops it, full wave moves the phase back */
 check(run(0.f,-8192)==0,"fmFloor 0 keeps the original half-wave FM");
 check(run(-65536.f,-8192)==3072,"full wave: -8192 moves a quarter cycle back");
 check(run(-65536.f,-32768)==0&&run(-65536.f,-16384)==2048,"full wave covers the whole negative range");
 for(int m=-32768;m<32768;m+=97){int16_t a=run(0.f,(int16_t)m),b=run(-65536.f,(int16_t)m);
  if(m>=0)check(a==b,"same for m>=0");else check(a==0,"original drops m<0");}
 printf("FM FULL WAVE PASS %u assertions\n",checks);return 0;}
'''


def run(code):
    (out / 'fm.c').write_text(code, encoding='latin-1')
    if os.name == 'nt':
        vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
        r = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:fm.exe fm.c && fm.exe',
                           shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    else:
        r = subprocess.run('cc -o fm fm.c -lm && ./fm', shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    return r.returncode, r.stdout + r.stderr


MUTATIONS = {
    'unsigned': ('osc', '#define OSC_FM_OFFSET(osc,x) ((uint32_t)(int32_t)fmaxf((x),(osc)->fmFloor))',
                 '#define OSC_FM_OFFSET(osc,x) ((uint32_t)(int32_t)fmaxf((x),0.f))'),
    'always-full': ('osc', '#define OSC_FM_OFFSET(osc,x) ((uint32_t)(int32_t)fmaxf((x),(osc)->fmFloor))',
                    '#define OSC_FM_OFFSET(osc,x) ((uint32_t)(int32_t)(x))'),
    'drum-not-full': ('drum', 'voiceArray[i].osc.fmFloor = -65536.f;', 'voiceArray[i].osc.fmFloor = 0.f;'),
}

src = load()
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        m = dict(src)
        assert m[key].count(old) == 1, name
        m[key] = m[key].replace(old, new)
        hit = bool(contract(m)) or run(harness(m))[0] != 0
        caught += hit
        print(name, 'caught' if hit else 'MISSED')
    print(f'{caught}/{len(MUTATIONS)} mutations caught')
    sys.exit(0 if caught == len(MUTATIONS) else 1)

found = contract(src)
for f in found:
    print('FAIL', f)
if found:
    sys.exit(1)
code, text = run(harness(src))
print(text.strip().splitlines()[-1] if text.strip() else text)
if code:
    print(text)
    sys.exit(1)
