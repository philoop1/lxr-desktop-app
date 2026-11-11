"""0.2.81 INS1 kit block: the production presetManager.c functions with the real
InsertFx.c. Roundtrip, values reach the effect, old kits (no block, project
padding 0x00 or 0xFF, short standalone file) get the defaults and keep the
padding aligned, corrupt values clamp, the kit still fits the 512 byte slot."""
from pathlib import Path
import os
import re
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "build/ins-kit-audit"
out.mkdir(parents=True, exist_ok=True)
source = (root / "Core/Src/Preset/presetManager.c").read_text(encoding="latin-1")

def function(name):
    match = re.search(r"^.*\b" + name + r"\([^)]*\)\s*\{", source, re.M)
    assert match, name
    pos, depth = match.end(), 1
    while depth:
        depth += (source[pos] == "{") - (source[pos] == "}")
        pos += 1
    return source[match.start():pos]

def define(name):
    match = re.search(r"^#define " + name + r"\b.*$", source, re.M)
    assert match, name
    return match.group(0) + "\n"

code = r'''
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Parameters.h"
#include "Soundengine/DSPAudio/FX/InsertFx.h"
typedef unsigned UINT;
typedef int FIL;
#define FR_OK 0
FIL SDFile;
uint8_t activeParameters[NUM_PARAMS],disk[600];
unsigned size,cursor;
int f_write(FIL *file,const void *data,unsigned count,UINT *written){(void)file;memcpy(disk+cursor,data,count);cursor+=count;if(cursor>size)size=cursor;*written=count;return FR_OK;}
int f_read(FIL *file,void *data,unsigned count,UINT *read){(void)file;*read=cursor+count>size?size-cursor:count;memcpy(data,disk+cursor,*read);cursor+=*read;return FR_OK;}
static unsigned checks;
static void check(int condition,const char *message){checks++;if(!condition){fprintf(stderr,"FAIL %s\n",message);exit(1);}}
#define END_OF_SOUND_PARAMETERS_BYTES END_OF_SOUND_PARAMETERS
'''
for name in ("SNARE_NOISE_KIT_BYTES", "RPS_EXTRA_BYTES", "INS1_EXTRA_BYTES", "INS2_EXTRA_BYTES", "INS3_EXTRA_BYTES", "INS_EXTRA_BYTES", "LFO_EXTRA_BYTES"):
    code += define(name)
for name in ("preset_defaultInsExtras", "preset_captureInsExtras", "preset_applyInsExtras",
             "preset_writeInsExtras", "preset_readInsExtras"):
    code += function(name) + "\n"
