"""Native round-trip and legacy fallback for CND3, CND2 and CND1 pattern extensions."""
from pathlib import Path
import os
import re
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "build/trig-storage-audit"
out.mkdir(parents=True, exist_ok=True)
source = (root / "Core/Src/Preset/presetManager.c").read_text()

def function(name):
    match = re.search(r"static void " + name + r"\([^)]*\)\s*\{", source)
    assert match, name
    pos, depth = match.end(), 1
    while depth:
        depth += (source[pos] == "{") - (source[pos] == "}")
        pos += 1
    return source[match.start():pos]

code = (root / 'Core/Inc/Preset/TrigConditions.h').read_text() + '\n' + r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define NUM_TRACKS 7
#define NUM_STEPS 64
#define TRIG_COND_ALWAYS 0
#define TRIG_COND_COUNT 47
typedef unsigned UINT;
typedef int FIL;
typedef int FRESULT;
#define FR_OK 0
FIL SDFile;
uint8_t file[1024];unsigned length,position;
struct {uint8_t transform[1];TrigTrack trigCondition[1][NUM_TRACKS];}seq_patternSet;
FRESULT f_write(FIL *f,const void *src,UINT count,UINT *written){(void)f;if(position+count>sizeof(file))return 1;memcpy(file+position,src,count);position+=count;if(position>length)length=position;*written=count;return FR_OK;}
FRESULT f_read(FIL *f,void *dst,UINT count,UINT *read){(void)f;*read=length-position<count?length-position:count;memcpy(dst,file+position,*read);position+=*read;return FR_OK;}
static void check(int ok,const char *why){if(!ok){fprintf(stderr,"FAIL %s\n",why);exit(1);}}
''' + function("preset_writeTrigConditions") + "\n" + function("preset_readTrigConditions") + r'''
static uint8_t expected[NUM_TRACKS][NUM_STEPS];
static void checkConditions(int empty) {
 for(unsigned t=0;t<NUM_TRACKS;t++)for(unsigned s=0;s<NUM_STEPS;s++)
  check(trigTrackGet(&seq_patternSet.trigCondition[0][t],s)==(empty?0:expected[t][s]),"decoded condition");
}
int main(void){
 for(unsigned t=0;t<NUM_TRACKS;t++)for(unsigned s=0;s<NUM_STEPS;s++){
  expected[t][s]=(t*64+s)%TRIG_COND_COUNT;
  trigTrackSet(&seq_patternSet.trigCondition[0][t],s,expected[t][s]);
 }
 check(sizeof(seq_patternSet.trigCondition[0])==336,"packed pattern size");
 seq_patternSet.transform[0]=2;preset_writeTrigConditions(0);
 check(length==341&&!memcmp(file,"CND3",4)&&file[4]==2,"packed marker, size and transform");
 for(unsigned t=0;t<NUM_TRACKS;t++)for(unsigned s=0;s<NUM_STEPS;s+=4)
  for(unsigned lane=0;lane<3;lane++)
   check(file[5+t*48+(s/4)*3+lane]==(expected[t][s+lane]|(((expected[t][s+3]>>(2*lane))&3u)<<6)),"CND3 wire layout");
 memset(seq_patternSet.trigCondition[0],0,sizeof(seq_patternSet.trigCondition[0]));
 position=0;preset_readTrigConditions(0);checkConditions(0);
 check(position==341&&seq_patternSet.transform[0]==2,"CND3 round trip including SCT");
 file[5]|=63;file[4]=99;position=0;preset_readTrigConditions(0);
 check(!trigTrackGet(&seq_patternSet.trigCondition[0][0],0)&&!seq_patternSet.transform[0],"invalid packed values");
 length=340;position=0;preset_readTrigConditions(0);checkConditions(1);
 for(unsigned version=1;version<=2;version++){
  const unsigned offset=version==1?4:5;
  memcpy(file,version==1?"CND1":"CND2",4);file[4]=3;
  memcpy(file+offset,expected,sizeof(expected));length=offset+sizeof(expected);position=0;
  preset_readTrigConditions(0);checkConditions(0);
  check(position==length&&seq_patternSet.transform[0]==(version==1?0:3),"legacy transform and next trailer offset");
  file[offset+63]=255;position=0;preset_readTrigConditions(0);
  check(!trigTrackGet(&seq_patternSet.trigCondition[0][0],63),"invalid legacy condition");
  length--;position=0;preset_readTrigConditions(0);checkConditions(1);
 }
 memset(seq_patternSet.trigCondition[0],255,sizeof(seq_patternSet.trigCondition[0]));
 position=length=0;preset_readTrigConditions(0);checkConditions(1);
 puts("TRIG STORAGE PASS");return 0;
}
'''
(out / "contract.c").write_text(code)
if os.name == "nt":
    vs = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat"
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:contract.exe contract.c && contract.exe', shell=True, cwd=out, check=True)
else:
    subprocess.run(["cc", "-std=c11", "contract.c", "-o", "contract"], cwd=out, check=True)
    subprocess.run([str(out / "contract")], cwd=out, check=True)
