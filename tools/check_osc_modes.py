"""Exponential FM and phase distortion through the production oscillator blocks.

--mutate removes the expo rate limit and the PD warp; the check must then fail.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"
PRELUDE = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#define IN_ITCM_RAM
#define SINE_PI 3.14159265358979
enum {SINE,TRI,SAW,REC,NOISE,PWM,NUM_OSC_WAVEFORMS};
"""
STUBS = r"""
static int16_t sine_table[4097],triTable[11][1024],sawTable[11][1024],recTable[11][1024];
static unsigned noiseCalls,sampleCalls;
static void calcNoiseBlock(OscInfo *o,int16_t *b,const uint8_t s,const float g){(void)o;(void)b;(void)s;(void)g;noiseCalls++;}
static void calcUserSampleOscBlock(OscInfo *o,int16_t *b,const uint8_t s,const float g){(void)o;(void)b;(void)s;(void)g;sampleCalls++;}
static int16_t __QSUB16(int32_t a,int32_t b){int32_t r=a-b;return (int16_t)(r>32767?32767:r<-32768?-32768:r);}
"""
TESTS = r"""
static unsigned checks,failures;
static const char *lastFail;
static void check(int ok,const char *name)
{
 checks++;
 if(!ok){failures++;if(failures<20)printf("FAIL %s\n",name);}
}
static double brightness(OscInfo *o,unsigned period)
{
 /* Energy above the fundamental over one cycle. */
 static int16_t cycle[4096];
 for(unsigned i=0;i<period;i++)calcPhaseDistBlock(o,&cycle[i],1);
 double all=0,fundamental_re=0,fundamental_im=0;
 for(unsigned i=0;i<period;i++) {
  all+=(double)cycle[i]*cycle[i];
  fundamental_re+=cycle[i]*cos(2*SINE_PI*i/period);
  fundamental_im+=cycle[i]*sin(2*SINE_PI*i/period);
 }
 const double first=2*(fundamental_re*fundamental_re+fundamental_im*fundamental_im)/period;
 return (all-first)/all;
}
int main(void)
{
 for(unsigned i=0;i<=4096;i++)sine_table[i]=(int16_t)lrint(32767*sin(2*SINE_PI*i/4096));
 for(unsigned t=0;t<11;t++)for(unsigned i=0;i<1024;i++) {
  sawTable[t][i]=(int16_t)(i*64-32768);
  recTable[t][i]=i<512?30000:-30000;
  triTable[t][i]=(int16_t)(i<512?i*128-32768:(1023-i)*128-32768);
 }
 /* Ratio stays close to 2^x, is exact at whole octaves and never falls. */
 float last=0;
 for(int i=-4000;i<=4000;i++) {
  const float x=i/1000.f,r=osc_expoRatio(x);
  check(fabs(r/pow(2.,x)-1.)<0.001,"ratio close to 2^x");
  check(r>=last,"ratio is monotonic");last=r;
 }
 for(int i=-4;i<=4;i++)check(osc_expoRatio((float)i)==(float)pow(2.,i),"whole octaves are exact");

 static const uint8_t waves[]={SINE,TRI,SAW,REC,PWM};
 for(unsigned w=0;w<sizeof(waves);w++) {
  /* No modulation keeps the rate and the plain sample values. */
  OscInfo o;memset(&o,0,sizeof(o));
  o.waveform=waves[w];o.phaseInc=0x01234567;o.fmMod=1.f;
  int16_t mod[32],buf[32];memset(mod,0,sizeof(mod));
  calcExpoFmBlock(&o,mod,buf,32,0.25f);
  check(fabs(o.phase/32./0x01234567-1.)<1e-6,"silent modulator keeps pitch");
  /* A full-scale negative modulator lowers four octaves, positive raises at most four. */
  for(unsigned i=0;i<32;i++)mod[i]=-32768;
  uint32_t before=o.phase;calcExpoFmBlock(&o,mod,buf,32,0.25f);
  check(fabs((o.phase-before)/32.-0x01234567/16.)<1.1,"down four octaves");
  for(unsigned i=0;i<32;i++)mod[i]=32767;
  before=o.phase;calcExpoFmBlock(&o,mod,buf,8,0.25f);
  check(fabs((o.phase-before)/8./0x01234567-16.)<0.05,"up four octaves");
  /* Zero depth ignores any modulator. */
  o.fmMod=0;before=o.phase;calcExpoFmBlock(&o,mod,buf,32,0.25f);
  check(fabs((o.phase-before)/32./0x01234567-1.)<1e-6,"zero depth is silent");
  /* The rate limit holds at the top of the range. */
  o.fmMod=1.f;o.phaseInc=0x60000000;before=o.phase;
  calcExpoFmBlock(&o,mod,buf,1,0.25f);
  check(o.phase-before==0x80000000u,"rate stops at half the sample rate");
 }
 /* The same sine modulator raises the mean rate: the expo signature. */
 {
  OscInfo o;memset(&o,0,sizeof(o));o.phaseInc=0x00100000;o.fmMod=1.f;
  int16_t mod[200],buf[200];
  for(unsigned i=0;i<200;i++)mod[i]=(int16_t)(32767*sin(2*SINE_PI*i/200));
  calcExpoFmBlock(&o,mod,buf,200,0);
  check(o.phase/200./0x00100000>2.,"mean pitch rises with depth");
 }
 /* Sine start, no wave escapes. */
 OscInfo n;memset(&n,0,sizeof(n));n.waveform=NOISE;int16_t pb[8],pm[8];memset(pm,0,sizeof(pm));
 calcExpoFmBlock(&n,pm,pb,8,0);check(noiseCalls==1,"noise stays noise");
 n.waveform=PWM+1;calcExpoFmBlock(&n,pm,pb,8,0);check(sampleCalls==1,"sample wave stays a sample");
 calcPhaseDistBlock(&n,pb,8);check(sampleCalls==2,"phase distortion leaves samples alone");

 /* Amount zero is the plain sine. */
 {
  OscInfo o;memset(&o,0,sizeof(o));o.phaseInc=0x00100000;
  for(unsigned i=0;i<4096;i++) {
   int16_t s;const uint32_t p=o.phase;calcPhaseDistBlock(&o,&s,1);
   const int expected=(int)lrint(32767*sin(2*SINE_PI*p/4294967296.));
   check(abs(s-expected)<=2,"no warp reads the sine");
  }
 }
 /* More amount, more overtones, same cycle length, no clicks at low pitch. */
 double previous=-1;
 for(unsigned a=0;a<=8;a++) {
  OscInfo o;memset(&o,0,sizeof(o));o.phaseInc=1u<<20;o.fmMod=a/8.f;
  const double b=brightness(&o,4096);
  check(b>=previous-1e-6,"amount brightens");previous=b;
  check(o.phase==0,"cycle length unchanged");
  int16_t s,prev=0;int first=1;int jump=0;
  memset(&o,0,sizeof(o));o.phaseInc=1u<<20;o.fmMod=a/8.f;
  for(unsigned i=0;i<4096;i++) {
   calcPhaseDistBlock(&o,&s,1);
   if(!first&&abs(s-prev)>jump)jump=abs(s-prev);
   first=0;prev=s;
  }
  check(jump<16000,"steep edge spans several samples");
 }
 check(previous>0.15,"full amount is far from a sine");
 /* Every phase and amount stays inside the table, even at the top pitch. */
 for(uint32_t inc=1u<<20;inc&&inc<=0x70000000u;inc=inc*3u) {
  OscInfo o;memset(&o,0,sizeof(o));o.phaseInc=inc;
  for(unsigned a=0;a<=4;a++) {
   o.fmMod=a*0.5f-0.5f;
   for(unsigned i=0;i<4096;i++) {
    int16_t s;calcPhaseDistBlock(&o,&s,1);
    check(s>=-32768&&s<=32767,"range");
   }
  }
 }
 {
  OscInfo o;memset(&o,0,sizeof(o));
  static const uint32_t edges[]={0,1,0x3FFFFFFFu,0x40000000u,0xBFFFFFFFu,0xC0000000u,0xFFFFFFFFu};
  for(unsigned a=0;a<=16;a++)for(unsigned i=0;i<7;i++) {
   int16_t s;o.phase=edges[i];o.phaseInc=0;o.fmMod=a/16.f;calcPhaseDistBlock(&o,&s,1);
   check(s>=-32768,"edge phases read the table");
  }
 }
 printf("%s %u assertions\n",failures?"OSC MODES FAIL":"OSC MODES PASS",checks);
 return failures!=0;
}
"""


