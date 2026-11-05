"""Native tests of Scale persistence, timing, pattern copies and the long PERF gesture."""
from pathlib import Path
import os,re,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/pattern-scale-audit';OUT.mkdir(parents=True,exist_ok=True)
def read(p):return (ROOT/p).read_text()
def function(src,name):
 m=re.search(r'[^\n]*\b'+name+r'\([^)]*\)\s*\{',src);assert m,name
 pos=m.end();depth=1
 while depth:
  depth+=(src[pos]=='{')-(src[pos]=='}');pos+=1
 return src[m.start():pos]
seq=read('Core/Src/Soundengine/Sequencer/sequencer.c');preset=read('Core/Src/Preset/presetManager.c');btn=read('Core/Src/buttonHandler.c')
header=read('Core/Inc/Soundengine/Sequencer/sequencer.h')
code=r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Parameters.h"
#include "Soundengine/Sequencer/PerformanceScale.h"
#define NUM_PATTERN 64
#define NUM_TRACKS 7
#define NUM_STEPS 64
#define STEPS_PER_PATTERN 64
#define NUM_BARS 4
#define USE_SD_CARD 1
"""
code+=re.search(r'enum TrigCondition\s*\{.*?\};',header,re.S)[0]+"\n"
code+=read('Core/Inc/Preset/SeqStep.h').replace('#include "main.h"','')
for name in ['PatternSet','PatternBackupBuffer']:
 m=re.search(r'typedef struct '+name+r'Struct.*?}'+name+r';',header,re.S);assert m,name;code+=m[0]+'\n'
code+=r"""
PatternSet seq_patternSet;PatternBackupBuffer patternBackupBuffer;
typedef unsigned UINT;typedef int FIL;int SDFile;
#define FR_OK 0
uint8_t disk[65536];unsigned size,cursor;
int f_write(FIL *f,const void *src,unsigned count,UINT *done){(void)f;if(cursor+count>sizeof(disk))abort();memcpy(disk+cursor,src,count);cursor+=count;if(cursor>size)size=cursor;*done=count;return 0;}
int f_read(FIL *f,void *dst,unsigned count,UINT *done){(void)f;*done=size-cursor<count?size-cursor:count;memcpy(dst,disk+cursor,*done);cursor+=*done;return 0;}
"""
# 0.2.61: flam presets; the per-step FLV1 block of older files converts to presets
for line in ['FlamPreset seq_flamPresets[NUM_FLAM_PRESETS];','static uint32_t seq_flamMask[NUM_FLAM_PRESETS];','static const uint8_t seq_flamGridPulses[FLAM_NUM_GRIDS]={12,8,6,4,3,2};']:
 assert line in seq,line;code+=line+'\n'
for name in ['seq_flamDefaultPreset','seq_flamCalcMask','seq_flamPresetsChanged','seq_flamResetPresets']:
 code+=function(seq,name)+'\n'
code+='unsigned flamTouches;void preset_touchFlamTimer(void){flamTouches++;}\n'
for name in ['preset_writePatternScale','preset_readPatternScale','preset_writeFlamProbability','preset_readFlamProbability','preset_writeTrigConditions','preset_readTrigConditions','preset_flamSlotUsed','preset_flamSameShape','preset_flamForVelocity','preset_readFlamVelocity','preset_writePatternData','preset_readPatternData']:
 code+=function(preset,name)+'\n'
for name in ['seq_copyPatternToBackupBuffer','seq_copyBackupBufferToPattern','seq_copyPattern']:
 code+=function(seq,name)+'\n'
# Only the production mode-button cases are needed to exercise the gesture.
press=function(btn,'buttonHandler_buttonPressed')
a=press.index('case BUT_MODE2:');b=press.index('case BUT_SEQ8:',a)
release=function(btn,'buttonHandler_buttonReleased')
a2=release.index('case BUT_MODE2:');b2=release.index('case BUT_MODE3:',a2)
code+=r"""
enum {BUT_MODE1=20,BUT_MODE2,BUT_MODE3,BUT_MODE4,BUT_SEQ8,SELECT_MODE_VOICE=0,SELECT_MODE_PERF=1,PATTERN_SETTINGS_PAGE=13,LED_MODE3=3};
#define BUTTON_TIMEOUT 2000
#define LOAD_LONG_PRESS_TICKS (BUTTON_TIMEOUT*2)
uint32_t systick_ticks,buttonHandler_perfLongDeadline,buttonHandler_buttonTimer;
uint8_t buttonHandler_perfLongArmed,seq_activePattern,activeParameters[NUM_PARAMS];
uint8_t buttonHandler_loadLongArmed,transferActive;
uint32_t buttonHandler_loadLongDeadline;
unsigned shortcutCalls;
uint8_t menu_isTransferActive(void){return transferActive;}
void buttonHandler_enterPatternShortcut(void){shortcutCalls++;}
unsigned voiceTicks;void buttonHandler_voiceLongTick(void){voiceTicks++;}
void buttonHandler_stepLongTick(void){}
void buttonHandler_openPatternScale(void);
int8_t buttonHandler_buttonTimerStepNr=-1;
struct {uint8_t selectButtonMode;} buttonHandler_stateMemory;
unsigned opened,shortPerf,loadCalls,automationCalls;
void menu_openPatternScale(void);
uint8_t menu_activePage,menuIndex,menu_scalePattern,lastEncoderButton,seq_running;
void menu_switchPage(uint8_t page){menu_activePage=page;if(page==PATTERN_SETTINGS_PAGE)opened++;}
void menu_switchSubPage(uint8_t page,uint8_t toggle){(void)page;(void)toggle;}
void menu_repaintAll(void){}
void led_setMode2(uint8_t mode){(void)mode;}
void buttonHandler_armTimerActionStep(int8_t step){(void)step;automationCalls++;}
#define TIMER_ACTION_OCCURED -2
void buttonHandler_handleModeButtons(uint8_t mode){if(mode==1)shortPerf++;if(mode==2)loadCalls++;}
void pressButton(uint8_t buttonNr){
 if(buttonNr!=BUT_MODE2)buttonHandler_perfLongArmed=0;
 buttonHandler_loadLongArmed=0;
 switch(buttonNr){
"""
code+=press[a:b]+'}}\nvoid releaseButton(uint8_t buttonNr){switch(buttonNr){'+release[a2:b2]+'}}\n'
code+=function(btn,'buttonHandler_tick')
code+=function(btn,'buttonHandler_openPatternScale')
menu=read('Core/Src/menu/menu.c')
code+=function(menu,'menu_openPatternScale')
code+=function(seq,'seq_setPatternScale')
code+=r"""
#define PRESET_PAT_TIMER 0
unsigned saves;
void preset_touchTimer(unsigned timer){(void)timer;saves++;}
void screensaver_touch(void){}
uint8_t performance_set(uint16_t p,uint8_t value){activeParameters[p]=value;perf_speedSet(value,seq_running);return 1;}
"""
branch=function(menu,'menu_parseEncoder')
a=branch.index('uint8_t btnClicked=0;')
code+=branch[:a]+'}\n'

code+=r"""
static unsigned checks;
void check(int ok,const char *msg){checks++;if(!ok){puts(msg);exit(1);}}
int main(void){
 const uint8_t divisions[]={2,4,6,8,12,16,24,32};const uint16_t clocks[]={3072,1536,1024,768,384,384,256,192};
 for(unsigned mode=0;mode<8;mode++){
  perf_scaleSetPattern(perf_scaleDivision(mode),0);
  check(perf_scaleMode()==divisions[mode],"scale selection");
  unsigned count=perf_scaleCount(64);
  check(count==((mode==4)?48:64),"only 12 skips page tails");
  check(count*perf_scaleMidiClocks()==clocks[mode],"exact MIDI bar duration");
  check(perf_scaleFrames()==perf_scaleTicks()*2&&perf_scaleTicks()==perf_scaleMidiClocks()*4,"internal and MIDI tick agreement");
  for(unsigned i=0;i<count;i++){
   uint8_t source=perf_scaleToSource(i,64);
   check(mode!=4||(source&15)<12,"12 plays first twelve slots of every page");
   check(perf_scaleToOrdinal(source,64)==i,"source mapping round trip");
  }
 }
 perf_scaleSetPattern(32,0);perf_speedSet(PERF_SPEED_NEUTRAL,0);check(perf_scaleMode()==32,"stored division applies");
 perf_speedSet(PERF_SPEED_NEUTRAL-1,0);check(perf_scaleMode()==32&&perf_scaleTicks()==24,"spd keeps the stored division");
 perf_speedSet(PERF_SPEED_NEUTRAL,0);perf_scaleSetPattern(16,0);perf_scaleSetPattern(12,1);
 check(perf_scaleCommitOnBar(3)==0&&perf_scaleMode()==16,"live change waits for the bar");
 check(perf_scaleCommitOnBar(0)==1&&perf_scaleMode()==12,"bar commits the pending change");
 for(unsigned mode=0;mode<8;mode++){
  memset(&seq_patternSet,0,sizeof(seq_patternSet));
  seq_patternSet.scale[3]=divisions[mode];seq_patternSet.kitNr[3]=17;
  seq_patternSet.flamProbability[3][2][5]=37;
  seq_flamResetPresets();flamTouches=0;
  seq_patternSet.seq_stepTiming[3][2][5].flam=3;seq_patternSet.seq_stepTiming[3][2][6].flam=3;seq_patternSet.seq_stepTiming[3][2][7].flam=3;
  for(unsigned t=0;t<7;t++){seq_patternSet.length[3][t]=64;seq_patternSet.seq_mainSteps[3][3][t]=0xabcd;}
  size=cursor=0;preset_writePatternData(3);unsigned modernSize=size;
  check(size>911&&memcmp(disk+size-911,"SCL2",4)==0&&memcmp(disk+size-905,"FLP1",4)==0&&memcmp(disk+size-453,"CND2",4)==0,"tagged pattern trailers, no per-step flam velocity");
  cursor=0;check(preset_readPatternData(4,3),"modern pattern load succeeds");
  check(seq_patternSet.scale[4]==divisions[mode]&&seq_patternSet.kitNr[4]==17&&seq_patternSet.seq_mainSteps[3][4][0]==0xabcd,"scale and legacy pattern data roundtrip");
  check(seq_patternSet.flamProbability[4][2][5]==37,"flam probability roundtrip");
  check(seq_patternSet.seq_stepTiming[4][2][5].flam==3&&!flamTouches,"flam preset number roundtrip");
  /* a 0.2.56..0.2.60 file: FLV1 with 448 velocities after CND2 */
  memcpy(disk+modernSize,"FLV1",4);memset(disk+modernSize+4,FLAM_VELO_FLAT,448);
  disk[modernSize+4+2*64+5]=9;disk[modernSize+4+2*64+6]=9;disk[modernSize+4+1]=200;size=modernSize+452;
  memset(seq_patternSet.seq_stepTiming[3],0,sizeof(seq_patternSet.seq_stepTiming[3]));
  cursor=0;check(preset_readPatternData(4,3),"0.2.60 pattern load succeeds");
  check(seq_patternSet.seq_stepTiming[4][2][5].flam==15&&seq_patternSet.seq_stepTiming[4][2][6].flam==15,"own flam velocity moves to a free preset");
  check(seq_flamPresets[15].velo==9&&seq_flamPresets[15].repeats==4&&seq_flamPresets[15].grid==2&&!seq_flamPresets[15].plusOne,"the new preset keeps the flam shape");
  check(seq_patternSet.seq_stepTiming[4][2][7].flam==3&&seq_flamPresets[3].velo==FLAM_VELO_FLAT&&flamTouches==1,"flat steps keep their preset");
  check(seq_patternSet.seq_stepTiming[4][0][1].flam==0,"bad old velocity is ignored");
  check(seq_patternSet.flamProbability[4][2][5]==37,"flam probability survives the conversion");
  /* no free preset: the nearest velocity of the same shape */
  for(uint8_t i=11;i<16;i++)seq_flamPresets[i].pitch=13;
  seq_patternSet.seq_stepTiming[3][2][5].flam=0;seq_flamPresets[13].pitch=12;seq_flamPresets[13].repeats=4;seq_flamPresets[13].grid=2;seq_flamPresets[13].velo=20;
  disk[modernSize+4+2*64+5]=15;cursor=0;
  check(preset_readPatternData(4,3)&&seq_patternSet.seq_stepTiming[4][2][5].flam==13,"full presets use the nearest velocity");
  size=modernSize;
  size=modernSize-911;cursor=0;seq_patternSet.scale[4]=32;
  check(preset_readPatternData(4,3)&&seq_patternSet.scale[4]==16&&seq_patternSet.flamProbability[4][2][5]==100,"legacy pattern defaults safely");
  size=modernSize;disk[size-906]^=1;cursor=0;
  check(preset_readPatternData(4,3)&&seq_patternSet.scale[4]==16,"bad trailer checksum defaults safely");
  disk[size-906]^=1;
  seq_copyPattern(3,5);check(seq_patternSet.scale[5]==divisions[mode]&&seq_patternSet.flamProbability[5][2][5]==37,"copy retains scale and flam probability");
  seq_copyPatternToBackupBuffer(3);seq_patternSet.scale[3]=0;seq_patternSet.flamProbability[3][2][5]=0;seq_copyBackupBufferToPattern(3);
  check(seq_patternSet.scale[3]==divisions[mode]&&seq_patternSet.flamProbability[3][2][5]==37,"backup retains scale and flam probability");
 }
 seq_activePattern=3;seq_patternSet.scale[3]=16;memset(seq_patternSet.length[3],16,NUM_TRACKS);seq_patternSet.length[3][2]=7;seq_patternSet.length[3][4]=0;
 seq_copyPatternToBackupBuffer(3);seq_setPatternScale(3,7);
 check(seq_patternSet.length[3][0]==32&&seq_patternSet.length[3][4]==32&&seq_patternSet.length[3][2]==7,"rate 32 lengthens default tracks only");
 seq_copyBackupBufferToPattern(3);check(seq_patternSet.length[3][0]==32,"length survives leaving the pattern");
 seq_setPatternScale(3,6);check(seq_patternSet.length[3][0]==24&&seq_patternSet.length[3][2]==7,"rate 24 follows");
 seq_setPatternScale(3,5);check(seq_patternSet.length[3][0]==16&&seq_patternSet.length[3][2]==7,"returning to 16 restores the default");
 seq_patternSet.length[3][1]=20;seq_setPatternScale(3,7);check(seq_patternSet.length[3][1]==20,"hand-set length stays");
 seq_setPatternScale(3,5);memset(seq_patternSet.length[3],16,NUM_TRACKS);
 seq_activePattern=3;seq_patternSet.scale[3]=16;seq_copyPatternToBackupBuffer(3);seq_setPatternScale(3,4);seq_copyBackupBufferToPattern(3);check(seq_patternSet.scale[3]==12,"pattern rate survives leaving the pattern");
 seq_activePattern=3;seq_patternSet.scale[3]=12;
 /* 0.2.52: long PERF opens the pattern selection, long LOAD the pattern Scale */
 systick_ticks=100;pressButton(BUT_MODE2);systick_ticks=2099;buttonHandler_tick();check(!shortcutCalls&&!opened,"short PERF does nothing more");
 releaseButton(BUT_MODE2);systick_ticks=2200;buttonHandler_tick();check(!shortcutCalls&&shortPerf==1,"release cancels hold");
 pressButton(BUT_MODE2);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_tick();
 check(shortcutCalls==1&&!opened,"long PERF opens the pattern selection");
 buttonHandler_tick();check(shortcutCalls==1&&!automationCalls,"hold fires once without step-automation action");
 releaseButton(BUT_MODE2);pressButton(BUT_MODE3);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_tick();check(!opened&&loadCalls==1,"short LOAD hold keeps LOAD + Step chords");
 releaseButton(BUT_MODE3);
 pressButton(BUT_MODE2);pressButton(BUT_MODE3);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_tick();check(shortcutCalls==1,"another button cancels PERF hold");
 releaseButton(BUT_MODE3);
 buttonHandler_stateMemory.selectButtonMode=SELECT_MODE_PERF;
 pressButton(BUT_MODE3);systick_ticks+=LOAD_LONG_PRESS_TICKS;buttonHandler_tick();
 check(opened==1&&activeParameters[PAR_PATTERN_SCALE]==4&&buttonHandler_stateMemory.selectButtonMode==SELECT_MODE_VOICE&&shortcutCalls==1,"long LOAD opens current pattern Scale");
 buttonHandler_tick();check(opened==1,"long LOAD fires once");
 releaseButton(BUT_MODE3);
 pressButton(BUT_MODE3);pressButton(BUT_SEQ8);systick_ticks+=LOAD_LONG_PRESS_TICKS;buttonHandler_tick();check(opened==1,"another button cancels long LOAD");
 transferActive=1;pressButton(BUT_MODE3);systick_ticks+=LOAD_LONG_PRESS_TICKS;buttonHandler_tick();check(opened==1,"transfer dialog ignores long LOAD");transferActive=0;
 check(voiceTicks>0,"the tick serves the voice hold");
 perf_scaleSetPattern(16,0);perf_speedSet(PERF_SPEED_NEUTRAL,0);seq_running=1;
 seq_activePattern=3;seq_patternSet.scale[3]=12;menu_openPatternScale();
 menu_parseEncoder(3,0);
 check(activeParameters[PAR_PATTERN_SCALE]==7&&seq_patternSet.scale[3]==12&&perf_scaleMode()==16,"encoder previews without applying or storing");
 menu_parseEncoder(0,1);
 check(seq_patternSet.scale[3]==32&&perf_scaleMode()==16&&perf_scaleHasPending()&&saves==1,"click confirms and queues on next downbeat");
 menu_parseEncoder(0,1);check(saves==1,"held encoder button confirms once");
 check(!perf_scaleCommitOnBar(767)&&perf_scaleMode()==16,"pending selection waits through bar end");
 check(perf_scaleCommitOnBar(0)&&perf_scaleMode()==32,"confirmed selection starts at bar one");
 menu_parseEncoder(0,0);seq_running=0;menu_parseEncoder(-5,0);menu_parseEncoder(0,1);
 check(seq_patternSet.scale[3]==6&&perf_scaleMode()==6,"stopped confirmation applies immediately");
 printf("PATTERN SCALE PASS %u assertions\n",checks);return 0;
}
"""
(OUT/'contract.c').write_text(code);(OUT/'Parameters.h').write_text(read('Core/Inc/Parameters.h'));(OUT/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
module=ROOT/'Core/Src/Soundengine/Sequencer/PerformanceScale.c';inc=ROOT/'Core/Inc'
if os.name=='nt':
 vs=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
 subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /I. /I"{inc}" /Fe:contract.exe contract.c "{module}" && contract.exe',shell=True,cwd=OUT,check=True)
else:
 subprocess.run(['cc','-std=c11','-I.',f'-I{inc}','contract.c',str(module),'-o','contract'],cwd=OUT,check=True);subprocess.run([str(OUT/'contract')],cwd=OUT,check=True)
