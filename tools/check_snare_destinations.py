"""Native audit of stable target IDs, target selection and the LFO dispatch path."""
from pathlib import Path
import re, os, subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/snare-destination-audit'; OUT.mkdir(parents=True,exist_ok=True)
def read(p): return (ROOT/p).read_text()
def function(src,name):
 m=re.search(r'[^\n]*\b'+name+r'\([^)]*\)\s*\{',src); assert m,name
 pos=m.end();depth=1
 while depth:
  depth+=(src[pos]=='{')-(src[pos]=='}');pos+=1
 return src[m.start():pos].replace('IN_ITCM_RAM ','')
cc=read('Core/Src/menu/Cc2Text.c')
texts=sorted(set(re.findall(r'TEXT_\w+',cc)))
code='#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include "Parameters.h"\n'
code+='enum {'+','.join(texts)+'};\n'
code+=r"""
#define pgm_read_byte(p) (*(const uint8_t*)(p))
#define pgm_read_word(p) (*(const uint16_t*)(p))
typedef struct {uint8_t nameIdx;uint16_t param;} ModTarg;
typedef struct {uint8_t start,end;} ModTargetVoiceOffset;
uint8_t voiceFromModTargValue(uint8_t);
"""
code+='\n'.join(line for line in cc.splitlines() if not line.startswith('#include'))
code+=r"""
typedef union {uint32_t itg;float flt;} ptrValue;
typedef struct {void *ptr;uint8_t type;} Parameter;
typedef struct {uint16_t destination;float amount,lastVal;ptrValue originalValue;} ModulationNode;
typedef struct {uint8_t status,data1,data2;} MidiMsg;
enum {MIDI_CC=0xb0,CC_2=0xa0};
Parameter parameterArray[END_OF_SOUND_PARAMETERS];
uint8_t activeParameters[NUM_PARAMS];
static unsigned applied;
uint8_t menu_getWaveformMax(void){return 5;}
void Snare_setNoiseAttack(uint8_t v){applied=v;}
void Snare_setNoiseDecay(uint8_t v){applied=v;}
void Snare_setNoiseSlope(uint8_t v){applied=v;}
void Snare_setLayerWave(uint8_t v){applied=v;}
void Snare_setLayerAmount(uint8_t v){applied=v;}
void Snare_setLayerFreq(uint8_t v){applied=v;}
void Snare_setLayerMode(uint8_t v){applied=v>2?2:v;}
void midiParser_ccHandler(MidiMsg msg,uint8_t update,uint8_t isFloatModulator,float v){
 struct {uint8_t itg;float flt;} value;
 value.itg=isFloatModulator?(uint8_t)(v*127):msg.data2;
 switch(msg.data1){
"""
parser=read('Core/Src/Soundengine/MIDI/MidiParser.c')
a=parser.index('case PAR_SNARE_NOISE_ATTACK-128:');b=parser.index('case CC2_VOLUME_MOD_ON_OFF1:',a)
code+=parser[a:b]+'}}\n'
code+=function(read('Core/Src/Soundengine/DSPAudio/modulationNode.c'),'modNode_updateValue')
# Exercise the production LFO/velocity CC destination handlers as well.
for prefix in ['VOICE_LFO','TARGET_LFO','VEL_DEST_']:
 for i in range(1,7):
  enum_name='CC2_'+prefix+str(i)
  param='PAR_'+prefix+str(i)
  code+=f'\n#define {enum_name} ({param}-128)\n'
