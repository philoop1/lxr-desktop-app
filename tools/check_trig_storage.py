"""Native round-trip and legacy fallback for production CND1 pattern extension."""
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

code = r'''
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
struct {uint8_t transform[1];uint8_t trigCondition[1][NUM_TRACKS][NUM_STEPS];}seq_patternSet;
FRESULT f_write(FIL *f,const void *src,UINT count,UINT *written){(void)f;if(position+count>sizeof(file))return 1;memcpy(file+position,src,count);position+=count;if(position>length)length=position;*written=count;return FR_OK;}
FRESULT f_read(FIL *f,void *dst,UINT count,UINT *read){(void)f;*read=length-position<count?length-position:count;memcpy(dst,file+position,*read);position+=*read;return FR_OK;}
static void check(int ok,const char *why){if(!ok){fprintf(stderr,"FAIL %s\n",why);exit(1);}}
''' + function("preset_writeTrigConditions") + "\n" + function("preset_readTrigConditions") + r'''
int main(void){
 for(unsigned t=0;t<NUM_TRACKS;t++)for(unsigned s=0;s<NUM_STEPS;s++)
  seq_patternSet.trigCondition[0][t][s]=(uint8_t)((t*64+s)%TRIG_COND_COUNT);
 uint8_t expected[NUM_TRACKS*NUM_STEPS];memcpy(expected,seq_patternSet.trigCondition[0],sizeof(expected));
 seq_patternSet.transform[0]=2;
 preset_writeTrigConditions(0);
 check(length==453&&!memcmp(file,"CND2",4),"versioned extension size and marker");
 memset(seq_patternSet.trigCondition[0],0,sizeof(expected));position=0;preset_readTrigConditions(0);
 check(!memcmp(expected,seq_patternSet.trigCondition[0],sizeof(expected))&&seq_patternSet.transform[0]==2,"round trip including SCT");
 uint8_t modern[453];memcpy(modern,file,453);
 memmove(file+4,file+5,448);memcpy(file,"CND1",4);length=452;position=0;
 preset_readTrigConditions(0);
 check(!memcmp(expected,seq_patternSet.trigCondition[0],sizeof(expected))&&seq_patternSet.transform[0]==0,"CND1 compatibility defaults SCT");
 memcpy(file,modern,453);
 position=0;length=0;memset(seq_patternSet.trigCondition[0],7,sizeof(expected));preset_readTrigConditions(0);
 for(unsigned i=0;i<sizeof(expected);i++)check(((uint8_t*)seq_patternSet.trigCondition[0])[i]==0,"legacy defaults to always");
 position=0;length=453;file[5]=255;preset_readTrigConditions(0);
 check(seq_patternSet.trigCondition[0][0][0]==0,"invalid condition clamped");
 position=0;length=25;preset_readTrigConditions(0);
 for(unsigned i=0;i<sizeof(expected);i++)check(((uint8_t*)seq_patternSet.trigCondition[0])[i]==0,"truncated extension defaults to always");
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
