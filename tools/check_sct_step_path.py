"""Gap slots through the real seq_nextStep and the production PerformanceScale.c.

--mutate removes the gap guard; the check must then fail.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"
GUARD = 'if(seq_running && perf_scaleSlotIsGap())return;'
PRELUDE = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "Soundengine/Sequencer/PerformanceScale.h"
#define IN_ITCM_RAM
#define NUM_TRACKS 7
#define NUM_PATTERN 2
#define SONG_END 100
#define SONG_LOOP 101
#define FOLLOW_BAR 1
#define LED_START_STOP 0
#define ROLL_VOLUME 100
enum {PAR_FOLLOW,NUM_PARAMS};
enum {MENU_MIDI_PAGE=7,PERF_PAGE=20,SEQ_PAGE,EUKLID_PAGE,PATTERN_LOAD_PAGE,SONG_MODE_PAGE};
typedef struct {uint8_t note;} Step;
struct {uint8_t length[NUM_PATTERN][NUM_TRACKS];Step seq_subStepPattern[NUM_PATTERN][NUM_TRACKS][64];} seq_patternSet;
uint8_t activeParameters[NUM_PARAMS],seq_running,seq_scaleRestart,seq_activePattern,seq_pendingPattern;
uint8_t seq_mutedTracks,seq_eraseActive,frontParser_activeTrack,seq_rollRate=0xff,seq_rollState;
uint8_t menu_activeBar,menu_activePage,menu_playedPattern,midi_process_block,seq_songPositionPointer,seq_activeSong[64];
uint8_t seq_conditionLoop[NUM_TRACKS];
int8_t seq_stepIndex[NUM_TRACKS];
uint32_t seq_masterStepCnt;
unsigned blinks,advances[NUM_TRACKS],boundaries,led;
void led_blinkHandler(void){blinks++;}
uint8_t seq_getLongestTrack(void){return 0;}
uint8_t seq_determineNextPattern(uint8_t u){(void)u;return seq_activePattern;}
void seq_setRunning(uint8_t v){seq_running=v;}
void seq_setPendingPatternActive(void){boundaries++;}
void led_setValue(uint8_t v,uint8_t i){(void)v;(void)i;led++;}
void seq_perfAdvance(uint8_t t,uint8_t s,uint8_t l){(void)s;(void)l;advances[t]++;}
uint8_t seq_intIsMainStepActive(uint8_t t,uint8_t s,uint8_t p){(void)t;(void)s;(void)p;return 0;}
void seq_setMainStep(uint8_t p,uint8_t t,uint8_t s,uint8_t v){(void)p;(void)t;(void)s;(void)v;}
uint8_t led_idx2StepLed(uint8_t i){return i;}
void seq_triggerVoice(uint8_t t,uint8_t v,uint8_t n){(void)t;(void)v;(void)n;}
void seq_addNote(uint8_t t,uint8_t v,uint8_t n){(void)t;(void)v;(void)n;}
uint8_t menu_getActiveVoice(void){return 0;}
uint8_t menu_getViewedPattern(void){return 0;}
void menu_setShownPattern(uint8_t p){(void)p;}void menu_followPattern(uint8_t p){(void)p;}
void led_clearSequencerLeds(void){}
void led_updateSeqLeds(void){}
void led_setActive_step(uint8_t s){(void)s;}
void led_clearActive_step(void){}
uint8_t seq_chaseStep(uint8_t t){return (uint8_t)seq_stepIndex[t];} /* 0.2.92 */
void midiParser_checkMtc(void){}
void mixer_setPerformanceGatePhase(uint8_t o){(void)o;}
"""
TESTS = r"""
static unsigned checks,failures,gRate,gLen;
static void check(int ok,const char *name,unsigned mode,unsigned slot)
{
 checks++;
 if(!ok){failures++;printf("FAIL %s mode=%u slot=%u\n",name,mode,slot);}
}
static void reset(unsigned rate,unsigned mode,unsigned length)
{
 memset(advances,0,sizeof(advances));memset(seq_conditionLoop,0,sizeof(seq_conditionLoop));
 memset(seq_stepIndex,-1,sizeof(seq_stepIndex));
 memset(seq_patternSet.length,length,sizeof(seq_patternSet.length));
 blinks=boundaries=seq_masterStepCnt=0;seq_scaleRestart=1;seq_running=1;
 perf_scaleSetPattern((uint8_t)rate,0);perf_speedSet(PERF_SPEED_NEUTRAL,0);
 perf_transformSet((uint8_t)mode,0);perf_scaleSlotReset();
}
/* Ternary sct: one slot in four is silent and every other slot takes one stored step. */
static void ternary(unsigned rate,unsigned mode,unsigned length)
{
 gRate=rate;gLen=length;
 static const uint8_t gap[4]={0,3,1,2};
 reset(rate,mode,length);
 /* Rate 12 plays twelve of every sixteen stored slots. */
 uint8_t sources[64];unsigned count=0;
 for(unsigned i=0;i<length;i++)if(rate!=12||(i&15u)<12)sources[count++]=(uint8_t)i;
 unsigned stored=0,loops=0;
 for(unsigned slot=0;slot<960;slot++) {
  const int isGap=mode&&(slot%4u)==gap[mode];
  const int before=seq_stepIndex[0];
  seq_nextStep();
  check((int)perf_scaleInGap()==isGap,"gap position",mode,slot);
  if(isGap) {
   for(unsigned t=0;t<NUM_TRACKS;t++)check(seq_stepIndex[t]==before,"gap keeps every track",mode,slot);
   continue;
  }
  const int expected=sources[stored%count];
  if(stored&&!(stored%count))loops++;
  stored++;
  for(unsigned t=0;t<NUM_TRACKS;t++) {
   check(seq_stepIndex[t]==expected,"stored steps stay in order",mode,slot);
   check(advances[t]==stored,"one advance per stored step",mode,slot);
   check(seq_conditionLoop[t]==(uint8_t)loops,"condition loop counts wraps",mode,slot);
  }
  check(seq_masterStepCnt==stored&&blinks==stored,"gap does not count as a step",mode,slot);
  check(boundaries==loops,"pattern boundary once per loop",mode,slot);
 }
 check(stored==(mode?720u:960u),"three stored steps in four slots",mode,960);
}
int main(void)
{
 static const uint8_t lengths[]={3,4,12,16,24,64};
 for(unsigned mode=0;mode<4;mode++)
  for(unsigned l=0;l<sizeof(lengths);l++) {
   ternary(12,mode,lengths[l]);
   ternary(24,mode,lengths[l]);
   ternary(6,mode,lengths[l]);
  }
 /* A stopped sequencer never consumes a slot. */
 reset(12,1,12);seq_running=0;
 for(unsigned i=0;i<8;i++)seq_nextStep();
 check(seq_stepIndex[0]==-1&&!seq_masterStepCnt,"stopped sequencer stays put",1,0);
 seq_running=1;
 for(unsigned i=0;i<3;i++)seq_nextStep();
 check(seq_stepIndex[0]==2,"slots start at the group edge after a stop",1,3);
 printf("%s %u assertions\n",failures?"SCT STEP PATH FAIL":"SCT STEP PATH PASS",checks);
 return failures!=0;
}
"""


