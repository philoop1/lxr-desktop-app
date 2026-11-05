"""Compare the imported LFO trajectories against Mutador with identical RNG streams.

The xtr wave and the one-shots (Mutador 0.2.49) are not in the reference; they
are checked against the looping waves instead. --mutate runs each one-shot
mutation and expects the check to fail.
"""
from pathlib import Path
import re,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/lfo-audit';OUT.mkdir(parents=True,exist_ok=True)
def function(src,name):
 m=re.search(r'[^\n]*\b'+name+r'\([^)]*\)\s*\{',src);assert m,name
 pos=m.end();depth=1
 while depth:
  depth+=(src[pos]=='{')-(src[pos]=='}');pos+=1
 return src[m.start():pos].replace('IN_ITCM_RAM ','')
target=(ROOT/'Core/Src/Soundengine/DSPAudio/lfo.c').read_text()
MUTATIONS={
 'no-hold':('if(lfo->phase<oldPhase) lfo->shot = LFO_SHOT_DONE;',''),
 'no-delay':('lfo->shot = lfo->phaseOffset ? LFO_SHOT_WAIT : LFO_SHOT_RUN;','lfo->shot = LFO_SHOT_RUN;'),
 'square-not-inverted':('return phase > 0x7fffffff ? 0.f : 1.f;','return phase > 0x7fffffff ? 1.f : 0.f;'),
 'noise-not-rerolled':('if(lfo->shot==LFO_SHOT_RUN && lfo->waveform==LFO_ONESHOT_NOISE) lfo_setRandomValue(lfo);',''),
 'rps-selectable':('if(waveform >= NUM_LFO_WAVEFORMS)','if(waveform > NUM_LFO_WAVEFORMS)'),
 'xtr-linear':('\t\t\t\treturn t*t*t;\n','\t\t\t\treturn t;\n'),
}
if '--mutate' in sys.argv:
 missed=[]
 for name in MUTATIONS:
  r=subprocess.run([sys.executable,__file__,'--mutation='+name],capture_output=True,text=True)
  print(('caught ' if r.returncode else 'MISSED ')+name)
  if not r.returncode:missed.append(name)
 sys.exit(1 if missed else 0)
for arg in sys.argv[1:]:
 if arg.startswith('--mutation='):
  old,new=MUTATIONS[arg.split('=',1)[1]]
  assert target.count(old)==1,old
  target=target.replace(old,new)
