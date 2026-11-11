"""0.2.78 spd restart under MIDI clock: the real clockSync.c and the real
seq_tick / restart code with the production PerformanceScale.c. MIDI START,
then 24 PPQ clocks at 120 bpm; a spd change while running must restart every
track at Step 1 on the downbeat (clock 96*n), with and without clock offset."""
from pathlib import Path
import os, re, subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/spd-restart-midi-audit'
OUT.mkdir(parents=True, exist_ok=True)
seq = (ROOT / 'Core/Src/Soundengine/Sequencer/sequencer.c').read_text(encoding='latin-1')
sync = (ROOT / 'Core/Src/Soundengine/Sequencer/clockSync.c').read_text(encoding='latin-1')
sync = re.sub(r'#include[^\n]*\n', '', sync)

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
#define WINDOW_SIZE 8
#define WINDOW_MASK 0x07
struct {uint32_t CYCCNT;} dwt,*DWT=&dwt;
uint32_t SystemCoreClock=216000000u;
uint32_t systick_ticks,seq_lastTick;
float seq_deltaT;uint16_t seq_tempo=120;
uint16_t seq_prescaleCounter,seq_scaleBarFrame;
uint8_t seq_finePhase,seq_running,seq_scaleRestart,seq_patternSwitchActive,seq_delayFiredMask;
uint8_t trigger_clockReceived;
uint8_t seq_conditionLoop[NUM_TRACKS],seq_conditionHistoryValid[NUM_TRACKS],seq_conditionCache[NUM_TRACKS][4],seq_conditionCacheIndex[NUM_TRACKS];
uint8_t seq_grooveNoteOff[NUM_TRACKS],seq_triggerSourceStep[NUM_TRACKS],seq_lastMasterStep[NUM_TRACKS];
int8_t seq_stepIndex[NUM_TRACKS];
const void *seq_perfTracks[NUM_TRACKS];
static void saveDiag_seq(void){}void mixer_setPerformanceGatePhase(uint8_t o){(void)o;}
void saveDiag_clock(uint32_t c){(void)c;}
uint8_t seq_getExtSync(void){return 2;}
uint16_t seq_getBpm(void){return seq_tempo;}
void seq_setBpm(uint16_t b){seq_tempo=b;}
void seq_calcDeltaT(uint16_t bpm,uint8_t x){(void)x;if(!bpm)bpm=120;seq_deltaT=(60000.f/(float)bpm)*4.f/192.f;}
void menu_repaint(void){}
void trigger_clockTick(uint8_t a,uint16_t b){(void)a;(void)b;}
void seq_sendRealtime(uint8_t m){(void)m;}
void perf_delayFineTick(void (*f)(void)){(void)f;}
static void seq_emitDelay(void){}
static uint32_t restartClock,clockNo;void perf_resetSteps(void){restartClock=clockNo;}
void perf_delayReset(void){}
static void seq_processScaleFrame(uint8_t f){(void)f;}
static void seq_setStepIndexToStart(void);
uint8_t seq_applyPendingTransform(void){return 0;}

void seq_resetPosition(void){seq_deltaT=0;}
void seq_setRunning(uint8_t r){
  seq_running=r;
  if(r){perf_scaleSetPattern(16,0);seq_scaleBarFrame=0;seq_scaleRestart=0;
    trigger_clockReceived=0;seq_prescaleCounter=0;seq_finePhase=0;seq_lastTick=systick_ticks;seq_deltaT=0;}
  else perf_scaleCommit();
  seq_setStepIndexToStart();
}
/* recorder: the real seq_nextStep advances every track by perf_scaleNext */
static int played[8192];static uint32_t playedClock[8192],playedTick[8192];static unsigned nPlayed;
void seq_nextStep(void){
  if(seq_running && perf_scaleSlotIsGap())return;
  if(!seq_running)return;
  for(int t=0;t<NUM_TRACKS;t++)seq_stepIndex[t]=(int8_t)perf_scaleNext(seq_stepIndex[t],16);
  seq_scaleRestart=0;
  if(nPlayed<8192){played[nPlayed]=seq_stepIndex[0];playedClock[nPlayed]=clockNo;playedTick[nPlayed]=systick_ticks;nPlayed++;}
}
void seq_MidiSyncQueue(uint8_t cnt);
uint8_t seq_applyPendingScale(void);
void sync_tickAtCycles(uint32_t);uint8_t sync_processStartLead(void);uint8_t sync_shouldLeadStep(void);void sync_markLeadStep(void);
'''
code += sync + '\n'
for name in ['seq_processFineFrame', 'seq_advanceFineFrame', 'seq_MidiSyncQueue', 'seq_applyPendingScale', 'seq_setStepIndexToStart', 'seq_tick']:
    f = function(seq, name)
    f = f.replace('/*IN_ITCM_RAM*/ ', '').replace('IN_ITCM_RAM ', '')
    code += f + '\n'
code += r'''
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
/* systick 4 kHz; 120 bpm = 48 clocks/s = one clock every 83.33 ticks */
static uint32_t t0;
static uint32_t clockTick(uint32_t k){return t0+1u+(uint32_t)((k*250u)/3u);}
static uint32_t nextClock;
static void runUntilClock(uint32_t k){
  while(nextClock<=k){
    const uint32_t due=clockTick(nextClock);
    while(systick_ticks<due){systick_ticks++;dwt.CYCCNT=systick_ticks*54000u;seq_tick();}
    clockNo=nextClock;sync_tickAtCycles(dwt.CYCCNT);nextClock++;
    seq_tick();
  }
}
static void dump(uint32_t from){for(unsigned i=0;i<nPlayed;i++)if(playedClock[i]+30>=from)printf("%d@c%u ",played[i]+1,(unsigned)playedClock[i]);printf("\n");}
int main(void){
  for(int offset=0;offset<2;offset++)
  for(int from=0;from<6;from++)for(int to=0;to<6;to++)for(uint32_t when=1;when<300;when+=7){
    if(from==to)continue;
    memset(&dwt,0,sizeof dwt);systick_ticks=t0=1000;dwt.CYCCNT=t0*54000u;nPlayed=0;nextClock=0;
    sync_setClockOffset(offset?50:0,0);
    perf_scaleSetPattern(16,0);perf_speedSet((uint8_t)from,0);
    sync_midiResetPosition();sync_midiStartStop(1);   /* MIDI START, as in MidiParser.c */
    runUntilClock(96*2+when);
    const uint32_t changeClock=clockNo;
    perf_speedSet((uint8_t)to,1);
    runUntilClock(96*12);
    /* the downbeat after the change: clocks 0,96,192.. are bar starts */
    const uint32_t bar=((changeClock/96u)+1u)*96u;
    int first=-1;uint32_t at=0;
    /* the lead (5 ms = 20 ticks) may play the downbeat step just before its clock */
    const uint32_t barTick=clockTick(bar),early=offset?25u:0u;
    uint32_t atTick=0;
    for(unsigned i=0;i<nPlayed;i++)if(playedTick[i]+early>=barTick){first=played[i];at=playedClock[i];atTick=playedTick[i];break;}
    const int ok=first==0 && atTick<=barTick && restartClock+1>=bar && restartClock<=bar;
    if(!ok){
      printf("offset %d from %d to %d, change at clock %u: restart at clock %u, bar %u, first step %d at clock %u\n",
             offset,from,to,(unsigned)changeClock,(unsigned)restartClock,(unsigned)bar,first+1,(unsigned)at);
      dump(changeClock);exit(1);}
    check(1,"restart on the downbeat");
  }
  printf("SPD MIDI RESTART PASS %u assertions\n",checks);return 0;}
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