def extract(source: str, name: str) -> str:
    # 0.2.103 seq_nextStep moved to flash (marker commented out, comments stripped)
    match = re.search(r'^(?:IN_ITCM_RAM )? ?void ' + name + r'\(\)\s*\{', source, re.M)
    assert match, name
    position, depth = match.end(), 1
    while depth:
        depth += (source[position] == '{') - (source[position] == '}')
        position += 1
    return source[match.start():position]


def main() -> None:
    sequencer = (ROOT / 'Core/Src/Soundengine/Sequencer/sequencer.c').read_text(errors='replace')
    sequencer = re.sub(r'/\*.*?\*/|//[^\n]*', '', sequencer, flags=re.S)
    body = extract(sequencer, 'seq_nextStep')
    assert body.count(GUARD) == 1
    if '--mutate' in sys.argv:
        body = body.replace(GUARD, '')
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        out = Path(folder)
        (out / 'contract.c').write_text(PRELUDE + body + TESTS, encoding='utf-8')
        scale = ROOT / 'Core/Src/Soundengine/Sequencer/PerformanceScale.c'
        command = (f'call "{VS}" -arch=x64 >nul && cl /nologo /W3 /TC /I"{ROOT / "Core/Inc"}" '
                   f'/Fe:contract.exe contract.c "{scale}" && .\\contract.exe')
        subprocess.run(command, shell=True, cwd=out, check=True)


if __name__ == '__main__':
    main()
