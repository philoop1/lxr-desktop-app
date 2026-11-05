"""Exponential FM, phase distortion and the user wavetables through the production oscillator blocks.

The wavetable part uses a fake bank (a wavetable with 3 frames and single
waves after it) and the real level layout from WaveBank.h: every mode plays
the selected wavetable at the level of the pitch, blended into the next
level, PWM scans its frames without steps and stays inside it, a single wave
scans on through the single waves after it, the scan glides, and an empty
slot is silent.
The PD knee glides within a block, so a falling amount (the pitch EG) does
not step the shape every block.
--mutate removes the expo rate limit, the PD warp, the plain-mode wavetable
call, the level blend and the PD glide; the check must then fail.
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
#define PD_SWEEP_LIMIT 200 /* about 3 with the glide, about 2300 with a step per block */
enum {SINE,TRI,SAW,REC,NOISE,PWM,NUM_OSC_WAVEFORMS};
"""
STUBS = r"""
static int16_t sine_table[4097],triTable[11][1024],sawTable[11][1024],recTable[11][1024];
static unsigned noiseCalls,builtinCalls;
static void calcNoiseBlock(OscInfo *o,int16_t *b,const uint8_t s,const float g){(void)o;(void)b;(void)s;(void)g;noiseCalls++;}
static void calcSineBlock(OscInfo *o,int16_t *b,const uint8_t s,const float g){(void)o;(void)b;(void)s;(void)g;builtinCalls++;}
static void calcFmSineBlock(OscInfo *o,int16_t *m,int16_t *b,uint8_t s,const float g){(void)o;(void)m;(void)b;(void)s;(void)g;builtinCalls++;}
static void calcWavetableOscBlock(OscInfo *o,const int16_t t[][1024],int16_t *b,const uint8_t s,const float g){(void)o;(void)t;(void)b;(void)s;(void)g;builtinCalls++;}
static void calcFmBlock(OscInfo *o,const int16_t t[][1024],int16_t *m,int16_t *b,uint8_t s,const float g){(void)o;(void)t;(void)m;(void)b;(void)s;(void)g;builtinCalls++;}
static void calcPwmBlock(OscInfo *o,int16_t *b,uint8_t s,const float g,const float p){(void)o;(void)b;(void)s;(void)g;(void)p;builtinCalls++;}
static void calcPwmFmBlock(OscInfo *o,int16_t *m,int16_t *b,uint8_t s,const float g,const float p){(void)o;(void)m;(void)b;(void)s;(void)g;(void)p;builtinCalls++;}
/* Fake bank: wavetable 0 has 3 frames, wavetables 1 to 3 one frame each.
   Frame f, level l, sample i of n: base + l*100 + (i*1024/n - 512)*4,
   base (f-1)*10000 for the 3 frames, then 7000, 8000, 9000 */
static int16_t bank[6][WAVEBANK_FRAME_SAMPLES];
static uint8_t bankCount;
static uint8_t waveBank_frames(uint8_t t){return t<bankCount?(t==0?3:1):0;}
static const int16_t* waveBank_frame(uint8_t t,uint8_t f){return f<waveBank_frames(t)?bank[t==0?f:2+t]:0;}
static int16_t __QSUB16(int32_t a,int32_t b){int32_t r=a-b;return (int16_t)(r>32767?32767:r<-32768?-32768:r);}
/* 0.2.51 user samples: waveform 38 and up go to the sample blocks */
#define SAMPLEBANK_FIRST_WAVE 38u
static unsigned sampleCalls,sampleFmCalls;
static uint8_t osc_isSample(const OscInfo* osc){return osc->waveform >= SAMPLEBANK_FIRST_WAVE;}
static void calcSampleBankBlock(OscInfo *o,int16_t *b,const uint8_t s,const float g){(void)o;(void)g;for(uint8_t i=0;i<s;i++)b[i]=1234;sampleCalls++;}
static void calcSampleBankFmBlock(OscInfo *o,int16_t *m,int16_t *b,const uint8_t s,const float g){(void)o;(void)m;(void)g;for(uint8_t i=0;i<s;i++)b[i]=4321;sampleFmCalls++;}
void calcNextOscSampleBlock(OscInfo* osc, int16_t* buf, const uint8_t size, const float gain, const float pwm);
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
 n.waveform=PWM+1;memset(pb,1,sizeof(pb));calcExpoFmBlock(&n,pm,pb,8,0);
 check(!pb[0]&&!pb[7],"expo FM on an empty wavetable slot is silent");
 memset(pb,1,sizeof(pb));calcPhaseDistBlock(&n,pb,8);check(!pb[0]&&!pb[7],"phase distortion on an empty slot is silent");

 /* User wavetables with PWM scan. */
 for(unsigned f=0;f<6;f++)for(unsigned l=0;l<WAVEBANK_LEVELS;l++) {
  const unsigned size=1u<<waveBank_levelBits((uint8_t)l);
  for(unsigned i=0;i<size;i++)
   bank[f][waveBank_levelOffset((uint8_t)l)+i]=(int16_t)((f<3?((int)f-1)*10000:7000+((int)f-3)*1000)+(int)l*100+((int)(i*1024/size)-512)*4);
 }
 bankCount=2;
 {
  OscInfo o;int16_t b[16],m[16];memset(m,0,sizeof(m));
#define AT_ZERO(wave,pw,expect,name) do{memset(&o,0,sizeof(o));o.waveform=(wave);o.tableOffset=3;o.scanPos=(pw)<0?0.f:(pw)>1?1.f:(pw);memset(b,0,sizeof(b)); \
   calcNextOscSampleBlock(&o,b,16,1.f,(pw));check(abs(b[0]-(expect))<=1&&abs(b[15]-(expect))<=1,name);}while(0)
  /* phase 0 reads sample 0: (0-512)*4 = -2048, level 3 adds 300 */
  const unsigned before=builtinCalls;
  AT_ZERO(PWM+1,0.f,-10000+300-2048,"plain mode plays the first frame");
  check(builtinCalls==before,"the wavetable needs no built-in waveform");
  AT_ZERO(PWM+1,1.f,10000+300-2048,"full PWM reaches the last frame");
  AT_ZERO(PWM+1,0.5f,300-2048,"half PWM is the middle frame");
  AT_ZERO(PWM+1,0.25f,-5000+300-2048,"a quarter blends the first two frames");
  AT_ZERO(PWM+1,-1.f,-10000+300-2048,"PWM below 0 clamps");
  AT_ZERO(PWM+1,2.f,10000+300-2048,"PWM above 1 clamps, inside the wavetable");
  AT_ZERO(PWM+2,0.f,7000+300-2048,"a wavetable with one frame plays it");
  AT_ZERO(PWM+2,0.8f,7000+300-2048,"a wavetable with one frame ignores PWM");
  AT_ZERO(PWM+3,0.f,0,"an empty slot is silent");
  /* every level reads its own length */
  for(uint8_t l=0;l<12;l++) {
   const uint8_t used=l<WAVEBANK_LEVELS?l:WAVEBANK_LEVELS-1;
   const uint8_t bits=waveBank_levelBits(used);
   memset(&o,0,sizeof(o));o.waveform=PWM+1;o.tableOffset=l;
   o.phase=((1u<<bits)-1)<<(32-bits);o.phaseInc=1u<<(31-bits);
   calcNextOscSampleBlock(&o,b,3,1.f,0.f);
   const int last=-10000+used*100+((int)(((1u<<bits)-1)*1024>>bits)-512)*4,first=-10000+used*100-2048;
   check(b[0]==last&&abs(b[1]-(last+first)/2)<=1&&b[2]==first,"each level wraps at its own length");
  }
  /* the sweep moves without steps and never back */
  int previous=-32768,maxStep=0,monotonic=1;
  for(unsigned k=0;k<=1000;k++) {
   memset(&o,0,sizeof(o));o.waveform=PWM+1;o.scanPos=k/1000.f;calcNextOscSampleBlock(&o,b,1,1.f,k/1000.f);
   if(k){monotonic&=b[0]>=previous;if(b[0]-previous>maxStep)maxStep=b[0]-previous;}
   previous=b[0];
  }
  check(monotonic&&maxStep<=25,"the PWM sweep is smooth");
  /* FM at zero depth and expo FM at zero depth equal the plain block, also while scanning */
  for(unsigned k=0;k<=4;k++) {
   OscInfo a,f,e;memset(&a,0,sizeof(a));a.waveform=PWM+1;a.phaseInc=0x01234000u; /* exact as a float, as expo FM computes it */a.tableOffset=5;a.fmMod=0;
   f=a;e=a;int16_t ba[16],bf[16],be[16];
   for(unsigned i=0;i<16;i++)m[i]=(int16_t)(i*2000-16000);
   calcNextOscSampleBlock(&a,ba,16,1.f,k/4.f);
   calcNextOscSampleFmBlock(&f,m,bf,16,1.f,k/4.f);
   calcExpoFmBlock(&e,m,be,16,k/4.f);
   check(!memcmp(ba,bf,sizeof(ba))&&a.phase==f.phase,"FM at zero depth is the plain wavetable");
   check(!memcmp(ba,be,sizeof(ba))&&a.phase==e.phase,"expo FM at zero depth is the plain wavetable");
  }
  /* FM moves the read position */
  {
   OscInfo a,f;memset(&a,0,sizeof(a));a.waveform=PWM+1;a.phaseInc=1u<<22;f=a;f.fmMod=0.5f;
   int16_t ba[16],bf[16];for(unsigned i=0;i<16;i++)m[i]=8000;
   calcNextOscSampleBlock(&a,ba,16,1.f,0.f);calcNextOscSampleFmBlock(&f,m,bf,16,1.f,0.f);
   check(memcmp(ba,bf,sizeof(ba))!=0,"FM changes the wavetable read");
  }
  memset(&o,0,sizeof(o));o.waveform=PWM+4;memset(b,1,sizeof(b));calcNextOscSampleFmBlock(&o,m,b,16,1.f,0.f);
  check(!b[0]&&!b[15],"FM on an empty slot is silent");
  /* a single wave scans on through the single waves after it */
  bankCount=4;
  AT_ZERO(PWM+2,0.f,7000+300-2048,"a single wave plays itself at PWM 0");
  AT_ZERO(PWM+2,0.5f,8000+300-2048,"half PWM reaches the middle single wave");
  AT_ZERO(PWM+2,0.25f,7500+300-2048,"a quarter blends the first two single waves");
  AT_ZERO(PWM+2,1.f,9000+300-2048,"full PWM reaches the last slot");
  AT_ZERO(PWM+3,0.f,8000+300-2048,"a later slot starts at itself");
  AT_ZERO(PWM+3,1.f,9000+300-2048,"a later slot scans to the last one too");
  AT_ZERO(PWM+4,0.7f,9000+300-2048,"the last slot ignores PWM");
  AT_ZERO(PWM+1,1.f,10000+300-2048,"a wavetable scans only its own frames");
  AT_ZERO(PWM+5,0.f,0,"past the count is silent");
  bankCount=2;
  /* the octave levels blend */
  memset(&o,0,sizeof(o));o.waveform=PWM+1;o.tableOffset=3;o.levelMix=16384;
  calcNextOscSampleBlock(&o,b,1,1.f,0.f);
  check(abs(b[0]-(-10000+350-2048))<=1,"half level mix blends two octave levels");
  memset(&o,0,sizeof(o));o.waveform=PWM+1;o.tableOffset=9;o.levelMix=32767;
  calcNextOscSampleBlock(&o,b,1,1.f,0.f);
  check(b[0]==-10000+900-2048,"the top level has no next level");
  {
   double prev=-1;int ok=1;
   for(float f=10.f;f<22000.f;f*=1.001f) {
    const uint8_t l=waveBank_level(f);
    const double level=l+osc_levelMix(f,l)/32767.;
    if(prev>=0&&(level<prev-1e-3||level-prev>0.01))ok=0;
    prev=level;
   }
   check(ok&&prev==WAVEBANK_LEVELS-1,"the octave levels fade into each other without a jump");
   check(osc_levelMix(54.9f,0)>32000&&osc_levelMix(56.f,1)<1000&&osc_levelMix(20.f,0)==0&&osc_levelMix(15000.f,9)==0,"level mix edges");
  }
  /* the scan glides to a new PWM value */
  memset(&o,0,sizeof(o));o.waveform=PWM+1;o.tableOffset=3;
  calcNextOscSampleBlock(&o,b,1,1.f,1.f);
  check(fabsf(o.scanPos-OSC_SCAN_GLIDE)<1e-6f&&abs(b[0]-(-8000+300-2048))<=2,"the scan glides to a new PWM value");
  for(unsigned k=0;k<200;k++)calcNextOscSampleBlock(&o,b,1,1.f,1.f);
  check(o.scanPos>0.999f,"the scan arrives");
 }

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
 /* A falling amount, block by block like the pitch EG: no step at the block edges.
    The second difference of a smooth curve stays small; a shape step shows up in it. */
 {
  OscInfo o;memset(&o,0,sizeof(o));o.phaseInc=1u<<20;
  int16_t b[64];int prev2=0,prev1=0,first=2,worst=0;
  for(unsigned k=0;k<64;k++) {
   o.fmMod=1.f-k/64.f;
   calcPhaseDistBlock(&o,b,64);
   for(unsigned i=0;i<64;i++) {
    if(!first){const int d=abs(b[i]-2*prev1+prev2);if(d>worst)worst=d;} else first--;
    prev2=prev1;prev1=b[i];
   }
  }
  check(worst<PD_SWEEP_LIMIT,"a falling PD amount glides without steps");
 }
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
 {
  /* samples: the dispatchers, expo FM and PD play them through the sample blocks */
  OscInfo o;memset(&o,0,sizeof(o));o.waveform=SAMPLEBANK_FIRST_WAVE+2;
  int16_t m[8]={0},b[8];
  sampleCalls=sampleFmCalls=0;
  calcNextOscSampleBlock(&o,b,8,1.f,0.f);check(sampleCalls==1&&b[7]==1234,"plain dispatcher plays the sample");
  calcNextOscSampleFmBlock(&o,m,b,8,1.f,0.f);check(sampleFmCalls==1&&b[0]==4321,"FM dispatcher plays the sample with FM");
  calcExpoFmBlock(&o,m,b,8,0.f);check(sampleCalls==2&&b[0]==1234,"expo FM plays a sample plain");
  calcPhaseDistBlock(&o,b,8);check(sampleCalls==3&&b[0]==1234,"PD plays a sample plain");
  o.waveform=SAMPLEBANK_FIRST_WAVE-1;bankCount=4;memset(b,1,sizeof(b));
  calcNextOscSampleBlock(&o,b,8,1.f,0.f);check(sampleCalls==3&&!b[0],"the last wavetable slot is no sample");
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
    menu_source = read('Core/Src/menu/menu.c')
    for v in '123':
        # the modulator offers the user wavetables too; DrumVoice plays it through calcNextOscSampleBlock
        assert f'/*PAR_MOD_WAVE_DRUM{v}*/  DTYPE_MENU | (MENU_WAVEFORM_WT<<8)' in menu_source
    assert 'calcNextOscSampleBlock(&voiceArray[voiceNr].modOsc' in drum
    # 0.2.49: the main waves of Snare, Cymbal and HiHat offer the user wavetables;
    # both osc dispatchers play every wave above PWM from the wave bank
    for par in ('PAR_OSC_WAVE_SNARE*/  DTYPE_MENU', 'PAR_WAVE1_CYM*/  \t\tDTYPE_MENU', 'PAR_WAVE1_HH*/  \t\tDTYPE_MENU'):
        assert '/*' + par + ' | (MENU_WAVEFORM_WT<<8)' in menu_source, par
    # 0.2.51: the Cymbal and HiHat modulators and the snare layer offer wavetables and samples too
    for par in ('PAR_WAVE2_CYM', 'PAR_WAVE3_CYM', 'PAR_WAVE2_HH', 'PAR_WAVE3_HH'):
        assert '/*' + par + '*/ \t\tDTYPE_MENU | (MENU_WAVEFORM_WT<<8)' in menu_source, par
    assert '/*PAR_SNARE_LAYER_WAVE*/ DTYPE_MENU | (MENU_WAVEFORM_WT<<8)' in menu_source
    osc_source = read('Core/Src/Soundengine/DSPAudio/Oscillator.c')
    for dispatcher, call in (('calcNextOscSampleBlock', 'calcWaveBankBlock(osc,buf,size,gain,pwm);'),
                             ('calcNextOscSampleFmBlock', 'calcWaveBankFmBlock(osc,modBuffer,buf,size,gain,pwm);')):
        body = osc_source[osc_source.index('IN_ITCM_RAM void ' + dispatcher + '('):]
        body = body[:body.index('\n}')]
        assert 'default:' in body and call in body, dispatcher
    assert 'isFloatModulator ? (uint8_t)(v*4.f+0.5f) : value.itg > 4 ? 4 : value.itg' in parser
    assert 'originalValue=activeParameters[destination]/4.f' in node
    menu = re.search(r'mixFmNames\[\]\[6\] =\s*\{(.*?)\};', names, re.S).group(1)
    assert re.findall(r'\{(.*?)\}', menu) == ['5', '"FM"', '"Mix"', '"rng"', '"exp"', '"pd"']

    defines = ''.join(re.findall(r'#define (?:EXPO_FM_OCTAVES|OSC_MAX_PHASE_INC|PD_MIN_KNEE|OSC_SCAN_GLIDE).*\n', header)).replace('#define', '\n#define')
    struct = re.search(r'typedef struct OscStruct.*?\} OscInfo;', header, re.S).group(0)
    oscillator = oscillator.replace('\r\n', '\n')
    bank = read('Core/Inc/Soundengine/DSPAudio/WaveBank.h').replace('\r\n', '\n')
    bank_defines = ''.join(re.findall(r'#define WAVEBANK_(?:MAX|LEVELS|FRAME_SAMPLES) .*\n', bank))
    bank_helpers = '\n'.join(extract(bank, sig) for sig in
                             ('static inline uint8_t waveBank_levelBits', 'static inline uint16_t waveBank_levelOffset'))
    scan_type = re.search(r'typedef struct\s*\{[^}]*\} WaveBankScan;', oscillator).group(0)
    bodies = [extract(oscillator, s) for s in (
        'static inline float osc_expoRatio', 'static inline int16_t osc_readTable')]
    bodies.append(scan_type)
    bodies += [extract(oscillator, s) for s in (
        'static inline uint16_t osc_levelMix', 'static uint8_t osc_waveBankScan', 'static inline int16_t osc_readLevel',
        'static inline int16_t osc_readFrame', 'static inline int16_t osc_readScan',
        'void calcWaveBankBlock(OscInfo', 'void calcWaveBankFmBlock(OscInfo',
        'static inline int16_t osc_readSine', 'IN_ITCM_RAM void calcExpoFmBlock',
        'IN_ITCM_RAM void calcPhaseDistBlock', 'IN_ITCM_RAM void calcNextOscSampleFmBlock',
        'IN_ITCM_RAM void calcNextOscSampleBlock')]
    wavebank = read('Core/Src/Soundengine/DSPAudio/WaveBank.c').replace('\r\n', '\n')
    bodies.append(extract(wavebank, 'uint8_t waveBank_level(float freq)'))
    source = '\n'.join(bodies)
    if '--mutate' in sys.argv:
        source = source.replace('if(inc>OSC_MAX_PHASE_INC) inc = OSC_MAX_PHASE_INC;', '')
        source = source.replace('0.5f - amount*(0.5f-minKnee)', '0.5f')
        old = 'else calcWaveBankBlock(osc,buf,size,gain,pwm);'
        assert old in source, 'mutation anchor'
        source = source.replace(old, ';')
        old = 'if(osc_isSample(osc)) calcSampleBankBlock(osc,buf,size,gain);'
        assert old in source, 'mutation anchor'
        source = source.replace(old, 'if(0);')
        old = 'const float knee = start + kneeStep*(i+1);'
        assert old in source, 'mutation anchor'
        source = source.replace(old, 'const float knee = target;')
        old = 'level < WAVEBANK_LEVELS-1 ? osc->levelMix : 0'
        assert old in source, 'mutation anchor'
        source = source.replace(old, '0')
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        out = Path(folder)
        (out / 'contract.c').write_text(PRELUDE + defines + bank_defines + struct + bank_helpers + STUBS + source + TESTS, encoding='utf-8')
        command = (f'call "{VS}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /Fe:contract.exe contract.c '
                   f'&& .\\contract.exe')
        subprocess.run(command, shell=True, cwd=out, check=True)


if __name__ == '__main__':
    main()
