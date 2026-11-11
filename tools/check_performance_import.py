"""Native tests of real desktop performance scheduling, flam dispatch and globals.

python tools/check_performance_import.py
python tools/check_performance_import.py --mutate   (each 2+1..8+1 flam mutation must fail)
Requires the existing Visual Studio compiler on Windows, or CC elsewhere.
Hardware output is replaced by spies; no SD card or firmware is written.
"""
from pathlib import Path
import os
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/performance-audit'
OUT.mkdir(parents=True,exist_ok=True)


def source(path):
    return re.sub(r'/\*.*?\*/|//[^\n]*','',(ROOT/path).read_text(),flags=re.S)


def function(code,name):
    m=re.search(r'^.*\b'+name+r'\([^)]*\)\s*\{',code,re.M)
    assert m,name
    pos=m.end(); depth=1
    while depth:
        depth+=(code[pos]=='{')-(code[pos]=='}'); pos+=1
    return code[m.start():pos]


(OUT/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
seq=source('Core/Src/Soundengine/Sequencer/sequencer.c')
# Each mutation removes one rule of the 2+1..8+1 flams; the tests must catch it.
MUTATIONS={
 'no-plus-one':('if(!seq_flamHasPlusOne(flam))return 0;','return 0;'),
 'ignore-following-note':('return (uint8_t)!seq_intIsMainStepActive(track,following->source,seq_activePattern);','return 1;'),
 'wrap-last-step':('if(source->timeline+1u>=length)return 0;',''),
 'ignore-fpr':('if(source->flamRoll>seq_patternSet.flamProbability[seq_activePattern][track][source->source])return 0;',''),
 'no-negative-shift':('(plusOne ? (1UL<<(shiftCurrentStep-1)) : 0)','0'),
 'flat-flam-velocity':('	if(!amount || total<2)return volume;','	return volume;'),
 'no-flam-pitch':('	if(!step)return note;','	return note;'),
 'no-flam-accel':('const int32_t span=last*spacing,a=accel-FLAM_ACCEL_FLAT;','const int32_t span=last*spacing,a=0;'),
 'repeats-ignored':('	int32_t hits=p->repeats;','	int32_t hits=24/spacing;'),
 'grid-ignored':('	const int32_t spacing=seq_flamGridPulses[p->grid];','	const int32_t spacing=6;'),
 'flam-index-ignores-shift':('(int16_t)idx - 3 * getShiftValue(\n\t\t\t\t\t\tseq_patternSet.seq_stepTiming[seq_activePattern][track][currentStep].shift);','(int16_t)idx;'),
 'no-rise':('	const int32_t percent=amount<0 ? 100+(int32_t)amount*index/last\n	                               : 100-(int32_t)amount*(last-index)/last;','	const int32_t percent=amount<0 ? 100+(int32_t)amount*index/last : 100;'),
 'no-human':('const int16_t human=perf_grooveHuman(&seq_groove,planned->timeline,planned->eventId);','const int16_t human=0;'),
 'shared-human':('const int16_t human=perf_grooveHuman(&seq_groove,planned->timeline,planned->eventId);','const int16_t human=perf_grooveHuman(&seq_groove,planned->timeline,planned->source+1u);'),
 'long-flam-off':('	if(!flam || flam>=NUM_FLAM_PRESETS || seq_flamPresets[flam].steps<2)return;','	return;'),
 'long-flam-no-priority':('				prevActive=currentActive=nextActive=0;\n',''),
 'long-flam-groove-no-priority':('            continue;\n        }\n        const PerfTrack *state','        }\n        const PerfTrack *state'),
 'long-flam-no-plus-one':('		} else if(f->preset.plusOne && f->elapsed==f->lastFrame) {','		} else if(0) {'),
 'long-flam-ignores-fpr':('	if(planned->flamRoll>seq_patternSet.flamProbability[seq_activePattern][track][source])return;\n	LongFlam','	LongFlam'),
 'flam-grid-floor':('	if(hits>(24+spacing-1)/spacing)hits=(24+spacing-1)/spacing;','	if(hits>24/spacing)hits=24/spacing;'),
 'long-flam-grid-floor':('	const int32_t room=((int32_t)p->steps*24+spacing-1)/spacing;','	const int32_t room=(int32_t)p->steps*24/spacing;'),
 'long-flam-no-cancel':('	for(uint8_t i=0;i<NUM_TRACKS;i++)seq_longFlam[i].lastFrame=0;',''),
 'no-groove':('due=perf_grooveDue(&seq_groove,1UL<<23,shift,steps[n+3]->timeline,(int8_t)(n+1),frame,human);','due=0;'),
}
if '--mutate' in sys.argv:
    failed=[]
    for name in MUTATIONS:
        r=subprocess.run([sys.executable,__file__,'--mutation='+name],capture_output=True,text=True)
        print(('caught ' if r.returncode else 'MISSED ')+name)
        if not r.returncode: failed.append(name)
    sys.exit(1 if failed else 0)
for arg in sys.argv[1:]:
    if arg.startswith('--mutation='):
        old,new=MUTATIONS[arg.split('=',1)[1]]
        assert seq.count(old)==1,old
        seq=seq.replace(old,new)
btn=source('Core/Src/buttonHandler.c')
led=source('Core/Src/ledHandler.c')
preset=source('Core/Src/Preset/presetManager.c')
menu=source('Core/Src/menu/menu.c')
sync=source('Core/Src/Soundengine/Sequencer/clockSync.c')
# Check the actual shortcut dispatch, not just helper entry points.
assert re.search(r'case SEQ_DRUM2:[^\n]*\s*buttonHandler_openPerformanceLayer\(PERF_GROOVE_SUBPAGE\)',btn)
assert re.search(r'case SEQ_SNARE:[^\n]*\s*buttonHandler_openPerformanceLayer\(PERF_ACCENT_SUBPAGE\)',btn)
assert re.search(r'case SEQ_CL_HH:[^\n]*\s*buttonHandler_openPerformanceLayer\(PERF_INT_SEND_SUBPAGE\)',btn)
assert re.search(r'case SEQ_DRUM3:\s*buttonHandler_openPerformanceLayer\(PERF_DELAY_SUBPAGE\)',btn)
assert re.search(r'case SEQ_CLP:.*\s*buttonHandler_openPerformanceLayer\(PERF_SEND_SUBPAGE\)',btn)
prelude=r'''
#define DISABLE_CONV_WARNING
static void saveDiag_seq(void){}void mixer_setPerformanceGatePhase(unsigned char o){(void)o;}
static void saveDiag_clock(unsigned cycles){(void)cycles;}
#define END_DISABLE_CONV_WARNING
#include <assert.h>
#include <stdio.h>
#include "Preset/TrigConditions.h"
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "Parameters.h"
#include "Soundengine/Sequencer/PerformanceSteps.h"
#include "Soundengine/Sequencer/PerformanceScale.h"
#include "Soundengine/Sequencer/PerformanceDelay.h"
#define NUM_TRACKS 7
#define NUM_STEPS 64
#define MAX_SONG_LENGTH 64
#define STEP_VOLUME_MASK 127
enum {TRIG_COND_ALWAYS,TRIG_COND_FIRST,TRIG_COND_NOT_FIRST,
      TRIG_COND_FILL,TRIG_COND_NOT_FILL,TRIG_COND_RATIO_BASE,
      TRIG_COND_PRE=TRIG_COND_RATIO_BASE+36,TRIG_COND_NOT_PRE,TRIG_COND_NEI,TRIG_COND_NOT_NEI,TRIG_COND_LAST,TRIG_COND_NOT_LAST,TRIG_COND_COUNT};
#define USE_PATTERN_EDIT_BUFFER 0
#define USE_SD_CARD 1
#define LED_PAGE_DOWN 16
#define LED_PAGE_UP 17
/* 0.2.92 perf blink in pattern select: never pattern mode here */
#define LED_MODE2 60
#define SELECT_MODE_PATTERN 8
#define PATTERN_SAVE_PAGE 40
#define PATTERN_SAVE_PAGE_OK 41
static uint8_t buttonHandler_getMode(void){return 0;}
#define LED_VOICE1 32
#define NUM_OF_PULSABLE_LEDS 8
#define LED_PULSE_TIME 200
#define PERF_PAGE 10
#define PERF_DELAY_SUBPAGE 2
#define PERF_ACCENT_SUBPAGE 3
#define PERF_GROOVE_SUBPAGE 4
#define PERF_SEND_SUBPAGE 6
#define PERF_INT_SEND_SUBPAGE 7
#define SELECT_MODE_PERF 1
#define PAGE_SHIFT 3
#define NUM_SUB_PAGES 8
#define MENU_MIDI_PAGE 7
#define SEQ_PAGE 11
#define MASK_PARAMETER 7
#define MASK_PAGE 248
#define TEXT_EMPTY 0
#define pgm_read_byte(p) (*(const uint8_t*)(p))
#define menu_activePage currentPage
/* all real pages: the LFO extra pages lie above 16 */
struct {uint8_t top1,top2,top3,top4,top5,top6,top7,top8;}menuPages[64][8];
typedef enum {STEP_PREV,STEP_CURRENT,STEP_NEXT} StepPosition;
typedef struct {uint8_t note,volume,prob,token;} Step;
struct {
  uint8_t length[64][7];
  uint16_t seq_mainSteps[4][64][7];
  Step seq_subStepPattern[64][7][64];
  struct {uint8_t shift,flam;} seq_stepTiming[64][7][64];
  uint8_t flamProbability[64][7][64];
  TrigTrack trigCondition[64][7];
} seq_patternSet;
uint8_t seq_stepIndex[7],seq_activePattern,seq_running=1,seq_mutedTracks;
uint32_t seq_conditionLoop[7];
uint8_t seq_conditionTimingOnly,seq_conditionHistory[7],seq_conditionHistoryValid[7],seq_conditionCacheIndex[7];
struct {uint32_t id;uint8_t result;}seq_conditionCache[7][8];
uint8_t seq_conditionLastLoop(void){return 0;}
uint8_t lastWasNoteOn[7],chokeCurrent,chokeNext;
uint8_t seq_delayFiredMask,seq_usesFineClock,seq_finePhase;
uint8_t seq_prescaleCounter,seq_grooveNoteOff[7];
PerfGroove seq_groove;
uint8_t externalSync,trigger_clockReceived,captureFine;
uint16_t seq_tempo=125;
uint32_t seq_lastTick;
uint16_t seq_scaleBarFrame;uint8_t seq_scaleRestart;
void menu_repaint(void){}
void seq_setStepIndexToStart(void);
float seq_deltaT;
unsigned fineNow,fineHits,fineTimes[2048],fineSources[2048],fineVoices[2048],fineVelocities[2048];
unsigned boundaryCalls,midiClocks,clockTicks,groovePulses,on2State,on4State;
#define HANDLE_SEQ_IN_CLOCK_INTERRUPT 0
#define WINDOW_SIZE 8
#define WINDOW_MASK 7
float sync_window[8];
uint8_t sync_writePos,sync_samples,sync_armed,sync_stepFlip;uint16_t sync_clockCnt;
uint32_t sync_lastClockTick;
uint32_t sync_lastClockCycles,sync_cycleWindow[8],sync_nextLeadCycles;
uint8_t sync_cycleSamples,sync_cycleWritePos,sync_leadArmed,sync_leadConsumed;
#define SYNC_CLOCK_LOST_TICKS 4000u
uint8_t sync_barClockCnt,sync_barPhaseValid,sync_barPhaseFromStart,sync_startOnNextBar,sync_startLeadArmed;
uint32_t sync_nextStartCycles;
uint32_t sync_beatStartCycles;uint8_t sync_beatClocks,sync_beatRunning,sync_beatOutliers;float sync_beatCycles;
#define SYNC_BEAT_SMOOTHING 0.08f
#define SYNC_BEAT_RETAKE 0.04f
#define SYNC_BEAT_TIMEOUT_TICKS 2000u
uint8_t sync_clockOffsetTenths=50,sync_clockOffsetHundredths;
struct {uint32_t CYCCNT;} dwtMock;
#define DWT (&dwtMock)
uint32_t SystemCoreClock=216000000u;
uint8_t sync_shouldLeadStep(void);
void sync_markLeadStep(void);
void sync_tickAtCycles(uint32_t cycles);
uint8_t sync_processStartLead(void);
static void seq_longFlamCancel(void);
void seq_setRunning(uint8_t running){seq_longFlamCancel();seq_running=running;}
static void seq_perfAdvance(uint8_t,uint8_t,uint8_t);
uint16_t seq_getBpm(void){return seq_tempo;}
void seq_setBpm(uint16_t bpm){seq_tempo=bpm;}

uint8_t activeParameters[NUM_PARAMS],midi_MidiChannels[8];
uint8_t seq_triggerSourceStep[7]={255,255,255,255,255,255,255};
uint32_t seq_triggerEventId,seq_lastLfoEventId[7];
uint8_t seq_patternSwitchActive;
unsigned lfoTriggers[7];
void lfo_stepTrigger(uint8_t voice){if(voice<7)lfoTriggers[voice]++;}
const PerfTrack *seq_perfTracks[7];
PerfTrack seq_scaledTracks[7];
struct {uint8_t prev,current,next;} seq_rndValue[7];
uint8_t seq_songModeEnabled,seq_songPositionPointer,seq_activeSong[64];
uint8_t menu_activePatternBank,menu_playedPattern,viewed;
uint8_t currentPage,menuIndex,editModeActive;
uint8_t buttonHandler_mutedVoices,menu_muteModeActive,voiceMask,selectedVoice;
uint8_t lastMode;
struct {uint8_t selectButtonMode;} buttonHandler_stateMemory;
unsigned repaintCount,maskWrites,pulseCalls,systick_ticks;
uint8_t led_pulsingLeds,led_pulseLedNumber[8];
uint32_t led_pulseEndTime[8];
void menu_openPerformanceLayer(uint8_t page);
void buttonHandler_refreshVoiceDisplay(void);
uint8_t menu_getActivePage(void){return currentPage;}
uint8_t menu_getSubPage(void){return (uint8_t)(menuIndex>>PAGE_SHIFT);}
uint8_t menu_getActiveVoice(void){return selectedVoice;}
uint8_t getMenuIndx(void){return menuIndex;}
void menu_switchPage(uint8_t page){currentPage=page;}
void menu_repaintAll(void){repaintCount++;}
void led_setMode2(uint8_t mode){lastMode=mode;}
void led_setActiveVoiceLeds(uint8_t mask){voiceMask=mask&127;}
void led_setActiveVoice(uint8_t voice){voiceMask=(uint8_t)(1u<<voice);}
void led_toggleTemp(uint8_t n){(void)n;pulseCalls++;}
void midiParser_setDelayParameter(uint16_t p,uint8_t v){
 assert(p==PAR_PERF_DELAY_INPUT_MASK);activeParameters[p]=v&127;maskWrites++;
}
static uint16_t buttonHandler_heldPatternKeys;
static uint8_t buttonHandler_heldPattern[16];
uint8_t leds[18],blink[18];
unsigned hits,outputs,off,automations,checks;
uint8_t lastNote,lastVelocity,lastAuto,outVelocity;
uint32_t rng=1;
uint32_t GetRngValue(void) {rng=rng*1664525u+1013904223u; return rng;}
uint8_t led_idx2StepLed(uint8_t n){return n;}
void led_setValue(uint8_t v,uint8_t i){assert(i<18);leds[i]=v;}
void led_setBlinkLed(uint8_t i,uint8_t v){assert(i<18);blink[i]=v;}
void led_clearAllBlinkLeds(void){memset(blink,0,sizeof(blink));}
void led_clearSequencerLeds(void){memset(leds,0,16);}
uint8_t menu_getViewedPattern(void){return viewed;}
uint8_t seq_getExtSync(void){return externalSync;}
void seq_nextStep(void){
 if(!seq_running)return;
 boundaryCalls++;
 for(uint8_t t=0;t<7;t++) {
   uint8_t len=seq_patternSet.length[0][t];if(!len||len>64)len=16;
   seq_stepIndex[t]=perf_scaleNext(seq_stepIndex[t]==255?-1:seq_stepIndex[t],len);
   seq_perfAdvance(t,seq_stepIndex[t],len);
 }
}
void seq_setStepIndexToStart(void){memset(seq_stepIndex,255,sizeof(seq_stepIndex));seq_prescaleCounter=seq_finePhase=0;}
void trigger_clockTick(uint8_t a,uint8_t b){(void)a;(void)b;clockTicks++;}
void trigger_clockGrooveTick(uint8_t a,uint8_t b){on2State=a;on4State=b;groovePulses++;}
#define MIDI_CLOCK 248
#define MIDI_PRESCALER_MASK 4
void seq_sendRealtime(uint8_t m){if(m==MIDI_CLOCK)midiClocks++;}
void seq_parseAutomationNodes(uint8_t v,Step *s){(void)v;automations++;lastAuto=s->token;}
void voiceControl_noteOff(uint8_t v){(void)v;off++;}
#define SLIDE_TRACKS 3
unsigned slideCalls;uint8_t seq_getSlide(uint8_t p,uint8_t t,uint8_t st){(void)p;(void)t;(void)st;return 0;}
void Drum_setSlideNext(uint8_t v,uint8_t on){(void)v;(void)on;slideCalls++;}
uint8_t seq_getAccent(uint8_t p,uint8_t t,uint8_t st){(void)p;(void)t;(void)st;return 0;}
uint8_t fenv_accentVelocity(uint8_t v,uint8_t a,uint8_t vel){(void)v;(void)a;return vel;}
void voiceControl_noteOnNoEchoWithMod(uint8_t v,uint8_t n,uint8_t vel,uint8_t modVelocity){(void)modVelocity;(void)v;hits++;lastNote=n;lastVelocity=vel;if(captureFine){assert(fineHits<2048);fineVelocities[fineHits]=vel;fineVoices[fineHits]=v;fineTimes[fineHits]=fineNow;fineSources[fineHits++]=(uint8_t)(n-40);}}
void seq_sendMidiNoteOn(uint8_t c,uint8_t n,uint8_t v){(void)c;(void)n;outputs++;outVelocity=v;}
typedef unsigned UINT;
typedef int FIL;
int SDFile;
uint8_t fileData[64];
unsigned fileSize;
int f_read(FIL *f,void *dest,unsigned count,unsigned *read){
 (void)f;*read=fileSize<count?fileSize:count;memcpy(dest,fileData,*read);return 0;
}
'''
prelude+='\n'+'\n'.join(re.findall(r'#define FLAM_(?:PLUS_ONE_\w+|VELO_FLAT) \d+',source('Core/Inc/Preset/SeqStep.h')))+'\n'
# 0.2.61 flam presets: the real preset type and table
_step=source('Core/Inc/Preset/SeqStep.h')
prelude+=_step[_step.index('#define NUM_FLAM_PRESETS'):_step.index('}FlamPreset;')+len('}FlamPreset;')]+'\n'
for _line in ['FlamPreset seq_flamPresets[NUM_FLAM_PRESETS];','static uint32_t seq_flamMask[NUM_FLAM_PRESETS];','static const uint8_t seq_flamGridPulses[FLAM_NUM_GRIDS]={12,8,6,4,3,2,16,24,32,48,64,72};']:
    assert _line in seq,_line; prelude+=_line+'\n'
LONG_BLOCK=seq[seq.index('typedef struct LongFlamStruct'):seq.index('uint8_t chokeCurrent=0;')]
functions='\n'.join((LONG_BLOCK if n=='LONG_FLAM_BLOCK' else function(seq,n)) for n in (
    'seq_perfRandom','seq_perfAdvance','seq_conditionAllows','seq_conditionResolve','seq_intIsMainStepActive','seq_getLongestTrack','getShiftValue',
    'seq_flamDefaultPreset','seq_flamPosition','seq_flamCalcMask','seq_flamPresetsChanged','seq_flamResetPresets',
    'flamIdxToPattern','seq_flamHasPlusOne','seq_flamPlusOne','seq_flamHitIndex','seq_flamVolumeAt','seq_flamLongHits','seq_flamLongTotal','seq_flamNoteAt','seq_getShiftFlamPattern','seq_triggerVoice','seq_triggerFlamHit','seq_emitDelay',
    'LONG_FLAM_BLOCK','seq_processFlam',
    'seq_processGrooveFine','seq_applyPendingScale','seq_applyPendingTransform','seq_processScaleFrame','seq_processFineFrame','seq_advanceFineFrame','seq_calcDeltaT','seq_MidiSyncQueue','seq_tick','seq_determineNextPattern'))
functions+='\n'+'\n'.join(function(sync,n) for n in ('sync_calcBpm','sync_trackBeat','sync_getBeatBpm','sync_tick','sync_tickAtCycles','sync_requestStartOnNextBar','sync_processStartLead','sync_setClockOffset','sync_shouldLeadStep','sync_markLeadStep'))
functions+='\n'+function(btn,'buttonHandler_selectPatternLoop')
functions+='\n'+function(led,'led_initPatternSelectLeds')
functions+='\n'+function(preset,'preset_readGlobalData')
functions+='\n'+function(btn,'buttonHandler_showMuteLEDs')
functions+='\n'+function(btn,'buttonHandler_isMidiDelayPage')
functions+='\n'+function(btn,'buttonHandler_refreshVoiceDisplay')
functions+='\n'+function(btn,'buttonHandler_handleDelayVoice')
functions+='\n'+function(menu,'menu_openPerformanceLayer')
functions+='\n'+function(menu,'menu_isPerfShortcutSubPage')+'\n'+function(menu,'has2ndPage')+'\n'+function(menu,'menu_switchSubPage')
functions+='\n'+function(menu,'menu_openLfoExtra')+'\n'+function(menu,'menu_cycleVoiceLfo')+'\n'+function(menu,'menu_resetActiveParameter')
functions+='\n'+function(btn,'buttonHandler_openPerformanceLayer')
functions+='\n'+function(led,'led_pulseLed')

page_header=source('Core/Inc/menu/menu.h')
page_enum=re.search(r'enum PageNames\s*\{.*?\};',page_header,re.S).group(0)
# Existing harness uses a compact page enum; add the new names using real offsets.
extra_page_names=['VOICE7_PAGE','LFO_EXTRA1_PAGE','LFO_EXTRA6_PAGE']
for name in extra_page_names:
    if not re.search(r'\b'+name+r'\b',prelude):
        names=[n.strip() for n in page_enum.split('{',1)[1].split('}',1)[0].split(',') if n.strip()]
        prelude+='\n#define '+name+' '+str(names.index(name))+'\n'

tests=r'''
static void check(int ok,const char *what){checks++;if(!ok){fprintf(stderr,"FAIL %s\n",what);exit(1);}}
static void clearSpies(void){hits=outputs=off=automations=0;}
static void setup(uint64_t active){
 memset(&seq_patternSet,0,sizeof(seq_patternSet));for(int t=0;t<7;t++)seq_perfTracks[t]=0;
 seq_flamResetPresets();seq_longFlamCancel();
 memset(lfoTriggers,0,sizeof(lfoTriggers));memset(seq_lastLfoEventId,0,sizeof(seq_lastLfoEventId));seq_triggerEventId=0;
 memset(lastWasNoteOn,0,sizeof(lastWasNoteOn));memset(activeParameters,0,sizeof(activeParameters));activeParameters[PAR_PERF_RANDOM_VELO]=100;activeParameters[PAR_PERF_AVL]=100;
 memset(seq_conditionLoop,0,sizeof(seq_conditionLoop));memset(seq_conditionCache,0,sizeof(seq_conditionCache));memset(seq_conditionHistoryValid,0,sizeof(seq_conditionHistoryValid));
 seq_scaleBarFrame=0;seq_scaleRestart=0;captureFine=0;externalSync=0;fineHits=0;boundaryCalls=midiClocks=clockTicks=groovePulses=0;
 perf_grooveConfigure(&seq_groove,0,63,63,63);perf_delaySetGroove(&seq_groove);seq_usesFineClock=0;seq_finePhase=0;seq_prescaleCounter=0;
 perf_scaleSetPattern(16,0);perf_speedSet(PERF_SPEED_NEUTRAL,0);perf_resetSteps();seq_activePattern=0;seq_mutedTracks=126;seq_running=1;
 perf_setNoteProbability(100);
 perf_delayConfigure((PerfDelayConfig){0,6,0,63,5,0,64,127,0});perf_delayReset();
 for(int t=0;t<7;t++){
   seq_patternSet.length[0][t]=16;seq_stepIndex[t]=0;
   for(int b=0;b<4;b++)seq_patternSet.seq_mainSteps[b][0][t]=(uint16_t)(active>>(b*16));
   for(int s=0;s<64;s++){
     seq_patternSet.seq_subStepPattern[0][t][s]=(Step){(uint8_t)(40+s),(uint8_t)(20+s),100,(uint8_t)s};
     seq_patternSet.seq_stepTiming[0][t][s].shift=7;
     seq_patternSet.flamProbability[0][t][s]=100;
   }
 }
 clearSpies();
}
static unsigned delayEvents,delayClock;
static unsigned eventTimes[1000];
static uint8_t eventTracks[1000],eventSources[1000],eventScales[1000];
static int16_t eventPitches[1000];
static void captureDelay(uint8_t t,uint8_t s,uint8_t scale,int16_t pitch){
 assert(delayEvents<1000);eventTimes[delayEvents]=delayClock;eventTracks[delayEvents]=t;
 eventSources[delayEvents]=s;eventScales[delayEvents]=scale;eventPitches[delayEvents]=pitch;delayEvents++;
}
static void delayTicks(unsigned n){for(unsigned i=0;i<n;i++){delayClock++;perf_delayTick(captureDelay);}}

static void runFrames(unsigned count) {
 captureFine=1;
 for(unsigned t=0;t<count;t++) {
   fineNow=t;
   uint16_t span=perf_scaleFrames();
   uint16_t frame=(uint16_t)(t%span);
   if(!frame) {
     for(uint8_t track=0;track<7;track++) {
       uint8_t length=seq_patternSet.length[0][track];if(!length)length=16;
       seq_stepIndex[track]=perf_scaleToSource((uint8_t)((t/span)%perf_scaleCount(length)),length);
       seq_perfAdvance(track,seq_stepIndex[track],length);
     }
   }
   seq_prescaleCounter=frame/2;seq_finePhase=frame&1u;
   seq_processFineFrame();
 }
 captureFine=0;
}

int main(void){
 setup(3);perf_configure(0,0,100,100);seq_perfAdvance(0,0,16);
 PerfStep historyEvent={0,100,0,0,1,0x70000001};
 seq_patternSet.seq_subStepPattern[0][0][0].prob=0;
 check(!seq_conditionResolve(0,&historyEvent,0),"failed probability enters condition history");
 PerfStep dependent={1,1,0,1,1,0x70000002};
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 1, TRIG_COND_PRE);
 check(!seq_conditionResolve(0,&dependent,1),"PRE follows failed condition");
 dependent.eventId++;
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 1, TRIG_COND_NOT_PRE);
 check(seq_conditionResolve(0,&dependent,1),"not-PRE follows failure without replacing history");
 check(!seq_conditionHistory[0],"PRE variants do not replace history");
 seq_patternSet.seq_subStepPattern[0][0][0].prob=100;
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 0, TRIG_COND_FIRST);historyEvent.eventId+=10;
 check(seq_conditionResolve(0,&historyEvent,0),"true first condition enters history");
 trigTrackSet(&seq_patternSet.trigCondition[0][1], 0, TRIG_COND_NEI);historyEvent.eventId++;
 check(seq_conditionResolve(1,&historyEvent,0),"NEI follows preceding track");
 seq_conditionHistory[0]=0;
 check(seq_conditionResolve(1,&historyEvent,0),"flam reuses cached NEI result");
 setup(1);perf_configure(0,0,100,100);seq_perfAdvance(0,0,16);
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 0, TRIG_COND_FILL);
 check(seq_getShiftFlamPattern(0,0,STEP_CURRENT)==0,"FILL blocks step when off");
 activeParameters[PAR_PERF_FILL]=1;
 check(seq_getShiftFlamPattern(0,0,STEP_CURRENT)!=0,"FILL enables step when on");
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 0, TRIG_COND_RATIO_BASE+1);
 check(seq_getShiftFlamPattern(0,0,STEP_CURRENT)!=0,"1:2 plays first loop");
 seq_conditionLoop[0]=1;
 check(seq_getShiftFlamPattern(0,0,STEP_CURRENT)==0,"1:2 skips second loop");
 setup(1);perf_configure(0,0,100,100);
 seq_patternSet.seq_stepTiming[0][0][0].flam=5;
 seq_perfAdvance(0,0,16);
 seq_patternSet.flamProbability[0][0][0]=0;
 check(seq_getShiftFlamPattern(0,0,STEP_CURRENT)==(1u<<23),"FPR0 keeps main hit only");
 seq_patternSet.flamProbability[0][0][0]=100;
 check(seq_getShiftFlamPattern(0,0,STEP_CURRENT)==flamIdxToPattern(5),"FPR100 keeps all flam hits");
 for(unsigned frame=0;frame<24;frame++)seq_processFlam((uint8_t)frame);
 check(lfoTriggers[0]==1,"played flam group triggers step random once");
 for(unsigned track=1;track<=2;track++){
   setup(1);perf_configure(0,0,100,100);
   seq_mutedTracks=(uint8_t)(127u^(1u<<track));
   seq_perfAdvance((uint8_t)track,0,16);
   for(unsigned frame=0;frame<24;frame++)seq_processFlam((uint8_t)frame);
   check(lfoTriggers[track]==1,"voice 2 and 3 playback dispatch their own step event");
 }
 setup(1);perf_configure(0,0,100,100);
 seq_patternSet.seq_stepTiming[0][0][0].flam=5;seq_perfAdvance(0,0,16);
 seq_patternSet.flamProbability[0][0][0]=100;
 for(unsigned frame=0;frame<24;frame++)seq_processFlam((uint8_t)frame);
 check(hits==8,"FPR100 emits all eight flam notes");
 clearSpies();seq_patternSet.flamProbability[0][0][0]=0;
 for(unsigned frame=0;frame<24;frame++)seq_processFlam((uint8_t)frame);
 check(hits==1,"FPR0 emits exactly the main note");
 setup(1);seq_mutedTracks=127;seq_perfAdvance(0,0,16);
 for(unsigned frame=0;frame<24;frame++)seq_processFlam((uint8_t)frame);
 check(lfoTriggers[0]==0,"muted step does not trigger random LFO");
 setup(1);seq_patternSet.seq_subStepPattern[0][0][0].prob=0;seq_perfAdvance(0,0,16);
 for(unsigned frame=0;frame<24;frame++)seq_processFlam((uint8_t)frame);
 check(lfoTriggers[0]==0,"probability-skipped step does not trigger random LFO");
 for(int length=1;length<=64;length++) {
   perf_configure(0,0,100,100);perf_resetSteps();
   for(int tick=0;tick<length*4;tick++){
     const PerfTrack *s=perf_advance(0,(uint8_t)(tick%length),(uint8_t)length,UINT64_MAX,GetRngValue);
     check(s->current.source==tick%length,"neutral source timeline");
     check(s->prev.source==(tick%length?tick%length-1:length-1),"neutral previous wrap");
     check(s->next.source==(tick+1)%length,"neutral next wrap");
     check(s->prev2.source==(tick%length+2*length-2)%length&&s->next2.source==(tick+2)%length,
           "two-neighbor window wraps for all track lengths");
     check(s->current.probability>=1&&s->current.probability<=100,"step probability bounds");
   }
 }
 perf_configure(0,127,100,100);perf_resetSteps();
 for(int tick=0;tick<100;tick++){
   const PerfTrack *s=perf_advance(0,tick%16,16,1,GetRngValue);
   check(s->current.source==0,"CSR127 repeats last active source");
 }
 for(int amount=0;amount<=100;amount+=100){
   perf_configure(100,0,(uint8_t)amount,100);perf_resetSteps();
   for(int tick=0;tick<1024;tick++){
     const PerfTrack *s=perf_advance(0,tick%64,64,UINT64_MAX,GetRngValue);
     check(s->current.source<64,"random source within full track");
     check(s->current.drop==(amount==0),"Scarcity endpoints");
   }
 }
 perf_configure(0,0,100,0);
 for(int i=0;i<100;i++)check(!perf_allowHit(GetRngValue),"PST0 never plays");
 perf_configure(0,0,100,100);
 for(int i=0;i<100;i++)check(perf_allowHit(GetRngValue),"PST100 always permits");
 // Changing source controls must not wipe the event currently being played.
 const PerfTrack *live=perf_advance(0,5,16,UINT64_MAX,GetRngValue);
 uint8_t sourceBefore=live->current.source;
 perf_configure(100,0,100,100);
 check(live->current.source==sourceBefore,"no mid-step cache wipe");
 perf_configure(0,0,100,100);perf_resetSteps();
 perf_advance(0,0,16,UINT64_MAX,GetRngValue);
 perf_advance(0,1,16,UINT64_MAX,GetRngValue);
 perf_configure(0,127,100,100);
 live=perf_advance(0,2,16,UINT64_MAX,GetRngValue);
 check(live->current.source==1&&live->prev.source==1,"live CSR remembers last played source");
 // Actual flam dispatcher and actual trigger: notes, velocity, automation and
 // external MIDI all come from the same chosen source, with one MIDI output.
 setup(UINT64_MAX);perf_configure(100,0,100,100);
 for(int step=0;step<64;step++){
   seq_stepIndex[0]=step;seq_patternSet.length[0][0]=64;seq_perfAdvance(0,step,64);
   const PerfTrack *s=seq_perfTracks[0];uint8_t wanted=s->current.source;
   clearSpies();seq_processFlam(0);
   check(hits==1&&outputs==1&&automations==1,"one source hit and MIDI output");
   check(lastNote==40+wanted&&lastVelocity==20+wanted&&outVelocity==lastVelocity&&lastAuto==wanted,
       "random source note velocity automation consistent");
   check(seq_triggerSourceStep[0]==255,"source override released after trigger");
 }
 // One negative-shifted note belongs to next step and is triggered early.
 setup(2);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][1].shift=6;
 seq_perfAdvance(0,0,16);seq_processFlam(21);
 check(hits==1&&lastNote==41&&lastAuto==1,"negative shift lookahead source");
 setup(1);perf_configure(0,0,0,100);seq_patternSet.seq_stepTiming[0][0][0].flam=5;
 seq_perfAdvance(0,0,16);
 for(int i=0;i<24;i++)seq_processFlam(i);
 check(hits==0&&outputs==0,"Scarcity drops the entire flam step");
 setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_subStepPattern[0][0][0].prob=0;
 seq_perfAdvance(0,0,16);for(int i=0;i<24;i++)seq_processFlam(i);
 check(hits==0,"stored per-step probability remains effective");
 setup(1);perf_configure(0,0,100,0);seq_perfAdvance(0,0,16);
 for(int i=0;i<24;i++)seq_processFlam(i);check(hits==0,"PST gates sequencer hits");
 // Actual 606 button helper, all banks, followed by actual next-pattern logic.
 for(int bank=0;bank<4;bank++){
   buttonHandler_heldPatternKeys=0;menu_activePatternBank=bank;
   check(buttonHandler_selectPatternLoop(2)==bank*16+2&&!perf_getLoop(0,0),"single cancels loop");
   check(buttonHandler_selectPatternLoop(6)==bank*16+2&&perf_getLoop(0,0),"held range loop");
   for(int p=bank*16+2;p<=bank*16+6;p++){
     seq_activePattern=p;
     check(seq_determineNextPattern(1)==(p==bank*16+6?bank*16+2:p+1),"606 bounded sequence");
   }
   menu_playedPattern=bank*16+4;viewed=menu_playedPattern;led_initPatternSelectLeds();
   for(int i=0;i<16;i++)check(leds[i]==(i>=2&&i<=6),"loop range LEDs");
   check(blink[4]==1,"playing loop pattern blinks");
   buttonHandler_heldPatternKeys=0;buttonHandler_selectPatternLoop(9);
   check(!perf_getLoop(0,0),"single after release exits loop");
 }
 perf_setLoop(60,2);uint8_t start,end;
 check(perf_getLoop(&start,&end)&&start==2&&end==60,"loop endpoints normalize");
 perf_setLoop(63,255);check(perf_nextPattern(63)==63,"loop clamps to pattern63");
 seq_songModeEnabled=1;seq_songPositionPointer=0;seq_activeSong[1]=17;
 check(seq_determineNextPattern(1)==17,"song mode priority over live loop");seq_songModeEnabled=0;
 // Actual globals loader with old files and new appended fields.
 for(unsigned size=30;size<=64;size++){
   memset(activeParameters,255,sizeof(activeParameters));memset(fileData,0,sizeof(fileData));fileSize=size;
   for(unsigned i=30;i<size;i++)fileData[i]=255;
   check(preset_readGlobalData()==1,"old globals load");
   check(activeParameters[PAR_GLOBAL_DECAY]==63&&activeParameters[PAR_RANDOM_STEP]==0&&
       activeParameters[PAR_PERF_NOTE_REPEAT_CHANCE]==0&&activeParameters[PAR_PERF_SCARCITY]==100&&
       activeParameters[PAR_PERF_PROB]==100,"old file/padding extension defaults");
   check(activeParameters[PAR_PERF_NOTE_PROB]==100&&activeParameters[PAR_PERF_DELAY_CHANCE]==0&&
       activeParameters[PAR_PERF_DELAY_INPUT_MASK]==127&&activeParameters[PAR_PERF_VELO_LEVEL]==63&&
       activeParameters[PAR_PERF_VELO_DECAY]==63&&activeParameters[PAR_PERF_VELO_DRIVE]==63,
       "old delay/accent defaults and transient VLV reset");
   check(activeParameters[PAR_GROOVE_SH2]==63&&activeParameters[PAR_GROOVE_SH3]==63&&
       activeParameters[PAR_GROOVE_SH4]==63,"old project groove defaults are neutral");
 }
 memset(fileData,0,sizeof(fileData));fileSize=64;
 fileData[PAR_GLOBAL_DECAY-PAR_BEGINNING_OF_GLOBALS]=72;
 fileData[PAR_GLOBAL_PITCH-PAR_BEGINNING_OF_GLOBALS]=80;
 fileData[PAR_RANDOM_STEP-PAR_BEGINNING_OF_GLOBALS]=83;
 fileData[PAR_PERF_NOTE_REPEAT_CHANCE-PAR_BEGINNING_OF_GLOBALS]=127;
 fileData[PAR_PERF_SCARCITY-PAR_BEGINNING_OF_GLOBALS]=42;
 fileData[PAR_PERF_PROB-PAR_BEGINNING_OF_GLOBALS]=66;
 /* 0.2.86: gpt and gdc are live only and load neutral */
 check(preset_readGlobalData()&&activeParameters[PAR_GLOBAL_DECAY]==63&&activeParameters[PAR_GLOBAL_PITCH]==63&&activeParameters[PAR_RANDOM_STEP]==83&&
       activeParameters[PAR_PERF_NOTE_REPEAT_CHANCE]==127&&activeParameters[PAR_PERF_SCARCITY]==42&&
       activeParameters[PAR_PERF_PROB]==66,"new globals round trip fields");
 check(PAR_CPU_USE-PAR_BEGINNING_OF_GLOBALS==64&&PAR_PERF_VELO_LEVEL>PAR_CPU_USE,
       "stored globals fit reserved section; VLV excluded");
 check(PAR_GROOVE_SH2-PAR_BEGINNING_OF_GLOBALS==58&&PAR_GROOVE_SH4-PAR_BEGINNING_OF_GLOBALS==60,
       "groove appends without moving older stored fields");
 for(unsigned liveLoad=0;liveLoad<2;liveLoad++)for(unsigned storedLoad=0;storedLoad<2;storedLoad++) {
   memset(fileData,0,sizeof(fileData));fileSize=64;
   activeParameters[PAR_SHUFFLE_LOAD]=(uint8_t)liveLoad;
   activeParameters[PAR_GROOVE_SH2]=71;activeParameters[PAR_GROOVE_SH3]=42;activeParameters[PAR_GROOVE_SH4]=99;
   fileData[PAR_SHUFFLE_LOAD-PAR_BEGINNING_OF_GLOBALS]=(uint8_t)storedLoad;
   fileData[58]=11;fileData[59]=22;fileData[60]=33;
   check(preset_readGlobalData(),"groove globals load result");
   int allow=liveLoad&&storedLoad;
   check(activeParameters[PAR_GROOVE_SH2]==(allow?11:71)&&
         activeParameters[PAR_GROOVE_SH3]==(allow?22:42)&&
         activeParameters[PAR_GROOVE_SH4]==(allow?33:99),"LSH off preserves live groove during project load");
   check(activeParameters[PAR_SHUFFLE_LOAD]==allow,"project load cannot unlock live LSH off");
 }
 // CNT scales stored probability independently of PST and Scarcity.
 for(int cnt=0;cnt<=100;cnt++)for(int prob=0;prob<=100;prob++){
   perf_setNoteProbability((uint8_t)cnt);
   check(perf_scaleProbability((uint8_t)prob)==(prob*cnt+50)/100,"CNT probability scaling");
 }
 setup(1);perf_setNoteProbability(0);perf_configure(0,0,100,100);seq_perfAdvance(0,0,16);
 for(int i=0;i<24;i++)seq_processFlam(i);check(hits==0,"CNT0 silences original step");
 uint8_t sources[7]={0,1,2,3,4,5,6};
 const unsigned periods[16]={384,288,192,144,128,96,72,64,48,36,32,24,16,12,6,3};
 for(int rate=0;rate<16;rate++){
   PerfDelayConfig exact={100,(uint8_t)rate,3,63,10,0,64,1,0};
   perf_delayReset();perf_delayConfigure(exact);delayEvents=delayClock=0;
   perf_delayOffer(1,sources,GetRngValue);delayTicks(periods[rate]*3u);
   check(delayEvents==3&&eventTimes[0]==periods[rate]&&eventTimes[2]==periods[rate]*3u,
       "all named delay divisions exact at 96 PPQ");
 }
 PerfDelayConfig cfg={100,15,3,63,0,0,64,127,2};
 perf_delayReset();perf_delayConfigure(cfg);delayEvents=delayClock=0;
 perf_delayOffer(1,sources,GetRngValue);delayTicks(9);
 check(delayEvents==3&&eventTimes[0]==3&&eventTimes[1]==6&&eventTimes[2]==9,
       "delay exact pulse timing and repeat count");
 check(eventPitches[0]==2&&eventPitches[1]==4&&eventPitches[2]==6&&
       eventScales[0]==67&&eventScales[2]==0,"repeat pitch/velocity progression");
 for(int count=0;count<=32;count++){
   cfg=(PerfDelayConfig){100,15,(uint8_t)count,63,10,0,64,127,0};
   perf_delayReset();perf_delayConfigure(cfg);delayEvents=delayClock=0;
   perf_delayOffer(1,sources,GetRngValue);delayTicks(3u*(count+1));
   check(delayEvents==(unsigned)count,"bounded repeat counts");
 }
 cfg=(PerfDelayConfig){0,15,2,63,10,0,64,127,0};
 perf_delayReset();perf_delayConfigure(cfg);delayEvents=0;
 perf_delayOffer(127,sources,GetRngValue);delayTicks(20);check(!delayEvents,"RPT0 prevents chains");
 cfg.chance=100;cfg.mask=8;
 perf_delayConfigure(cfg);delayEvents=delayClock=0;perf_delayOffer(127,sources,GetRngValue);
 cfg.mask=0;perf_delayConfigure(cfg);perf_delayOffer(127,sources,GetRngValue);delayTicks(6);
 check(delayEvents==2&&eventTracks[0]==3&&eventTracks[1]==3,
       "input mask controls feeding; existing chain continues");
 cfg=(PerfDelayConfig){100,15,2,63,10,1,64,127,0};
 perf_delayReset();perf_delayConfigure(cfg);delayEvents=delayClock=0;
 for(int i=0;i<6;i++)perf_delayOffer(127,sources,GetRngValue);delayTicks(6);
 check(delayEvents==56,"poly capacity four chains per voice");
 cfg.poly=0;perf_delayConfigure(cfg);delayEvents=delayClock=0;
 perf_delayOffer(127,sources,GetRngValue);perf_delayOffer(127,sources,GetRngValue);delayTicks(6);
 check(delayEvents==2&&eventTracks[0]==eventTracks[1],"mono one global chain");
 cfg=(PerfDelayConfig){100,15,3,127,10,0,64,1,-12};
 perf_delayReset();perf_delayConfigure(cfg);delayEvents=delayClock=0;perf_delayOffer(1,sources,GetRngValue);
 cfg.pitch=12;cfg.bounce=0;perf_delayConfigure(cfg);delayTicks(30);
 check(delayEvents==3&&eventTimes[2]<9&&eventPitches[2]==-36,"chain snapshots and accelerating bounce");
 perf_delayReset();delayEvents=delayClock=0;perf_delayOffer(1,sources,GetRngValue);delayTicks(30);
 check(delayEvents==3&&eventTimes[2]>9,"negative bounce slows repeats");
 // Actual sequencer integration: repeats don't feed new repeat chains.
 setup(1);perf_configure(0,0,100,100);seq_perfAdvance(0,0,16);
 cfg=(PerfDelayConfig){100,15,2,63,10,1,64,1,1};perf_delayConfigure(cfg);
 for(int i=0;i<24;i++)seq_processFlam(i);
 check(hits==3&&outputs==3&&lastNote==42&&lastAuto==0,
       "two repeats emitted once with source automation and no feedback");
 // Real UI accessors/layer helpers and pulse function with LED spies.
 buttonHandler_mutedVoices=18;activeParameters[PAR_PERF_DELAY_INPUT_MASK]=53;
 selectedVoice=4;buttonHandler_openPerformanceLayer(PERF_DELAY_SUBPAGE);
 check(currentPage==PERF_PAGE&&menu_getSubPage()==2&&voiceMask==53&&!menu_muteModeActive&&
       buttonHandler_stateMemory.selectButtonMode==SELECT_MODE_PERF,"SHIFT3 layer and input LEDs");
 check(buttonHandler_handleDelayVoice(2)&&activeParameters[PAR_PERF_DELAY_INPUT_MASK]==49&&
       voiceMask==49&&buttonHandler_mutedVoices==18,"delay voice toggles don't change mutes");
 pulseCalls=0;led_pulsingLeds=0;led_pulseLed(LED_VOICE1+2);
 check(!pulseCalls&&!led_pulsingLeds,"trigger pulse cannot steal input-mask LED");
 buttonHandler_openPerformanceLayer(PERF_ACCENT_SUBPAGE);
 check(menu_getSubPage()==3&&voiceMask==((uint8_t)~18&127)&&buttonHandler_mutedVoices==18&&menu_muteModeActive,
       "SHIFT4 accent layer restores mute display");
 buttonHandler_openPerformanceLayer(PERF_GROOVE_SUBPAGE);
 check(menu_getSubPage()==4&&voiceMask==((uint8_t)~18&127)&&menu_muteModeActive,
       "SHIFT2 groove page keeps ordinary mute LEDs");
 buttonHandler_openPerformanceLayer(PERF_SEND_SUBPAGE);
 check(menu_getSubPage()==6&&voiceMask==((uint8_t)~18&127)&&menu_muteModeActive,
       "SHIFT5 send page keeps ordinary mute LEDs");
 buttonHandler_openPerformanceLayer(PERF_INT_SEND_SUBPAGE);
 check(menu_getSubPage()==7&&voiceMask==((uint8_t)~18&127)&&menu_muteModeActive,
       "SHIFT6 internal send page keeps ordinary mute LEDs");
 buttonHandler_openPerformanceLayer(PERF_SEND_SUBPAGE);
 check(!buttonHandler_handleDelayVoice(2)&&activeParameters[PAR_PERF_DELAY_INPUT_MASK]==49,
       "voice buttons outside delay don't toggle mask");
 currentPage=0;buttonHandler_refreshVoiceDisplay();check(voiceMask==16,"normal voice LED restored");
 led_pulseLed(LED_VOICE1+2);check(pulseCalls==1,"voice trigger pulse returns outside delay");

 // Exact half-tick positions through the actual integrated dispatcher.
 setup(2);perf_configure(0,0,100,100);
 perf_grooveConfigure(&seq_groove,127,0,63,63);perf_delaySetGroove(&seq_groove);
 runFrames(192);
 check(fineHits==1&&fineTimes[0]==12&&fineSources[0]==1,"SH2 negative advance keeps next source note/automation");
 setup(2);perf_configure(0,0,100,100);
 perf_grooveConfigure(&seq_groove,127,127,63,63);perf_delaySetGroove(&seq_groove);
 runFrames(192);
 check(fineHits==1&&fineTimes[0]==84&&fineSources[0]==1,"SH2 positive delay keeps source");
 setup(4);perf_configure(0,0,100,100);
 perf_grooveConfigure(&seq_groove,127,63,127,63);perf_delaySetGroove(&seq_groove);
 seq_patternSet.seq_stepTiming[0][0][2].shift=14;
 seq_patternSet.seq_stepTiming[0][0][2].flam=5;
 runFrames(384);
 check(fineHits==8,"groove plus shift preserves all eight flam hits");
 for(unsigned i=0;i<8;i++)check(fineTimes[i]==174+6*i&&fineSources[i]==2,"previous-two-step shifted flam tail");
 setup(4);perf_configure(0,0,100,100);
 perf_grooveConfigure(&seq_groove,127,63,0,63);perf_delaySetGroove(&seq_groove);
 seq_patternSet.seq_stepTiming[0][0][2].shift=0;
 runFrames(192);
 check(fineHits==1&&fineTimes[0]==18&&fineSources[0]==2,"next-two-step negative shift and groove");
 // A nonzero shape with zero master is identical to the legacy neutral path.
 for(unsigned gate=0;gate<3;gate++) {
   setup(2);perf_configure(0,0,gate==0?0:100,gate==1?0:100);
   if(gate==2)perf_setNoteProbability(0);
   perf_grooveConfigure(&seq_groove,127,0,63,63);perf_delaySetGroove(&seq_groove);
   perf_delayConfigure((PerfDelayConfig){100,11,2,63,10,1,64,1,0});
   runFrames(192);check(!fineHits,"Scarcity/PST/CNT also gate grooved events and delay input");
 }
 setup(UINT64_MAX);perf_configure(0,0,100,100);
 perf_grooveConfigure(&seq_groove,0,0,127,0);perf_delaySetGroove(&seq_groove);
 runFrames(192);
 check(fineHits==4,"neutral fine wrapper does not double trigger");
 for(unsigned i=0;i<4;i++)check(fineTimes[i]==i*perf_scaleFrames(),"neutral events stay on straight boundaries");
 // 0.2.55 humanize: two voices on every step, each rolls its own offset within +-12 frames
 setup(UINT64_MAX);perf_configure(0,0,100,100);seq_mutedTracks=124;
 for(unsigned lane=0;lane<4;lane++)seq_groove.human[lane]=127;perf_delaySetGroove(&seq_groove);
 runFrames(800);
 {
   int when[2][16];unsigned count[2][16];memset(count,0,sizeof(count));
   for(unsigned i=0;i<fineHits;i++)if(fineVoices[i]<2&&fineSources[i]<16&&fineTimes[i]<15*48){
     when[fineVoices[i]][fineSources[i]]=(int)fineTimes[i];count[fineVoices[i]][fineSources[i]]++;}
   unsigned apart=0,moved=0;
   for(unsigned s=1;s<15;s++){
     check(count[0][s]==1&&count[1][s]==1,"humanize keeps one hit per voice and step");
     for(unsigned v=0;v<2;v++){int d=when[v][s]-(int)s*48;check(d>=-12&&d<=12&&!(d&1),"humanize stays within +-12 even frames");moved+=d!=0;}
     apart+=when[0][s]!=when[1][s];
   }
   check(apart>=7,"voices on the same step are humanized independently");
   check(moved>=14,"humanize moves most hits");
 }
 setup(UINT64_MAX);perf_configure(0,0,100,100);seq_mutedTracks=124;
 memset(seq_groove.human,0,sizeof(seq_groove.human));seq_groove.human[0]=127;perf_delaySetGroove(&seq_groove);
 runFrames(15*48);
 for(unsigned i=0;i<fineHits;i++)if(fineSources[i]&3)check(fineTimes[i]==fineSources[i]*48u,"hm1 leaves the other lanes straight");
 memset(seq_groove.human,0,sizeof(seq_groove.human));
 // Odd Mutador offsets must survive as odd 192-PPQ frame positions.
 setup(2);perf_configure(0,0,100,100);
 perf_grooveConfigure(&seq_groove,127,68,63,63);perf_delaySetGroove(&seq_groove);
 runFrames(192);
 check(fineHits==1&&fineTimes[0]==51,"half-96-PPQ-tick event is not rounded");
 // Delay starts from the groove lane that played, and follows live target lanes.
 setup(2);perf_configure(0,0,100,100);
 perf_grooveConfigure(&seq_groove,127,127,63,63);perf_delaySetGroove(&seq_groove);
 perf_delayConfigure((PerfDelayConfig){100,11,2,63,10,1,64,1,0});
 runFrames(192);
 check(fineHits==3&&fineTimes[0]==84&&fineTimes[1]==96&&fineTimes[2]==144,
       "grooved delay corrects initial and subsequent lane spacing");
 // Internal scheduler: 192 fine pulses, 96 legacy clock ticks and 24 MIDI clocks/quarter.
 setup(2);perf_configure(0,0,100,100);
 perf_grooveConfigure(&seq_groove,127,0,63,63);perf_delaySetGroove(&seq_groove);
 memset(seq_stepIndex,255,sizeof(seq_stepIndex));seq_prescaleCounter=seq_finePhase=0;
 seq_tempo=125;seq_deltaT=0;seq_lastTick=0;captureFine=1;
 for(systick_ticks=0;systick_ticks<1920;systick_ticks++){fineNow=systick_ticks;seq_tick();}
 captureFine=0;
 check(boundaryCalls==4&&clockTicks==96&&midiClocks==24,"internal quarter timing and unchanged MIDI clock");
 check(fineHits==1&&fineTimes[0]==120,"internal clock executes advanced note on exact fine tick");
 // All eight rates keep MIDI clock straight and produce exact steps per bar.
 const uint8_t divisions[8]={2,4,6,8,12,16,24,32};
 for(unsigned rate=0;rate<8;rate++) {
   setup(UINT64_MAX);perf_scaleSetPattern(perf_scaleDivision(rate),0);perf_configure(0,0,100,100);
   memset(seq_stepIndex,255,sizeof(seq_stepIndex));seq_prescaleCounter=seq_finePhase=0;
   seq_tempo=125;seq_deltaT=0;seq_lastTick=0;
   for(systick_ticks=0;systick_ticks<7680;systick_ticks++)seq_tick();
   check(boundaryCalls==divisions[rate]&&midiClocks==96&&clockTicks==384,
       "eight scale rates preserve full-bar MIDI clock and event count");
 }
 // A confirmed selection stays pending mid-bar and restarts Step 1 once on the next 1.
 setup(UINT64_MAX);perf_scaleSetPattern(16,0);perf_configure(0,0,100,100);
 memset(seq_stepIndex,255,sizeof(seq_stepIndex));seq_prescaleCounter=seq_finePhase=0;
 seq_tempo=125;seq_deltaT=0;seq_lastTick=0;
 for(systick_ticks=0;systick_ticks<1000;systick_ticks++)seq_tick();
 perf_scaleSetPattern(32,1);
 for(;systick_ticks<7680;systick_ticks++)seq_tick();
 check(perf_scaleMode()==16&&boundaryCalls==16,"confirmed internal scale waits for next bar");
 seq_tick();check(perf_scaleMode()==32&&boundaryCalls==17&&seq_stepIndex[0]==0&&midiClocks==97,
       "confirmed internal scale starts Step 1 once on next downbeat");
 // Live sct keeps the musical place: every quarter starts the same source group.
 for(unsigned path=0;path<256;path++) {
  setup(UINT64_MAX);perf_scaleSetPattern(16,0);perf_transformSet(0,0);perf_configure(0,0,100,100);
  memset(seq_stepIndex,255,sizeof(seq_stepIndex));seq_prescaleCounter=seq_finePhase=0;
  seq_tempo=125;seq_deltaT=0;seq_lastTick=0;unsigned quarter=0,mode=0,previous=0;
  for(systick_ticks=0;systick_ticks<16u*1920u;systick_ticks++) {
   if(systick_ticks%437u==path%437u)perf_transformSet((uint8_t)(mode=(mode+path+1u)&3u),1);
   seq_tick();
   const unsigned frame=seq_scaleBarFrame;
   if(frame>=1u && frame%192u==1u && frame!=previous) {
    previous=frame;quarter++;
    check(seq_stepIndex[0]==(int8_t)(((quarter-1u)*4u)&15u),"live sct stays on the quarter grid");
   }
  }
  perf_transformSet(0,0);
 }
 // Ternary gaps pause every track for one slot and keep the bar length.
 // External scheduler uses each actual MIDI edge, without groove on the transport.
 setup(2);perf_configure(0,0,100,100);externalSync=2;
 perf_grooveConfigure(&seq_groove,127,0,63,63);perf_delaySetGroove(&seq_groove);
 memset(seq_stepIndex,255,sizeof(seq_stepIndex));seq_prescaleCounter=24;seq_finePhase=0;
 seq_tempo=125;seq_lastTick=0;seq_deltaT=0;sync_clockCnt=sync_armed=sync_samples=sync_writePos=0;
 memset(sync_window,0,sizeof(sync_window));captureFine=1;
 for(systick_ticks=0;systick_ticks<1920;systick_ticks++){
   fineNow=systick_ticks;if(systick_ticks%80==0)sync_tick();seq_tick();
 }
 captureFine=0;
 check(boundaryCalls==4&&clockTicks==96&&!midiClocks&&seq_tempo==125,"external warmup timing and no clock echo");
 check(fineHits==1&&fineTimes[0]==120,"external interpolation preserves negative groove note");
 unsigned before=hits;for(systick_ticks=1920;systick_ticks<4000;systick_ticks++)seq_tick();
 check(hits==before&&boundaryCalls==4,"clock loss does not free-run notes or delay");
 externalSync=0;
 // MIDI clock lead: step fires once before the expected edge and the edge
 // confirms it without a second trigger. Zero offset keeps edge timing.
 setup(2);externalSync=2;sync_clockCnt=sync_armed=sync_samples=sync_writePos=0;
 sync_cycleSamples=sync_cycleWritePos=sync_leadArmed=sync_leadConsumed=0;
 memset(sync_window,0,sizeof(sync_window));sync_setClockOffset(50,0);
 seq_prescaleCounter=24;dwtMock.CYCCNT=0;systick_ticks=0;sync_tick();
 const uint32_t edgeCycles=4320000u;
 for(unsigned pulse=1;pulse<6;pulse++){
   systick_ticks+=80;dwtMock.CYCCNT=pulse*edgeCycles;sync_tick();
 }
 check(sync_leadArmed&&sync_nextLeadCycles==6*edgeCycles-1080000u,"five millisecond lead scheduled after sixth clock");
 before=boundaryCalls;dwtMock.CYCCNT=sync_nextLeadCycles-1;seq_tick();
 check(boundaryCalls==before,"lead waits until deadline");
 dwtMock.CYCCNT=sync_nextLeadCycles;seq_tick();
 check(boundaryCalls==before+1&&sync_leadConsumed,"lead plays one step early");
 systick_ticks+=80;dwtMock.CYCCNT=6*edgeCycles;sync_tick();
 check(boundaryCalls==before+1&&!sync_leadConsumed,"real MIDI edge does not duplicate the led step");
 sync_setClockOffset(0,0);for(unsigned pulse=7;pulse<=12;pulse++){
   systick_ticks+=80;dwtMock.CYCCNT=pulse*edgeCycles;sync_tick();
 }
 check(!sync_leadArmed&&boundaryCalls==before+2,"zero offset returns to edge-triggered playback");
 // Manual PLAY while MIDI Clock runs waits for the next 96-pulse bar.
 setup(2);externalSync=2;seq_running=0;seq_prescaleCounter=24;
 // Without MIDI START the pulse count is no bar, so PLAY starts at once.
 sync_barPhaseFromStart=0;sync_barPhaseValid=1;sync_barClockCnt=40;sync_startOnNextBar=0;seq_running=0;
 sync_requestStartOnNextBar();
 check(seq_running&&!sync_startOnNextBar&&sync_barClockCnt==95&&!sync_clockCnt,"PLAY without MIDI START starts at once");
 seq_running=0;sync_barPhaseFromStart=1;sync_barClockCnt=40;
 sync_requestStartOnNextBar();
 check(!seq_running&&sync_startOnNextBar,"PLAY after MIDI START waits for the bar");
 sync_startOnNextBar=0;sync_lastClockTick=0;systick_ticks=4001;sync_tickAtCycles(1000);
 check(!sync_barPhaseFromStart,"lost clock forgets the MIDI START position");
 sync_barPhaseFromStart=1;seq_running=0;
 sync_barPhaseValid=1;sync_barClockCnt=94;sync_clockCnt=4;
 sync_startOnNextBar=sync_startLeadArmed=sync_leadArmed=sync_leadConsumed=0;
 sync_armed=1;sync_cycleSamples=1;sync_cycleWindow[0]=edgeCycles;
 sync_lastClockCycles=94*edgeCycles;sync_setClockOffset(50,0);
 before=boundaryCalls;sync_requestStartOnNextBar();
 check(sync_startOnNextBar&&!seq_running,"manual start arms while bar is in progress");
 dwtMock.CYCCNT=95*edgeCycles;systick_ticks+=80;sync_tick();
 check(sync_startLeadArmed&&!seq_running,"manual start predicts upcoming bar boundary");
 dwtMock.CYCCNT=sync_nextStartCycles;seq_tick();
 check(seq_running&&boundaryCalls==before+1,"manual start plays once before bar edge");
 dwtMock.CYCCNT=96*edgeCycles;systick_ticks+=80;sync_tick();
 check(boundaryCalls==before+1,"real bar edge confirms without duplicate step");
 seq_running=0;sync_barClockCnt=94;sync_clockCnt=4;
 sync_setClockOffset(0,0);before=boundaryCalls;sync_requestStartOnNextBar();
 dwtMock.CYCCNT=97*edgeCycles;systick_ticks+=80;sync_tick();
 check(!seq_running&&!sync_startLeadArmed,"zero-offset manual start waits through pulse 95");
 dwtMock.CYCCNT=98*edgeCycles;systick_ticks+=80;sync_tick();
 check(seq_running&&boundaryCalls==before+1,"zero-offset manual start plays on pulse 96");
 sync_setClockOffset(80,9);check(sync_clockOffsetHundredths==0,"8 ms maximum clears fine digit");
 externalSync=0;
 setup(UINT64_MAX);perf_scaleSetPattern(12,0);externalSync=2;
 sync_clockCnt=sync_armed=sync_samples=sync_writePos=0;
 sync_cycleSamples=sync_cycleWritePos=sync_leadArmed=sync_leadConsumed=0;
 sync_setClockOffset(0,0);before=boundaryCalls;
 for(unsigned pulse=0;pulse<=8;pulse++){
   systick_ticks=pulse*80;dwtMock.CYCCNT=pulse*edgeCycles;sync_tick();
   if(pulse==6)check(boundaryCalls==before+1,"12-grid waits beyond sixth MIDI pulse");
 }
 check(boundaryCalls==before+2,"12-grid advances on eighth MIDI pulse");
 // Six-tick steps alternate one and two clocks, so a bar keeps all 64 of them.
 setup(UINT64_MAX);perf_scaleSetPattern(16,0);perf_speedSet(5,0);externalSync=2;sync_setClockOffset(0,0);
 sync_clockCnt=sync_armed=sync_samples=sync_writePos=sync_stepFlip=0;sync_barClockCnt=95;sync_barPhaseValid=1;
 sync_cycleSamples=sync_cycleWritePos=sync_leadArmed=sync_leadConsumed=0;
 memset(seq_stepIndex,255,sizeof(seq_stepIndex));
 for(unsigned pulse=0;pulse<96;pulse++){systick_ticks=pulse*80;sync_tickAtCycles(pulse*edgeCycles);}
 check(boundaryCalls==64,"six-tick steps fill the bar on MIDI clock");
 perf_speedSet(PERF_SPEED_NEUTRAL,0);
 // External MIDI uses the transport downbeat even when a change was queued mid-bar.
 setup(UINT64_MAX);perf_scaleSetPattern(16,0);externalSync=2;sync_setClockOffset(0,0);
 sync_clockCnt=sync_armed=sync_samples=sync_writePos=0;sync_barClockCnt=95;sync_barPhaseValid=1;
 sync_cycleSamples=sync_cycleWritePos=sync_leadArmed=sync_leadConsumed=0;
 memset(seq_stepIndex,255,sizeof(seq_stepIndex));
 for(unsigned pulse=0;pulse<96;pulse++){
   if(pulse==20)perf_scaleSetPattern(32,1);
   systick_ticks=pulse*80;sync_tickAtCycles(pulse*edgeCycles);
 }
 check(perf_scaleMode()==16&&boundaryCalls==16,"external scale remains pending until MIDI downbeat");
 systick_ticks=96*80;sync_tickAtCycles(96*edgeCycles);
 check(perf_scaleMode()==32&&boundaryCalls==17&&seq_stepIndex[0]==0,"MIDI downbeat applies scale with one Step 1");
 externalSync=0;perf_scaleSetPattern(16,0);
 for(unsigned mode=1;mode<=8;mode++) {
   setup(UINT64_MAX);perf_configure(0,0,100,100);perf_scaleSetPattern(mode?perf_scaleDivision((uint8_t)(mode-1)):16,0);
   unsigned count=perf_scaleCount(16);runFrames(count*perf_scaleFrames());
   check(fineHits==count,"global grid compresses actual playback timeline");
   for(unsigned i=0;i<count;i++)check(fineSources[i]==perf_scaleToSource((uint8_t)i,16)&&fineTimes[i]==i*perf_scaleFrames(),
       "actual grid dispatcher uses correct stored source and timing");
 }
 setup(8);perf_configure(0,0,100,100);perf_scaleSetPattern(12,0);
 perf_grooveConfigure(&seq_groove,127,63,63,0);perf_delaySetGroove(&seq_groove);
 runFrames(192);check(fineHits==1&&fineTimes[0]==144&&fineSources[0]==3,"12-step page and negative groove use scaled timing");
 setup(UINT64_MAX);perf_configure(100,0,100,100);perf_scaleSetPattern(12,0);runFrames(1152);
 for(unsigned i=0;i<fineHits;i++)check((fineSources[i]&15u)<12,"RST stays inside selected global grid");
 setup(1);perf_configure(0,127,100,100);perf_scaleSetPattern(12,0);runFrames(768);
 check(fineHits==12,"CSR retains repeats on compressed grid");
 for(unsigned i=0;i<fineHits;i++)check(fineSources[i]==0,"CSR source metadata survives grid mapping");
 perf_scaleSetPattern(16,0);
 currentPage=PERF_PAGE;menuIndex=0;
 for(unsigned page=0;page<8;page++){menuPages[PERF_PAGE][page].top1=1;menuPages[PERF_PAGE][page].top5=(page==4||page==5)?0:1;}
 const uint8_t screens[6]={0,4,8,12,40,0};
 for(unsigned i=0;i<6;i++) {
   check(menuIndex==screens[i],"PERF cycle excludes dedicated SHIFT windows, sends and VCA page");
   menu_switchSubPage(menu_getSubPage(),1);
 }
 setup(UINT64_MAX);for(unsigned t=0;t<7;t++)seq_patternSet.length[0][t]=4;
 seq_patternSet.length[0][3]=0;
 check(seq_getLongestTrack()==3,"legacy length zero is sixteen when choosing pattern boundary");
 perf_scaleSetPattern(12,0);check(seq_getLongestTrack()==3,"pattern boundary follows longest compressed track");
 perf_scaleSetPattern(16,0);


 for(unsigned voice=0;voice<7;voice++) {
   selectedVoice=(uint8_t)voice;currentPage=(uint8_t)voice;menuIndex=0;
   menuPages[voice][6].top5=1;
   unsigned extra=LFO_EXTRA1_PAGE+(voice>5?5:voice);
   menuPages[extra][0].top5=1;
   for(unsigned cycle=0;cycle<3;cycle++) {
     for(unsigned screen=0;screen<4;screen++) {
       check(menu_cycleVoiceLfo(6),"LFO click handled in voice editing");
       menu_resetActiveParameter();
       check(currentPage==(screen<2?voice:extra),"LFO click reaches correct voice or random page");
       check(menuIndex==(screen<2?(6u<<PAGE_SHIFT):0u)+(screen&1u)*4u,"LFO four-screen cycle survives parameter reset");
     }
   }
   check(menu_cycleVoiceLfo(5)&&currentPage==voice&&menuIndex==(5u<<PAGE_SHIFT),"another voice button exits random page");
 }
 currentPage=PERF_PAGE;menuIndex=0;
 check(!menu_cycleVoiceLfo(6)&&currentPage==PERF_PAGE,"LFO helper leaves PERF alone");
 // Tape delay tempo: whole smoothed beats, so jittery clocks hold steady.
 setup(UINT64_MAX);externalSync=2;sync_setClockOffset(0,0);
 sync_clockCnt=sync_armed=sync_samples=sync_writePos=0;
 sync_beatRunning=sync_beatOutliers=0;sync_beatCycles=0.f;
 {
  uint32_t cyc=0,tick=0,seed=1;float lo=1e9f,hi=0.f,slowest=0.f;
  const uint32_t pulse120=4500000u; // 120 BPM: 216 MHz * 0.5 s / 24
  for(unsigned n=0;n<24u*60u;n++){
   seed=seed*1664525u+1013904223u;
   const int32_t jitter=(int32_t)(seed%432001u)-216000; // +-1 ms
   cyc+=pulse120;tick+=125;dwtMock.CYCCNT=cyc+(uint32_t)jitter;systick_ticks=tick;sync_tick();
   if(n>=24u*20u){const float b=sync_getBeatBpm();if(b<lo)lo=b;if(b>hi)hi=b;}
  }
  check(lo>119.88f&&hi<120.12f,"jittered clock holds the tape tempo within 0.1 %");
  check(seq_tempo>=119&&seq_tempo<=121,"sequencer tempo rounds to 120");
  // The clock slows to 100 BPM: two beats off retake the tempo at once.
  for(unsigned n=0;n<24u*4u;n++){cyc+=5400000u;tick+=150;dwtMock.CYCCNT=cyc;systick_ticks=tick;sync_tick();
   if(n==24u*3u)slowest=sync_getBeatBpm();}
  check(slowest>99.f&&slowest<101.f,"tempo change arrives after three beats");
  // One beat with a lost clock is ignored, not taken.
  cyc+=5400000u*2u;tick+=300;dwtMock.CYCCNT=cyc;systick_ticks=tick;sync_tick();
  for(unsigned n=0;n<23u;n++){cyc+=5400000u;tick+=150;dwtMock.CYCCNT=cyc;systick_ticks=tick;sync_tick();}
  check(sync_getBeatBpm()>99.f&&sync_getBeatBpm()<101.f,"single odd beat is ignored");
  // No clock for half a second: back to the sequencer tempo.
  seq_tempo=133;systick_ticks=tick+2001u;
  check(sync_getBeatBpm()==133.f,"clock timeout falls back to the sequencer tempo");
 }
 externalSync=0;
 // 2+1..8+1: the roll plus one hit at the start of the following empty step.
 for(unsigned k=0;k<5;k++)
   check(flamIdxToPattern((uint8_t)(FLAM_PLUS_ONE_FIRST+k))==flamIdxToPattern((uint8_t)(k+1)),"2+1..8+1 roll like x2..x8");
 setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=FLAM_PLUS_ONE_FIRST;
 runFrames(192);
 check(fineHits==3&&fineTimes[0]==0&&fineTimes[1]==24&&fineTimes[2]==48,"2+1 adds one hit at the start of the empty next step");
 check(fineSources[0]==0&&fineSources[1]==0&&fineSources[2]==0,"the +1 hit plays the note of its own step");
 setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=FLAM_PLUS_ONE_LAST;
 runFrames(192);
 check(fineHits==9&&fineTimes[8]==48&&fineSources[8]==0,"8+1 plays the eight-hit roll and one more");
 setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=5;
 runFrames(192);
 check(fineHits==8,"x8 stays inside its step");
 // 0.2.56 flam velocity: straight path and fine (groove/humanize) path, fade and rise
 for(unsigned path=0;path<2;path++){
   static const char *names[2]={"straight","fine"};
   for(unsigned curve=0;curve<3;curve++){
     const uint8_t fvl=curve==0?0:curve==1?100:25; /* -100, +100, -50 */
     setup(1);perf_configure(0,0,100,100);
     if(path){seq_groove.human[1]=127;perf_delaySetGroove(&seq_groove);} /* fine path, lane 0 stays straight */
     seq_patternSet.seq_stepTiming[0][0][0].flam=3; /* x4 */
     seq_flamPresets[3].velo=fvl; /* 0.2.61: the velocity curve belongs to the preset */
     runFrames(48);
     const unsigned base=seq_patternSet.seq_subStepPattern[0][0][0].volume&STEP_VOLUME_MASK;
     check(fineHits==4,names[path]);
     if(fineHits==4){
       if(curve==0)check(fineVelocities[0]==base&&fineVelocities[3]==0&&fineVelocities[1]>fineVelocities[2],"fvl -100 fades to silence");
       if(curve==1)check(fineVelocities[0]==0&&fineVelocities[3]==base&&fineVelocities[1]<fineVelocities[2],"fvl +100 rises to the step velocity");
       if(curve==2)check(fineVelocities[0]==base&&fineVelocities[3]==(base+1)/2,"fvl -50 ends at half");
     }
     memset(seq_groove.human,0,sizeof(seq_groove.human));perf_delaySetGroove(&seq_groove);
   }
 }
 setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=FLAM_PLUS_ONE_FIRST;
 seq_flamPresets[FLAM_PLUS_ONE_FIRST].velo=0;runFrames(192);
 check(fineHits==3&&fineVelocities[2]==0&&fineVelocities[1]>0&&fineVelocities[1]<fineVelocities[0],"2+1: the +1 hit is the last of the curve");
 setup(1);perf_configure(0,0,100,100);seq_flamPresets[3].velo=0;runFrames(48);
 check(fineHits==1&&fineVelocities[0]==(seq_patternSet.seq_subStepPattern[0][0][0].volume&STEP_VOLUME_MASK),"fvl leaves a step without flam alone");
 setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=3;seq_patternSet.seq_stepTiming[0][0][0].shift=10;
 seq_flamPresets[3].velo=0;runFrames(96);
 check(fineHits==4&&fineVelocities[0]==(seq_patternSet.seq_subStepPattern[0][0][0].volume&STEP_VOLUME_MASK)&&fineVelocities[0]>fineVelocities[1]&&fineVelocities[1]>fineVelocities[2]&&fineVelocities[3]==0,"shifted flam keeps its curve");
 setup(3);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=FLAM_PLUS_ONE_FIRST;
 runFrames(192);
 check(fineHits==3&&fineTimes[2]==48&&fineSources[2]==1,"a note on the next step plays alone, the flam stays normal");
 setup(3);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=FLAM_PLUS_ONE_FIRST;
 seq_patternSet.seq_subStepPattern[0][0][1].prob=0;
 runFrames(192);
 check(fineHits==2,"a next note muted by its chance still blocks the +1 hit");
 setup(1u<<15);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][15].flam=FLAM_PLUS_ONE_FIRST;
 runFrames(17*48);
 check(fineHits==2&&fineTimes[0]==720&&fineTimes[1]==744,"the last step of the track plays only its normal flam");
 setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=FLAM_PLUS_ONE_FIRST;
 seq_patternSet.flamProbability[0][0][0]=0;
 runFrames(192);
 check(fineHits==1,"fpr 0 drops the +1 hit with the other repeats");
 setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=FLAM_PLUS_ONE_FIRST;
 seq_patternSet.seq_stepTiming[0][0][0].shift=8;
 runFrames(192);
 check(fineHits==3&&fineTimes[0]==6&&fineTimes[1]==30&&fineTimes[2]==54,"a positive shift moves the +1 hit along");
 setup(4);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][2].flam=FLAM_PLUS_ONE_FIRST;
 seq_patternSet.seq_stepTiming[0][0][2].shift=6;
 runFrames(192);
 check(fineHits==3&&fineTimes[0]==90&&fineTimes[1]==114&&fineTimes[2]==138&&fineSources[2]==2,
       "a negative shift moves the +1 hit back into its own step");
 setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=FLAM_PLUS_ONE_FIRST;
 perf_grooveConfigure(&seq_groove,127,127,63,63);perf_delaySetGroove(&seq_groove);
 runFrames(192);
 check(fineHits==3&&fineTimes[0]==0&&fineTimes[1]==24&&fineTimes[2]==84&&fineSources[2]==0,
       "with groove the +1 hit takes the groove of the step it sits on");
 // 0.2.61 flam presets: repeats on a grid, accelerate/brake, pitch per hit
 for(unsigned path=0;path<2;path++){
   setup(1);perf_configure(0,0,100,100);
   if(path){seq_groove.human[1]=127;perf_delaySetGroove(&seq_groove);}
   seq_flamPresets[11]=(FlamPreset){3,2,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(48);
   check(fineHits==3&&fineTimes[0]==0&&fineTimes[1]==12&&fineTimes[2]==24,"3 repeats on the x4 grid");
   setup(1);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){12,1,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(48);
   check(fineHits==3&&fineTimes[2]==32,"repeats stay inside the step");
   setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(48);
   check(fineHits==4&&fineTimes[1]==16&&fineTimes[2]==28&&fineTimes[3]==36,"F11 accelerates: gaps 8, 6, 4 pulses");
   setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=12;runFrames(48);
   check(fineHits==4&&fineTimes[1]==8&&fineTimes[2]==20&&fineTimes[3]==36,"F12 brakes: gaps 4, 6, 8 pulses");
   setup(1);perf_configure(0,0,100,100);seq_patternSet.seq_stepTiming[0][0][0].flam=13;runFrames(48);
   check(fineHits==3&&fineSources[0]==0&&fineSources[1]==2&&fineSources[2]==4,"F13 raises each hit by two semitones");
   setup(1);perf_configure(0,0,100,100);seq_flamPresets[7].pitch=FLAM_PITCH_ZERO-1;seq_flamPresetsChanged();
   seq_patternSet.seq_subStepPattern[0][0][0].note=43;seq_patternSet.seq_stepTiming[0][0][0].flam=7;runFrames(192);
   check(fineHits==4&&fineSources[0]==3&&fineSources[1]==2&&fineSources[2]==1&&fineSources[3]==0&&fineTimes[3]==48,"pitch steps reach the +1 hit");
   setup(1);perf_configure(0,0,100,100);seq_flamPresets[13].pitch=FLAM_PITCH_ZERO-3;seq_flamPresetsChanged();
   seq_patternSet.seq_subStepPattern[0][0][0].note=1;seq_patternSet.seq_stepTiming[0][0][0].flam=13;runFrames(48);
   check(fineHits==3&&fineSources[1]==(uint8_t)(0-40)&&fineSources[2]==(uint8_t)(0-40),"pitch stops at note 0");
   memset(seq_groove.human,0,sizeof(seq_groove.human));perf_delaySetGroove(&seq_groove);
 }
 // 0.2.63 long flams: stp spreads the hits over several steps, the flam has priority
 for(unsigned path=0;path<2;path++){
   setup(3);perf_configure(0,0,100,100);
   if(path){seq_groove.human[1]=127;perf_delaySetGroove(&seq_groove);}
   seq_flamPresets[11]=(FlamPreset){4,0,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT,2};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(96);
   check(fineHits==4&&fineTimes[0]==0&&fineTimes[1]==24&&fineTimes[2]==48&&fineTimes[3]==72,"stp 2 x2 grid: 4 hits over two steps");
   check(fineSources[1]==0&&fineSources[2]==0&&fineSources[3]==0,"the long flam has priority over the next note");
   setup(3);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){2,0,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT,2};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(96);
   check(fineHits==2&&fineTimes[1]==24,"a note in a gap of the long flam stays silent");
   setup(7);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){4,0,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT,2};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(144);
   check(fineHits==5&&fineTimes[4]==96&&fineSources[4]==2,"the step after the flam plays again");
   setup(1);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){3,0,50,FLAM_PITCH_ZERO+1,0,FLAM_ACCEL_FLAT,4};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(192);
   check(fineHits==3&&fineTimes[2]==48&&fineSources[1]==1&&fineSources[2]==2,"rep limits a long flam and the pitch runs over it");
   setup(5);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){2,0,50,FLAM_PITCH_ZERO,1,FLAM_ACCEL_FLAT,2};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(192);
   check(fineHits==3&&fineTimes[1]==24&&fineTimes[2]==96&&fineSources[2]==0,"the +1 hit follows the end of the long flam and wins");
   setup(1);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){8,2,50,FLAM_PITCH_ZERO,0,80,2};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(96);
   check(fineHits==8,"bb keeps all hits of a long flam");
   for(unsigned i=2;i<fineHits;i++)check(fineTimes[i]-fineTimes[i-1]<=fineTimes[i-1]-fineTimes[i-2],"bb accelerates over the whole length");
   setup(1);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){4,0,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT,2};seq_flamPresetsChanged();
   seq_patternSet.flamProbability[0][0][0]=0;seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(96);
   check(fineHits==1,"fpr drops the whole long flam");
   // 0.2.65 slow grids: t8 = 3 hits over 4 steps (eighth triplets), t16 = 3 over 2, /3 = every 3 steps
   setup(1);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){3,8,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT,4};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(192);
   check(fineHits==3&&fineTimes[0]==0&&fineTimes[1]==64&&fineTimes[2]==128,"t8 plays eighth triplets over 4 steps");
   setup(1);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){6,6,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT,2};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(96);
   check(fineHits==3&&fineTimes[1]==32&&fineTimes[2]==64,"t16 plays sixteenth triplets, stp limits rep");
   setup(1);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){2,6,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT,1};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(48);
   check(fineHits==2&&fineTimes[1]==32,"t16 inside one step keeps the second hit");
   setup(1);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){4,11,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT,4};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(192);
   check(fineHits==2&&fineTimes[1]==144,"/3 hits every third step");
   setup(1);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){4,7,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT,1};seq_flamPresetsChanged();
   seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(48);
   check(fineHits==1,"res 1 inside one step is the main hit only");
   memset(seq_groove.human,0,sizeof(seq_groove.human));perf_delaySetGroove(&seq_groove);
 }
 setup(1);perf_configure(0,0,100,100);seq_flamPresets[11]=(FlamPreset){4,0,50,FLAM_PITCH_ZERO,0,FLAM_ACCEL_FLAT,2};seq_flamPresetsChanged();
 seq_patternSet.seq_stepTiming[0][0][0].flam=11;runFrames(30);
 check(seq_longFlamOwns(0),"a long flam owns its track while it runs");
 seq_setRunning(0);check(!seq_longFlamOwns(0),"stop ends a running long flam");seq_running=1;
 for(uint8_t i=1;i<NUM_FLAM_PRESETS;i++){
   FlamPreset factory;seq_flamDefaultPreset(i,&factory);
   check(factory.velo==FLAM_VELO_FLAT||i==14,"factory presets are flat except F14");
 }
 puts("PERFORMANCE PASS");printf("%u assertions against actual performance/flam/trigger/button/LED/globals code\n",checks);
 return 0;
}
'''
(OUT/'performance_contract.c').write_text(prelude+'\n'+functions+'\n'+tests)
includes=ROOT/'Core/Inc'
module=ROOT/'Core/Src/Soundengine/Sequencer/PerformanceSteps.c'
scale_module=ROOT/'Core/Src/Soundengine/Sequencer/PerformanceScale.c'
groove_module=ROOT/'Core/Src/Soundengine/Sequencer/PerformanceGroove.c'
delay_module=ROOT/'Core/Src/Soundengine/Sequencer/PerformanceDelay.c'
if os.name=='nt':
    vsdev=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vsdev}" -arch=x64 >nul && cl /nologo /W3 /TC '
                   f'/I. /I"{includes}" /Fe:performance_contract.exe performance_contract.c "{module}" "{delay_module}" "{groove_module}" "{scale_module}" '
                   '&& performance_contract.exe',shell=True,cwd=OUT,check=True)
else:
    subprocess.run([os.environ.get('CC','cc'),'-std=c11','-I.','-I'+str(includes),
                    'performance_contract.c',str(module),str(delay_module),str(groove_module),str(scale_module),'-o','performance_contract'],cwd=OUT,check=True)
    subprocess.run([str(OUT/'performance_contract')],cwd=OUT,check=True)
