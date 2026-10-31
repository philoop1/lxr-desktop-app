"""Host check of the production played-step random LFO trigger and source routing."""
from pathlib import Path
import os
import re
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "build/lfo-step-audit"
out.mkdir(parents=True, exist_ok=True)
source = (root / "Core/Src/Soundengine/DSPAudio/lfo.c").read_text()

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
#define LFO_RANDOM_STEP 10
typedef struct {uint8_t waveform,retrigger,stepSlew,stepPolarity;uint32_t phaseOffset;float stepValue,rndTarget;} Lfo;
typedef struct {Lfo lfo;} Voice;
Voice voiceArray[3],snareVoice,cymbalVoice,hatVoice;
uint32_t GetRngValue(void){return 0x40000000u;}
static void check(int condition,const char *message){if(!condition){fprintf(stderr,"FAIL %s\n",message);exit(1);}}
'''
for name in ("lfo_random01", "lfo_byVoice", "lfo_setStepSlew", "lfo_setStepPolarity", "lfo_stepTrigger"):
    code += function(name) + "\n"
code += r'''
int main(void){
  voiceArray[0].lfo=(Lfo){LFO_RANDOM_STEP,1,0,2,0,0.5f,0.5f};
  snareVoice.lfo=(Lfo){LFO_RANDOM_STEP,1,80,2,0,0.5f,0.5f};
  cymbalVoice.lfo=(Lfo){LFO_RANDOM_STEP,5,0,2,0,0.5f,0.5f};
  hatVoice.lfo=(Lfo){LFO_RANDOM_STEP,6,0,2,0,0.5f,0.5f};
  lfo_stepTrigger(0);
  check(voiceArray[0].lfo.stepValue<0.26f && voiceArray[0].lfo.stepValue>0.24f,"source voice 1 snaps");
  check(snareVoice.lfo.rndTarget<0.26f && snareVoice.lfo.stepValue==0.5f,"slew retains prior output");
  check(cymbalVoice.lfo.stepValue==0.5f && hatVoice.lfo.stepValue==0.5f,"other sources unchanged");
  lfo_stepTrigger(6);
  check(hatVoice.lfo.stepValue<0.26f && hatVoice.lfo.stepValue>0.24f,"open hat shares source voice 6");
  lfo_setStepSlew(4,200);lfo_setStepPolarity(4,9);
  check(cymbalVoice.lfo.stepSlew==127 && cymbalVoice.lfo.stepPolarity==2,"controls clamp");
  puts("LFO STEP PASS");return 0;
}
'''
(out / "contract.c").write_text(code)
if os.name == "nt":
    vs = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat"
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:contract.exe contract.c && contract.exe', shell=True, cwd=out, check=True)
else:
    subprocess.run(["cc", "-std=c11", "contract.c", "-o", "contract"], cwd=out, check=True)
    subprocess.run([str(out / "contract")], cwd=out, check=True)
