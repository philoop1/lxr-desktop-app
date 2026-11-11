"""Exercise the production trigger-condition evaluator at loop boundaries."""
from pathlib import Path
import os
import re
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "build/trig-condition-audit"
out.mkdir(parents=True, exist_ok=True)
source = (root / "Core/Src/Soundengine/Sequencer/sequencer.c").read_text()
match = re.search(r"static uint8_t seq_conditionAllows\([^)]*\)\s*\{", source)
assert match
end, depth = match.end(), 1
while depth:
    depth += (source[end] == "{") - (source[end] == "}")
    end += 1
function = source[match.start():end]
last_match = re.search(r"static uint8_t seq_conditionLastLoop\(void\)\s*\{", source)
pos, depth = last_match.end(), 1
while depth:
    depth += (source[pos] == "{") - (source[pos] == "}")
    pos += 1
last_function = source[last_match.start():pos]

code = r'''
#include <stdint.h>
#include <stdio.h>
#include "Preset/TrigConditions.h"
#include <stdlib.h>
#include "Soundengine/Sequencer/PerformanceScale.h"
#include "Soundengine/Sequencer/PerformanceSteps.h"
#define NUM_TRACKS 7
#define NUM_STEPS 64
#define PAR_PERF_FILL 1
enum {TRIG_COND_ALWAYS,TRIG_COND_FIRST,TRIG_COND_NOT_FIRST,
      TRIG_COND_FILL,TRIG_COND_NOT_FILL,TRIG_COND_RATIO_BASE,
      TRIG_COND_PRE=TRIG_COND_RATIO_BASE+36,TRIG_COND_NOT_PRE,TRIG_COND_NEI,TRIG_COND_NOT_NEI,TRIG_COND_LAST,TRIG_COND_NOT_LAST,TRIG_COND_COUNT};

struct {TrigTrack trigCondition[1][NUM_TRACKS];} seq_patternSet;
uint8_t seq_activePattern,activeParameters[2];
int8_t seq_stepIndex[NUM_TRACKS];
uint32_t seq_conditionLoop[NUM_TRACKS];
uint8_t seq_conditionHistory[NUM_TRACKS],seq_conditionHistoryValid[NUM_TRACKS];
#define MAX_SONG_LENGTH 64
#define SONG_END 64
#define SONG_LOOP 65
uint8_t seq_pendingPattern,seq_loadPendigFlag,seq_songModeEnabled,seq_songPositionPointer;
uint8_t *seq_activeSong;

static void check(int ok,const char *message){if(!ok){fprintf(stderr,"FAIL %s\n",message);exit(1);}}
''' + last_function + '\n' + function + r'''
int main(void){
 PerfStep current={4,0,0,4,0,1};seq_stepIndex[0]=4;
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 4, TRIG_COND_FIRST);
 check(seq_conditionAllows(0,&current,0),"first on loop one");
 seq_conditionLoop[0]=1;check(!seq_conditionAllows(0,&current,0),"first ends");
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 4, TRIG_COND_NOT_FIRST);
 check(seq_conditionAllows(0,&current,0),"not-first after loop one");
 seq_conditionLoop[0]=0;check(!seq_conditionAllows(0,&current,0),"not-first excludes first");
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 4, TRIG_COND_FILL);
 check(!seq_conditionAllows(0,&current,0),"fill disabled");
 activeParameters[PAR_PERF_FILL]=1;check(seq_conditionAllows(0,&current,0),"fill enabled");
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 4, TRIG_COND_NOT_FILL);
 check(!seq_conditionAllows(0,&current,0),"not-fill disabled during fill");
 activeParameters[PAR_PERF_FILL]=0;check(seq_conditionAllows(0,&current,0),"not-fill enabled");
 for(unsigned b=1,base=TRIG_COND_RATIO_BASE;b<=8;base+=b,b++)
  for(unsigned a=1;a<=b;a++){
   trigTrackSet(&seq_patternSet.trigCondition[0][0], 4, (uint8_t)(base+a-1));
   for(unsigned loop=0;loop<3*b;loop++){
    seq_conditionLoop[0]=loop;
    check(seq_conditionAllows(0,&current,0)==(loop%b==a-1),"A:B cycle");
   }
  }
 PerfStep next={0,0,0,0,0,2};seq_stepIndex[0]=15;seq_conditionLoop[0]=0;
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 0, TRIG_COND_FIRST);
 check(!seq_conditionAllows(0,&next,1),"next step at wrap is second loop");
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 0, TRIG_COND_NOT_FIRST);
 check(seq_conditionAllows(0,&next,1),"next step after wrap is not first");
 PerfStep previous={15,0,0,15,0,3};seq_stepIndex[0]=0;seq_conditionLoop[0]=1;
 trigTrackSet(&seq_patternSet.trigCondition[0][0], 15, TRIG_COND_FIRST);
 check(seq_conditionAllows(0,&previous,-1),"previous shifted step belongs to first loop");
 seq_conditionLoop[0]=0;check(!seq_conditionAllows(0,&previous,-1),"no synthetic previous loop");
 perf_scaleSetPattern(16,0);perf_speedSet(PERF_SPEED_NEUTRAL,0);
 for(unsigned mode=0;mode<=3;mode++){
  perf_transformSet(mode,0);unsigned count=0;
  for(unsigned step=0;step<16;step++){
   unsigned excluded=mode==1?3:mode==2?1:2;
   check(perf_scaleAllowed(step)==(!mode || step%4!=excluded),"SCT exact mask");
   count+=perf_scaleAllowed(step);
  }
  check(count==(mode?12:16),"SCT step count");
 }
 perf_transformSet(0,0);perf_transformSet(1,1);
 check(perf_scaleAllowed(3),"SCT waits while running");perf_transformCommit();
 check(!perf_scaleAllowed(3),"SCT commits at boundary");
 perf_transformSet(0,0);
 seq_pendingPattern=1;check(seq_conditionLastLoop(),"queued pattern activates LST");
 seq_pendingPattern=0;check(!seq_conditionLastLoop(),"no queued switch is not LST");
 uint8_t song[64]={0,2};seq_activeSong=song;seq_songModeEnabled=1;
 check(seq_conditionLastLoop(),"song transition is LST");song[1]=0;
 check(!seq_conditionLastLoop(),"same song pattern is not LST");song[1]=SONG_END;
 check(seq_conditionLastLoop(),"song end is LST");seq_songModeEnabled=0;
 perf_setLoop(0,1);check(seq_conditionLastLoop(),"pattern loop transition is LST");perf_clearLoop();
 puts("TRIG CONDITION PASS");return 0;
}
'''
(out / "contract.c").write_text(code)
if os.name == "nt":
    vs = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat"
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /I"{root / "Core/Inc"}" /Fe:contract.exe contract.c "{root / "Core/Src/Soundengine/Sequencer/PerformanceScale.c"}" "{root / "Core/Src/Soundengine/Sequencer/PerformanceSteps.c"}" && contract.exe', shell=True, cwd=out, check=True)
else:
    subprocess.run(["cc", "-std=c11", "-I" + str(root / "Core/Inc"), "contract.c",
                    str(root / "Core/Src/Soundengine/Sequencer/PerformanceScale.c"),
                    str(root / "Core/Src/Soundengine/Sequencer/PerformanceSteps.c"), "-o", "contract"], cwd=out, check=True)
    subprocess.run([str(out / "contract")], cwd=out, check=True)
