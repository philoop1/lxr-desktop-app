"""Read every staged card pattern using the production C loader before applying."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    match = re.search(r"[^\n]*\b" + name + r"\([^)]*\)\s*\{", source)
    assert match, name
    position, depth = match.end(), 1
    while depth:
        depth += (source[position] == "{") - (source[position] == "}")
        position += 1
    return source[match.start():position]


def main(plan_path):
    plan_path = plan_path.resolve(strict=True)
    manifest = json.loads(plan_path.read_text())
    out = ROOT / "build/card-velocity-audit"
    out.mkdir(parents=True, exist_ok=True)
    header = (ROOT / "Core/Inc/Soundengine/Sequencer/sequencer.h").read_text()
    preset = (ROOT / "Core/Src/Preset/presetManager.c").read_text()
    sequencer = (ROOT / "Core/Src/Soundengine/Sequencer/sequencer.c").read_text()
    code = r"""
#include <stdint.h>
#include <stdio.h>
#include "Preset/TrigConditions.h"
#include <stdlib.h>
#include <string.h>
#include "Soundengine/Sequencer/PerformanceScale.h"
#define NUM_PATTERN 64
#define NUM_TRACKS 7
#define NUM_STEPS 64
#define STEPS_PER_PATTERN 64
#define NUM_BARS 4
#define USE_SD_CARD 1
#define FR_OK 0
#define NO_AUTOMATION 255
"""
    for name in ("SEQ_DEFAULT_NOTE", "SEQ_DEFAULT_VELOCITY"):
        code += re.search(r"^#define " + name + r" .*", header, re.M)[0] + "\n"
    code += (ROOT / "Core/Inc/Preset/SeqStep.h").read_text().replace('#include "main.h"', "")
    code += re.search(r"enum TrigCondition\s*\{.*?\};", header, re.S)[0] + "\n"
    code += re.search(r"typedef struct PatternSetStruct.*?}PatternSet;", header, re.S)[0]
    code += r"""
PatternSet seq_patternSet;
typedef unsigned UINT;typedef int FIL;int SDFile;
static uint8_t disk[65536];static unsigned size,cursor;
int f_read(FIL *f,void *dest,unsigned count,UINT *bytes){
 (void)f;*bytes=size-cursor<count?size-cursor:count;
 memcpy(dest,disk+cursor,*bytes);cursor+=*bytes;return FR_OK;
}
"""
    code += "FlamPreset seq_flamPresets[NUM_FLAM_PRESETS];\n"
    code += "static uint32_t seq_flamMask[NUM_FLAM_PRESETS];\n"
    code += re.search(r"static const uint8_t seq_flamGridPulses\[.*?;", sequencer)[0] + "\n"
    for name in ("seq_flamDefaultPreset", "seq_flamPosition", "seq_flamCalcMask",
                 "seq_flamPresetsChanged", "seq_flamResetPresets"):
        code += function(sequencer, name) + "\n"
    code += "void preset_touchFlamTimer(void) {}\n"
    for name in ("preset_readPatternScale", "preset_readFlamProbability", "preset_readTrigConditions",
                 "preset_flamSlotUsed", "preset_flamSameShape", "preset_flamForVelocity",
                 "preset_readFlamVelocity", "preset_readPatternData"):
        code += function(preset, name) + "\n"
    code += function(sequencer, "seq_resetNote") + "\n"
    code += r"""
