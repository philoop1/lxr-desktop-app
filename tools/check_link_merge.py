"""0.2.92 link loop save, bar follow chord, random step chase light.

Pattern Save with a link loop of 2-4 one-bar patterns that holds the playing
pattern saves the loop as one pattern of 2-4 bars. In voice/step edit both bar
buttons together switch follow; perf blinks in pattern select mode; the chase
light shows the step that really plays (random step). Runs the production
merge, chase, blink and chord functions on the host plus source contracts;
--mutate shows the checks bite."""
from pathlib import Path
import os, re, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root / 'build/link-merge'
out.mkdir(parents=True, exist_ok=True)
FILES = {
    'seq': 'Core/Src/Soundengine/Sequencer/sequencer.c',
    'seqh': 'Core/Inc/Soundengine/Sequencer/sequencer.h',
    'menu': 'Core/Src/menu/menu.c',
    'led': 'Core/Src/ledHandler.c',
    'button': 'Core/Src/buttonHandler.c',
}


def load():
    return {k: (root / p).read_text(encoding='latin-1').replace('\r\n', '\n') for k, p in FILES.items()}


def body(src, sig):
    start = src.index(sig)
    i = src.index('{', start)
    depth = 0
    while True:
        depth += (src[i] == '{') - (src[i] == '}')
        if depth == 0:
            return src[start:i + 1]
        i += 1


def contract(s):
    p = []
    m = s['menu']
    case = m[m.index('case SAVE_TYPE_PATTERN:\n\n'):]
    case = case[:case.index('preset_refreshTmpPat')]
    if 'if(seq_mergeLinkLoop(menu_selectedPresetNr[SAVE_TYPE_PATTERN])) {' not in case:
        p.append('pattern save does not merge the link loop')
    elif case.index('preset_savePatternRAM') < case.index('seq_mergeLinkLoop'):
        p.append('the normal RAM save runs before the merge and overwrites it')
    if 'preset_savePatternSD(menu_selectedPresetNr[SAVE_TYPE_PATTERN]);' not in case:
        p.append('the merged pattern is not written to the card')
    i = s['seq'].index('void seq_nextStep()')  # 0.2.103 in flash now
    nxt = s['seq'][i:s['seq'].index('uint8_t seq_getExtSync()', i)]
    if 'const uint8_t stepIdx = seq_chaseStep(frontParser_activeTrack);' not in nxt:
        p.append('the chase light does not show the random step')
    b = s['button']
    if b.count('if(buttonHandler_barChord(1u)) break;') != 1 or b.count('if(buttonHandler_barChord(2u)) break;') != 1:
        p.append('a bar button does not check the follow chord')
    if 'buttonHandler_barHeld &= (uint8_t)~1u;' not in b or 'buttonHandler_barHeld &= (uint8_t)~2u;' not in b:
        p.append('releasing a bar button does not end the chord')
    if 'led_setMode2(SELECT_MODE_PATTERN); // 0.2.92 perf blinks' not in body(b, 'static void buttonHandler_enterPatternShortcut(void)\n{'):
        p.append('the pattern shortcut does not make perf blink')
    mode = body(s['led'], 'void led_setMode2(uint8_t status)')
    if 'case SELECT_MODE_PATTERN:' not in mode or 'led_setBlinkLed(LED_MODE2,1);' not in mode[mode.index('case SELECT_MODE_PATTERN:'):]:
        p.append('pattern select mode does not blink perf')
    if 'led_setBlinkLed(LED_MODE2,1);' not in body(s['led'], 'void led_initPatternSelectLeds()'):
        p.append('a pattern LED refresh stops the perf blink')
    for fn in ('uint8_t seq_mergeLinkLoop', 'uint8_t seq_linkLoopBars', 'static uint8_t seq_chaseStep'):
        if '__attribute__((noinline)) ' + fn not in s['seq']:
            p.append(f'{fn} must stay in flash (ITCM is full)')
    return p


def harness(s):
    seq, led, btn = s['seq'], s['led'], s['button']
    code = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#define __attribute__(x)
