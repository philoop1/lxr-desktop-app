"""0.2.88 pd resonance for drum voices 1-3.

In the pd mode the 2nd oscillator used to be idle. Now its rate sets a
resonance: every main cycle restarts a sine at the 2nd osc's rate (sync),
faded by a falling window, and the FM amount (DCW) sweeps it from the main
pitch up to the 2nd osc. At or below the main pitch, and for the snare, the
plain phase distortion stays. Runs the production calcPdResonanceBlock on the
host; --mutate shows the checks bite."""
from pathlib import Path
import math, os, re, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root / 'build/pd-resonance'
out.mkdir(parents=True, exist_ok=True)
OSC = root / 'Core/Src/Soundengine/DSPAudio/Oscillator.c'
DRUM = root / 'Core/Src/Soundengine/DSPAudio/DrumVoice.c'
SNARE = root / 'Core/Src/Soundengine/DSPAudio/Snare.c'


def load():
    return {k: p.read_text(encoding='latin-1').replace('\r\n', '\n')
            for k, p in (('osc', OSC), ('drum', DRUM), ('snare', SNARE))}


def function(src, signature):
    start = src.index(signature)
    i = src.index('{', start)
    depth = 0
    while True:
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1


def contract(src):
    p = []
    if 'if(osc->pdRatio>1.01f) { calcPdResonanceBlock(osc,buf,size); return; }' not in function(src['osc'], 'void calcPhaseDistBlock(OscInfo* osc, int16_t* buf, uint8_t size) //'):
        p.append('pd does not switch to the resonance above the main pitch')
    if 'osc.pdRatio = (mainInc && voiceArray[voiceNr].modOsc.waveform <= PWM)' not in src['drum']:
        p.append('drum voices do not pass the 2nd osc rate')
    if 'osc.pdRes = 0.f;' not in src['drum']:
        p.append('a trigger does not restart the resonance glide')
    if 'pdRatio' in src['snare']:
        p.append('the snare pd must stay plain')
    return p


def harness(src):
    o = src['osc']
    return r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#define __attribute__(x)
typedef struct {uint32_t phase,phaseInc;int16_t output;float fmMod,pdRatio,pdRes;} OscInfo;
static int16_t sine_table[4097];
''' + re.search(r'#define PD_RES_MAX_REL.*\n', o).group(0) + function(o, 'static inline int16_t osc_readSine') + '\n' + \
        function(o, '__attribute__((noinline)) void calcPdResonanceBlock') + r'''
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
static int16_t at(float amount,float ratio,uint32_t phase,uint32_t inc){OscInfo o={0};o.phase=phase;o.phaseInc=inc;o.fmMod=amount;o.pdRatio=ratio;
 int16_t b[1];calcPdResonanceBlock(&o,b,1);return b[0];}
int main(void){
 for(int i=0;i<4097;i++)sine_table[i]=(int16_t)lrint(32767.0*sin(2*M_PI*i/4096.0));
 const uint32_t inc=1u<<22; /* about 43 Hz */
 /* amount 0: one windowed sine per cycle, whatever the 2nd osc */
 check(abs(at(0.f,8.f,0x40000000u,inc)-24575)<40,"DCW 0 plays the main pitch (sin 90 deg x 0.75)");
 /* amount 1: the sine runs at the 2nd osc's rate, restarted every cycle */
 check(abs(at(1.f,4.f,0x10000000u,inc)-30719)<40,"DCW 1: ratio 4, 1/16 cycle = 90 deg of the resonance");
 check(abs(at(1.f,4.f,0x20000000u,inc))<40,"ratio 4 at 1/8 cycle = 180 deg");
 check(abs(at(0.5f,5.f,0x10000000u,inc)-30274*15/16)<60,"DCW 0.5: ratio 3 at 1/16 cycle = 67.5 deg");
 /* the window fades to 0 at the end of a cycle: the restart does not click */
 check(abs(at(1.f,7.3f,0xFFF00000u,inc))<40,"end of the cycle is silent");
 check(at(1.f,7.3f,0u,inc)==0,"start of the cycle is silent");
 /* the resonance stays below the Nyquist limit */
 {OscInfo o={0};o.phaseInc=1u<<28;o.fmMod=1.f;o.pdRatio=1000.f;int16_t b[1];calcPdResonanceBlock(&o,b,1);
  check(o.pdRes<=0.45f*16.f+0.001f&&o.pdRes>7.f,"ratio limited to 0.45 of the sample rate");}
 /* the DCW glides within a block from the last block's ratio */
 {OscInfo o={0};o.phaseInc=inc;o.fmMod=1.f;o.pdRatio=6.f;int16_t b[32];calcPdResonanceBlock(&o,b,32);
  check(o.pdRes==6.f,"first block starts at its target");o.fmMod=0.f;calcPdResonanceBlock(&o,b,32);check(o.pdRes==1.f,"next block glides to DCW 0");}
 for(int k=0;k<20000;k++){OscInfo o={0};o.phase=(uint32_t)k*214013u;o.phaseInc=(uint32_t)(k*7919u)|1u;o.fmMod=(k%11)/10.f;o.pdRatio=(k%37)/3.f;
  int16_t b[16];calcPdResonanceBlock(&o,b,16);for(int i=0;i<16;i++)check(b[i]>=-32767&&b[i]<=32767,"bounded");}
 printf("PD RESONANCE PASS %u assertions\n",checks);return 0;}
'''


def run(code):
    (out / 'pd.c').write_text(code, encoding='latin-1')
    if os.name == 'nt':
        vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
        r = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /D_USE_MATH_DEFINES /Fe:pd.exe pd.c && pd.exe',
                           shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    else:
        r = subprocess.run('cc -o pd pd.c -lm && ./pd', shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    return r.returncode, r.stdout + r.stderr


MUTATIONS = {
    'no-window': ('osc', '*(1.f-ph));', '*(1.f));'),
    'no-limit': ('osc', 'if(inc>0.f && ratio>PD_RES_MAX_REL/inc) ratio = PD_RES_MAX_REL/inc;', ''),
    'no-dcw': ('osc', 'const float target = 1.f + amount*(ratio-1.f);', 'const float target = ratio;'),
    'no-switch': ('osc', 'if(osc->pdRatio>1.01f) { calcPdResonanceBlock(osc,buf,size); return; }', ''),
    'any-wave': ('drum', 'osc.pdRatio = (mainInc && voiceArray[voiceNr].modOsc.waveform <= PWM)', 'osc.pdRatio = (mainInc)'),
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
