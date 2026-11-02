"""Run the desktop sequencer's COPY functions with a 64-slot host pattern set."""
from pathlib import Path
import os
import re
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'build' / 'copy-import-audit'
out.mkdir(parents=True, exist_ok=True)
source = (root / 'Core/Src/Soundengine/Sequencer/sequencer.c').read_text()

def extract(name):
    match = re.search(r'^void ' + name + r'\([^)]*\)\s*\{', source, re.M)
    assert match, name
    position, depth = match.end(), 1
    while depth:
        depth += (source[position] == '{') - (source[position] == '}')
        position += 1
    return source[match.start():position]

code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define NUM_TRACKS 7
#define NUM_PATTERN 64
#define NUM_STEPS 64
#define NUM_BARS 4
typedef struct {uint8_t note,volume,prob,param1Nr,param1Val,param2Nr,param2Val;} Step;
typedef struct {uint8_t flam,shift;} Timing;
static struct {
  Step seq_subStepPattern[NUM_PATTERN][NUM_TRACKS][NUM_STEPS];
  Timing seq_stepTiming[NUM_PATTERN][NUM_TRACKS][NUM_STEPS];
  uint8_t flamProbability[NUM_PATTERN][NUM_TRACKS][NUM_STEPS];
  uint8_t trigCondition[NUM_PATTERN][NUM_TRACKS][NUM_STEPS];
  uint16_t seq_mainSteps[NUM_BARS][NUM_PATTERN][NUM_TRACKS];
  uint8_t length[NUM_PATTERN][NUM_TRACKS];
} seq_patternSet;
static unsigned checks;
static void check(int ok,const char *what){checks++;if(!ok){fprintf(stderr,"FAIL %s\n",what);exit(1);}}
'''
code += '\n'.join(extract(name) for name in
                  ('seq_copyTrackPattern', 'seq_copyStep', 'seq_copyStepGroup'))
code += r'''
int main(void){
  seq_patternSet.seq_subStepPattern[3][2][17]=(Step){60,97,41,5,77,6,88};
  seq_patternSet.seq_stepTiming[3][2][17]=(Timing){4,9};
  seq_patternSet.flamProbability[3][2][17]=37;
  seq_patternSet.trigCondition[3][2][17]=5;
  seq_patternSet.seq_mainSteps[1][3][2]=(uint16_t)(1u<<1);
  seq_copyStep(2,3,17,33);
  check(!memcmp(&seq_patternSet.seq_subStepPattern[3][2][17],
      &seq_patternSet.seq_subStepPattern[3][2][33],sizeof(Step)),"one complete step");
  check(!memcmp(&seq_patternSet.seq_stepTiming[3][2][17],
      &seq_patternSet.seq_stepTiming[3][2][33],sizeof(Timing)),"Flam and Shift");
  check(seq_patternSet.flamProbability[3][2][33]==37,"Flam Probability");
  check(seq_patternSet.trigCondition[3][2][33]==5,"Trig Condition");
  check(seq_patternSet.seq_mainSteps[2][3][2]&(1u<<1),"on bit across bars");
  seq_copyStep(2,3,32,33);
  check(!(seq_patternSet.seq_mainSteps[2][3][2]&(1u<<1)),"off bit across bars");
  for(unsigned i=0;i<8;i++){
    seq_patternSet.seq_subStepPattern[3][2][i].note=(uint8_t)(40+i);
    seq_patternSet.seq_stepTiming[3][2][i].shift=(uint8_t)i;
  }
  seq_patternSet.seq_mainSteps[0][3][2]=0x55;
  seq_copyStepGroup(2,3,0,7);
  for(unsigned i=0;i<8;i++){
    check(seq_patternSet.seq_subStepPattern[3][2][56+i].note==40+i,"group note");
    check(seq_patternSet.seq_stepTiming[3][2][56+i].shift==i,"group timing");
  }
  check((seq_patternSet.seq_mainSteps[3][3][2]>>8)==0x55,"group on bits");
  seq_patternSet.length[3][2]=61;
  seq_copyTrackPattern(2,3,63);
  check(seq_patternSet.length[63][2]==61,"track length in slot 64");
  check(seq_patternSet.seq_subStepPattern[63][2][17].note==60,"track note in slot 64");
  check(seq_patternSet.seq_stepTiming[63][2][17].flam==4,"track timing in slot 64");
  check(seq_patternSet.flamProbability[63][2][17]==37,"track Flam Probability in slot 64");
  check(seq_patternSet.trigCondition[63][2][17]==5,"track Trig Condition in slot 64");
  check(seq_patternSet.seq_mainSteps[3][63][2]==seq_patternSet.seq_mainSteps[3][3][2],"track main steps in slot 64");
  printf("COPY IMPORT PASS %u assertions\n",checks);
  return 0;
}
'''
(out / 'copy_import.c').write_text(code)
if os.name == 'nt':
    vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:copy_import.exe copy_import.c && copy_import.exe',
                   shell=True, cwd=out, check=True)
else:
    subprocess.run(['cc', '-std=c11', '-o', 'copy_import', 'copy_import.c'], cwd=out, check=True)
    subprocess.run([str(out / 'copy_import')], cwd=out, check=True)