#define NUM_PATTERN 64
#define NUM_TRACKS 7
#define NUM_STEPS 64
#define NUM_BARS 4
#define SLIDE_TRACKS 3
#define PATTERN_INT_SENDS 6
#define LINK_NOT_MERGEABLE 255
typedef struct {uint8_t volume,note,locks;} Step;
typedef struct {uint8_t flam,shift;} StepTiming;
typedef struct {uint8_t c[64];} TrigTrack;
static uint8_t trigTrackGet(const TrigTrack*t,uint8_t s){return t->c[s];}
static void trigTrackSet(TrigTrack*t,uint8_t s,uint8_t v){t->c[s]=v;}
static unsigned plockCopies;
static void plock_copy(Step*d,const Step*s){*d=*s;plockCopies++;}
struct {
 Step seq_subStepPattern[NUM_PATTERN][NUM_TRACKS][NUM_STEPS];
 StepTiming seq_stepTiming[NUM_PATTERN][NUM_TRACKS][NUM_STEPS];
 uint8_t flamProbability[NUM_PATTERN][NUM_TRACKS][NUM_STEPS];
 TrigTrack trigCondition[NUM_PATTERN][NUM_TRACKS];
 uint16_t seq_mainSteps[NUM_BARS][NUM_PATTERN][NUM_TRACKS];
 uint8_t length[NUM_PATTERN][NUM_TRACKS];
 uint8_t shuffle[NUM_PATTERN],kitNr[NUM_PATTERN],scale[NUM_PATTERN],transform[NUM_PATTERN];
 uint8_t intSend[NUM_PATTERN][PATTERN_INT_SENDS];
 uint64_t slide[NUM_PATTERN][SLIDE_TRACKS];
 uint64_t accent[NUM_PATTERN][NUM_TRACKS];
} seq_patternSet;
uint8_t seq_activePattern,seq_revertActiveOnSwitch,seq_stepIndex[NUM_TRACKS];
static int backupOf=-1,nextOf=-1;
static void seq_copyPatternToBackupBuffer(uint8_t p){backupOf=p;}
static void seq_setNextPattern(uint8_t p){nextOf=p;}
'''
    code += '#include "' + (root / 'Core/Src/Soundengine/Sequencer/PerformanceSteps.c').as_posix() + '"\n'
    code += 'static const PerfTrack *seq_perfTracks[NUM_TRACKS];\n'
    code += body(seq, '__attribute__((noinline)) uint8_t seq_getSlide') + '\n' + body(seq, '__attribute__((noinline)) void seq_setSlide') + '\n'
    code += body(seq, '__attribute__((noinline)) uint8_t seq_getAccent') + '\n' + body(seq, '__attribute__((noinline)) void seq_setAccent') + '\n'
    code += body(seq, 'static void seq_copyStepAcross') + '\n' + body(seq, 'static uint8_t seq_loopLength') + '\n'
    code += body(seq, '__attribute__((noinline)) uint8_t seq_linkLoopBars') + '\n' + body(seq, '__attribute__((noinline)) uint8_t seq_mergeLinkLoop') + '\n'
    code += body(seq, '__attribute__((noinline)) static uint8_t seq_chaseStep') + '\n'
    # blink slots
    code += r'''
#define NUM_OF_BLINKABLE_LEDS 4
static uint8_t led_blinkingLeds,led_blinkLedNumber[NUM_OF_BLINKABLE_LEDS],ledLevel[256];
static void led_toggleTemp(uint8_t l){ledLevel[l]^=1;}
static void led_reset(uint8_t l){ledLevel[l]=0;}
'''
    code += body(led, 'void led_setBlinkLed(const uint8_t ledNr, const uint8_t onOff)') + '\n'
    # follow chord
    code += r'''
#define FOLLOW_BAR 0x1
enum {PAR_FOLLOW=3};
uint8_t activeParameters[10],menu_activeBar,playStep=255;
static unsigned notes,ledUpdates;static const char *lastNote;
static uint8_t seq_getStepIndex(uint8_t v){(void)v;return playStep;}
static uint8_t menu_getActiveVoice(void){return 0;}
static void led_updateSeqLeds(void){ledUpdates++;}
static void led_updateBarLeds(void){}
static void menu_showNote(const char*a,const char*b){(void)b;notes++;lastNote=a;}
'''
    code += re.search(r'static uint8_t buttonHandler_barHeld, buttonHandler_barBefore;\n', btn).group(0)
    code += body(btn, 'static uint8_t buttonHandler_barChord(uint8_t bit)') + '\n'
    rel_up = 'buttonHandler_barHeld &= (uint8_t)~1u;' in btn
    rel_dn = 'buttonHandler_barHeld &= (uint8_t)~2u;' in btn
    code += 'static void releaseUp(void){' + ('buttonHandler_barHeld &= (uint8_t)~1u;' if rel_up else '') + '}\n'
    code += 'static void releaseDown(void){' + ('buttonHandler_barHeld &= (uint8_t)~2u;' if rel_dn else '') + '}\n'
    code += r'''