def read(path: str) -> str:
    return (ROOT / path).read_text(errors='replace')


def extract(source: str, signature: str) -> str:
    start = source.index(signature)
    position, depth = source.index('{', start) + 1, 1
    while depth:
        depth += (source[position] == '{') - (source[position] == '}')
        position += 1
    return source[start:position]


def main() -> None:
    oscillator = read('Core/Src/Soundengine/DSPAudio/Oscillator.c')
    header = read('Core/Inc/Soundengine/DSPAudio/Oscillator.h')
    drum = read('Core/Src/Soundengine/DSPAudio/DrumVoice.c')
    parser = read('Core/Src/Soundengine/MIDI/MidiParser.c')
    node = read('Core/Src/Soundengine/DSPAudio/modulationNode.c')
    names = read('Core/Inc/menu/MenuText.h')
    assert 'mixOscs >= 2 ? 1.f' in drum and 'mixOscs == 4' in drum and 'mixOscs == 3' in drum
    assert 'isFloatModulator ? (uint8_t)(v*4.f+0.5f) : value.itg > 4 ? 4 : value.itg' in parser
    assert 'originalValue=activeParameters[destination]/4.f' in node
    menu = re.search(r'mixFmNames\[\]\[6\] =\s*\{(.*?)\};', names, re.S).group(1)
    assert re.findall(r'\{(.*?)\}', menu) == ['5', '"FM"', '"Mix"', '"rng"', '"exp"', '"pd"']

    defines = ''.join(re.findall(r'#define (?:EXPO_FM_OCTAVES|OSC_MAX_PHASE_INC|PD_MIN_KNEE).*\n', header)).replace('#define', '\n#define')
    struct = re.search(r'typedef struct OscStruct.*?\} OscInfo;', header, re.S).group(0)
    bodies = [extract(oscillator, s) for s in (
        'static inline float osc_expoRatio', 'static inline int16_t osc_readTable',
        'static inline int16_t osc_readSine', 'IN_ITCM_RAM void calcExpoFmBlock',
        'IN_ITCM_RAM void calcPhaseDistBlock')]
    source = '\n'.join(bodies)
    if '--mutate' in sys.argv:
        source = source.replace('if(inc>OSC_MAX_PHASE_INC) inc = OSC_MAX_PHASE_INC;', '')
        source = source.replace('0.5f - amount*(0.5f-minKnee)', '0.5f')
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        out = Path(folder)
        (out / 'contract.c').write_text(PRELUDE + defines + struct + STUBS + source + TESTS, encoding='utf-8')
        command = (f'call "{VS}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /Fe:contract.exe contract.c '
                   f'&& .\\contract.exe')
        subprocess.run(command, shell=True, cwd=out, check=True)


if __name__ == '__main__':
    main()
