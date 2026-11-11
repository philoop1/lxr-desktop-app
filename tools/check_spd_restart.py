"""0.2.78 spd restart: the real seq_tick / fine-frame / restart code with the
production PerformanceScale.c, internal clock. A spd change while running must
take effect on a bar and restart every track at Step 1. seq_nextStep is a
recorder that only advances the step index like the real one."""
from pathlib import Path
import os, re, subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/spd-restart-audit'
OUT.mkdir(parents=True, exist_ok=True)
seq = (ROOT / 'Core/Src/Soundengine/Sequencer/sequencer.c').read_text(encoding='latin-1')

def function(src, name):
    m = re.search(r'^[^\n;{}]*\b' + name + r'\s*\([^;{]*\)\s*\{', src, re.M)
    assert m, name
    i = src.index('{', m.start()); depth = 0
    for j in range(i, len(src)):
        if src[j] == '{': depth += 1
        elif src[j] == '}':
            depth -= 1
            if not depth: return src[m.start():j + 1]
    raise AssertionError(name)

code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Soundengine/Sequencer/PerformanceScale.h"
#define NUM_TRACKS 7
#define HANDLE_SEQ_IN_CLOCK_INTERRUPT 0
#define IN_ITCM_RAM
#define MIDI_CLOCK 0xF8
#define MIDI_PRESCALER_MASK 4
uint32_t systick_ticks,seq_lastTick;
float seq_deltaT,seq_tempo=120.f;
uint16_t seq_prescaleCounter,seq_scaleBarFrame;
uint8_t seq_finePhase,seq_running,seq_scaleRestart,seq_patternSwitchActive,seq_delayFiredMask;
uint8_t trigger_clockReceived,extSync;
uint8_t seq_conditionLoop[NUM_TRACKS],seq_conditionHistoryValid[NUM_TRACKS],seq_conditionCache[NUM_TRACKS][4],seq_conditionCacheIndex[NUM_TRACKS];
uint8_t seq_grooveNoteOff[NUM_TRACKS],seq_triggerSourceStep[NUM_TRACKS],seq_lastMasterStep[NUM_TRACKS];
int8_t seq_stepIndex[NUM_TRACKS];
const void *seq_perfTracks[NUM_TRACKS];
static void saveDiag_seq(void){}void mixer_setPerformanceGatePhase(uint8_t o){(void)o;}
uint8_t seq_getExtSync(void){return extSync;}
void sync_processStartLead(void){}
uint8_t sync_shouldLeadStep(void){return 0;}
void sync_markLeadStep(void){}
void seq_MidiSyncQueue(uint8_t c){(void)c;}
void seq_calcDeltaT(float t,uint8_t x){(void)t;(void)x;seq_deltaT=1.f;}
void menu_repaint(void){}
void trigger_clockTick(uint8_t a,uint16_t b){(void)a;(void)b;}
void seq_sendRealtime(uint8_t m){(void)m;}
void perf_delayFineTick(void (*f)(void)){(void)f;}
static void seq_emitDelay(void){}
static uint32_t restartTick;void perf_resetSteps(void){restartTick=systick_ticks;}
void perf_delayReset(void){}
static void seq_processScaleFrame(uint8_t f){(void)f;}
static void seq_setStepIndexToStart(void);
uint8_t seq_applyPendingTransform(void){return 0;}
/* recorder: the real seq_nextStep advances every track by perf_scaleNext */
static int played[4096];static uint32_t playedAt[4096];static unsigned nPlayed;
void seq_nextStep(void){
  if(seq_running && perf_scaleSlotIsGap())return;
  for(int t=0;t<NUM_TRACKS;t++)seq_stepIndex[t]=(int8_t)perf_scaleNext(seq_stepIndex[t],16);
  seq_scaleRestart=0;
  if(nPlayed<4096){played[nPlayed]=seq_stepIndex[0];playedAt[nPlayed]=systick_ticks;nPlayed++;}
}
'''
for name in ['seq_processFineFrame', 'seq_advanceFineFrame', 'seq_applyPendingScale', 'seq_setStepIndexToStart', 'seq_tick']:
    f = function(seq, name)
    f = f.replace('/*IN_ITCM_RAM*/ ', '').replace('IN_ITCM_RAM ', '')
    code += f + '\n'
code += r'''
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
/* one systick = one fine frame step of seq_tick; 768 fine frames per bar */
static void run(unsigned ticks){for(unsigned i=0;i<ticks;i++){systick_ticks++;seq_tick();}}
static void start(void){
  perf_scaleSetPattern(16,0);perf_speedSet(PERF_SPEED_NEUTRAL,0);
  seq_setStepIndexToStart();seq_scaleBarFrame=0;seq_scaleRestart=0;seq_lastTick=systick_ticks;seq_deltaT=0.f;
  seq_running=1;nPlayed=0;
}
/* tick of the first played step after 'from' and its step */
static int firstAfter(uint32_t from,uint32_t *at){for(unsigned i=0;i<nPlayed;i++)if(playedAt[i]>from){*at=playedAt[i];return played[i];}return -1;}
int main(void){
  const unsigned BAR=768;
  const int speeds[6]={0,1,2,3,4,5};
  for(int from=0;from<6;from++)for(int to=0;to<6;to++)for(unsigned when=1;when<3*BAR;when+=97){
    if(from==to)continue;
    systick_ticks=1000;start();
    perf_speedSet((uint8_t)speeds[from],1);run(BAR+5);           /* applies at bar 1 */
    check(perf_scaleHasPending()==0,"first change applied");
    run(when);
    const uint32_t changeAt=systick_ticks;
    perf_speedSet((uint8_t)speeds[to],1);
    run(9*BAR);
    /* the change waits for the next bar, restarts there, and Step 1 plays on that bar */
    const uint32_t bar=1001+((changeAt-1001+BAR-1)/BAR)*BAR; /* step 1 played on tick 1001 */
    uint32_t at;const int step=firstAfter(bar-1,&at);
    if(restartTick!=bar||step!=0||at!=bar){
      for(unsigned i=0;i<nPlayed;i++)printf("%d@%u%s ",played[i],(unsigned)(playedAt[i]-1000),playedAt[i]>changeAt?"*":"");
      printf("\nfrom %d to %d, change at %u: restart at %u, bar %u, first step %d at %u\n",from,to,(unsigned)(changeAt-1000),(unsigned)(restartTick-1000),(unsigned)(bar-1000),step,(unsigned)(at-1000));exit(1);}
    check(1,"restart on the bar, Step 1 first");
    (void)step;
  }
  printf("SPD RESTART PASS %u assertions\n",checks);return 0;}
'''
(OUT / 'contract.c').write_text(code, encoding='latin-1')
inc = ROOT / 'Core/Inc'
if os.name == 'nt':
    vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /I"{inc}" /Fe:contract.exe contract.c "{ROOT / "Core/Src/Soundengine/Sequencer/PerformanceScale.c"}" && contract.exe',
                   shell=True, cwd=OUT, check=True)
else:
    subprocess.run(['cc', f'-I{inc}', '-o', 'contract', 'contract.c', str(ROOT / 'Core/Src/Soundengine/Sequencer/PerformanceScale.c')], cwd=OUT, check=True)
    subprocess.run([str(OUT / 'contract')], cwd=OUT, check=True)
