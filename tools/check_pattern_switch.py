"""Production pattern switching with an injected reentrant kit-load callback."""
from pathlib import Path
import os,re,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/pattern-switch-audit';OUT.mkdir(parents=True,exist_ok=True)
src=(ROOT/'Core/Src/Soundengine/Sequencer/sequencer.c').read_text()
src=re.sub(r'/\*.*?\*/|//[^\n]*','',src,flags=re.S)
def function(name):
 m=re.search(r'[^\n]*\b'+name+r'\([^{};]*\)\s*\{',src);pos=m.end();depth=1
 while depth:
  depth+=(src[pos]=='{')-(src[pos]=='}');pos+=1
 return src[m.start():pos]
code=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Parameters.h"
#define IN_ITCM_RAM
enum {FX_OFF,SAVE_TYPE_KIT=0,CURRENT_KIT=0,PRESET_KIT_TIMER=0,PATTERN_LOAD_PAGE=20,SONG_MODE_PAGE=22,SELECT_MODE_PATTERN=8,SELECT_MODE_SONG=9};
#define SKIP_NEXT_KIT_AUTOLOAD 2
uint8_t seq_patternSwitchActive,midi_process_block,seq_activePattern,seq_pendingPattern,seq_loadPendigFlag;
uint8_t activeParameters[NUM_PARAMS],menu_selectedPresetNr[1],menu_loadedPresetNr[1];
uint8_t menu_playedPattern,menu_songMenuPosition,seq_songPositionPointer,menu_activePage,menu_shownPattern;
struct {uint8_t kitNr[64],scale[64],shuffle[64];}seq_patternSet;
struct {uint8_t fxType;}fxBus;
unsigned restores,backups,loads,repaints,resets,leadChecks,tickBody,checks;
uint8_t restored,backedUp,loaded;
void seq_setPendingPatternActive(void);void seq_tick(void);
void check(int ok,const char *msg){checks++;if(!ok){puts(msg);exit(1);}}
void seq_setStepIndexToStart(void){resets++;}
void seq_copyBackupBufferToPattern(uint8_t p){restores++;restored=p;}
void seq_copyPatternToBackupBuffer(uint8_t p){backups++;backedUp=p;}
void perf_scaleSetPattern(uint8_t a,uint8_t b){(void)a;(void)b;}
void seq_setShuffle(float v){(void)v;}
void preset_loadDrumsetRam(uint8_t kit,uint8_t morph,uint8_t now){
 (void)morph;(void)now;loads++;loaded=kit;
 /* Mimic soundengine_process while a kit is being applied. */
 seq_tick();seq_setPendingPatternActive();
}
void preset_touchTimer(uint8_t t){(void)t;}
uint8_t led_idx2StepLed(uint8_t p){return p%16;}
void led_setBlinkLed(uint8_t a,uint8_t b){(void)a;(void)b;}
void seq_sendProgChg(uint8_t p){(void)p;}
void voiceControl_noteOff(uint8_t p){(void)p;}
void menu_setShownPattern(uint8_t p){menu_shownPattern=p;}
void led_clearSequencerLeds(void){}
uint8_t menu_getActiveVoice(void){return 0;}
void led_updateSeqLeds(void){}
uint8_t seq_getTrackLength(uint8_t t){(void)t;return 16;}
void menu_repaint(void){repaints++;}
void menu_repaintAll(void){repaints++;}
uint8_t buttonHandler_getMode(void){return SELECT_MODE_PATTERN;}
void led_clearAllBlinkLeds(void){}
void led_initPatternSelectLeds(void){}
uint8_t seq_getExtSync(void){return 2;}
void sync_processStartLead(void){leadChecks++;}
'''
code+=function('seq_setPendingPatternActive')+'\n'
tick=function('seq_tick');code+=tick[:tick.index('if(!seq_running)')]+'tickBody++;}\n'
code+=r'''
int main(void){
 for(unsigned old=0;old<64;old++)for(unsigned next=0;next<64;next++){
  seq_activePattern=old;seq_pendingPattern=next;seq_loadPendigFlag=1;
  seq_patternSet.kitNr[next]=(next*3)%64;seq_patternSet.scale[next]=16;
  activeParameters[PAR_PATTERN_MODE]=1;restores=backups=loads=repaints=resets=leadChecks=tickBody=0;
  seq_setPendingPatternActive();
  check(restores==1&&restored==old&&backups==1&&backedUp==next,"backup transaction exactly once for all bank transitions");
  check(loads==1&&loaded==(next*3)%64&&seq_activePattern==next,"correct kit and active slot");
  check(resets==1&&repaints==2,"recursive kit callback must not repeat switch or repaint");
  check(!tickBody&&!leadChecks,"audio servicing cannot advance half-switched pattern state");
  check(!seq_patternSwitchActive&&!midi_process_block,"switch guard released");
  seq_tick();check(tickBody==1&&leadChecks==1,"clock processing resumes after switch");
 }
 printf("PATTERN SWITCH PASS %u assertions across 4096 slot transitions\n",checks);return 0;
}
'''
(OUT/'contract.c').write_text(code);(OUT/'Parameters.h').write_text((ROOT/'Core/Inc/Parameters.h').read_text());(OUT/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
if os.name=='nt':
 vs=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
 subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /Fe:contract.exe contract.c && contract.exe',shell=True,cwd=OUT,check=True)
else:
 subprocess.run(['cc','-I.','-o','contract','contract.c'],cwd=OUT,check=True);subprocess.run([str(OUT/'contract')],cwd=OUT,check=True)
