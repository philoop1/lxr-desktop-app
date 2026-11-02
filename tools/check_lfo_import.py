"""Compare the imported LFO trajectories against Mutador with identical RNG streams."""
from pathlib import Path
import re,os,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/lfo-audit';OUT.mkdir(parents=True,exist_ok=True)
def function(src,name):
 m=re.search(r'[^\n]*\b'+name+r'\([^)]*\)\s*\{',src);assert m,name
 pos=m.end();depth=1
 while depth:
  depth+=(src[pos]=='{')-(src[pos]=='}');pos+=1
 return src[m.start():pos].replace('IN_ITCM_RAM ','')
target=(ROOT/'Core/Src/Soundengine/DSPAudio/lfo.c').read_text()
ref=(ROOT.parent/'mutador/mainboard/LxrStm32/src/DSPAudio/lfo.c').read_text()
header=(ROOT/'Core/Inc/Soundengine/DSPAudio/lfo.h').read_text()
struct=re.search(r'typedef struct LfoStruct.*?} Lfo;',header,re.S)[0]
enum=re.search(r'enum\s*\{.*?NUM_LFO_WAVEFORMS\s*\};',header,re.S)[0]
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
for name in names:code+=function(target,name)+'\n'
ref_code='\n'.join(function(ref,name) for name in names)
ref_code=re.sub(r'\blfo_(\w+)',r'ref_lfo_\1',ref_code).replace('GetRngValue()','ref_GetRngValue()')
code+=ref_code+r"""
static unsigned checks;
void check(int ok,const char *msg){checks++;if(!ok){puts(msg);exit(1);}}
int main(void){
 for(unsigned i=0;i<4096;i++)sine_table[i]=(int16_t)(sinf((float)i*6.283185307f/4096.f)*32767);
 for(unsigned wave=0;wave<LFO_RANDOM_STEP;wave++)for(unsigned offset=0;offset<128;offset+=31){
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
