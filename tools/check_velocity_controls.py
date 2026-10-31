"""Native velocity math, production trigger flow and any-mode pattern shortcut audit."""
from pathlib import Path
import os,re,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/velocity-controls-audit';OUT.mkdir(parents=True,exist_ok=True)
def read(p):return (ROOT/p).read_text()
def function(src,name):
 m=re.search(r'[^\n]*\b'+name+r'\([^{};]*\)\s*\{',src);assert m,name
 pos=m.end();depth=1
 while depth:
  depth+=(src[pos]=='{')-(src[pos]=='}');pos+=1
 return src[m.start():pos]
code=r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Parameters.h"
uint32_t randomWord;unsigned randomCalls;
uint32_t GetRngValue(void){randomCalls++;return randomWord;}
uint8_t seq_perfRandomVelocity;
"""
steps=read('Core/Src/Soundengine/Sequencer/PerformanceSteps.c')
for n in ['perf_randomVelocity','perf_adjustVelocity','perf_formatVelocityGain']:code+=function(steps,n)+'\n'
reference=(ROOT.parent/'mutador/mainboard/LxrStm32/src/Sequencer/sequencer.c').read_text()
code+=function(reference,'seq_randomizeVelocityValue')
code+=r"""
#define USE_PATTERN_EDIT_BUFFER 0
uint8_t activeParameters[NUM_PARAMS],midi_MidiChannels[8],seq_activePattern;
uint8_t seq_triggerSourceStep[7]={255,255,255,255,255,255,255},seq_stepIndex[7];
struct {uint8_t seq_subStepPattern[1][7][64];}seq_patternSet;
unsigned automations,triggered,modulated,output,active_voices,front;
uint8_t soundVelocity,modVelocity,outVelocity;
void seq_parseAutomationNodes(uint8_t voice,void *step){(void)voice;(void)step;automations++;}
void voiceControl_noteOff(uint8_t voice){(void)voice;}
uint8_t midiParser_applyPerformanceVelocity(uint8_t voice,uint8_t velocity,uint8_t note){(void)voice;modulated++;modVelocity=velocity;return note;}
void Drum_trigger(uint8_t voice,uint8_t velocity,uint8_t note){(void)voice;(void)note;triggered++;soundVelocity=velocity;}
void Snare_trigger(uint8_t velocity,uint8_t note){Drum_trigger(3,velocity,note);}
void Cymbal_trigger(uint8_t velocity,uint8_t note){Drum_trigger(4,velocity,note);}
void HiHat_trigger(uint8_t velocity,uint8_t open,uint8_t note){Drum_trigger(5+open,velocity,note);}
void seq_sendMidiNoteOn(uint8_t channel,uint8_t note,uint8_t velocity){(void)channel;(void)note;output++;outVelocity=velocity;}
#define NOTE_ON 144
void uart_sendFrontpanelByte(uint8_t value){(void)value;front++;}
"""
voice=read('Core/Src/Soundengine/MIDI/MidiVoiceControl.c')
for n in ['voiceControl_trigger','voiceControl_noteOnNoEchoWithMod']:code+=function(voice,n)+'\n'
code+=function(read('Core/Src/Soundengine/Sequencer/sequencer.c'),'seq_triggerVoice')
code+=r"""
#define NO_STEP_SELECTED -1
#define SELECT_MODE_PATTERN 8
#define SELECT_MODE_PERF 1
#define SEQ_DRUM1 0
uint8_t shift,copyClear_Mode,currentPage,layer,modeLED;
int8_t buttonHandler_buttonTimerStepNr;
struct {uint8_t selectButtonMode;}buttonHandler_stateMemory;
unsigned shortcuts,disarmed;
uint8_t buttonHandler_getShift(void){return shift;}
void buttonHandler_disarmTimerActionStep(void){disarmed++;}
void copyClear_reset(void){copyClear_Mode=0;}
void menu_openPerformanceLayer(uint8_t page){currentPage=10;layer=page;}
void led_setMode2(uint8_t mode){modeLED=mode;}
void led_initPatternSelectLeds(void){shortcuts++;}
"""
btn=read('Core/Src/buttonHandler.c');code+=function(btn,'buttonHandler_enterPatternShortcut')
prefix=function(btn,'buttonHandler_seqButtonPressed');prefix=prefix[:prefix.index('if(copyClear_Mode')]
code+=prefix+'}\n'
code+=r"""
static unsigned checks;
void check(int ok,const char *msg){checks++;if(!ok){puts(msg);exit(1);}}
int main(void){
 const uint32_t words[]={0,1,99,123456789u,0xffffffffu};
 for(unsigned velocity=0;velocity<128;velocity++)for(unsigned floor=0;floor<=100;floor++)for(unsigned r=0;r<5;r++){
  randomWord=words[r];seq_perfRandomVelocity=floor;
  check(perf_randomVelocity(velocity,floor,GetRngValue)==seq_randomizeVelocityValue(velocity),"Rvl matches Mutador arithmetic");
 }
 for(unsigned v=0;v<128;v++){
  unsigned previous=0;
  for(unsigned gain=0;gain<=200;gain++){
   unsigned result=perf_adjustVelocity(v,gain);
   check(result<=127&&result>=previous,"AVL is bounded and monotonic");previous=result;
   if(gain<=100)check(result==((v*gain+50)/100),"negative percent attenuates original velocity");
   else check(result==(((v*gain+50)/100)>127?127:((v*gain+50)/100)),"positive percent uses proportional gain and clips at 127");
  }
  check(perf_adjustVelocity(v,0)==0&&perf_adjustVelocity(v,100)==v&&perf_adjustVelocity(v,200)==(v*2>127?127:v*2),"AVL mute, neutral and double gain");
 }
 for(unsigned gain=0;gain<=200;gain++){
  char text[6]={'L',' ',' ',' ',' ','R'},number[5]={0};perf_formatVelocityGain(&text[1],gain);
  memcpy(number,&text[1],4);
  check(text[0]=='L'&&text[5]=='R'&&atoi(number)==(int)gain-100,"four-cell signed percent display");
 }
 for(unsigned voice=0;voice<7;voice++)for(unsigned velocity=0;velocity<128;velocity++)for(unsigned gain=0;gain<=200;gain+=25){
  for(unsigned floor=0;floor<=100;floor+=50){
   automations=triggered=modulated=output=front=0;randomCalls=0;randomWord=0;
   activeParameters[PAR_PERF_RANDOM_VELO]=floor;activeParameters[PAR_PERF_AVL]=gain;
   seq_triggerVoice(voice,velocity,60);
   unsigned randomized=(velocity*floor+50)/100;
   unsigned expectedAudio=perf_adjustVelocity(voice==0?velocity:randomized,gain);
   unsigned expectedMod=perf_adjustVelocity(randomized,gain);
   check(automations==1&&triggered==1&&modulated==1&&output==1&&front==3,"one complete trigger path");
   check(soundVelocity==expectedAudio&&outVelocity==expectedAudio&&modVelocity==expectedMod,"Rvl then AVL reaches sound, modulation and MIDI exactly once");
   check(randomCalls==(floor<100&&velocity>0),"neutral Rvl preserves random sequence");
  }
 }
 for(unsigned page=0;page<32;page++)for(unsigned mode=0;mode<13;mode++)for(unsigned copy=0;copy<9;copy++){
  currentPage=page;buttonHandler_stateMemory.selectButtonMode=mode;copyClear_Mode=copy;
  buttonHandler_buttonTimerStepNr=7;shift=1;shortcuts=disarmed=0;
  buttonHandler_seqButtonPressed(0);
  check(shortcuts==1&&disarmed==1&&copyClear_Mode==0&&buttonHandler_buttonTimerStepNr==NO_STEP_SELECTED,
      "SHIFT Step1 bypasses every mode and cancels pending automation/copy");
  check(currentPage==10&&layer==0&&modeLED==SELECT_MODE_PERF&&buttonHandler_stateMemory.selectButtonMode==SELECT_MODE_PATTERN,
      "any-mode shortcut selects patterns while showing first PERF view");
 }
 shift=0;shortcuts=0;buttonHandler_seqButtonPressed(0);check(!shortcuts,"unshifted Step1 is not intercepted");
 shift=1;buttonHandler_seqButtonPressed(1);check(!shortcuts,"other shifted steps are not intercepted");
 printf("VELOCITY/SHORTCUT PASS %u assertions\n",checks);return 0;
}
"""
(OUT/'contract.c').write_text(code);(OUT/'Parameters.h').write_text(read('Core/Inc/Parameters.h'));(OUT/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
if os.name=='nt':
 vs=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
 subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /Fe:contract.exe contract.c && contract.exe',shell=True,cwd=OUT,check=True)
else:
 subprocess.run(['cc','-std=c11','-o','contract','contract.c'],cwd=OUT,check=True);subprocess.run([str(OUT/'contract')],cwd=OUT,check=True)
