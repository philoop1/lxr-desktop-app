"""0.2.100 CPU fast paths from the Mutador reference: the decimator leaves at
full rate, and a silent built-in 2nd drum osc only moves its phase. Both must
give the same samples as the full path. The real functions are extracted and
compared with the full path on the host; --mutate shows the checks bite."""
from pathlib import Path
import os, re, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build' / 'fast-paths'
MIX = 'Core/Src/Soundengine/DSPAudio/mixer.c'
OSC = 'Core/Src/Soundengine/DSPAudio/Oscillator.c'
DRUM = 'Core/Src/Soundengine/DSPAudio/DrumVoice.c'


def read(p):
    return (ROOT / p).read_text(encoding='latin-1').replace('\r\n', '\n')


def body(src, sig):
    start = src.index(sig)
    i = src.index('{', start)
    depth = 0
    while True:
        depth += (src[i] == '{') - (src[i] == '}')
        if depth == 0:
            return src[start:i + 1]
        i += 1


FAST = '\tif(phaseInc >= 1.f) { mixer_voice_samples[voiceNr] = buffer[OUTPUT_DMA_SIZE-1]; return; }\n'


def contract(s):
    p = []
    dec = body(s['mix'], 'IN_ITCM_RAM void mixer_decimateBlock(')
    if FAST not in dec:
        p.append('decimator has no full-rate fast path')
    drum = body(s['drum'], 'IN_ITCM_RAM void calcDrumVoiceSyncBlock(')
    if 'voiceArray[voiceNr].modOsc.waveform <= REC &&' not in drum:
        p.append('the skip must stay on stateless built-in waves (noise/wavetables/samples keep state)')
    if '(modMode == 0 || modMode == 1) && voiceArray[voiceNr].fmModAmount == 0.f' not in drum:
        p.append('FM/mix skip must need amount exactly 0')
    if '(modMode == 2 && (int32_t)(voiceArray[voiceNr].fmModAmount * 32767.f + 0.5f) == 0)' not in drum:
        p.append('ring skip must match the wet value of the ring mix')
    i = drum.find('if(modSilent)')
    if i < 0 or 'modOsc.phase += voiceArray[voiceNr].modOsc.phaseInc * size;' not in drum[i:i + 200] \
            or 'bufferTool_clearBuffer(modBuf,size);' not in drum[i:i + 260]:
        p.append('a skipped 2nd osc must move its phase and clear its buffer')
    if 'else if(modMode != 4)' not in drum:
        p.append('the full 2nd osc path is gone')
    return p


