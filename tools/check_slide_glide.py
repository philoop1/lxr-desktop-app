"""0.2.90 slide and glide for drum voices 1-3.

Step page sld marks steps of tracks 1-3 (pattern block SLD1). A slide step,
and its flam repeats, glides in from the last note without retriggering the
pitch and amp EG while the voice still sounds. The osc page's 2nd screen sets
per voice gli (off/on/leg) and glt (10 ms .. 1 s), kit block GLD1. Both
oscillators glide. Runs the production glide, slide and storage functions on
the host plus source contracts; --mutate shows the checks bite.

0.2.91 adds aef on the filter page's 2nd screen of voices 1-3: the amp EG
moves the cutoff up or down by up to 6 octaves (kit block AEF1 after GLD1).
0.2.93 moves aef into FilterEnv (tools/check_filter_env.py); here only the
kit storage GLD1 + AEF1 + FEN1 is checked."""
from pathlib import Path
import os, re, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root / 'build/slide-glide'
out.mkdir(parents=True, exist_ok=True)
FILES = {
    'drum': 'Core/Src/Soundengine/DSPAudio/DrumVoice.c',
    'drumh': 'Core/Inc/Soundengine/DSPAudio/DrumVoice.h',
    'seq': 'Core/Src/Soundengine/Sequencer/sequencer.c',
    'pm': 'Core/Src/Preset/presetManager.c',
    'menu': 'Core/Src/menu/menu.c',
    'pages': 'Core/Inc/menu/menuPages.h',
    'led': 'Core/Src/ledHandler.c',
    'button': 'Core/Src/buttonHandler.c',
    'midi': 'Core/Src/Soundengine/MIDI/MidiParser.c',
    'fenv': 'Core/Src/Soundengine/DSPAudio/FilterEnv.c',
    'fenvh': 'Core/Inc/Soundengine/DSPAudio/FilterEnv.h',
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
    trig = body(s['drum'], 'void Drum_trigger(const uint8_t voiceNr, const uint8_t vol, const uint8_t note)')
    if 'const uint8_t legato = drum_glideTrigger(voiceNr, note);' not in trig:
        p.append('the trigger does not ask the glide')
    if 'osc_setBaseNote' in trig:
        p.append('the trigger sets the note past the glide')
    keep = trig[trig.index('if(!legato) {'):]
    for eg in ('DecayEg_trigger(&voiceArray[voiceNr].oscPitchEg);', 'slopeEg2_trigger(&voiceArray[voiceNr].oscVolEg);'):
        if eg not in body(keep, 'if(!legato) {'):
            p.append(f'a slide still runs {eg}')
    if 'if(!legato)\n#ifdef USE_AMP_FILTER' not in trig:
        p.append('a slide resets the oscillator phase')
    asy = body(s['drum'], 'IN_ITCM_RAM void calcDrumVoiceAsync(const uint8_t voiceNr)')
    snap = asy.index('osc.pitchMod += snapVal')
    tick = asy.find('if(drum_glide[voiceNr].log2Ratio != 0.f) drum_glideTick(voiceNr);')
    if tick < snap:
        p.append('the glide does not run after the pitch EG and snap')
    for fn in ('uint8_t drum_glideTrigger', 'void drum_glideTick', 'void Drum_setGlideParameter'):
        if '__attribute__((noinline)) ' + fn not in s['drum']:
            p.append(f'{fn} must stay in flash (ITCM is full)')
    tv = body(s['seq'], 'void seq_triggerVoice(uint8_t voiceNr, uint8_t vol, uint8_t note)')
    i = tv.find('Drum_setSlideNext(voiceNr,seq_getSlide(seq_activePattern,voiceNr,')
    if i < 0 or 'seq_triggerSourceStep[voiceNr]!=255 ? seq_triggerSourceStep[voiceNr] : seq_stepIndex[voiceNr]' not in tv[i:i+200] or i > tv.find('voiceControl_noteOnNoEchoWithMod'):
        p.append('the sequencer does not pass the slide of the source step (flam repeats)')
    for sig, needle in (('void seq_copyPattern(uint8_t src, uint8_t dst)', 'seq_patternSet.slide[dst], seq_patternSet.slide[src]'),
                        ('void seq_copyTrackPattern(', 'seq_patternSet.slide[dstPattern][track]=seq_patternSet.slide[srcPattern][track]'),
                        ('void seq_copyTrack(uint8_t srcNr, uint8_t dstNr, uint8_t pattern)', 'seq_patternSet.slide[pattern][dstNr]'),
                        ('void seq_copyStep(', 'seq_setSlide(pattern,track,dst,seq_getSlide(pattern,track,src))'),
                        ('void seq_clearTrack(uint8_t trackNr, uint8_t pattern)', 'seq_patternSet.slide[pattern][trackNr]=0'),
                        ('void seq_copyPatternToBackupBuffer(uint8_t patternNr)', 'patternBackupBuffer.slide'),
                        ('void seq_copyBackupBufferToPattern(uint8_t patternNr)', 'patternBackupBuffer.slide')):
        if needle not in body(s['seq'], sig):
            p.append(f'{sig} does not carry the slide')
    pm = s['pm']
    if pm.count('preset_readSlide(patternNr);') != 2:
        p.append('a pattern loader does not read SLD1')
    if pm.count('preset_writeSlide(') != 3 or pm.count('preset_slideBytes(presetNr)') != 2:
        p.append('a pattern writer or its size check misses SLD1')
    if 'INS_EXTRA_BYTES + GLD_EXTRA_BYTES' not in body(pm, 'FRESULT preset_saveDrumsetSD(uint8_t presetNr, uint8_t isMorph)'):
        p.append('kit size check misses GLD1')
    if 'INS_EXTRA_BYTES + GLD_EXTRA_BYTES);' not in pm[pm.index('// read padding'):]:
        p.append('old project kit padding misses GLD1')
    for needle, what in (('preset_writeGldExtras(mainGldExtras[presetNr]);', 'kit file write'),
                         ('preset_readGldExtras(mainGldExtras[presetNr]);', 'kit file read'),
                         ('preset_applyGldExtras(mainGldExtras[presetNr]);', 'kit load'),
                         ('preset_captureGldExtras(mainGldExtras[presetNr]);', 'kit store'),
                         ('preset_captureGldExtras(gldExtras);preset_writeGldExtras(gldExtras);', 'live kit write'),
                         ('preset_readGldExtras(gldExtras);preset_applyGldExtras(gldExtras);', 'live kit read')):
        if needle not in pm:
            p.append(f'GLD1 missing in {what}')
    if pm.count('preset_applyGldExtras(mainGldExtras[presetNr]);') != 2 or pm.count('preset_captureGldExtras(mainGldExtras[presetNr]);') != 2:
        p.append('GLD1 missing in one of the RAM kit paths')
    m = s['menu']
    if 'i!=PAR_STEP_SLIDE' not in body(m, 'void menu_sendAllGlobals()'):
        p.append('a global resend would set slide on selected steps')
    if 'Drum_setGlideParameter((uint8_t)(paramNr-PAR_GLIDE_MODE1),value);' not in m:
        p.append('gli/glt do not reach the voice')
    if 'curParmVal==1 && menu_getActiveVoice()>=SLIDE_TRACKS ? "---"' not in m:
        p.append('tracks 4-7 do not show ---')
    if 'if(menu_activePage==SEQ_PAGE)led_updateSeqLeds();' not in body(m, 'static void menu_moveToMenuItem(int8_t inc)\n{'):
        p.append('the LEDs do not switch when the cursor reaches sld')
    for v in '123':
        if f'PAR_PWM_{v},PAR_GLIDE_MODE{v},PAR_GLIDE_TIME{v},' not in s['pages']:
            p.append(f'osc page of voice {v} misses gli/glt')
    if s['pages'].count('TEXT_PWM,TEXT_GLIDE_MODE,TEXT_GLIDE_TIME,') != 3:
        p.append('gli/glt labels missing')
    if 'PAR_STEP_SHIFT,		PAR_STEP_SLIDE,' not in s['pages']:
        p.append('sld does not follow shf')
    if 'if(showSlide) {' not in body(s['led'], 'void led_updateSeqLeds()'):
        p.append('the step LEDs do not show the slide steps')
    if 'if(menu_isSlideCursor()) {' not in s['button'] or 'seq_setSlide(pattern,voice,step,on);' not in s['button']:
        p.append('step keys do not toggle slide on sld')
    if pm.count('uint8_t gldExtras[GLD_KIT_VALUES];') != 2:
        p.append('a live kit buffer is too small for AEF1')
    return p


def harness(s):
    d, pm, seq = s['drum'], s['pm'], s['seq']
    code = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#define __attribute__(x)
#define NUM_DRUM_VOICES 3
#define OUTPUT_DMA_SIZE 64
#define REAL_FS 44140.f
#define EG_STOPPED 0
#define EG_D 2
typedef struct {float freq,pitchMod;uint8_t baseNote;} OscInfo;
typedef struct {uint8_t state;} SlopeEg2;
typedef struct {float f;} ResonantFilter;
typedef struct {OscInfo osc,modOsc;SlopeEg2 oscVolEg;double ampFilterInput;ResonantFilter filter;} DrumVoice;
DrumVoice voiceArray[3];
static void SVF_directSetFilterValue(ResonantFilter*r,float v){r->f=v;}
static void osc_setBaseNote(OscInfo*o,uint8_t n){o->freq=(o==&voiceArray[0].modOsc||o==&voiceArray[1].modOsc||o==&voiceArray[2].modOsc?2.f:1.f)*440.f*powf(2.f,(n-69)/12.f);o->baseNote=n;}
'''
    h = s['drumh']
    code += h[h.index('enum { GLIDE_OFF'):h.index('extern DrumGlide drum_glide')]
    for name in ('GLIDE_DONE', 'GLIDE_MAX_OCT', 'GLIDE_SOUNDING'):
        code += define(d, name)
    code += 'DrumGlide drum_glide[NUM_DRUM_VOICES];\n'
    for sig in ('static float drum_glideCoef(uint8_t time)\n{', '__attribute__((noinline)) void Drum_setGlideParameter',
                '__attribute__((noinline)) uint8_t Drum_getGlideParameter', '__attribute__((noinline)) void Drum_setSlideNext',
                '__attribute__((noinline)) uint8_t drum_glideTrigger', '__attribute__((noinline)) void drum_glideTick'):
        code += body(d, sig) + '\n'
    fh = s['fenvh']
    code += fh[fh.index('#define FENV_SLOTS'):fh.index('typedef struct')]
    code += r'''
static uint8_t fv[FENV_KINDS][FENV_SLOTS];
static void fenv_setParam(uint8_t kind,uint8_t slot,uint8_t v){if(kind>=FENV_KINDS||slot>=FENV_SLOTS)return;if(v>127)v=127;if(kind==FENV_AMOUNT&&!v)v=1;fv[kind][slot]=v;}
static uint8_t fenv_getParam(uint8_t kind,uint8_t slot){return kind<FENV_KINDS&&slot<FENV_SLOTS?fv[kind][slot]:0;}
'''
    code += body(s['fenv'], '__attribute__((noinline)) void fenv_extraIndex') + '\n'
    # sequencer slide bits
    code += r'''
#define NUM_PATTERN 64
#define NUM_STEPS 64
#define SLIDE_TRACKS 3
struct {uint64_t slide[NUM_PATTERN][SLIDE_TRACKS];} seq_patternSet;
'''
    code += body(seq, '__attribute__((noinline)) uint8_t seq_getSlide') + '\n' + body(seq, '__attribute__((noinline)) void seq_setSlide') + '\n'
    # file storage
    code += r'''
typedef unsigned UINT; typedef unsigned FSIZE_t; typedef int FRESULT; typedef int FIL;
#define FR_OK 0
#define FR_DISK_ERR 1
FIL SDFile; uint8_t disk[700]; unsigned size,cursor;
static int f_write(FIL*f,const void*d,unsigned n,UINT*w){(void)f;memcpy(disk+cursor,d,n);cursor+=n;if(cursor>size)size=cursor;*w=n;return FR_OK;}
static int f_read(FIL*f,void*d,unsigned n,UINT*r){(void)f;*r=cursor+n>size?size-cursor:n;memcpy(d,disk+cursor,*r);cursor+=*r;return FR_OK;}
static FSIZE_t f_tell(FIL*f){(void)f;return cursor;}
static int f_lseek(FIL*f,FSIZE_t p){(void)f;cursor=p;return FR_OK;}
uint8_t activeParameters[600];
enum {PAR_GLIDE_MODE1=500,PAR_AEF_AMT1=510,PAR_AEF_AMT4=513};
static void Drum_setGlideParameter(uint8_t index, uint8_t value);
static uint8_t Drum_getGlideParameter(uint8_t index);
'''
    code += body(pm, 'static FRESULT preset_lockWrite(const void *data,UINT size)') + '\n'
    code += body(pm, 'static uint8_t preset_lockRead(void *data,UINT size)') + '\n'
    code += define(pm, 'SLIDE_BLOCK_BYTES') + define(pm, 'AEF_PARAMS') + define(pm, 'AEF_CENTER') + define(pm, 'GLD_KIT_VALUES') + define(pm, 'GLD_EXTRA_BYTES') + define(pm, 'FEN_AT')
    for sig in ('static FSIZE_t preset_slideBytes(uint8_t pattern)', 'static FRESULT preset_writeSlide(uint8_t pattern)',
                'static void preset_readSlide(uint8_t pattern)', 'static void preset_defaultGldExtras(uint8_t *data)',
                'static void preset_captureGldExtras(uint8_t *data)', 'static void preset_applyGldExtras(const uint8_t *data)',
                'static void preset_writeGldExtras(const uint8_t *data)', 'static void preset_readGldExtras(uint8_t *data)'):
        code += body(pm, sig) + '\n'
    code = code.replace('static void Drum_setGlideParameter(uint8_t index, uint8_t value);\nstatic uint8_t Drum_getGlideParameter(uint8_t index);\n', '')
    code += r'''
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
static void reset(void){for(int v=0;v<3;v++){memset(&voiceArray[v],0,sizeof(DrumVoice));voiceArray[v].osc.pitchMod=voiceArray[v].modOsc.pitchMod=1.f;
 drum_glide[v].mode=GLIDE_OFF;drum_glide[v].log2Ratio=0;drum_glide[v].slideNext=0;Drum_setGlideParameter((uint8_t)(3+v),GLIDE_TIME_DEFAULT);}}
static void sound(int v,int on){voiceArray[v].oscVolEg.state=on?EG_D:EG_STOPPED;voiceArray[v].ampFilterInput=on?0.5:0;}
static float pitch(int v){return voiceArray[v].osc.freq*powf(2.f,drum_glide[v].log2Ratio);}
static int blocksTo(int v,float frac){float start=fabsf(drum_glide[v].log2Ratio);int n=0;while(fabsf(drum_glide[v].log2Ratio)>start*frac&&n<100000){voiceArray[v].osc.pitchMod=1.f;drum_glideTick((uint8_t)v);n++;}return n;}
int main(void){
 reset();
 /* mode off, normal step: no glide, EGs retrigger */
 osc_setBaseNote(&voiceArray[0].osc,48);sound(0,1);
 check(drum_glideTrigger(0,60)==0,"plain note retriggers");check(drum_glide[0].log2Ratio==0.f,"plain note jumps");
 check(fabsf(voiceArray[0].osc.freq-261.63f)<0.1f,"note set on osc");check(fabsf(voiceArray[0].modOsc.freq-523.25f)<0.2f,"note set on mod osc");
 /* mode off: a slide step plays like a normal step */
 Drum_setSlideNext(0,1);check(drum_glideTrigger(0,72)==0&&drum_glide[0].log2Ratio==0.f,"off: slide step jumps and retriggers");
 check(drum_glide[0].slideNext==0,"off: slide flag used once");
 /* mode leg: a step without slide jumps; a slide step while the voice sounds glides, no retrigger */
 Drum_setGlideParameter(0,GLIDE_LEGATO);check(drum_glideTrigger(0,60)==0&&drum_glide[0].log2Ratio==0.f,"leg: step without slide jumps");
 Drum_setSlideNext(0,1);check(drum_glideTrigger(0,72)==1,"slide keeps the EGs");
 check(fabsf(drum_glide[0].log2Ratio+1.f)<1e-4f,"glides from one octave below");check(drum_glide[0].slideNext==0,"slide flag used once");
 check(fabsf(voiceArray[0].modOsc.pitchMod-0.5f)<1e-4f,"mod osc starts at the old pitch too");
 /* the glide arrives: both oscillators move */
 voiceArray[0].osc.pitchMod=1.f;drum_glideTick(0);check(voiceArray[0].osc.pitchMod>0.5f&&voiceArray[0].osc.pitchMod<1.f,"osc moves up");
 check(voiceArray[0].modOsc.pitchMod==voiceArray[0].osc.pitchMod,"mod osc moves along");
 /* time: 95 % of the way in glt; 0 = 10 ms, 127 = 1 s */
 for(int t=0;t<2;t++){reset();Drum_setGlideParameter(0,GLIDE_LEGATO);Drum_setGlideParameter(3,t?127:0);osc_setBaseNote(&voiceArray[0].osc,48);sound(0,1);Drum_setSlideNext(0,1);drum_glideTrigger(0,60);
  const float want=(t?1.f:0.01f)*REAL_FS/OUTPUT_DMA_SIZE;const int n=blocksTo(0,0.05f);check(fabsf(n-want)<=1.f+want*0.02f,t?"glt 127 = 1 s":"glt 0 = 10 ms");}
 for(int k=0;k<100000&&drum_glide[0].log2Ratio!=0.f;k++)drum_glideTick(0);
 check(drum_glide[0].log2Ratio==0.f&&voiceArray[0].modOsc.pitchMod==1.f,"glide ends exactly on the note");
 /* a new slide mid-glide starts from the pitch heard now */
 reset();Drum_setGlideParameter(0,GLIDE_LEGATO);Drum_setGlideParameter(3,100);osc_setBaseNote(&voiceArray[0].osc,48);sound(0,1);Drum_setSlideNext(0,1);drum_glideTrigger(0,60);
 for(int k=0;k<40;k++){voiceArray[0].osc.pitchMod=1.f;drum_glideTick(0);}
 {const float heard=pitch(0);Drum_setSlideNext(0,1);drum_glideTrigger(0,67);check(fabsf(pitch(0)-heard)<0.01f,"retarget starts from the heard pitch");}
 /* slide step on a silent voice plays a normal note */
 reset();Drum_setGlideParameter(1,GLIDE_LEGATO);osc_setBaseNote(&voiceArray[1].osc,48);sound(1,0);Drum_setSlideNext(1,1);
 check(drum_glideTrigger(1,60)==0&&drum_glide[1].log2Ratio==0.f,"slide on a silent voice retriggers");
 voiceArray[1].oscVolEg.state=EG_D;voiceArray[1].ampFilterInput=0.001;Drum_setSlideNext(1,1);check(drum_glideTrigger(1,62)==0,"a died away tail retriggers");
 /* mode on: every note glides, EGs retrigger */
 reset();Drum_setGlideParameter(2,GLIDE_ON);osc_setBaseNote(&voiceArray[2].osc,48);sound(2,0);
 check(drum_glideTrigger(2,60)==0&&fabsf(drum_glide[2].log2Ratio+1.f)<1e-4f,"on: glide with retrigger");
 drum_glide[2].log2Ratio=0;sound(2,1);Drum_setSlideNext(2,1);check(drum_glideTrigger(2,72)==0&&fabsf(drum_glide[2].log2Ratio+1.f)<1e-4f,"on: slide step glides, EGs still restart");
 /* mode leg: glide without retrigger while sounding */
 reset();Drum_setGlideParameter(1,GLIDE_LEGATO);osc_setBaseNote(&voiceArray[1].osc,60);sound(1,1);
 check(drum_glideTrigger(1,48)==0&&drum_glide[1].log2Ratio==0.f,"leg: no slide flag, no glide");
 Drum_setSlideNext(1,1);check(drum_glideTrigger(1,60)==1&&fabsf(drum_glide[1].log2Ratio+1.f)<1e-4f,"leg: slide glides legato");
 sound(1,0);Drum_setSlideNext(1,1);check(drum_glideTrigger(1,48)==0&&drum_glide[1].log2Ratio==0.f,"leg slide on a silent voice plays normally");
 /* other voices untouched, limits */
 check(drum_glide[0].mode==GLIDE_OFF,"mode is per voice");
 Drum_setGlideParameter(0,9);check(Drum_getGlideParameter(0)==GLIDE_OFF,"bad mode is off");
 Drum_setGlideParameter(5,200);check(Drum_getGlideParameter(5)==127,"time clamps");Drum_setGlideParameter(6,1);check(Drum_getGlideParameter(6)==0,"index range");
 reset();Drum_setGlideParameter(0,GLIDE_LEGATO);osc_setBaseNote(&voiceArray[0].osc,0);sound(0,1);Drum_setSlideNext(0,1);drum_glideTrigger(0,127);check(drum_glide[0].log2Ratio>=-GLIDE_MAX_OCT,"ratio limited");
 /* sequencer slide bits */
 seq_setSlide(5,2,63,1);seq_setSlide(5,2,0,1);check(seq_getSlide(5,2,63)&&seq_getSlide(5,2,0)&&!seq_getSlide(5,2,1),"slide bits");
 check(!seq_getSlide(5,1,63)&&!seq_getSlide(4,2,63),"per track and pattern");seq_setSlide(5,2,0,0);check(!seq_getSlide(5,2,0),"slide off");
 seq_setSlide(5,3,1,1);seq_setSlide(64,0,1,1);seq_setSlide(5,0,64,1);check(!seq_getSlide(5,3,1)&&!seq_getSlide(64,0,1),"tracks 4-7 have no slide");
 /* SLD1 */
 memset(&seq_patternSet,0,sizeof seq_patternSet);size=cursor=0;check(preset_writeSlide(7)==FR_OK&&size==0&&preset_slideBytes(7)==0,"no slide, old layout");
 seq_patternSet.slide[7][0]=0x8000000000000001ull;seq_patternSet.slide[7][2]=0x0123456789abcdefull;
 size=cursor=0;preset_writeSlide(7);check(size==SLIDE_BLOCK_BYTES&&preset_slideBytes(7)==size&&!memcmp(disk,"SLD1",4),"SLD1 written");
 cursor=0;preset_readSlide(9);check(seq_patternSet.slide[9][0]==0x8000000000000001ull&&seq_patternSet.slide[9][1]==0&&seq_patternSet.slide[9][2]==0x0123456789abcdefull&&cursor==size,"SLD1 roundtrip");
 seq_patternSet.slide[9][0]=5;size=cursor=0;preset_readSlide(9);check(seq_patternSet.slide[9][0]==0,"old pattern file: slide off");
 memcpy(disk,"PLK1xxxx",8);size=8;cursor=0;seq_patternSet.slide[9][0]=5;preset_readSlide(9);check(cursor==0&&seq_patternSet.slide[9][0]==0,"next block untouched");
 memcpy(disk,"SLD1abc",7);size=7;cursor=0;preset_readSlide(9);check(cursor==0&&seq_patternSet.slide[9][2]==0,"short SLD1 ignored");
 /* GLD1 */
 {uint8_t a[GLD_KIT_VALUES],b[GLD_KIT_VALUES];for(int i=0;i<6;i++)activeParameters[PAR_GLIDE_MODE1+i]=(uint8_t)(i<3?i:20+i);
  for(int i=0;i<3;i++)activeParameters[PAR_AEF_AMT1+i]=(uint8_t)(10+50*i);
  for(int i=0;i<FENV_EXTRA_VALUES;i++)activeParameters[PAR_AEF_AMT4+i]=(uint8_t)(30+5*i);
  preset_captureGldExtras(a);size=cursor=0;preset_writeGldExtras(a);check(size==GLD_EXTRA_BYTES&&!memcmp(disk,"GLD1",4)&&!memcmp(disk+10,"AEF1",4)&&!memcmp(disk+17,"FEN1",4),"GLD1, AEF1 and FEN1 written");
  cursor=0;preset_readGldExtras(b);check(!memcmp(a,b,GLD_KIT_VALUES)&&cursor==GLD_EXTRA_BYTES,"GLD1/AEF1/FEN1 roundtrip");
  memset(activeParameters,0,sizeof activeParameters);preset_applyGldExtras(b);check(drum_glide[1].mode==GLIDE_ON&&drum_glide[2].mode==GLIDE_LEGATO&&drum_glide[0].time==23,"GLD1 reaches the voices");
  check(activeParameters[PAR_GLIDE_MODE1+5]==25,"GLD1 shown");
  check(fenv_getParam(FENV_AMOUNT,2)==110&&fenv_getParam(FENV_AMOUNT,0)==10&&activeParameters[PAR_AEF_AMT1]==10,"AEF1 reaches the voices");
  check(fenv_getParam(FENV_AMOUNT,3)==30&&fenv_getParam(FENV_DECAY,0)==45&&fenv_getParam(FENV_ACCENT,5)==100&&activeParameters[PAR_AEF_AMT4+14]==100,"FEN1 reaches env, fdc, acc of every filter");
  /* a 0.2.92 kit file: GLD1 + AEF1, no FEN1 */
  size=17;cursor=0;preset_readGldExtras(b);check(b[8]==110&&b[FEN_AT]==FENV_CENTER&&b[FEN_AT+3]==0&&b[FEN_AT+14]==FENV_ACC_DEFAULT,"0.2.92 kit: filter env off, accent default");
  /* a 0.2.90 kit file: GLD1 without AEF1 */
  size=10;cursor=0;preset_readGldExtras(b);check(b[0]==0&&b[6]==AEF_CENTER&&b[8]==AEF_CENTER,"0.2.90 kit: aef off");
  for(int fill=0;fill<2;fill++){memset(disk,fill?0xff:0,sizeof disk);size=300;cursor=0;preset_readGldExtras(b);
   check(cursor==GLD_EXTRA_BYTES&&b[0]==GLIDE_OFF&&b[3]==GLIDE_TIME_DEFAULT&&b[7]==AEF_CENTER&&b[FEN_AT+5]==0,"old project kit: glide and env off, padding aligned");}
  size=cursor=0;preset_readGldExtras(b);check(b[2]==GLIDE_OFF&&b[5]==GLIDE_TIME_DEFAULT,"old kit file: glide off");
  memset(b,255,GLD_KIT_VALUES);preset_applyGldExtras(b);check(Drum_getGlideParameter(0)==GLIDE_OFF&&Drum_getGlideParameter(3)==127&&fenv_getParam(FENV_AMOUNT,0)==127&&fenv_getParam(FENV_DECAY,5)==127,"corrupt GLD1 clamps");}
 printf("SLIDE GLIDE PASS %u assertions\n",checks);return 0;}
'''
    return code


def run(code):
    (out / 'slide.c').write_text(code, encoding='latin-1')
    if os.name == 'nt':
        vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
        r = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:slide.exe slide.c && slide.exe',
                           shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    else:
        r = subprocess.run('cc -o slide slide.c -lm && ./slide', shell=True, cwd=out, capture_output=True, text=True, errors='replace')
    return r.returncode, r.stdout + r.stderr


MUTATIONS = {
    'amp-retrigger': ('drum', '''	if(!legato) {
		DecayEg_trigger(&voiceArray[voiceNr].oscPitchEg);
		slopeEg2_trigger(&voiceArray[voiceNr].oscVolEg);''', '''	slopeEg2_trigger(&voiceArray[voiceNr].oscVolEg);
	if(!legato) {
		DecayEg_trigger(&voiceArray[voiceNr].oscPitchEg);'''),
    'no-sounding': ('drum', 'const uint8_t legato = sounding && g->slideNext && g->mode==GLIDE_LEGATO;',
                    'const uint8_t legato = g->slideNext && g->mode==GLIDE_LEGATO;'),
    'off-slides': ('drum', 'const uint8_t legato = sounding && g->slideNext && g->mode==GLIDE_LEGATO;',
                   'const uint8_t legato = sounding && g->slideNext && g->mode!=GLIDE_ON;'),
    'on-legato': ('drum', 'const uint8_t legato = sounding && g->slideNext && g->mode==GLIDE_LEGATO;',
                  'const uint8_t legato = sounding && g->slideNext && g->mode!=GLIDE_OFF;'),
    'leg-always': ('drum', 'const uint8_t glide = legato || g->mode==GLIDE_ON;', 'const uint8_t glide = legato || g->mode!=GLIDE_OFF;'),
    'from-target': ('drum', 'const float oldFreq = v->osc.freq*exp2f(g->log2Ratio);', 'const float oldFreq = v->osc.freq;'),
    'mod-stays': ('drum', '	voiceArray[voiceNr].modOsc.pitchMod = f;\n}', '}'),
    'flag-sticks': ('drum', '	g->slideNext = 0;\n', ''),
    'slow-time': ('drum', 'return expf(-3.f*(float)OUTPUT_DMA_SIZE/(REAL_FS*seconds));', 'return expf(-1.f*(float)OUTPUT_DMA_SIZE/(REAL_FS*seconds));'),
    'no-tick': ('drum', '	if(drum_glide[voiceNr].log2Ratio != 0.f) drum_glideTick(voiceNr); // 0.2.90\n', ''),
    'main-step-only': ('seq', 'seq_triggerSourceStep[voiceNr]!=255 ? seq_triggerSourceStep[voiceNr] : seq_stepIndex[voiceNr]));', 'seq_stepIndex[voiceNr]));'),
    'copy-forgets': ('seq', '	memcpy(seq_patternSet.slide[dst], seq_patternSet.slide[src], sizeof(seq_patternSet.slide[dst]));\n', ''),
    'no-rewind': ('pm', '    if(bytes!=4 || memcmp(block,"SLD1",4)) { f_lseek(&SDFile,start); return; }', '    if(bytes!=4 || memcmp(block,"SLD1",4)) return;'),
    'stale-slide': ('pm', '    memset(seq_patternSet.slide[pattern],0,sizeof(seq_patternSet.slide[pattern]));\n', ''),
    'no-pad': ('pm', 'INS_EXTRA_BYTES + GLD_EXTRA_BYTES);\n	while(remain){', 'INS_EXTRA_BYTES);\n	while(remain){'),
    'led-off': ('led', '			if(showSlide) {', '			if(0) {'),
    'resend': ('menu', ' && i!=PAR_STEP_SLIDE &&', ' &&'),
    'aef-not-stored': ('pm', '    f_write((FIL*)&SDFile,"AEF1",4,&written);\n', ''),
    'fen-not-stored': ('pm', '    f_write((FIL*)&SDFile,"FEN1",4,&written);\n', ''),
    'fen-not-read': ('pm', '            memcpy(data+FEN_AT,fen+4,FENV_EXTRA_VALUES);\n', '            ;\n'),
    'aef-small-buf': ('pm', 'uint8_t gldExtras[GLD_KIT_VALUES];preset_captureGldExtras', 'uint8_t gldExtras[GLIDE_PARAMS];preset_captureGldExtras'),
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
