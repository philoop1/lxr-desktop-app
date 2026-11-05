"""Native test of the 0.2.52 voice hold: a held voice button shows which patterns have steps."""
from pathlib import Path
import os, re, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/used-patterns-audit'
OUT.mkdir(parents=True, exist_ok=True)


def read(p):
    return (ROOT / p).read_text(encoding='utf-8').replace('\r\n', '\n')


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
#include <string.h>
#define NUM_PATTERN 64
#define NUM_TRACKS 7
#define NUM_BARS 4
#define BUTTON_TIMEOUT 2000
enum {BUT_PAGE_UP=40,BUT_PAGE_DOWN,BUT_SEQ1,LED_PAGE_UP=60,LED_PAGE_DOWN,LED_STEP1=70};
enum {SELECT_MODE_VOICE=0,SELECT_MODE_PERF,SELECT_MODE_STEP,SELECT_MODE_PATTERN=6,SELECT_MODE_SONG=7};
enum {MODE_COPY_PATTERN=2};
#define PERF_PAGE 20
struct {uint16_t seq_mainSteps[NUM_BARS][NUM_PATTERN][NUM_TRACKS];} seq_patternSet;
struct {unsigned selectButtonMode:4;} buttonHandler_stateMemory;
uint32_t systick_ticks;
uint8_t menu_playedPattern,copyClear_Mode,shift,menu_activePage,delayPage;
uint8_t led[128],blink[128];unsigned seqLedUpdates,patternLedInits;
void led_setValue(uint8_t v,uint8_t n){led[n]=v;}
void led_setBlinkLed(const uint8_t n,const uint8_t v){blink[n]=v;}
uint8_t led_idx2StepLed(uint8_t i){return (uint8_t)(LED_STEP1+(i%16));}
void led_updateSeqLeds(void){seqLedUpdates++;for(int i=0;i<16;i++)led[LED_STEP1+i]=9;}
void led_initPatternSelectLeds(void){patternLedInits++;}
uint8_t buttonHandler_getShift(void){return shift;}
uint8_t buttonHandler_isMidiDelayPage(void){return delayPage;}
SEQ_CODE
BUTTON_CODE
static unsigned checks,failures;
static void check(int ok,const char *msg){checks++;if(!ok){failures++;printf("FAIL %s\n",msg);}}
static int litMask(void){int m=0;for(int i=0;i<16;i++)if(led[LED_STEP1+i]==1)m|=1<<i;return m;}
static int blinkMask(void){int m=0;for(int i=0;i<16;i++)if(blink[LED_STEP1+i])m|=1<<i;return m;}
static void hold(uint8_t voice){buttonHandler_voiceLongOtherButton(BUT_SEQ1+30);buttonHandler_voiceLongPress(voice);}
int main(void){
 /* bank 0: patterns 0 (track 0, bar 0), 5 (track 6, bar 3); bank 2: pattern 33 */
 seq_patternSet.seq_mainSteps[0][0][0]=1;seq_patternSet.seq_mainSteps[3][5][6]=0x8000;seq_patternSet.seq_mainSteps[1][33][3]=4;
 check(seq_isPatternUsed(0)&&seq_isPatternUsed(5)&&seq_isPatternUsed(33),"steps on any track and bar count");
 check(!seq_isPatternUsed(1)&&!seq_isPatternUsed(63)&&!seq_isPatternUsed(64)&&!seq_isPatternUsed(255),"empty and out-of-range patterns are free");
 menu_playedPattern=5;
 systick_ticks=1000;hold(2);
 systick_ticks+=BUTTON_TIMEOUT-1;buttonHandler_voiceLongTick();check(litMask()==0&&!blinkMask(),"short hold shows nothing");
 systick_ticks++;buttonHandler_voiceLongTick();
 check(litMask()==((1<<0)|(1<<5)),"used patterns of the played bank are lit");
 check(blinkMask()==(1<<5),"played pattern blinks");
 check(led[LED_PAGE_DOWN]==0&&led[LED_PAGE_UP]==0,"bank LEDs show bank 0");
 check(buttonHandler_voiceLongOtherButton(BUT_PAGE_UP)==1,"PAGE UP is used while shown");
 buttonHandler_voiceLongOtherButton(BUT_PAGE_UP);
 check(litMask()==(1<<1)&&!blinkMask()&&led[LED_PAGE_DOWN]==1&&led[LED_PAGE_UP]==0,"PAGE UP twice shows bank 2");
 buttonHandler_voiceLongOtherButton(BUT_PAGE_UP);buttonHandler_voiceLongOtherButton(BUT_PAGE_UP);
 check(led[LED_PAGE_DOWN]==1&&led[LED_PAGE_UP]==1,"bank stops at 3");
 for(int i=0;i<5;i++)buttonHandler_voiceLongOtherButton(BUT_PAGE_DOWN);
 check(litMask()==((1<<0)|(1<<5))&&led[LED_PAGE_DOWN]==0,"PAGE DOWN stops at bank 0");
 buttonHandler_voiceLongRelease(3);check(litMask()==((1<<0)|(1<<5)),"another voice release keeps the display");
 buttonHandler_voiceLongRelease(2);
 check(seqLedUpdates==1&&!blinkMask()&&led[LED_STEP1]==9,"release restores the step LEDs");
 systick_ticks+=10*BUTTON_TIMEOUT;buttonHandler_voiceLongTick();check(seqLedUpdates==1&&led[LED_STEP1]==9,"nothing after release");
 /* not shown yet: release cancels, page keys pass through */
 hold(1);check(buttonHandler_voiceLongOtherButton(BUT_PAGE_UP)==0,"PAGE UP before the display acts normally");
 systick_ticks+=BUTTON_TIMEOUT;buttonHandler_voiceLongTick();check(led[LED_STEP1]==9,"another button cancels the hold");
 hold(1);buttonHandler_voiceLongRelease(1);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_voiceLongTick();check(led[LED_STEP1]==9&&seqLedUpdates==1,"short press shows nothing");
 /* another button while shown hides it, pattern mode restores the pattern LEDs */
 buttonHandler_stateMemory.selectButtonMode=SELECT_MODE_PATTERN;
 hold(0);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_voiceLongTick();check(litMask()==((1<<0)|(1<<5)),"shown in pattern mode");
 check(buttonHandler_voiceLongOtherButton(BUT_SEQ1)==0&&patternLedInits==1&&!blinkMask(),"another button hides it in pattern mode");
 buttonHandler_stateMemory.selectButtonMode=SELECT_MODE_VOICE;
 /* mute, copy and the MIDI delay keep their voice buttons */
 static const char *why[]={"shift (mute)","perf page (mute)","copy mode","MIDI delay page"};
 for(int c=0;c<4;c++){
  memset(led,9,sizeof(led));shift=c==0;menu_activePage=c==1?PERF_PAGE:0;copyClear_Mode=c==2?MODE_COPY_PATTERN:0;delayPage=c==3;
  hold(4);systick_ticks+=BUTTON_TIMEOUT;buttonHandler_voiceLongTick();check(led[LED_STEP1]==9,why[c]);
 }
 printf("%s %u assertions\n",failures?"USED PATTERNS FAIL":"USED PATTERNS PASS",checks);
 return failures!=0;
}
"""

MUTATIONS = {
    'only-track-0': ('sequencer.c', 'if(seq_patternSet.seq_mainSteps[bar][pattern][track])return 1;', 'if(seq_patternSet.seq_mainSteps[bar][pattern][track]&&!track)return 1;'),
    'only-bar-0': ('sequencer.c', 'if(seq_patternSet.seq_mainSteps[bar][pattern][track])return 1;', 'if(seq_patternSet.seq_mainSteps[bar][pattern][track]&&!bar)return 1;'),
    'no-blink': ('buttonHandler.c', 'led_setBlinkLed(led_idx2StepLed(i),(uint8_t)(pattern==menu_playedPattern));', ';'),
    'no-restore': ('buttonHandler.c', '    if(shown)buttonHandler_hideUsedPatterns();', ''),
    'no-shift-guard': ('buttonHandler.c', ' || buttonHandler_getShift() ||', ' ||'),
    'page-passes': ('buttonHandler.c', '        buttonHandler_showUsedPatterns();\n        return 1;', '        return 0;'),
    'no-delay': ('buttonHandler.c', '    if((int32_t)(systick_ticks-buttonHandler_voiceLongDeadline)<0)return;', ''),
}


def build(mutation=None):
    seq = read('Core/Src/Soundengine/Sequencer/sequencer.c')
    btn = read('Core/Src/buttonHandler.c')
    if mutation:
        f, a, c = MUTATIONS[mutation]
        src = seq if f == 'sequencer.c' else btn
        if src.count(a) != 1:
            return 'BAD MUTATION'
        if f == 'sequencer.c': seq = seq.replace(a, c)
        else: btn = btn.replace(a, c)
    head = re.search(r'#define VOICE_LONG_NONE.*?static uint32_t buttonHandler_voiceLongDeadline;', btn, re.S)[0]
    code = head + '\n' + '\n'.join(function(btn, n) for n in (
        'buttonHandler_showUsedPatterns', 'buttonHandler_hideUsedPatterns', 'buttonHandler_voiceLongCancel',
        'buttonHandler_voiceLongPress', 'buttonHandler_voiceLongRelease', 'buttonHandler_voiceLongOtherButton',
        'buttonHandler_voiceLongTick'))
    (OUT / 'test.c').write_text(TEST.replace('SEQ_CODE', function(seq, 'seq_isPatternUsed')).replace('BUTTON_CODE', code), encoding='utf-8')
    if os.name == 'nt':
        vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
        r = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:test.exe test.c >nul && test.exe', shell=True, cwd=OUT, capture_output=True, text=True)
    else:
        r = subprocess.run('cc -std=c11 test.c -o test && ./test', shell=True, cwd=OUT, capture_output=True, text=True)
    return r.stdout + r.stderr


out = build()
print(out.strip().splitlines()[-1] if out.strip() else 'NO OUTPUT')
if 'USED PATTERNS PASS' not in out:
    print(out); sys.exit(1)
missed = 0
for name in MUTATIONS:
    res = build(name)
    caught = 'USED PATTERNS PASS' not in res and 'BAD MUTATION' not in res
    print(f'mutation {name}: {"caught" if caught else "MISSED " + res.strip()[:80]}')
    missed += not caught
sys.exit(1 if missed else 0)
