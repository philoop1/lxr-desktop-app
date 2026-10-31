"""Native contract check of the production LFX1 kit extension."""
from pathlib import Path
import os
import re
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "build/lfo-kit-audit"
out.mkdir(parents=True, exist_ok=True)
source = (root / "Core/Src/Preset/presetManager.c").read_text()

def function(name):
    match = re.search(r"^.*\b" + name + r"\([^)]*\)\s*\{", source, re.M)
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
#include "Parameters.h"
#define LFO_EXTRA_BYTES 16u
typedef unsigned UINT;
typedef int FIL;
#define FR_OK 0
FIL SDFile;
uint8_t activeParameters[NUM_PARAMS],disk[64];
unsigned size,cursor,applied;
int f_write(FIL *file,const void *data,unsigned count,UINT *written){(void)file;memcpy(disk+cursor,data,count);cursor+=count;if(cursor>size)size=cursor;*written=count;return FR_OK;}
int f_read(FIL *file,void *data,unsigned count,UINT *read){(void)file;*read=cursor+count>size?size-cursor:count;memcpy(data,disk+cursor,*read);cursor+=*read;return FR_OK;}
void menu_parseGlobalParam(uint16_t parameter,uint8_t value){(void)parameter;(void)value;applied++;}
static void check(int condition,const char *message){if(!condition){fprintf(stderr,"FAIL %s\n",message);exit(1);}}
'''
for name in ("preset_defaultLfoExtras", "preset_captureLfoExtras", "preset_applyLfoExtras", "preset_writeLfoExtras", "preset_readLfoExtras"):
    code += function(name) + "\n"
code += r'''
int main(void){
 uint8_t original[12],loaded[12];
 for(unsigned voice=0;voice<6;voice++){
   activeParameters[PAR_LFO_SLEW1+voice]=(uint8_t)(voice*10);
   activeParameters[PAR_LFO_POL1+voice]=(uint8_t)(voice%3);
 }
 preset_captureLfoExtras(original);preset_writeLfoExtras(original);
 check(size==16 && !memcmp(disk,"LFX1",4),"new marker and fixed extension size");
 cursor=0;preset_readLfoExtras(loaded);
 check(cursor==16 && !memcmp(original,loaded,12),"kit extension roundtrip");
 memset(activeParameters,0,sizeof(activeParameters));preset_applyLfoExtras(loaded);
 check(applied==12 && activeParameters[PAR_LFO_SLEW6]==50 && activeParameters[PAR_LFO_POL6]==2,"loaded controls applied to sound engine");
 memset(disk,0xff,16);size=16;cursor=0;preset_readLfoExtras(loaded);
 check(cursor==16 && loaded[0]==0 && loaded[6]==2 && loaded[11]==2,"legacy project padding stays aligned and defaults");
 size=0;cursor=0;preset_readLfoExtras(loaded);
 check(loaded[0]==0 && loaded[6]==2,"legacy standalone kit defaults");
 memcpy(disk,"LFX1",4);memset(disk+4,255,12);size=16;cursor=0;preset_readLfoExtras(loaded);
 check(loaded[0]==127 && loaded[6]==2,"corrupt values clamp");
 puts("LFO KIT PASS");return 0;
}
'''
(out / "contract.c").write_text(code)
(out / "stm32f7xx_hal.h").write_text("#include <stdint.h>\n")
if os.name == "nt":
    vs = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat"
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /I. /I"{root / "Core/Inc"}" /Fe:contract.exe contract.c && contract.exe', shell=True, cwd=out, check=True)
else:
    subprocess.run(["cc", "-std=c11", "-I.", f"-I{root / 'Core/Inc'}", "contract.c", "-o", "contract"], cwd=out, check=True)
    subprocess.run([str(out / "contract")], cwd=out, check=True)
