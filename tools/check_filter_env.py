"""0.2.93 filter envelope and accent of every voice filter.

Filter page 2nd screen of voices 1-3, snare, cymbal and hihat: env (-63..+63,
up to 6 octaves), fdc (0 = amp EG, 1..127 = own decay 10 ms .. 2 s) and acc
(accent strength), kit block FEN1 (env 1-3 stay in AEF1). Step page acc marks
accent steps on every track (pattern block ACC1): louder, a filter sweep that
builds up over accents in a row, and a short own decay. Runs the production
FilterEnv, accent bit and ACC1 storage code on the host plus source
contracts; --mutate shows the checks bite."""
from pathlib import Path
import os, re, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root / 'build/filter-env'
out.mkdir(parents=True, exist_ok=True)
FILES = {
    'fenv': 'Core/Src/Soundengine/DSPAudio/FilterEnv.c',
    'fenvh': 'Core/Inc/Soundengine/DSPAudio/FilterEnv.h',
    'drum': 'Core/Src/Soundengine/DSPAudio/DrumVoice.c',
    'snare': 'Core/Src/Soundengine/DSPAudio/Snare.c',
    'cym': 'Core/Src/Soundengine/DSPAudio/CymbalVoice.c',
    'hat': 'Core/Src/Soundengine/DSPAudio/HiHat.c',
    'midi': 'Core/Src/Soundengine/MIDI/MidiParser.c',
    'vc': 'Core/Src/Soundengine/MIDI/MidiVoiceControl.c',
    'seq': 'Core/Src/Soundengine/Sequencer/sequencer.c',
    'pm': 'Core/Src/Preset/presetManager.c',
    'menu': 'Core/Src/menu/menu.c',
    'pages': 'Core/Inc/menu/menuPages.h',
    'params': 'Core/Inc/Parameters.h',
    'led': 'Core/Src/ledHandler.c',
    'button': 'Core/Src/buttonHandler.c',
    'cmake': 'Core/CMakeLists.txt',
    'mtext': 'Core/Inc/menu/MenuText.h',
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


def define(src, name):
    return re.search(r'^#define ' + name + r'\b.*$', src, re.M).group(0) + '\n'


def contract(s):
    p = []
    hooks = (('drum', 'if(fenv_on[voiceNr]) fenv_tick(voiceNr, voiceArray[voiceNr].ampFilterInput);', 'slopeEg2_calc(&voiceArray[voiceNr].oscVolEg)'),
             ('snare', 'if(fenv_on[3]) fenv_tick(3, snareVoice.egValueOscVol);', 'snareVoice.egValueOscVol = slopeEg2_calc(&snareVoice.oscVolEg);'),
             ('cym', 'if(fenv_on[4]) fenv_tick(4, cymbalVoice.egValueOscVol);', 'cymbalVoice.egValueOscVol = slopeEg2_calc(&cymbalVoice.oscVolEg);'),
             ('hat', 'if(fenv_on[5]) fenv_tick(5, hatVoice.egValueOscVol);', 'hatVoice.egValueOscVol = slopeEg2_calc(&hatVoice.oscVolEg);'))
    for key, hook, after in hooks:
        src = s[key]
        if hook not in src or after not in src or src.index(hook) < src.index(after):
            p.append(f'{key}: the filter env does not run after the amp EG')
    if 'fenv_init();' not in body(s['drum'], 'void initDrumVoice()'):
        p.append('fenv_init is not called at start')
    for sig in re.findall(r'^(?:\w+ )+?(fenv_\w+)\(', s['fenvh'], re.M):
        if not re.search(r'__attribute__\(\(noinline\)\) \w+ ' + sig + r'\(', s['fenv']):
            p.append(f'{sig} must stay in flash (ITCM is full)')
    for slot in ('(uint8_t)(msg.data1-FILTER_FREQ_DRUM1)', '3', '4', '5'):
        if f'fenv_setBase({slot},valueShaperF2F(f,FILTER_SHAPER));' not in s['midi']:
            p.append(f'filter cutoff {slot} does not become the env base')
    for direct in ('SVF_directSetFilterValue(&cymbalVoice.filter,valueShaperF2F', 'SVF_directSetFilterValue(&hatVoice.filter,valueShaperF2F',
                   'SVF_directSetFilterValue(&voiceArray[msg.data1-FILTER_FREQ_DRUM1]'):
        if direct in s['midi']:
            p.append('a cutoff still bypasses the env base')
    vt = body(s['vc'], 'void voiceControl_trigger')
    if 'fenv_trigger(voice,vel);' not in vt or vt.index('fenv_trigger(voice,vel);') < vt.index('HiHat_trigger(vel,voice-5,soundNote);'):
        p.append('the filter env must restart after the voice decided on a slide')
    dt = body(s['drum'], 'void Drum_trigger(const uint8_t voiceNr, const uint8_t vol, const uint8_t note)')
    if 'if(legato) fenv_slide(voiceNr);' not in dt:
        p.append('a legato slide restarts the filter env')
    trig = s['seq'][s['seq'].index('/* 0.2.93 an accent step'):]
    trig = trig[:trig.index('voiceControl_noteOnNoEchoWithMod(voiceNr,note,vol,modVelocity);')]
    for v in ('modVelocity=fenv_accentVelocity(voiceNr,accent,modVelocity);', 'vol=fenv_accentVelocity(voiceNr,accent,vol);',
              'seq_triggerSourceStep[voiceNr]!=255 ? seq_triggerSourceStep[voiceNr] : seq_stepIndex[voiceNr]'):
        if v not in trig:
            p.append(f'the trigger misses {v}')
    seq = s['seq']
    for what, sig in (('clear', 'void seq_clearTrack(uint8_t trackNr, uint8_t pattern)'), ('copy track', 'void seq_copyTrack(uint8_t srcNr, uint8_t dstNr, uint8_t pattern)'),
                      ('copy pattern', 'void seq_copyPattern(uint8_t src, uint8_t dst)'), ('track pattern', 'void seq_copyTrackPattern(uint8_t track,uint8_t srcPattern,uint8_t dstPattern)'),
                      ('backup', 'void seq_copyPatternToBackupBuffer(uint8_t patternNr)'), ('restore', 'void seq_copyBackupBufferToPattern(uint8_t patternNr)')):
        if 'accent' not in body(seq, sig + '\n{'):
            p.append(f'{what} forgets accent')
    if 'seq_setAccent(pattern,track,dst,seq_getAccent(pattern,track,src));' not in seq or 'seq_setAccent(dp,track,ds,seq_getAccent(sp,track,ss));' not in seq:
        p.append('step copies forget accent')
    m = s['menu']
    if 'i!=PAR_STEP_ACCENT' not in body(m, 'void menu_sendAllGlobals()'):
        p.append('a global resend would set accent on selected steps')
    cur = body(m, 'uint8_t menu_isSlideCursor(void)')
    if 'if(mode==2) return 2;' not in cur or 'return mode==1 && menu_getActiveVoice()<SLIDE_TRACKS;' not in cur:
        p.append('the 303 field does not pick sld/acc for the step keys')
    if 'PAR_STEP_SLIDE) return 0;' in cur or 'menuIndex' in cur:
        p.append('the 303 view only shows with the cursor on the field (0.2.98: the value counts)')
    par303 = m[m.index('	if(paramNr==PAR_STEP_SLIDE) {'):]
    par303 = par303[:par303.index('		return;')]
    if 'seq_setSlide' in par303 or 'seq_setAccent' in par303 or 'value = before==0 ? 2 : 0;' not in par303        or 'const uint8_t before=last303;' not in par303 or 'last303=value;' not in par303:
        p.append('the 303 field must only pick the mode (tracks 4-7 skip sld)')
    if '{"303"}' not in s['mtext'] or 'step303Names[][4]={{3},{"off"},{"sld"},{"acc"}}' not in s['mtext']:
        p.append('the 303 field misses its names')
    bt = s['button']
    tog = bt[bt.index('if(menu_isSlideCursor()) {'):bt.index('preset_touchTimer(PRESET_PAT_TIMER);', bt.index('if(menu_isSlideCursor()) {'))]
    if 'activeParameters[PAR_STEP_SLIDE]' in tog:
        p.append('a step key overwrites the 303 mode')
    if 'if(menu_noteOctave(12)) break;' not in bt or 'if(menu_noteOctave(-12)) break;' not in bt or bt.index('if(menu_noteOctave(12)) break;') > bt.index('if(buttonHandler_barChord(1u)) break;'):
        p.append('the bar buttons do not move the octave on nte')
    oc = body(m, 'uint8_t menu_noteOctave(int8_t semitones)')
    if '!=PAR_STEP_NOTE)return 0;' not in oc or 'stepEdit_transpose(menu_getViewedPattern(),menu_getActiveVoice(),semitones)' not in oc:
        p.append('octave keys work outside nte or on the wrong steps')
    if 'if(buttonHandler_getCopy() || buttonHandler_getShift())return 0;' not in oc or oc.index('buttonHandler_getCopy()') > oc.index('stepEdit_transpose('):
        p.append('COPY/SHIFT + bar on nte move the octave instead of doubling the bar')
    if 'fenv_extraIndex((uint8_t)(paramNr-PAR_AEF_AMT4),&kind,&slot);' not in m:
        p.append('env/fdc/acc do not reach the filter env')
    pg = s['pages']
    if pg.count('TEXT_AEF_AMT,TEXT_FENV_DECAY,TEXT_ACC_AMT,TEXT_EMPTY') != 7:
        p.append('a filter page misses env/fdc/acc')
    for v in ('1', '2', '3', '4', '5'):
        if f'PAR_AEF_AMT{v},PAR_FDC{v},PAR_ACC_AMT{v},PAR_NONE' not in pg:
            p.append(f'filter page {v} misses env/fdc/acc')
    if pg.count('PAR_AEF_AMT6,PAR_FDC6,PAR_ACC_AMT6,PAR_NONE') != 2:
        p.append('a hihat filter page misses env/fdc/acc')
    if 'PAR_STEP_ACCENT' in pg or 'TEXT_STEP_ACCENT' in pg:
        p.append('the old acc field is still on the step page')
    par = s['params']
    blk = par[par.index('PAR_AEF_AMT4'):par.index('PAR_STEP_ACCENT')]
    names = re.findall(r'PAR_\w+', blk)
    want = ['PAR_AEF_AMT4', 'PAR_AEF_AMT5', 'PAR_AEF_AMT6'] + [f'PAR_FDC{i}' for i in range(1, 7)] + [f'PAR_ACC_AMT{i}' for i in range(1, 7)]
    if names != want:
        p.append('PAR_AEF_AMT4..PAR_ACC_AMT6 are not in kit order')
    fxk = bt[bt.index('case SEQ_FX:'):]
    fxk = fxk[:fxk.index('break;')]
    if 'mixer_audioRouting[voice<6 ? voice : 5]' not in fxk or '(uint8_t)(routing-MIXER_ROUTING_INSERT_FIRST+1u) : 0;' not in fxk or fxk.index('activeParameters[PAR_FX_PAGE] =') > fxk.index('menu_switchSubPage('):
        p.append('SHIFT+FX does not open the insert of the active voice (0.2.97)')
    blink = re.search(r'#define NUM_OF_BLINKABLE_LEDS (\d+)', s['led'])
    if not blink or not 17 <= int(blink.group(1)) <= 32 or 'volatile uint32_t led_blinkingLeds;' not in s['led'] or '(1<<i)' in s['led'].split('void led_clearAllBlinkLeds()')[1].split('void led_tickHandler()')[0]:
        p.append('a selection of 16 steps cannot blink (0.2.97 blink slots)')
    if 'seq_getAccent(patternNr,trackNr,step)' not in body(s['led'], 'void led_updateSeqLeds()'):
        p.append('the step LEDs do not show the accent steps')
    if 'seq_setAccent(pattern,voice,step,accent);' not in s['button']:
        p.append('step keys do not toggle accent')
    pm = s['pm']
    if pm.count('preset_readAccent(patternNr);') != 2 or pm.count('=preset_writeAccent(') != 2 or pm.count('+ preset_accentBytes(presetNr)') != 2:
        p.append('ACC1 missing in one of the pattern paths')
    if s['cmake'].count('Src/Soundengine/DSPAudio/FilterEnv.c') != 2:
        p.append('FilterEnv.c is not built')
    return p


def harness(s):
    fh, f = s['fenvh'], s['fenv']
    code = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#define __attribute__(x)
#define OUTPUT_DMA_SIZE 64
#define REAL_FS 44140.f
typedef struct {float f,q;} ResonantFilter;
typedef struct {ResonantFilter filter;} Voice;
Voice voiceArray[3],snareVoice,cymbalVoice,hatVoice;
static void SVF_directSetFilterValue(ResonantFilter*r,float v){r->f=v;}
'''
    code += fh[fh.index('#define FENV_SLOTS'):fh.index('extern FilterEnv')]
    code += f[f.index('FilterEnv fenv[FENV_SLOTS];'):]
    code += r'''
#define NUM_PATTERN 64
#define NUM_STEPS 64
#define NUM_TRACKS 7
struct {uint64_t accent[NUM_PATTERN][NUM_TRACKS];} seq_patternSet;
'''
    seq = s['seq']
    code += body(seq, '__attribute__((noinline)) uint8_t seq_getAccent') + '\n' + body(seq, '__attribute__((noinline)) void seq_setAccent') + '\n'
    pm = s['pm']
    code += r'''
typedef unsigned UINT; typedef unsigned FSIZE_t; typedef int FRESULT; typedef int FIL;
#define FR_OK 0
#define FR_DISK_ERR 1
FIL SDFile; uint8_t disk[700]; unsigned size,cursor;
static int f_write(FIL*f,const void*d,unsigned n,UINT*w){(void)f;memcpy(disk+cursor,d,n);cursor+=n;if(cursor>size)size=cursor;*w=n;return FR_OK;}
static int f_read(FIL*f,void*d,unsigned n,UINT*r){(void)f;*r=cursor+n>size?size-cursor:n;memcpy(d,disk+cursor,*r);cursor+=*r;return FR_OK;}
static FSIZE_t f_tell(FIL*f){(void)f;return cursor;}
static int f_lseek(FIL*f,FSIZE_t p){(void)f;cursor=p;return FR_OK;}
'''
    code += body(pm, 'static FRESULT preset_lockWrite(const void *data,UINT size)') + '\n'
    code += body(pm, 'static uint8_t preset_lockRead(void *data,UINT size)') + '\n'
    code += define(pm, 'ACCENT_BLOCK_BYTES')
    for sig in ('static FSIZE_t preset_accentBytes(uint8_t pattern)', 'static FRESULT preset_writeAccent(uint8_t pattern)',
                'static void preset_readAccent(uint8_t pattern)'):
        code += body(pm, sig) + '\n'
    code += r'''
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
static float cut(int slot){return slot<3?voiceArray[slot].filter.f:slot==3?snareVoice.filter.f:slot==4?cymbalVoice.filter.f:hatVoice.filter.f;}
static int near(float a,float b){return fabsf(a-b)<=fabsf(b)*1e-3f+1e-6f;}
int main(void){
 fenv_init();
 for(int s=0;s<FENV_SLOTS;s++)check(!fenv_on[s]&&fenv_getParam(FENV_AMOUNT,s)==FENV_CENTER&&fenv_getParam(FENV_DECAY,s)==0&&fenv_getParam(FENV_ACCENT,s)==FENV_ACC_DEFAULT,"defaults: env off");
 /* fdc 0: the amp EG drives the cutoff, both directions */
 fenv_setBase(0,0.3f);check(cut(0)==0.3f,"base reaches the filter");
 fenv_setParam(FENV_AMOUNT,0,127);check(fenv_on[0]&&near(fenv[0].amount,FENV_OCTAVES),"+63 = 6 octaves, env on");
 fenv_setBase(0,0.01f);fenv_tick(0,0.5f);check(near(cut(0),0.08f),"half EG = half the octaves");
 fenv_setBase(0,0.1f);fenv_tick(0,1.f);check(cut(0)==1.f,"opens no further than the top");
 fenv_setBase(0,0.01f);fenv_tick(0,0.f);check(near(cut(0),0.01f),"EG 0 = base");
 fenv_setParam(FENV_AMOUNT,1,1);fenv_setBase(1,0.3f);fenv_tick(1,0.5f);check(near(cut(1),0.0375f),"-63 closes");
 fenv_setBase(1,0.01f);fenv_tick(1,1.f);check(cut(1)==FENV_MIN_F,"closes no further than the floor");
 fenv_setParam(FENV_AMOUNT,1,0);check(fenv_getParam(FENV_AMOUNT,1)==1,"0 shows -63 like 1");
 fenv_setBase(2,0.f);fenv_setParam(FENV_AMOUNT,2,96);fenv_tick(2,1.f);check(cut(2)>FENV_MIN_F,"a closed cutoff still opens");
 fenv_tick(0,1.f);fenv_setParam(FENV_AMOUNT,0,FENV_CENTER);check(!fenv_on[0]&&near(cut(0),0.01f),"env back to 0 restores the cutoff");
 /* own decay: restarts on each hit, ignores the amp EG */
 fenv_setParam(FENV_AMOUNT,3,127);fenv_setParam(FENV_DECAY,3,127);fenv_setBase(3,0.02f);fenv_trigger(3,100);
 fenv_tick(3,0.f);check(cut(3)==1.f&&snareVoice.filter.f==1.f&&fenv[3].att==1.f,"snare: no attack, own decay starts open, amp EG ignored");
 fenv_setParam(FENV_AMOUNT,0,127);fenv_setParam(FENV_DECAY,0,127);fenv_setBase(0,0.02f);fenv_trigger(0,100);
 fenv_tick(0,0.f);check(cut(0)<0.5f&&cut(0)>0.02f,"voice 1: short attack, not a jump");
 fenv_tick(0,0.f);fenv_tick(0,0.f);check(cut(0)==1.f&&fenv[0].att==1.f,"voice 1: open after ~3 ms");
 fenv_setParam(FENV_DECAY,0,0);fenv_setParam(FENV_AMOUNT,0,FENV_CENTER);fenv_setBase(0,0.01f);
 {int n=3;while(fenv[3].env>0.05f&&n<100000){fenv_tick(3,1.f);n++;}const float want=2.f*REAL_FS/OUTPUT_DMA_SIZE;check(fabsf(n-want)<=2.f+want*0.02f,"fdc 127 = 2 s");}
 fenv_trigger(3,100);check(fenv[3].env==1.f,"a hit restarts the own decay");
 fenv_setParam(FENV_DECAY,3,1);{int n=0;fenv_trigger(3,100);while(fenv[3].env>0.05f&&n<100000){fenv_tick(3,0.f);n++;}const float want=0.0104f*REAL_FS/OUTPUT_DMA_SIZE;check(fabsf(n-want)<=1.5f,"fdc 1 = 10 ms");}
 fenv_setParam(FENV_AMOUNT,4,1);fenv_setBase(4,0.5f);fenv_tick(4,0.25f);check(near(cymbalVoice.filter.f,0.17678f)&&voiceArray[0].filter.f==0.01f,"cymbal slot 4 alone");
 check(fenv_slot(5)==5&&fenv_slot(6)==5&&fenv_slot(3)==3,"closed and open hat share slot 5");
 /* accent: louder */
 fenv_setParam(FENV_ACCENT,0,127);check(fenv_accentVelocity(0,0,100)==100&&!fenv[0].accentNext,"no accent: velocity as is");
 check(fenv_accentVelocity(0,1,80)==120&&fenv[0].accentNext,"acc 127 = +50 %");check(fenv_accentVelocity(0,1,100)==127,"capped at 127");
 fenv_setParam(FENV_ACCENT,1,0);check(fenv_accentVelocity(1,1,80)==80&&!fenv[1].accentNext,"acc 0: no accent");
 check(fenv_accentVelocity(7,1,80)==80,"voice range");
 /* accent: filter sweep even with env 0, back to the base, idle */
 fenv_setParam(FENV_AMOUNT,0,FENV_CENTER);fenv_setBase(0,0.01f);fenv_accentVelocity(0,1,80);fenv_trigger(0,100);
 check(fenv_on[0]&&fenv[0].accentNote&&!fenv[0].accentNext,"an accented hit switches the env on");
 float peak=0;for(int k=0;k<200;k++){fenv_tick(0,0.f);if(cut(0)>peak)peak=cut(0);}
 check(peak>0.02f,"accent opens the filter");
 for(int k=0;k<5000&&fenv_on[0];k++)fenv_tick(0,0.f);check(!fenv_on[0]&&cut(0)==0.01f,"sweep leaks away, env idles at the base");
 /* accents in a row build up */
 float peak2=0;for(int hit=0;hit<4;hit++){fenv_accentVelocity(0,1,80);fenv_trigger(0,100);for(int k=0;k<86;k++){fenv_tick(0,0.f);if(cut(0)>peak2)peak2=cut(0);}}
 check(peak2>peak*1.3f,"accents in a row build up");
 for(int k=0;k<20000&&fenv_on[0];k++)fenv_tick(0,0.f);
 for(int k=0;k<3000;k++){fenv_accentVelocity(0,1,80);fenv_trigger(0,100);fenv_tick(0,0.f);}check(fenv[0].sweep<=2.f*FENV_ACC_OCTAVES+1e-4f,"sweep limited");
 /* a plain hit after an accent is not accented; live notes never are */
 fenv_accentVelocity(0,0,80);fenv_trigger(0,100);check(!fenv[0].accentNote,"plain step not accented");
 fenv_accentVelocity(0,1,80);fenv_trigger(0,100);fenv_trigger(0,100);check(!fenv[0].accentNote,"the accent mark is used once");
 /* accented note runs the own decay short */
 fenv_setParam(FENV_AMOUNT,2,127);fenv_setParam(FENV_DECAY,2,127);fenv_trigger(2,100);for(int k=0;k<100;k++)fenv_tick(2,0.f);{const float plain=fenv[2].env;
  fenv_accentVelocity(2,1,80);fenv_trigger(2,100);for(int k=0;k<100;k++)fenv_tick(2,0.f);check(fenv[2].env<plain*0.5f,"accent shortens the own decay");}
 /* a short fdc stays short on an accent */
 fenv_setParam(FENV_DECAY,2,40);fenv_trigger(2,100);for(int k=0;k<20;k++)fenv_tick(2,0.f);{const float plain=fenv[2].env;
  fenv_accentVelocity(2,1,80);fenv_trigger(2,100);for(int k=0;k<20;k++)fenv_tick(2,0.f);check(fenv[2].env==plain,"accent never lengthens a short fdc");}
 /* the sweep of one accent is gone after about 0.5 s */
 fenv_setParam(FENV_DECAY,2,0);fenv_setParam(FENV_AMOUNT,2,FENV_CENTER);for(int k=0;k<20000&&fenv_on[2];k++)fenv_tick(2,0.f);
 fenv_setParam(FENV_ACCENT,2,127);fenv_accentVelocity(2,1,80);fenv_trigger(2,100);{float top=0;int n=0;
  for(;n<20000&&fenv_on[2];n++){fenv_tick(2,0.f);if(fenv[2].sweep>top)top=fenv[2].sweep;else if(fenv[2].sweep<top*0.05f)break;}
  check(n*OUTPUT_DMA_SIZE/REAL_FS<0.7f,"single accent sweep short");}
 /* params, index */
 fenv_setParam(FENV_DECAY,6,10);fenv_setParam(3,0,10);check(fenv_getParam(FENV_DECAY,6)==0&&fenv_getParam(3,0)==0,"param range");
 fenv_setParam(FENV_ACCENT,0,200);check(fenv_getParam(FENV_ACCENT,0)==127,"value clamps");
 {uint8_t k,sl;fenv_extraIndex(0,&k,&sl);check(k==FENV_AMOUNT&&sl==3,"index 0 = env 4");fenv_extraIndex(3,&k,&sl);check(k==FENV_DECAY&&sl==0,"index 3 = fdc 1");
  fenv_extraIndex(14,&k,&sl);check(k==FENV_ACCENT&&sl==5,"index 14 = acc 6");}
 /* accent bits of every track */
 seq_setAccent(5,6,63,1);seq_setAccent(5,6,0,1);check(seq_getAccent(5,6,63)&&seq_getAccent(5,6,0)&&!seq_getAccent(5,6,1)&&!seq_getAccent(5,5,0),"accent bits, track 7 too");
 seq_setAccent(5,6,0,0);check(!seq_getAccent(5,6,0),"accent off");seq_setAccent(5,7,1,1);seq_setAccent(64,0,1,1);check(!seq_getAccent(64,0,1),"range");
 /* ACC1 */
 memset(&seq_patternSet,0,sizeof seq_patternSet);size=cursor=0;check(preset_writeAccent(7)==FR_OK&&size==0&&preset_accentBytes(7)==0,"no accent, old layout");
 seq_patternSet.accent[7][0]=0x8000000000000001ull;seq_patternSet.accent[7][6]=0x0123456789abcdefull;
 size=cursor=0;preset_writeAccent(7);check(size==ACCENT_BLOCK_BYTES&&preset_accentBytes(7)==size&&!memcmp(disk,"ACC1",4),"ACC1 written");
 cursor=0;preset_readAccent(9);check(seq_patternSet.accent[9][0]==0x8000000000000001ull&&seq_patternSet.accent[9][3]==0&&seq_patternSet.accent[9][6]==0x0123456789abcdefull&&cursor==size,"ACC1 roundtrip");
 seq_patternSet.accent[9][0]=5;size=cursor=0;preset_readAccent(9);check(seq_patternSet.accent[9][0]==0,"old pattern file: no accent");
 memcpy(disk,"PLK1xxxx",8);size=8;cursor=0;seq_patternSet.accent[9][0]=5;preset_readAccent(9);check(cursor==0&&seq_patternSet.accent[9][0]==0,"next block untouched");
 memcpy(disk,"ACC1abc",7);size=7;cursor=0;preset_readAccent(9);check(cursor==0&&seq_patternSet.accent[9][6]==0,"short ACC1 ignored");
 /* 0.2.95 a legato slide keeps the env running, the accent only charges the sweep */
 fenv_setParam(FENV_AMOUNT,1,127);fenv_setParam(FENV_DECAY,1,100);fenv_setParam(FENV_ACCENT,1,127);fenv_trigger(1,100);for(int k=0;k<50;k++)fenv_tick(1,0.f);
 {const float env=fenv[1].env;fenv_slide(1);fenv_trigger(1,100);check(fenv[1].env==env&&!fenv[1].slide,"slide: env keeps running");
  check(fenv[1].att==1.f,"slide keeps the attack done");
  fenv_slide(1);fenv_accentVelocity(1,1,80);fenv_trigger(1,100);check(fenv[1].env==env&&fenv[1].accEnv==1.f&&!fenv[1].accentNote,"accented slide charges the sweep only");
  fenv_trigger(1,100);check(fenv[1].env==1.f,"the next normal hit restarts");
  fenv_slide(1);fenv_trigger(1,0);fenv_trigger(1,100);check(fenv[1].env==1.f,"a zero hit drops the slide mark");
  fenv_slide(3);check(!fenv[3].slide,"only voices 1-3 slide");}
 /* resonance shapes the sweep: low = short, high = long */
 {int n[2];for(int r=0;r<2;r++){fenv_setParam(FENV_AMOUNT,2,FENV_CENTER);fenv_setParam(FENV_DECAY,2,0);for(int k=0;k<20000&&fenv_on[2];k++)fenv_tick(2,0.f);
   voiceArray[2].filter.q=r?0.1f:1.f;fenv_accentVelocity(2,1,80);fenv_trigger(2,100);float top=0;n[r]=0;
   for(;n[r]<20000;n[r]++){fenv_tick(2,0.f);if(fenv[2].sweep>top)top=fenv[2].sweep;else if(fenv[2].sweep<top*0.05f)break;}}
  const float lo=n[0]*OUTPUT_DMA_SIZE/REAL_FS,hi=n[1]*OUTPUT_DMA_SIZE/REAL_FS;
  check(lo<0.25f&&hi>0.4f&&hi<0.8f,"resonance 0 spiky, high resonance long");voiceArray[2].filter.q=0;}
 /* the sweep left from earlier accents makes the next accent louder */
 fenv_setParam(FENV_ACCENT,0,127);fenv[0].sweep=0;check(fenv_accentVelocity(0,1,40)==60,"no sweep: +50 %");
 fenv[0].sweep=FENV_ACC_OCTAVES;check(fenv_accentVelocity(0,1,40)==70,"half sweep: +75 %");
 fenv[0].sweep=2.f*FENV_ACC_OCTAVES;check(fenv_accentVelocity(0,1,40)==80&&fenv_accentVelocity(0,1,100)==127,"full sweep: +100 %, capped");
 check(fenv_accentVelocity(0,0,40)==40,"plain step stays");fenv[0].sweep=0;
 printf("FILTER ENV PASS %u assertions\n",checks);return 0;}
'''
    return code


def run(code):
    (out / 'fenv.c').write_text(code, encoding='latin-1')
    if os.name == 'nt':
        vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
        r = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:fenv.exe fenv.c && fenv.exe',
                           shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    else:
        r = subprocess.run('cc -o fenv fenv.c -lm && ./fenv', shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    return r.returncode, r.stdout + r.stderr


MUTATIONS = {
    'unipolar': ('fenv', 'e->amount=(float)((int)value-FENV_CENTER)*(FENV_OCTAVES/63.f);', 'e->amount=(float)value*(FENV_OCTAVES/127.f);'),
    'no-floor': ('fenv', '	if(base<FENV_MIN_F)base=FENV_MIN_F;\n', ''),
    'no-restore': ('fenv', '	SVF_directSetFilterValue(fenv_filter(slot), e->base);\n}', '}'),
    'amp-always': ('fenv', '	if(e->value[FENV_DECAY]) {', '	if(0) {'),
    'no-short-accent': ('fenv', 'e->env*= e->accentNote && fenv_accCoef<e->coef ? fenv_accCoef : e->coef;', 'e->env*= e->coef;'),
    'accent-lengthens': ('fenv', 'e->env*= e->accentNote && fenv_accCoef<e->coef ? fenv_accCoef : e->coef;', 'e->env*= e->accentNote ? fenv_accCoef : e->coef;'),
    'no-leak': ('fenv', '	e->sweep*=e->leak;\n', ''),
    'no-cap': ('fenv', '	if(e->sweep>2.f*FENV_ACC_OCTAVES)e->sweep=2.f*FENV_ACC_OCTAVES;\n', ''),
    'mark-sticks': ('fenv', '	e->accentNext=0;\n', ''),
    'no-loud': ('fenv', 'const float louder=(float)vel+extra+0.5f;', 'const float louder=(float)vel+0.5f;'),
    'wrong-slot': ('fenv', '	case 4: return &cymbalVoice.filter;\n', ''),
    'snare-hook': ('snare', '	if(fenv_on[3]) fenv_tick(3, snareVoice.egValueOscVol); // 0.2.93 filter env\n', ''),
    'hat-direct': ('midi', 'fenv_setBase(5,valueShaperF2F(f,FILTER_SHAPER));', 'SVF_directSetFilterValue(&hatVoice.filter,valueShaperF2F(f,FILTER_SHAPER));'),
    'no-trigger': ('vc', '	fenv_trigger(voice,vel); // 0.2.93 filter env and accent; 0.2.95 after the voice (slide)\n', ''),
    'slide-unmarked': ('drum', '	if(legato) fenv_slide(voiceNr); // 0.2.95 the filter env keeps running\n', ''),
    'slide-restarts': ('fenv', '	if(!slide) {', '	if(1) {'),
    'slide-sticks': ('fenv', '	e->slide=0;\n', ''),
    'reso-ignored': ('fenv', '		float reso=1.f-fenv_filter(slot)->q;', '		float reso=1.f;'),
    'sweep-not-louder': ('fenv', '*(1.f+e->sweep*(1.f/(2.f*FENV_ACC_OCTAVES)))', ''),
    'vol-not-accented': ('seq', '        vol=fenv_accentVelocity(voiceNr,accent,vol);\n', ''),
    'copy-forgets': ('seq', '	memcpy(seq_patternSet.accent[dst], seq_patternSet.accent[src], sizeof(seq_patternSet.accent[dst]));\n', ''),
    'no-rewind': ('pm', '    if(bytes!=4 || memcmp(block,"ACC1",4)) { f_lseek(&SDFile,start); return; }', '    if(bytes!=4 || memcmp(block,"ACC1",4)) return;'),
    'stale-accent': ('pm', '    memset(seq_patternSet.accent[pattern],0,sizeof(seq_patternSet.accent[pattern]));\n', ''),
    'resend': ('menu', ' && i!=PAR_STEP_ACCENT &&', ' &&'),
    'attack-everywhere': ('fenv', '		e->att = slot<3 ? 0.f : 1.f;', '		e->att = 0.f;'),
    'no-attack': ('fenv', '		drive=e->env*e->att;', '		drive=e->env;'),
    'attack-stuck': ('fenv', '			if(e->att>1.f)e->att=1.f;\n', ''),
    'fx-browsed': ('button', '(uint8_t)(routing-MIXER_ROUTING_INSERT_FIRST+1u) : 0;', 'activeParameters[PAR_FX_PAGE];'),
    'before-from-param': ('menu', '		const uint8_t before=last303;', '		const uint8_t before=activeParameters[PAR_STEP_SLIDE];'),
    'few-blinks': ('led', '#define NUM_OF_BLINKABLE_LEDS 24', '#define NUM_OF_BLINKABLE_LEDS 4'),
    'no-acc-cursor': ('menu', '	if(mode==2) return 2;\n', ''),
    'mode-sets-steps': ('menu', '		last303=value;\n		led_updateSeqLeds();', '		last303=value;\n		seq_setSlide(0,0,0,1);\n		led_updateSeqLeds();'),
    'key-overwrites': ('button', '				seq_setSlide(pattern,voice,step,on); // 0.2.96 the 303 field keeps its mode\n', '				seq_setSlide(pattern,voice,step,on); activeParameters[PAR_STEP_SLIDE]=on;\n'),
    'octave-everywhere': ('menu', '!=PAR_STEP_NOTE)return 0;', '==255)return 0;'),
    'octave-on-copy': ('menu', '	if(buttonHandler_getCopy() || buttonHandler_getShift())return 0;\n', ''),
    '303-cursor-only': ('menu', '	if(menu_activePage!=SEQ_PAGE)return 0;\n	/* 0.2.96 the 303 field', '	if(menu_activePage!=SEQ_PAGE)return 0;\n	if((menuIndex & MASK_PARAMETER)!=7)return 0;\n	/* 0.2.96 the 303 field'),
    'no-octave-key': ('button', '			if(menu_noteOctave(-12)) break; // 0.2.96 nte: octave down\n', ''),
    'led-slide-only': ('led', 'showSlide==2 ? seq_getAccent(patternNr,trackNr,step) : ', ''),
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