code += r'''
int main(void){
 InsertFx_init();
 uint8_t d[INS_VALUE_COUNT],original[INS_VALUE_COUNT],loaded[INS_VALUE_COUNT];
 InsertFx_defaultValues(d);
 check(END_OF_SOUND_PARAMETERS+SNARE_NOISE_KIT_BYTES+LFO_EXTRA_BYTES+RPS_EXTRA_BYTES+INS_EXTRA_BYTES<=512,"kit fits the project slot");
 check(INS1_EXTRA_BYTES==20&&INS2_EXTRA_BYTES==15&&INS3_EXTRA_BYTES==7,"block sizes");
 /* roundtrip */
 for(unsigned i=0;i<INS_VALUE_COUNT;i++)activeParameters[PAR_INS_DST_MIX+i]=(uint8_t)(i==INS_CMP_RATIO?5:i==INS_PH2_STAGES?1:i==INS_DST_TYPE?2:i*4+1);
 preset_captureInsExtras(original);size=cursor=0;preset_writeInsExtras(original);
 check(size==INS_EXTRA_BYTES && !memcmp(disk,"INS1",4) && !memcmp(disk+INS1_EXTRA_BYTES,"INS2",4)
       && !memcmp(disk+INS1_EXTRA_BYTES+INS2_EXTRA_BYTES,"INS3",4),"markers and size");
 cursor=0;preset_readInsExtras(loaded);
 check(cursor==INS_EXTRA_BYTES && !memcmp(original,loaded,INS_VALUE_COUNT),"roundtrip");
 memset(activeParameters,0,sizeof(activeParameters));preset_applyInsExtras(loaded);
 for(unsigned i=0;i<INS_VALUE_COUNT;i++)check(activeParameters[PAR_INS_DST_MIX+i]==original[i],"applied to parameters");
 check(insertFx_params.compRatio==8.f,"applied to the effect");
 check(fabsf(insertFx_params.mix[INSERT_FX_DIST]-1.f/127.f)<1e-6f,"dst mix applied");
 /* old project kit: padding after RPS2, 0x00 or 0xFF; the read takes 20 bytes, defaults */
 for(int fill=0;fill<2;fill++){
   memset(disk,fill?0xff:0,sizeof disk);size=512-(END_OF_SOUND_PARAMETERS+SNARE_NOISE_KIT_BYTES+LFO_EXTRA_BYTES+RPS_EXTRA_BYTES);cursor=0;
   preset_readInsExtras(loaded);
   check(cursor==INS_EXTRA_BYTES,"old padding stays aligned");
   check(!memcmp(loaded,d,INS_VALUE_COUNT),"old project kit gets defaults");}
 /* old standalone .snd: file ends after RPS2 */
 size=cursor=0;preset_readInsExtras(loaded);check(!memcmp(loaded,d,INS_VALUE_COUNT),"old standalone kit gets defaults");
 /* truncated block */
 memcpy(disk,"INS1",4);memset(disk+4,1,INS_VALUE_COUNT);size=10;cursor=0;preset_readInsExtras(loaded);
 check(!memcmp(loaded,d,INS_VALUE_COUNT),"short block gets defaults");
 /* 0.2.81 kit: INS1 only, then the file ends or padding follows -> its values, fln/ph2 defaults */
 for(int pad=0;pad<2;pad++){
   memset(disk,0,sizeof disk);memcpy(disk,"INS1",4);for(unsigned i=0;i<INS1_VALUE_COUNT;i++)disk[4+i]=(uint8_t)(i+3);
   size=pad?200:INS1_EXTRA_BYTES;cursor=0;preset_readInsExtras(loaded);
   for(unsigned i=0;i<INS1_VALUE_COUNT;i++)check(loaded[i]==i+3,"0.2.81 kit keeps its insert values");
   for(unsigned i=INS1_VALUE_COUNT;i<INS_VALUE_COUNT;i++)check(loaded[i]==d[i],"0.2.81 kit gets fln/ph2 defaults");
   if(pad)check(cursor==INS_EXTRA_BYTES,"padding stays aligned");}
 /* 0.2.82 kit: INS1 + INS2, no INS3 -> its values, dst type/bias/out defaults */
 for(int pad=0;pad<2;pad++){
   memset(disk,0,sizeof disk);memcpy(disk,"INS1",4);for(unsigned i=0;i<INS1_VALUE_COUNT;i++)disk[4+i]=(uint8_t)(i+3);
   memcpy(disk+INS1_EXTRA_BYTES,"INS2",4);for(unsigned i=0;i<INS2_VALUE_COUNT;i++)disk[INS1_EXTRA_BYTES+4+i]=(uint8_t)(i==INS_PH2_STAGES-INS1_VALUE_COUNT?0:i+40);
   size=pad?200:INS1_EXTRA_BYTES+INS2_EXTRA_BYTES;cursor=0;preset_readInsExtras(loaded);
   for(unsigned i=0;i<INS1_VALUE_COUNT;i++)check(loaded[i]==i+3,"0.2.82 kit keeps INS1");
   for(unsigned i=0;i<INS2_VALUE_COUNT;i++)check(loaded[INS1_VALUE_COUNT+i]==(i==INS_PH2_STAGES-INS1_VALUE_COUNT?0:i+40),"0.2.82 kit keeps INS2");
   for(unsigned i=INS12_VALUE_COUNT;i<INS_VALUE_COUNT;i++)check(loaded[i]==d[i],"0.2.82 kit gets dst defaults");
   if(pad)check(cursor==INS_EXTRA_BYTES,"padding stays aligned");}
 /* corrupt values clamp on apply */
 memset(loaded,255,INS_VALUE_COUNT);preset_applyInsExtras(loaded);
 for(unsigned i=0;i<INS_VALUE_COUNT;i++)check(activeParameters[PAR_INS_DST_MIX+i]==(i==INS_CMP_RATIO?INS_CMP_RATIO_STEPS-1:i==INS_PH2_STAGES?INS_PH2_STAGE_STEPS-1:i==INS_DST_TYPE?INS_DST_TYPE_STEPS-1:127),"corrupt values clamp");
 /* parameter order matches the effect's value order */
 check(PAR_INS_DST_OUT-PAR_INS_DST_MIX==INS_VALUE_COUNT-1,"parameter block matches value enum");
 check(PAR_INS_DST_TYPE-PAR_INS_DST_MIX==INS_DST_TYPE,"dst type position");
 check(PAR_INS_FLN_MIX-PAR_INS_DST_MIX==INS_FLN_MIX,"fln position");
 check(PAR_INS_CMP_RATIO-PAR_INS_DST_MIX==INS_CMP_RATIO,"ratio position");
 printf("INS KIT PASS %u assertions\n",checks);return 0;
}
'''
(out / "contract.c").write_text(code, encoding="latin-1")
(out / "stm32f7xx_hal.h").write_text("#include <stdint.h>\n")
srcs = [root / "Core/Src/Soundengine/DSPAudio/FX/InsertFx.c", root / "Core/Src/Soundengine/DSPAudio/FX/Phaser.c", root / "Core/Src/Soundengine/DSPAudio/FX/Flanger.c"]
if os.name == "nt":
    vs = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat"
    files = " ".join(f'"{s}"' for s in srcs)
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /I. /I"{root / "Core/Inc"}" /Fe:contract.exe contract.c {files} && contract.exe', shell=True, cwd=out, check=True)
else:
    subprocess.run(["cc", "-std=c11", "-I.", f"-I{root / 'Core/Inc'}", "contract.c", *map(str, srcs), "-o", "contract", "-lm"], cwd=out, check=True)
    subprocess.run([str(out / "contract")], cwd=out, check=True)
