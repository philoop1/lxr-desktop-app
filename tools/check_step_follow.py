"""0.2.89: the step edit selection follows the sequencer.

When the sequencer moves to the next pattern by itself (pattern link loop,
song, pattern end), the shown pattern follows and the selected steps stay
selected on the same voice in the new pattern. A pattern, voice or page the
user picks still clears it. Runs the production StepSelection.c selection
functions on the host; --mutate shows the checks bite."""
from pathlib import Path
import os, re, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root / 'build/step-follow'
out.mkdir(parents=True, exist_ok=True)
SEL = root / 'Core/Src/menu/StepSelection.c'
MENU = root / 'Core/Src/menu/menu.c'
SEQ = root / 'Core/Src/Soundengine/Sequencer/sequencer.c'


def load():
    return {k: p.read_text(encoding='latin-1').replace('\r\n', '\n')
            for k, p in (('sel', SEL), ('menu', MENU), ('seq', SEQ))}


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
    if s['seq'].count('menu_followPattern(seq_activePattern);') != 3:
        p.append('a sequencer pattern change still clears the selection')
    if 'menu_setShownPattern(seq_activePattern)' in s['seq']:
        p.append('the sequencer still uses the clearing menu_setShownPattern')
    follow = body(s['menu'], 'void menu_followPattern(uint8_t patternNr)')
    if 'stepEdit_follow(patternNr);' not in follow or 'stepEdit_clear' in follow:
        p.append('menu_followPattern does not move the selection')
    if 'if(patternNr!=menu_shownPattern)stepEdit_clear();' not in body(s['menu'], 'void menu_setShownPattern(uint8_t patternNr)'):
        p.append('a pattern the user picks must still clear the selection')
    return p


def harness(s):
    sel = s['sel']
    parts = [re.search(r'static uint64_t selection;\nstatic uint16_t held;\nstatic uint8_t selectedPattern,selectedVoice;\n', sel).group(0)]
    for sig in ('void stepEdit_clear(void)', 'void stepEdit_follow(uint8_t pattern)', 'uint64_t stepEdit_mask(uint8_t pattern,uint8_t voice)',
                'uint8_t stepEdit_press(uint8_t pattern,uint8_t voice,uint8_t key,uint8_t step)', 'void stepEdit_release(uint8_t key)',
                'uint8_t stepEdit_transpose(uint8_t pattern,uint8_t voice,int8_t semitones)'):
        parts.append(body(sel, sig))
    return r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#define __attribute__(x)
typedef struct {uint8_t note;} Step;
struct {Step seq_subStepPattern[64][7][64];} seq_patternSet;
''' + '\n'.join(parts) + r'''
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
int main(void){
 /* select steps 1, 5 and 9 of voice 2 in pattern 3 */
 stepEdit_press(3,2,0,1);stepEdit_press(3,2,4,5);stepEdit_press(3,2,8,9);
 stepEdit_release(0);stepEdit_release(4);stepEdit_release(8);
 const uint64_t want=(1ull<<1)|(1ull<<5)|(1ull<<9);
 check(stepEdit_mask(3,2)==want,"selection made");
 /* link loop 3 -> 4 -> 5 -> 3 */
 for(int round=0;round<3;round++)for(int p=4;p<=6;p++){
  const uint8_t pat=(uint8_t)(p==6?3:p);stepEdit_follow(pat);
  check(stepEdit_mask(pat,2)==want,"selection follows the playing pattern");
  for(uint8_t q=0;q<64;q++)if(q!=pat)check(stepEdit_mask(q,2)==0,"only the shown pattern is selected");
  check(stepEdit_mask(pat,1)==0,"other voices stay unselected");}
 /* a new press after following starts a new selection in that pattern */
 stepEdit_follow(5);stepEdit_press(5,2,2,2);stepEdit_release(2);check(stepEdit_mask(5,2)==(1ull<<2),"new selection in the followed pattern");
 stepEdit_follow(200);check(stepEdit_mask(5,2)==(1ull<<2),"invalid pattern ignored");
 stepEdit_clear();stepEdit_follow(6);check(stepEdit_mask(6,2)==0,"nothing to follow after a clear");
 /* 0.2.96 octave keys on nte move the selected steps */
 stepEdit_clear();check(stepEdit_transpose(4,1,12)==0,"no selection: nothing moves");
 for(int i=0;i<64;i++)seq_patternSet.seq_subStepPattern[4][1][i].note=60;seq_patternSet.seq_subStepPattern[4][1][9].note=120;seq_patternSet.seq_subStepPattern[4][1][3].note=5;
 stepEdit_press(4,1,0,3);stepEdit_press(4,1,1,9);stepEdit_press(4,1,2,20);stepEdit_release(0);stepEdit_release(1);stepEdit_release(2);
 check(stepEdit_transpose(4,1,12)==18&&seq_patternSet.seq_subStepPattern[4][1][20].note==72,"octave up, first selected note returned");
 check(seq_patternSet.seq_subStepPattern[4][1][9].note==127&&seq_patternSet.seq_subStepPattern[4][1][4].note==60,"capped at 127, other steps stay");
 stepEdit_transpose(4,1,-12);stepEdit_transpose(4,1,-12);check(seq_patternSet.seq_subStepPattern[4][1][3].note==0&&seq_patternSet.seq_subStepPattern[4][1][20].note==48,"octave down, floor 0");
 check(seq_patternSet.seq_subStepPattern[4][2][20].note==0,"other voice untouched");
 printf("STEP FOLLOW PASS %u assertions\n",checks);return 0;}
'''


def run(code):
    (out / 'follow.c').write_text(code, encoding='latin-1')
    if os.name == 'nt':
        vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
        r = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:follow.exe follow.c && follow.exe',
                           shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    else:
        r = subprocess.run('cc -o follow follow.c && ./follow', shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    return r.returncode, r.stdout + r.stderr


MUTATIONS = {
    'follow-noop': ('sel', 'void stepEdit_follow(uint8_t pattern) { if(pattern<64)selectedPattern=pattern; }',
                    'void stepEdit_follow(uint8_t pattern) { (void)pattern; }'),
    'follow-clears': ('sel', 'void stepEdit_follow(uint8_t pattern) { if(pattern<64)selectedPattern=pattern; }',
                      'void stepEdit_follow(uint8_t pattern) { if(pattern<64)selectedPattern=pattern; selection=0; }'),
    'seq-clears': ('seq', 'menu_followPattern(seq_activePattern);', 'menu_setShownPattern(seq_activePattern);'),
    'transpose-all': ('sel', '    for(uint8_t i=0;i<64;i++)if(mask&((uint64_t)1u<<i)) {\n        Step *step=&seq_patternSet.seq_subStepPattern[pattern][voice][i];\n        int16_t', '    for(uint8_t i=0;i<64;i++)if(mask|1) {\n        Step *step=&seq_patternSet.seq_subStepPattern[pattern][voice][i];\n        int16_t'),
    'no-cap': ('sel', '        if(note<0)note=0; else if(note>127)note=127;\n', ''),
    'manual-keeps': ('menu', 'if(patternNr!=menu_shownPattern)stepEdit_clear();', ''),
}

src = load()
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        m = dict(src)
        assert old in m[key], name
        m[key] = m[key].replace(old, new, 1)
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