static unsigned checks;
static void check(int ok,const char *message){
 checks++;if(!ok){fprintf(stderr,"FAIL: %s\n",message);exit(1);}
}
static void load(const char *path,unsigned header,unsigned version,unsigned slot){
 FILE *file=fopen(path,"rb");check(file!=NULL,path);
 size=(unsigned)fread(disk,1,sizeof(disk),file);check(!ferror(file),"pattern read");fclose(file);
 cursor=header;check(preset_readPatternData((uint8_t)slot,(uint8_t)version),"production pattern loader");
}
int main(int argc,char **argv){
 check(argc==2,"audit TSV argument");
 Step reset;memset(&reset,255,sizeof(reset));seq_resetNote(&reset);
 check(reset.volume==100&&reset.note==SEQ_DEFAULT_NOTE&&reset.prob==100&&
       reset.param1Nr==NO_AUTOMATION&&reset.param2Nr==NO_AUTOMATION,
       "new/reset step defaults to velocity 100 without an active flag");
 FILE *list=fopen(argv[1],"r");check(list!=NULL,"audit TSV exists");
 char line[4096];unsigned files=0,slots=0,changed=0;
 while(fgets(line,sizeof(line),list)){
   char *before=strtok(line,"\t"),*after=strtok(NULL,"\t");
   char *ver=strtok(NULL,"\t"),*head=strtok(NULL,"\r\n");
   check(before&&after&&ver&&head,"audit TSV row");
   unsigned version=(unsigned)atoi(ver),header=(unsigned)atoi(head);
   memset(&seq_patternSet,0,sizeof(seq_patternSet));
   seq_flamResetPresets();
   load(before,header,version,0);load(after,header,version,1);
   for(unsigned track=0;track<7;track++){
     for(unsigned step=0;step<64;step++){
       Step original=seq_patternSet.seq_subStepPattern[0][track][step];
       Step expected=original;
       expected.volume=(uint8_t)((original.volume&128)|(((original.volume&127)*100+63)/127));
       check(memcmp(&expected,&seq_patternSet.seq_subStepPattern[1][track][step],sizeof(Step))==0,
             "only proportional velocity changes in decoded Step");
       check(memcmp(&seq_patternSet.seq_stepTiming[0][track][step],
                    &seq_patternSet.seq_stepTiming[1][track][step],sizeof(StepTiming))==0,
             "Flam/Shift preserved");
       slots++;changed+=(original.volume!=expected.volume);
     }
     check(!memcmp(&seq_patternSet.trigCondition[0][track],&seq_patternSet.trigCondition[1][track],sizeof(TrigTrack)),
           "trigger conditions preserved");
     check(seq_patternSet.length[0][track]==seq_patternSet.length[1][track],"track length preserved");
     for(unsigned bar=0;bar<4;bar++)
       check(seq_patternSet.seq_mainSteps[bar][0][track]==seq_patternSet.seq_mainSteps[bar][1][track],
             "active step bits preserved");
   }
   check(seq_patternSet.shuffle[0]==seq_patternSet.shuffle[1]&&
         seq_patternSet.kitNr[0]==seq_patternSet.kitNr[1]&&
         seq_patternSet.scale[0]==seq_patternSet.scale[1],"pattern settings preserved");
   files++;
 }
 fclose(list);
 printf("CARD_VELOCITY_PLAN_PASS files=%u slots=%u changed=%u assertions=%u\n",files,slots,changed,checks);
 return 0;
}
"""
    (out / "contract.c").write_text(code)
    module = ROOT / "Core/Src/Soundengine/Sequencer/PerformanceScale.c"
    include = ROOT / "Core/Inc"
    if os.name == "nt":
        vs = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / (
            "Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat")
        subprocess.run(
            f'call "{vs}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /I"{include}" '
            f'/Fe:contract.exe contract.c "{module}" && contract.exe "{plan_path.parent / "audit.tsv"}"',
            shell=True, cwd=out, check=True)
    else:
        subprocess.run(["cc", "-std=c11", f"-I{include}", "contract.c", str(module), "-o", "contract"],
                       cwd=out, check=True)
        subprocess.run([str(out / "contract"), str(plan_path.parent / "audit.tsv")], cwd=out, check=True)
    print(f'EXPECTED_PLAN files={manifest["summary"]["files"]} slots={manifest["summary"]["step_slots"]}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    main(parser.parse_args().plan)