/* the bar button handlers around the chord: page up/down move one bar */
static void pressUp(void){if(buttonHandler_barChord(1u))return;if(menu_activeBar<NUM_BARS-1)menu_activeBar++;}
static void pressDown(void){if(buttonHandler_barChord(2u))return;if(menu_activeBar>0)menu_activeBar--;}
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
static void fill(uint8_t p,uint8_t tag){
 for(int t=0;t<NUM_TRACKS;t++){seq_patternSet.length[p][t]=16;for(int b=0;b<NUM_BARS;b++)seq_patternSet.seq_mainSteps[b][p][t]=0;
  for(int s=0;s<NUM_STEPS;s++){Step*st=&seq_patternSet.seq_subStepPattern[p][t][s];st->volume=tag;st->note=(uint8_t)s;st->locks=(uint8_t)(tag+t);
   seq_patternSet.seq_stepTiming[p][t][s].shift=(uint8_t)(tag&7);seq_patternSet.flamProbability[p][t][s]=tag;seq_patternSet.trigCondition[p][t].c[s]=(uint8_t)(tag+s);}
  seq_patternSet.seq_mainSteps[0][p][t]=(uint16_t)(1u<<(tag%16));}
 seq_patternSet.slide[p][0]=1ull<<(tag%16);seq_patternSet.shuffle[p]=tag;seq_patternSet.kitNr[p]=tag;seq_patternSet.scale[p]=(uint8_t)(tag%8);
 seq_patternSet.transform[p]=tag;memset(seq_patternSet.intSend[p],tag,PATTERN_INT_SENDS);}
static void setup(void){memset(&seq_patternSet,0,sizeof seq_patternSet);for(uint8_t p=4;p<=7;p++)fill(p,(uint8_t)(10+p));fill(20,99);
 perf_setLoop(4,7);seq_activePattern=5;seq_revertActiveOnSwitch=0;backupOf=nextOf=-1;}
static int barFrom(uint8_t dst,uint8_t t,uint8_t bar,uint8_t srcPattern){
 const uint8_t tag=(uint8_t)(10+srcPattern);
 for(int k=0;k<16;k++){const Step*s=&seq_patternSet.seq_subStepPattern[dst][t][bar*16+k];
  if(s->volume!=tag||s->note!=k||s->locks!=tag+t)return 0;
  if(seq_patternSet.flamProbability[dst][t][bar*16+k]!=tag||seq_patternSet.trigCondition[dst][t].c[bar*16+k]!=(uint8_t)(tag+k))return 0;}
 if(seq_patternSet.seq_mainSteps[bar][dst][t]!=(uint16_t)(1u<<(tag%16)))return 0;
 if(t==0&&((seq_patternSet.slide[dst][0]>>(bar*16))&0xffffu)!=(1u<<(tag%16)))return 0;
 return 1;}