ref=(ROOT.parent/'mutador/mainboard/LxrStm32/src/DSPAudio/lfo.c').read_text()
header=(ROOT/'Core/Inc/Soundengine/DSPAudio/lfo.h').read_text()
struct=re.search(r'typedef struct LfoStruct.*?} Lfo;',header,re.S)[0]
enum=re.search(r'enum\s*\{.*?NUM_LFO_WAVEFORMS\s*\};',header,re.S)[0]
enum+='\n'+'\n'.join(re.findall(r'#define LFO_(?:ONESHOT_FIRST|SHOT_\w+) \w+',header))
names=['lfo_random01','lfo_setRandomValue','lfo_reflectUnitRange','lfo_setSmoothRandomTarget','lfo_advanceSmoothRandom','lfo_calcSmoothRandom','lfo_applySmoothRandomBias','lfo_setRandomValueFromOffset','lfo_updateHeldRandomFromOffset','lfo_init','lfo_calc','lfo_dispatchNextValue','lfo_calcPhaseInc','lfo_setFreq','lfo_setWaveform','lfo_setPhaseOffset','lfo_setSync','lfo_retriggerVoice']
code=r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
typedef struct {float amount;} ModulationNode;
#define SINE 0
#define LFO_MAX_F 200
#define LFO_SR 1000.f
int16_t sine_table[4096];
uint32_t rng=1234567,ref_rng=1234567;
uint32_t GetRngValue(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
uint32_t ref_GetRngValue(void){ref_rng^=ref_rng<<13;ref_rng^=ref_rng>>17;ref_rng^=ref_rng<<5;return ref_rng;}
float seq_getBpm(void){return 120;}
float sent,ref_sent;
void modNode_init(ModulationNode *m){m->amount=0;}
void modNode_updateValue(ModulationNode *m,float v){(void)m;sent=v;}
void modNode_updateLfoValue(ModulationNode *m,float v,float source,uint32_t offset){(void)m;(void)source;(void)offset;ref_sent=v;}
"""
code+=enum+'\n'+struct+'\n'
target_only=['lfo_isOneShot','lfo_shapeAt','lfo_calcOneShot']
for name in names:
 if name=='lfo_calc':
  for extra in target_only:code+=function(target,extra).replace('__attribute__((noinline)) ','')+'\n'
 code+=function(target,name)+'\n'
ref_code='\n'.join(function(ref,name) for name in names)
ref_code=re.sub(r'\blfo_(\w+)',r'ref_lfo_\1',ref_code).replace('GetRngValue()','ref_GetRngValue()')
code+=ref_code+r"""
static unsigned checks;
void check(int ok,const char *msg){checks++;if(!ok){puts(msg);exit(1);}}
int main(void){
 for(unsigned i=0;i<4096;i++)sine_table[i]=(int16_t)(sinf((float)i*6.283185307f/4096.f)*32767);
 for(unsigned wave=0;wave<=LFO_GLIDE;wave++)for(unsigned offset=0;offset<128;offset+=31){
  Lfo a,b;rng=ref_rng=34567;
  lfo_init(&a);ref_lfo_init(&b);
  lfo_setWaveform(&a,wave);ref_lfo_setWaveform(&b,wave);
  lfo_setPhaseOffset(&a,offset);ref_lfo_setPhaseOffset(&b,offset);
  lfo_setFreq(&a,64.f/127.f);ref_lfo_setFreq(&b,64.f);
  check(a.phaseInc==b.phaseInc,"normalized frequency mapping");
  for(unsigned step=0;step<3000;step++){
   if(step==1500){lfo_retriggerVoice(&a);ref_lfo_retriggerVoice(&b);}
   lfo_dispatchNextValue(&a);ref_lfo_dispatchNextValue(&b);
   float expected=wave>=LFO_STRAY?ref_sent*0.5f:ref_sent;
   if(fabsf(sent-expected)>=0.000001f)printf("wave %u offset %u step %u: %f expected %f\n",wave,offset,step,sent,expected);
   check(fabsf(sent-expected)<0.000001f,"LFO output follows Mutador reference");
   check(a.phase==b.phase&&rng==ref_rng,"phase/retrigger/RNG follow reference");
   check(sent>=0&&sent<=1,"normalized desktop LFO output range");
  }
 }
 for(unsigned wave=0;wave<10;wave++){
  Lfo a,b;rng=ref_rng=9324;lfo_init(&a);ref_lfo_init(&b);
  lfo_setWaveform(&a,wave);ref_lfo_setWaveform(&b,wave);
  lfo_setFreq(&a,0);ref_lfo_setFreq(&b,0);
  lfo_setPhaseOffset(&a,63);ref_lfo_setPhaseOffset(&b,63);
  lfo_retriggerVoice(&a);ref_lfo_retriggerVoice(&b);
  check(a.phaseInc==0&&a.phase==b.phase&&a.rnd==b.rnd,"stopped LFO and held-random retrigger");
 }
 Lfo endpoint;lfo_init(&endpoint);lfo_setPhaseOffset(&endpoint,127);
 check(endpoint.phaseOffset==UINT32_MAX,"offset upper endpoint avoids float conversion overflow");
 Lfo a;lfo_init(&a);lfo_setWaveform(&a,127);check(a.waveform==LFO_SINE,"invalid wave defaults safely");
 lfo_init(&a);lfo_setWaveform(&a,LFO_RANDOM_STEP);check(a.waveform==LFO_SINE,"rps is not an LFO wave any more");
 // xtr: the triangle cubed
 {
  Lfo x,t;lfo_init(&x);lfo_init(&t);lfo_setWaveform(&x,LFO_EXP_TRI);lfo_setWaveform(&t,LFO_TRI);
  lfo_setFreq(&x,64.f/127.f);lfo_setFreq(&t,64.f/127.f);
  float peak=0;
  for(unsigned n=0;n<500;n++){const float v=lfo_calc(&x),w=lfo_calc(&t);check(fabsf(v-w*w*w)<1e-6f,"xtr is exponential up and down");if(v>peak)peak=v;}
  check(peak>0.9f,"xtr reaches the top");
 }
 // one-shots: one cycle like the looping wave, then hold the end value
 {
  const uint8_t bases[9]={LFO_SINE,LFO_TRI,LFO_SAW_UP,LFO_SAW_DOWN,LFO_REC,LFO_NOISE,LFO_EXP_UP,LFO_EXP_DOWN,LFO_EXP_TRI};
  const float ends[9]={0.5f,0.f,1.f,0.f,0.f,-1.f,1.f,0.f,0.f};
  for(unsigned k=0;k<9;k++){
   const uint8_t wave=(uint8_t)(LFO_ONESHOT_FIRST+k),base=bases[k];
   Lfo one,loop;lfo_init(&one);lfo_init(&loop);
   lfo_setFreq(&one,64.f/127.f);lfo_setFreq(&loop,64.f/127.f);
   lfo_setWaveform(&loop,base);lfo_setWaveform(&one,wave);
   check(one.shot==LFO_SHOT_RUN,"a chosen one-shot runs once without a retrigger");
   for(int round=0;round<2;round++){
    lfo_retriggerVoice(&one);lfo_retriggerVoice(&loop);
    const float held=one.rnd;
    const unsigned cycle=(unsigned)(4294967296.0/one.phaseInc);
    check(cycle>10,"test rate gives a usable cycle");
    for(unsigned n=0;n+1<cycle;n++){
     const float v=lfo_calc(&one),w=lfo_calc(&loop);
     if(base==LFO_NOISE)check(v==held,"rn1 holds one value per trigger");
     else if(base==LFO_REC)check(v==1.f-w,"sq1 is on first, then off");
     else check(fabsf(v-w)<1e-6f,"a one-shot follows its looping wave for one cycle");
    }
    for(unsigned n=0;n<3 && one.shot!=LFO_SHOT_DONE;n++)lfo_calc(&one); /* the cycle ends within a step */
    float last=lfo_calc(&one);
    for(unsigned n=0;n<3*cycle;n++){
     const float v=lfo_calc(&one);
     check(v==last,"a one-shot holds after its cycle");last=v;
    }
    check(one.shot==LFO_SHOT_DONE,"a one-shot ends");
    if(base==LFO_NOISE)check(last==held,"rn1 keeps its value");
    else check(fabsf(last-ends[k])<0.01f,"a one-shot holds the end of its shape");
   }
  }
  // two triggers give two random values
  Lfo n;lfo_init(&n);lfo_setFreq(&n,64.f/127.f);lfo_setWaveform(&n,LFO_ONESHOT_NOISE);
  lfo_retriggerVoice(&n);const float first=lfo_calc(&n);
  lfo_retriggerVoice(&n);check(lfo_calc(&n)!=first,"rn1 rolls a new value on every trigger");
  // the offset delays the start by part of a cycle
  for(unsigned k=0;k<9;k++){
   const uint8_t wave=(uint8_t)(LFO_ONESHOT_FIRST+k),base=bases[k];
   Lfo d;lfo_init(&d);lfo_setFreq(&d,64.f/127.f);lfo_setWaveform(&d,wave);lfo_setPhaseOffset(&d,63);
   lfo_retriggerVoice(&d);
   check(d.shot==LFO_SHOT_WAIT,"an offset makes the one-shot wait");
   const unsigned cycle=(unsigned)(4294967296.0/d.phaseInc);
   const float rest=lfo_calc(&d);
   unsigned waited=1;
   while(d.shot==LFO_SHOT_WAIT && waited<4*cycle){const float v=lfo_calc(&d);if(d.shot==LFO_SHOT_WAIT)check(v==rest,"the one-shot rests while it waits");waited++;}
   check(waited+2>=cycle/2 && waited<=cycle/2+2,"offset 63 waits about half a cycle");
   if(base==LFO_REC){check(rest==0.f,"sq1 is off while it waits");check(lfo_calc(&d)==1.f,"sq1 switches on after the wait");}
  }
 }
 printf("LFO IMPORT PASS %u assertions\n",checks);return 0;
}
"""
(OUT/'contract.c').write_text(code)
if os.name=='nt':
 vs=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
 subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:contract.exe contract.c && contract.exe',shell=True,cwd=OUT,check=True)
else:
 subprocess.run(['cc','-std=c11','-o','contract','contract.c','-lm'],cwd=OUT,check=True)
 subprocess.run([str(OUT/'contract')],cwd=OUT,check=True)