def program(s):
    dec = body(s['mix'], 'IN_ITCM_RAM void mixer_decimateBlock(').replace('IN_ITCM_RAM ', '')
    full = dec.replace(FAST, '').replace('void mixer_decimateBlock(', 'void full_decimateBlock(')
    sine = body(s['osc'], 'IN_ITCM_RAM void calcSineBlock(').replace('IN_ITCM_RAM ', '')
    table = body(s['osc'], 'IN_ITCM_RAM void calcWavetableOscBlock(').replace('IN_ITCM_RAM ', '')
    drum = body(s['drum'], 'IN_ITCM_RAM void calcDrumVoiceSyncBlock(')
    m = re.search(r'const uint8_t modSilent = (.*?);\n', drum, re.S)
    cond = m.group(1).replace('voiceArray[voiceNr].', 'v->').replace('modMode', 'v->mixOscs') if m else '0'
    return r'''
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#define OUTPUT_DMA_SIZE 64
#define INTERPOLATE_OSC 1
enum {SINE,TRI,SAW,REC,NOISE,PWM};
typedef struct {uint32_t phaseInc,phase;uint8_t tableOffset,waveform;} OscInfo;
typedef struct {OscInfo modOsc;uint8_t mixOscs;float fmModAmount;} Voice;
static int16_t sine_table[4097];
static int16_t tab[2][1025];
static float mixer_decimation_rate[7],mixer_decimation_cnt[6];
static int16_t mixer_voice_samples[6];
static unsigned checks,fails;
static void check(int ok,const char*m){checks++;if(!ok){fails++;if(fails<10)printf("FAIL %s\n",m);}}
static uint32_t rnd=12345;static uint32_t nx(void){rnd=rnd*1664525u+1013904223u;return rnd;}
''' + dec + '\n' + full + '\n' + sine + '\n' + table + r'''
static int silent(Voice*v){return ''' + cond + r''';}
int main(void){
 for(int i=0;i<4097;i++)sine_table[i]=(int16_t)(nx()>>16);
 for(int k=0;k<2;k++)for(int i=0;i<1025;i++)tab[k][i]=(int16_t)(nx()>>16);
 /* decimator: fast and full path give the same samples */
 const float rates[]={1.f,1.f,0.5f,0.37f,0.9999f};
 for(int r=0;r<5;r++)for(int v=0;v<6;v++){
  mixer_decimation_rate[v]=rates[r];mixer_decimation_rate[6]=r==1?1.f:(r>1?1.f:1.f);
  mixer_decimation_cnt[v]=0.25f;mixer_voice_samples[v]=7;
  float cnt2=0.25f;int16_t hold2=7;
  for(int b=0;b<40;b++){
   int16_t a[64],c[64];for(int i=0;i<64;i++)a[i]=c[i]=(int16_t)(nx()>>16);
   mixer_decimateBlock((uint8_t)v,a);
   float cs=mixer_decimation_cnt[v];int16_t hs=mixer_voice_samples[v];
   mixer_decimation_cnt[v]=cnt2;mixer_voice_samples[v]=hold2;
   full_decimateBlock((uint8_t)v,c);
   cnt2=mixer_decimation_cnt[v];hold2=mixer_voice_samples[v];
   mixer_decimation_cnt[v]=cs;mixer_voice_samples[v]=hs;
   check(!memcmp(a,c,sizeof a),"decimator samples");
   check(hs==hold2,"decimator held sample");
   if(rates[r]<1.f)check(cs==cnt2,"decimator counter below full rate");
  }
 }
 /* a silent 2nd osc: zeros and the same phase as rendering at gain 0 */
 for(int t=0;t<4000;t++){
  OscInfo a={nx(),nx(),(uint8_t)(nx()&1),(uint8_t)(nx()%4)},b=a;
  int16_t x[64],y[64];
  if(a.waveform==SINE)calcSineBlock(&a,x,64,0.f);else calcWavetableOscBlock(&a,(const int16_t(*)[1024])tab,x,64,0.f);
  b.phase+=b.phaseInc*64;memset(y,0,sizeof y);
  check(!memcmp(x,y,sizeof x),"gain 0 renders zeros");
  check(a.phase==b.phase,"skipped phase matches");
 }
 /* the condition: only built-in waves, only when nothing is heard */
 Voice v;memset(&v,0,sizeof v);
 for(int w=0;w<=PWM+3;w++)for(int m=0;m<5;m++){
  const float am[]={0.f,1e-6f,1.6e-5f,0.01f,1.f};
  for(int k=0;k<5;k++){
   v.modOsc.waveform=(uint8_t)w;v.mixOscs=(uint8_t)m;v.fmModAmount=am[k];
   int heard;
   if(w>REC)heard=1;
   else if(m==0||m==1)heard=am[k]!=0.f;
   else if(m==2)heard=(int)(am[k]*32767.f+0.5f)!=0;
   else heard=1;
   check(silent(&v)==!heard,"skip only when silent");
  }
 }
 printf(fails?"FAST PATHS FAIL %u/%u\n":"FAST PATHS PASS %u assertions\n",fails?fails:checks,checks);
 return fails!=0;
}
'''


def run(s):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'fast.c').write_text(program(s))
    if os.name == 'nt':
        vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
        r = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /Fe:fast.exe fast.c >nul && fast.exe',
                           shell=True, cwd=OUT, capture_output=True, text=True)
    else:
        r = subprocess.run('cc -O2 -std=c11 fast.c -o fast && ./fast', shell=True, cwd=OUT, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def failing(s):
    return bool(contract(s)) or run(s)[0] != 0


MUTATIONS = {
    'no-fast-decimator': ('mix', FAST, ''),
    'fast-decimator-no-hold': ('mix', 'mixer_voice_samples[voiceNr] = buffer[OUTPUT_DMA_SIZE-1]; return;', 'return;'),
    'skip-noise': ('drum', 'modOsc.waveform <= REC &&', 'modOsc.waveform <= NOISE &&'),
    'skip-small-amount': ('drum', 'voiceArray[voiceNr].fmModAmount == 0.f)', 'voiceArray[voiceNr].fmModAmount < 0.01f)'),
    'no-phase-move': ('drum', '\t\tvoiceArray[voiceNr].modOsc.phase += voiceArray[voiceNr].modOsc.phaseInc * size;\n', ''),
    'no-clear': ('drum', '\t\tbufferTool_clearBuffer(modBuf,size);\n', ''),
}

src = {'mix': read(MIX), 'osc': read(OSC), 'drum': read(DRUM)}
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        m = dict(src)
        assert m[key].count(old) == 1, name
        m[key] = m[key].replace(old, new)
        hit = failing(m)
        caught += hit
        print(name, 'caught' if hit else 'MISSED')
    print(f'{caught}/{len(MUTATIONS)} mutations caught')
    sys.exit(0 if caught == len(MUTATIONS) else 1)

problems = contract(src)
for p in problems:
    print('FAIL', p)
code, out = run(src)
print(out.strip())
sys.exit(1 if problems or code else 0)