int main(void){
 /* merge into a free slot */
 setup();check(seq_linkLoopBars()==4,"4 one-bar patterns = 4 bars");
 check(seq_mergeLinkLoop(30)==4,"merged");
 for(uint8_t t=0;t<NUM_TRACKS;t++){check(seq_patternSet.length[30][t]==64,"length 4 bars");
  for(uint8_t b=0;b<4;b++)check(barFrom(30,t,b,(uint8_t)(4+b)),"bar b comes from the b-th loop pattern");}
 check(seq_patternSet.shuffle[30]==14&&seq_patternSet.kitNr[30]==14&&seq_patternSet.intSend[30][5]==14,"pattern settings from the first loop pattern");
 check(!perf_getLoop(0,0),"the link is off after the save");
 check(nextOf==30&&seq_revertActiveOnSwitch==1&&backupOf==-1,"the saved slot plays next, like a save to a new slot");
 check(barFrom(4,0,0,4)&&barFrom(7,6,0,7),"the loop patterns stay");
 /* save slot inside the loop, not the first one */
 setup();check(seq_mergeLinkLoop(6)==4,"merge into a loop slot");
 for(uint8_t t=0;t<NUM_TRACKS;t++)for(uint8_t b=0;b<4;b++)check(barFrom(6,t,b,(uint8_t)(4+b)),"a loop slot keeps its own bar before it is overwritten");
 /* save onto the playing pattern */
 setup();seq_activePattern=4;check(seq_mergeLinkLoop(4)==4&&backupOf==4&&nextOf==-1,"saving the playing pattern keeps it playing");
 for(uint8_t b=0;b<4;b++)check(barFrom(4,2,b,(uint8_t)(4+b)),"in place merge");
 /* 2 patterns, short track, rest cleared */
 setup();perf_setLoop(4,5);seq_activePattern=4;seq_patternSet.length[5][3]=12;
 seq_patternSet.seq_mainSteps[2][40][3]=0xffff;seq_patternSet.seq_mainSteps[3][40][3]=0xffff;
 check(seq_mergeLinkLoop(40)==2&&seq_patternSet.length[40][3]==32,"2 bars");
 check(seq_patternSet.seq_mainSteps[2][40][3]==0&&seq_patternSet.seq_mainSteps[3][40][3]==0,"bars after the merge are empty");
 {int ok=1;for(int k=0;k<16;k++)ok&=seq_patternSet.seq_subStepPattern[40][3][16+k].note==k%12;check(ok,"a 12 step track plays from step 1 in each bar");}
 /* not mergeable */
 setup();seq_patternSet.length[6][2]=32;check(seq_linkLoopBars()==LINK_NOT_MERGEABLE&&seq_mergeLinkLoop(30)==0&&perf_getLoop(0,0),"a 2 bar pattern in the loop: no merge");
 setup();perf_setLoop(4,8);check(seq_linkLoopBars()==LINK_NOT_MERGEABLE,"5 patterns: no merge");
 setup();seq_activePattern=20;check(seq_linkLoopBars()==0&&seq_mergeLinkLoop(30)==0,"the playing pattern outside the loop: normal save");
 setup();perf_clearLoop();check(seq_linkLoopBars()==0,"no link: normal save");
 setup();check(seq_mergeLinkLoop(64)==0,"bad slot");
 setup();seq_patternSet.length[5][1]=0;check(seq_mergeLinkLoop(30)==4&&barFrom(30,1,1,5),"length 0 counts as one bar");
 /* chase light */
 {static PerfTrack pt;seq_stepIndex[2]=5;check(seq_chaseStep(2)==5,"no random state: timeline step");
  pt.current.timeline=5;pt.current.source=37;seq_perfTracks[2]=&pt;check(seq_chaseStep(2)==37,"random step shown");
  pt.current.timeline=4;check(seq_chaseStep(2)==5,"stale state ignored");
  pt.current.timeline=5;pt.current.source=70;check(seq_chaseStep(2)==5,"bad source ignored");check(seq_chaseStep(9)==0,"track range");}
 /* blink slots */
 led_setBlinkLed(50,1);led_setBlinkLed(50,1);check(led_blinkingLeds==1,"an LED blinks in one slot only");
 led_setBlinkLed(51,1);check(led_blinkingLeds==3,"another LED gets its own slot");
 led_setBlinkLed(50,0);check(led_blinkingLeds==2,"blink off frees the slot");
 /* follow chord */
 activeParameters[PAR_FOLLOW]=FOLLOW_BAR;menu_activeBar=1;
 pressUp();check(menu_activeBar==2&&notes==0,"single press moves one bar");releaseUp();
 pressUp();pressDown();check(activeParameters[PAR_FOLLOW]==0&&menu_activeBar==2&&notes==1&&lastNote[7]=='o'&&lastNote[8]=='f',"both buttons: follow off, the first move undone");
 releaseDown();releaseUp();pressDown();check(menu_activeBar==1&&activeParameters[PAR_FOLLOW]==0,"follow off: single press navigates");releaseDown();
 playStep=50;pressDown();pressUp();check(activeParameters[PAR_FOLLOW]==FOLLOW_BAR&&menu_activeBar==3&&lastNote[8]=='n',"follow on again jumps to the playing bar");
 releaseUp();releaseDown();pressDown();check(activeParameters[PAR_FOLLOW]==FOLLOW_BAR&&menu_activeBar==2,"after release a single press is no chord");
 printf("LINK MERGE PASS %u assertions\n",checks);return 0;}