code+=r"""
typedef struct {ModulationNode modTarget;} Lfo;
Lfo lfos[6];ModulationNode velocityModulators[6];
Lfo *midiParser_voiceLfo(uint8_t voice){return &lfos[voice];}
void modNode_setDestination(ModulationNode *m,uint16_t destination){m->destination=destination;}
void targetCc(uint8_t cc,uint8_t data){
 MidiMsg msg={0};msg.data1=cc;
 struct {uint8_t itg;} value;value.itg=data;
 switch(cc){
"""
a1=parser.index('case CC2_VEL_DEST_1:');b1=parser.index('case CC2_VELO_MOD_AMT_1:',a1)
a2=parser.index('case CC2_VOICE_LFO1:');b2=parser.index('case CC2_OFFSET_LFO1:',a2)
code+=parser[a1:b1]+parser[a2:b2]+'}}\n'
code+=r"""
static unsigned checks;
void check(int ok,const char *msg){checks++;if(!ok){puts(msg);exit(1);}}
int main(void){
 check(getNumModTargets()==242,"target count");
 check(modTargetVoiceOffsets[3].start==116&&modTargetVoiceOffsets[3].end==152,"legacy snare indices");
 check(modTargets[153].param==PAR_COARSE5&&modTargets[191].param==PAR_COARSE6,"legacy cymbal and hat indices");
 for(unsigned i=229;i<=235;i++){
  check(voiceFromModTargValue(i)==4,"appended snare voice");
  uint8_t gap=getModTargetGapIndex(i);
  check(getModTargetIdxFromGapIdx(3,gap)==i,"snare gap roundtrip");
  check(getModTargetIdxFromGapIdx(0,gap)==0,"other voice turns snare-only target off");
 }
 check(modTargetClampVoice(3,153,1)==229,"encoder crosses extension gap forward");
 check(modTargetClampVoice(3,228,-1)==152,"encoder crosses extension gap backward");
 check(modTargetClampVoice(3,239,1)==239,"extension end clamp");
 check(modTargetClampVoice(3,236,1)==239&&modTargetClampVoice(3,238,-1)==235,"encoder reaches dry/wet");
 for(unsigned v=0;v<6;v++){
  const unsigned wet=236+v,end=modTargetVoiceOffsets[v].end;
  check(modTargets[wet].param==PAR_FX_DRY_WET&&voiceFromModTargValue(wet)==v+1,"dry/wet per voice");
  check(modTargetFromFraction(v,1)==wet,"pot reaches dry/wet");
  check(modTargetClampVoice(v,250,1)==wet,"dry/wet end clamp");
  if(v!=3)check(modTargetClampVoice(v,end+1,1)==wet&&modTargetClampVoice(v,wet-1,-1)==end,"encoder steps between list and dry/wet");
  for(unsigned o=0;o<6;o++)check(getModTargetIdxFromGapIdx(o,getModTargetGapIndex(wet))==236+o,"dry/wet survives a voice change");
 }
 check(modTargetFromFraction(3,0)==0&&modTargetFromFraction(3,1)==239&&modTargetFromFraction(3,0.96f)==235,"pot reaches extension");
 for(unsigned i=229;i<=235;i++){
  unsigned id=modTargets[i].param;
  parameterArray[id].ptr=&activeParameters[id];
  activeParameters[id]=(id==PAR_SNARE_LAYER_MODE)?1:(id==PAR_SNARE_LAYER_WAVE)?2:63;
  ModulationNode node={0};node.destination=id;node.amount=1;
  modNode_updateValue(&node,0);check(applied==0,"LFO minimum reaches setter");
  modNode_updateValue(&node,1);
  check(applied==((id==PAR_SNARE_LAYER_MODE)?2:(id==PAR_SNARE_LAYER_WAVE)?5:127),"LFO maximum reaches setter");
  node.amount=0;modNode_updateValue(&node,0.75f);
  check(applied==activeParameters[id],"zero depth preserves selected base value");
 }
 paramToModTargetInit();
 for(unsigned voice=0;voice<6;voice++){
  targetCc(CC2_TARGET_LFO1+voice,PAR_PAN4);
  check(lfos[voice].modTarget.destination==PAR_PAN4&&activeParameters[PAR_VOICE_LFO1+voice]==4,"CC81 connects target and display");
  targetCc(CC2_VOICE_LFO1+voice,1);
  check(lfos[voice].modTarget.destination==PAR_PAN1&&activeParameters[PAR_VOICE_LFO1+voice]==1,"CC80 moves logical target to selected voice");
  if(voice<3){
    const uint8_t coarse[3]={PAR_COARSE1,PAR_COARSE2,PAR_COARSE3};
    targetCc(CC2_TARGET_LFO1+voice,coarse[voice]);
    check(lfos[voice].modTarget.destination==coarse[voice],"each drum LFO reaches its own coarse parameter");
  }
  targetCc(CC2_TARGET_LFO1+voice,0);
  check(lfos[voice].modTarget.destination==0&&activeParameters[PAR_TARGET_LFO1+voice]==0,"CC81 off");
  targetCc(CC2_VEL_DEST_1+voice,PAR_PAN4);
  check(velocityModulators[voice].destination==PAR_PAN4&&activeParameters[PAR_VEL_DEST_1+voice]==paramToModTarget[PAR_PAN4],"CC25 connects velocity target and display");
 }
 printf("SNARE DESTINATIONS PASS %u assertions\n",checks);return 0;
}
"""
(OUT/'contract.c').write_text(code)
(OUT/'Parameters.h').write_text(read('Core/Inc/Parameters.h'))
(OUT/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
if os.name=='nt':
 vs=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
 subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:contract.exe contract.c && contract.exe',shell=True,cwd=OUT,check=True)
else:
 subprocess.run(['cc','-std=c11','-o','contract','contract.c'],cwd=OUT,check=True)
 subprocess.run([str(OUT/'contract')],cwd=OUT,check=True)
