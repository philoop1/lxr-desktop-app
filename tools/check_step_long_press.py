"""Native test of the 0.2.53 step edit gesture: short press selects, long press sets or clears."""
from pathlib import Path
import os, re, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/step-long-press-audit'
OUT.mkdir(parents=True, exist_ok=True)


def function(src, name):
    m = re.search(r'[^\n]*\b' + name + r'\([^)]*\)\s*\{', src)
    assert m, name
    pos = m.end(); depth = 1
    while depth:
        depth += (src[pos] == '{') - (src[pos] == '}'); pos += 1
    return src[m.start():pos]


TEST = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define BUTTON_TIMEOUT 2000
enum {SELECT_MODE_VOICE=0,SELECT_MODE_STEP=2,LED_MODE1=50};
struct {unsigned selectButtonMode:4;} buttonHandler_stateMemory;
uint32_t systick_ticks;uint8_t menu_activeBar;
static uint16_t held;static unsigned selects,toggles,blinkClears;static uint8_t lastToggle;
uint8_t menu_getViewedPattern(void){return 3;}
uint8_t menu_getActiveVoice(void){return 1;}
/* 0.2.90: the cursor is not on sld here */
uint8_t activeParameters[600];enum{PAR_STEP_SLIDE=500,PAR_STEP_ACCENT=501,PRESET_PAT_TIMER=1};
uint8_t menu_isSlideCursor(void){return 0;}
uint8_t seq_getSlide(uint8_t p,uint8_t v,uint8_t s){(void)p;(void)v;(void)s;return 0;}
void seq_setSlide(uint8_t p,uint8_t v,uint8_t s,uint8_t on){(void)p;(void)v;(void)s;(void)on;}
uint8_t seq_getAccent(uint8_t p,uint8_t v,uint8_t s){(void)p;(void)v;(void)s;return 0;}
void seq_setAccent(uint8_t p,uint8_t v,uint8_t s,uint8_t on){(void)p;(void)v;(void)s;(void)on;}
void preset_touchTimer(uint8_t t){(void)t;}
void led_updateSeqLeds(void){}
void menu_repaintAll(void){}
uint8_t stepEdit_press(uint8_t p,uint8_t v,uint8_t key,uint8_t step){(void)p;(void)v;(void)step;uint8_t first=!held;held|=(uint16_t)(1u<<key);return first;}
void stepEdit_release(uint8_t key){held&=(uint16_t)~(1u<<key);}
void led_clearAllBlinkLeds(void){blinkClears++;}
void led_setBlinkLed(uint8_t l,uint8_t v){(void)l;(void)v;}
void buttonHandler_selectActiveStep(uint8_t led,uint8_t key){(void)led;(void)key;selects++;}
void buttonHandler_setRemoveStep(uint8_t led,uint8_t key){(void)led;lastToggle=key;toggles++;}
DECLS
TICK
void pressStep(uint8_t seqButtonPressed){
 const uint8_t ledNr=(uint8_t)(100+seqButtonPressed);
 PRESS_RESET
 switch(buttonHandler_stateMemory.selectButtonMode){
 STEP_CASE
 default:break;
 }
}
void pressOther(void){PRESS_RESET}
void releaseStep(uint8_t seqButtonPressed){
 RELEASE
}
static unsigned checks,failures;
static void check(int ok,const char *msg){checks++;if(!ok){failures++;printf("FAIL %s\n",msg);}}
int main(void){
 buttonHandler_stateMemory.selectButtonMode=SELECT_MODE_STEP;systick_ticks=500;
 pressStep(4);check(selects==1&&!toggles,"press selects at once");
 systick_ticks+=BUTTON_TIMEOUT-1;buttonHandler_stepLongTick();releaseStep(4);
 systick_ticks+=BUTTON_TIMEOUT;buttonHandler_stepLongTick();check(!toggles,"short press only selects");
 pressStep(4);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_stepLongTick();check(toggles==1&&lastToggle==4,"long press sets/clears the step");
 buttonHandler_stepLongTick();systick_ticks+=10*BUTTON_TIMEOUT;buttonHandler_stepLongTick();check(toggles==1,"one toggle per hold");
 releaseStep(4);check(toggles==1&&selects==2,"release after a long press does nothing more");
 pressStep(7);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_stepLongTick();releaseStep(7);
 pressStep(7);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_stepLongTick();releaseStep(7);
 check(toggles==3&&lastToggle==7,"a second long press toggles again");
 /* chord: the second key selects a group, nothing toggles */
 pressStep(1);systick_ticks+=100;pressStep(2);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_stepLongTick();
 check(toggles==3,"a chord does not toggle");
 releaseStep(2);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_stepLongTick();check(toggles==3,"releasing the chord partner does not re-arm");
 releaseStep(1);
 pressStep(5);pressOther();systick_ticks+=BUTTON_TIMEOUT;buttonHandler_stepLongTick();releaseStep(5);check(toggles==3,"another button cancels");
 pressStep(6);buttonHandler_stateMemory.selectButtonMode=SELECT_MODE_VOICE;systick_ticks+=BUTTON_TIMEOUT;buttonHandler_stepLongTick();releaseStep(6);
 check(toggles==3,"leaving step mode cancels");
 buttonHandler_stateMemory.selectButtonMode=SELECT_MODE_STEP;
 systick_ticks=0xffffff00u;pressStep(9);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_stepLongTick();releaseStep(9);check(toggles==4,"timer survives the systick wrap");
 printf("%s %u assertions\n",failures?"STEP LONG FAIL":"STEP LONG PASS",checks);
 return failures!=0;
}
"""

MUTATIONS = {
    'no-arm': '				buttonHandler_stepLongKey=seqButtonPressed;\n',
    'no-release-cancel': '	if(seqButtonPressed==buttonHandler_stepLongKey)buttonHandler_stepLongKey=STEP_LONG_NONE;\n',
    'no-other-cancel': '	buttonHandler_stepLongKey=STEP_LONG_NONE; // a second button makes a chord, no long press\n',
    'no-disarm': '	buttonHandler_stepLongKey=STEP_LONG_NONE;\n	if(buttonHandler_stateMemory.selectButtonMode!=SELECT_MODE_STEP)return;\n',
    'no-mode-check': '	if(buttonHandler_stateMemory.selectButtonMode!=SELECT_MODE_STEP)return;\n	buttonHandler_setRemoveStep',
    'no-wait': '	if((int32_t)(systick_ticks-buttonHandler_stepLongDeadline)<0)return;\n',
}
REPLACE = {'no-disarm': '	if(buttonHandler_stateMemory.selectButtonMode!=SELECT_MODE_STEP)return;\n',
           'no-mode-check': '	buttonHandler_setRemoveStep'}


def build(mutation=None):
    btn = (ROOT / 'Core/Src/buttonHandler.c').read_text(encoding='utf-8').replace('\r\n', '\n')
    if mutation:
        a = MUTATIONS[mutation]
        if btn.count(a) != 1:
            return 'BAD MUTATION'
        btn = btn.replace(a, REPLACE.get(mutation, ''))
    decls = re.search(r'#define STEP_LONG_NONE.*?static uint32_t buttonHandler_stepLongDeadline;', btn, re.S)[0]
    press = function(btn, 'buttonHandler_seqButtonPressed')
    a = press.index('		case SELECT_MODE_STEP:\n')
    b = press.index('		case SELECT_MODE_PATTERN:', a)
    pressed = function(btn, 'buttonHandler_buttonPressed')
    reset = re.search(r'\tbuttonHandler_stepLongKey=STEP_LONG_NONE;[^\n]*\n', pressed)
    rel = re.search(r'\tstepEdit_release\(seqButtonPressed\);\n(\tif\(seqButtonPressed==buttonHandler_stepLongKey\)[^\n]*\n)?', btn)[0]
    code = (TEST.replace('DECLS', decls).replace('TICK', function(btn, 'buttonHandler_stepLongTick'))
            .replace('PRESS_RESET', reset[0] if reset else '').replace('STEP_CASE', press[a:b]).replace('RELEASE', rel))
    (OUT / 'test.c').write_text(code, encoding='utf-8')
    if os.name == 'nt':
        vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
        r = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:test.exe test.c >nul && test.exe', shell=True, cwd=OUT, capture_output=True, text=True)
    else:
        r = subprocess.run('cc -std=c11 test.c -o test && ./test', shell=True, cwd=OUT, capture_output=True, text=True)
    return r.stdout + r.stderr


out = build()
print(out.strip().splitlines()[-1] if out.strip() else 'NO OUTPUT')
if 'STEP LONG PASS' not in out:
    print(out); sys.exit(1)
missed = 0
for name in MUTATIONS:
    res = build(name)
    caught = 'STEP LONG PASS' not in res and 'BAD MUTATION' not in res
    print(f'mutation {name}: {"caught" if caught else "MISSED " + res.strip()[:80]}')
    missed += not caught
sys.exit(1 if missed else 0)