'''
    return code


def run(code):
    (out / 'merge.c').write_text(code, encoding='latin-1')
    inc = (root / 'Core/Inc').as_posix()
    if os.name == 'nt':
        vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
        r = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /I"{inc}" /Fe:merge.exe merge.c && merge.exe',
                           shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    else:
        r = subprocess.run(f'cc -I"{inc}" -o merge merge.c && ./merge', shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    return r.returncode, r.stdout + r.stderr


MUTATIONS = {
    'merge-after-save': ('menu', '''							if(seq_mergeLinkLoop(menu_selectedPresetNr[SAVE_TYPE_PATTERN])) {''',
                         '''							preset_savePatternRAM(menu_selectedPresetNr[SAVE_TYPE_PATTERN]);
							if(seq_mergeLinkLoop(menu_selectedPresetNr[SAVE_TYPE_PATTERN])) {'''),
    'own-bar-late': ('seq', 'const uint8_t b = own==255 ? i : (i==0 ? own : (i<=own ? (uint8_t)(i-1) : i));', 'const uint8_t b = i;'),
    'no-short-wrap': ('seq', '(uint8_t)(k%len[b][t])', 'k'),
    'keep-length': ('seq', '		seq_patternSet.length[dst][t]=(uint8_t)(bars*16u);\n', ''),
    'no-clear-rest': ('seq', '		for(uint8_t b=bars;b<NUM_BARS;b++) seq_patternSet.seq_mainSteps[b][dst][t]=0;\n', ''),
    'no-slide': ('seq', '	if(track<SLIDE_TRACKS)seq_setSlide(dp,track,ds,seq_getSlide(sp,track,ss));\n', ''),
    'no-cond': ('seq', '	trigTrackSet(&seq_patternSet.trigCondition[dp][track],ds,trigTrackGet(&seq_patternSet.trigCondition[sp][track],ss));\n	if(track<SLIDE_TRACKS)seq_setSlide(dp', '	if(track<SLIDE_TRACKS)seq_setSlide(dp'),
    'long-ok': ('seq', '			if(seq_loopLength(p,t)>16u) return LINK_NOT_MERGEABLE;\n', ''),
    'link-stays': ('seq', '	perf_clearLoop();\n	if(dst==seq_activePattern)', '	if(dst==seq_activePattern)'),
    'not-playing': ('seq', ' || seq_activePattern<start || seq_activePattern>end) return 0;', ') return 0;'),
    'zero-len': ('seq', '	return (len==0 || len>NUM_STEPS) ? 16 : len;', '	return len ? len : 1;'),
    'chase-timeline': ('seq', 'const uint8_t stepIdx = seq_chaseStep(frontParser_activeTrack); // 0.2.92', 'const uint8_t stepIdx = seq_stepIndex[frontParser_activeTrack];'),
    'chase-stale': ('seq', '(t && t->current.timeline==step && t->current.source<NUM_STEPS)', '(t && t->current.source<NUM_STEPS)'),
    'blink-twice': ('led', '			if((led_blinkingLeds & (1<<i)) && led_blinkLedNumber[i]==ledNr) return;\n', ''),
    'no-undo': ('button', '	menu_activeBar = buttonHandler_barBefore;\n', ''),
    'no-release': ('button', '			buttonHandler_barHeld &= (uint8_t)~1u; // 0.2.92\n', ''),
    'no-jump': ('button', '		if(step != 255) menu_activeBar = step/16;\n', ''),
    'perf-steady': ('button', '    led_setMode2(SELECT_MODE_PATTERN); // 0.2.92 perf blinks\n', '    led_setMode2(SELECT_MODE_PERF);\n'),
}

src = load()
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        m = dict(src)
        assert m[key].count(old) == 1, name
        m[key] = m[key].replace(old, new)
        hit = bool(contract(m)) or run(harness(m))[0] != 0
        caught += hit
        print(name, 'caught' if hit else 'MISSED')
    print(f'{caught}/{len(MUTATIONS)} mutations caught')
    sys.exit(0 if caught == len(MUTATIONS) else 1)

found = contract(src)
for f in found:
    print('FAIL', f)
if found:
    sys.exit(1)
code, text = run(harness(src))
print(text.strip().splitlines()[-1] if text.strip() else text)
if code:
    print(text)
    sys.exit(1)
