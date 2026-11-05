"""Native contract check of saving the morphed kit (Mutador 0.2.58/0.2.59).

Runs the production preset_saveDrumsetRam/preset_getMorphValue and checks the
Save menu writes the MorphKit slot to the SD card. --mutate shows that each
check catches a broken implementation.
"""
from pathlib import Path
import os
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root / "build/morph-kit-audit"
out.mkdir(parents=True, exist_ok=True)
PRESET = (root / "Core/Src/Preset/presetManager.c").read_text(encoding="latin-1")
MENU = (root / "Core/Src/menu/menu.c").read_text(encoding="latin-1")


def function(source, name):
    match = re.search(r"^.*\b" + name + r"\([^)]*\)\s*\{", source, re.M)
    assert match, name
    pos, depth = match.end(), 1
    while depth:
        depth += (source[pos] == "{") - (source[pos] == "}")
        pos += 1
    return source[match.start():pos]


def menu_ok(menu):
    case = re.search(r"case SAVE_TYPE_MORPH:\s*//[^\n]*\n(.*?)break;", menu, re.S)
    if not case:
        return False
    body = case.group(1)
    return ("preset_saveDrumsetRam(menu_selectedPresetNr[SAVE_TYPE_MORPH],1)" in body
            and "preset_saveDrumsetSD(menu_selectedPresetNr[SAVE_TYPE_MORPH],0)" in body
            and "HAL_TIM_Base_Start_IT" in body
            and body.index("preset_saveDrumsetRam") < body.index("preset_saveDrumsetSD"))


def run(preset, menu):
    code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Parameters.h"
#define NUM_KIT_SLOTS 64
uint8_t activeParameters[NUM_PARAMS];
uint8_t mainParameters[NUM_KIT_SLOTS][END_OF_SOUND_PARAMETERS];
uint8_t mainLfoExtras[NUM_KIT_SLOTS][16],mainRpsExtras[NUM_KIT_SLOTS][16];
uint8_t *morphParameters;
unsigned checks;
static uint8_t interpolate(uint8_t a,uint8_t b,uint8_t m){return (uint8_t)(a+((int)b-(int)a)*m/127);}
static void preset_captureLfoExtras(uint8_t *data){data[0]=0xA1;}
static void preset_captureRpsExtras(uint8_t *data){data[0]=0xB2;}
static void check(int ok,const char *msg){checks++;if(!ok){fprintf(stderr,"FAIL %s\n",msg);exit(1);}}
uint8_t preset_getMorphValue(uint16_t index, uint8_t morph);
'''
    code += function(preset, "preset_getMorphValue") + "\n"
    code += function(preset, "preset_morphedKitValue") + "\n"
    code += function(preset, "preset_saveDrumsetRam") + "\n"
    code += r'''
int main(void){
 for(unsigned i=0;i<END_OF_SOUND_PARAMETERS;i++){activeParameters[i]=20;mainParameters[5][i]=120;}
 activeParameters[PAR_MORPH_KIT_DEST]=5;mainParameters[5][PAR_MORPH_KIT_DEST]=40;
 activeParameters[PAR_TARGET_LFO1]=7;mainParameters[5][PAR_TARGET_LFO1]=90;
 activeParameters[PAR_AUDIO_OUT3]=1;mainParameters[5][PAR_AUDIO_OUT3]=4;
 activeParameters[PAR_BANK_CHANGE]=2;mainParameters[5][PAR_BANK_CHANGE]=60;
 morphParameters=mainParameters[5];
 activeParameters[PAR_MORPH]=127;
 preset_saveDrumsetRam(9,1);
 check(mainParameters[9][PAR_COARSE1]==120,"full morph saves the target sound");
 check(mainParameters[9][PAR_TARGET_LFO1]==7,"mod targets come from the playing kit");
 check(mainParameters[9][PAR_MORPH_KIT_DEST]==5,"morph target slot is kept, not interpolated");
 check(mainParameters[9][PAR_AUDIO_OUT3]==1,"audio routing comes from the playing kit, like the live Morph");
 check(mainParameters[9][PAR_BANK_CHANGE]==2,"bank change is not morphed, like the live Morph");
 check(mainLfoExtras[9][0]==0xA1&&mainRpsExtras[9][0]==0xB2,"LFO and rps extras are saved with the morphed kit");
 activeParameters[PAR_MORPH]=0;preset_saveDrumsetRam(10,1);
 check(mainParameters[10][PAR_COARSE1]==20,"morph 0 saves the playing kit");
 activeParameters[PAR_MORPH]=64;preset_saveDrumsetRam(11,1);
 check(mainParameters[11][PAR_COARSE1]>20&&mainParameters[11][PAR_COARSE1]<120,"half morph saves a mix");
 memset(mainLfoExtras[12],0,16);preset_saveDrumsetRam(12,0);
 check(mainParameters[12][PAR_COARSE1]==20&&mainLfoExtras[12][0]==0xA1,"normal kit save unchanged");
 printf("MORPH KIT PASS %u assertions\n",checks);return 0;
}
'''
    (out / "contract.c").write_text(code)
    (out / "stm32f7xx_hal.h").write_text("#include <stdint.h>\n")
    if os.name == "nt":
        vs = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat"
        result = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /I. /I"{root / "Core/Inc"}" /Fe:contract.exe contract.c && contract.exe',
                                shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    else:
        result = subprocess.run(f'cc -std=c11 -I. -I"{root / "Core/Inc"}" contract.c -o contract && ./contract',
                                shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    ok = result.returncode == 0 and menu_ok(menu)
    return ok, result.stdout + result.stderr


MUTATIONS = {
    'no-dest-keep': ('PRESET', ' ||\n\t   i == PAR_MORPH_KIT_DEST || i == PAR_BANK_CHANGE)', ' ||\n\t   i == PAR_BANK_CHANGE)'),
    'no-routing-keep': ('PRESET', '\t   (i >= PAR_AUDIO_OUT1 && i <= PAR_AUDIO_OUT6) ||\n', ''),
    'no-bank-keep': ('PRESET', ' || i == PAR_BANK_CHANGE)', ')'),
    'no-morph-extras': ('PRESET', '		preset_captureLfoExtras(mainLfoExtras[presetNr]);\n		preset_captureRpsExtras(mainRpsExtras[presetNr]);\n	}\n	else', '	}\n	else'),
    'ram-only': ('MENU', 'preset_saveDrumsetSD(menu_selectedPresetNr[SAVE_TYPE_MORPH],0);', ''),
}

if '--mutate' in sys.argv:
    caught = 0
    for name, (where, old, new) in MUTATIONS.items():
        preset, menu = PRESET.replace('\r\n', '\n'), MENU.replace('\r\n', '\n')
        target = preset if where == 'PRESET' else menu
        assert target.count(old) >= 1, name
        target = target.replace(old, new)
        ok, _ = run(target if where == 'PRESET' else preset, target if where == 'MENU' else menu)
        print(name, 'caught' if not ok else 'MISSED')
        caught += not ok
    print(f'{caught}/{len(MUTATIONS)} mutations caught')
    sys.exit(0 if caught == len(MUTATIONS) else 1)

ok, text = run(PRESET, MENU)
print(text.strip().splitlines()[-1] if text.strip() else '')
if not menu_ok(MENU):
    print('FAIL Save menu does not write the MorphKit slot to the SD card')
sys.exit(0 if ok else 1)
