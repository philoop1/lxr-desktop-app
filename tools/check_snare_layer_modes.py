"""The Snare wmd modes exp and pd (Mutador 0.2.49) on the host.

The check compiles the real Snare_calcSyncBlock(), Snare_calcAsync() and
Snare_setLayerMode() from Snare.c with spies for the oscillator blocks and
checks the routing: exp runs the layer osc and expo FM, pd warps the snare osc
without the layer osc, both take their depth from layer amount times the pitch
EG, give it back afterwards (FM keeps its own fmMod), and keep the osc level.
The DSP of the expo FM and PD blocks is checked in check_osc_modes.py.
--mutate runs each mutation and expects the check to fail.
"""
from pathlib import Path
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build' / 'snare-layer-audit'
OUT.mkdir(parents=True, exist_ok=True)
snare = (ROOT / 'Core/Src/Soundengine/DSPAudio/Snare.c').read_text(encoding='utf-8')
header = (ROOT / 'Core/Inc/Soundengine/DSPAudio/Snare.h').read_text(encoding='utf-8')

MUTATIONS = {
    'depth-not-passed': ('snareVoice.osc.fmMod=snareVoice.layerDepth;', ''),
    'fm-not-restored': ('snareVoice.osc.fmMod=fmMod;\n\t\tfor', '\t\tfor'),
    'fm-mode-not-restored': ('snareVoice.osc.fmMod=fmMod;\n\t} else {', '\t} else {'),
    'no-osc-level': ('for(uint8_t i=0;i<size;i++)oscBuf[i]=(int16_t)(oscBuf[i]*oscGain);', ''),
    'exp-without-layer': ('calcNextOscSampleBlock(&snareVoice.layerOsc,layerBuf,size,1.f,snareVoice.pwm);\n\t\t\tcalcExpoFmBlock',
                          'calcExpoFmBlock'),
    'depth-ignores-eg': ('snareVoice.layerDepth = snareVoice.layerAmount*egPitchVal;',
                         'snareVoice.layerDepth = snareVoice.layerAmount;'),
    'no-knee-reset': ('snareVoice.osc.pdKnee = 0.f;', ''),
    'mode-clamp-2': ('value>SNARE_LAYER_MODE_MAX?SNARE_LAYER_MODE_MAX:value', 'value>2?2:value'),
    'fm-no-depth': ('snareVoice.osc.fmMod=1.f;', ''),
}
if '--mutate' in sys.argv:
    missed = []
    for name in MUTATIONS:
        r = subprocess.run([sys.executable, __file__, '--mutation=' + name], capture_output=True, text=True)
        print(('caught ' if r.returncode else 'MISSED ') + name)
        if not r.returncode:
            missed.append(name)
    sys.exit(1 if missed else 0)
snare = snare.replace('\r\n', '\n')
for arg in sys.argv[1:]:
    if arg.startswith('--mutation='):
        old, new = MUTATIONS[arg.split('=', 1)[1]]
        if snare.count(old) != 1:
            print('BAD MUTATION', old)
            sys.exit(0)
        snare = snare.replace(old, new)


def function(name):
    m = re.search(r'^.*\b' + name + r'\([^)]*\)\s*\{', snare, re.M)
    assert m, name
    pos, depth = m.end(), 1
    while depth:
        depth += (snare[pos] == '{') - (snare[pos] == '}')
        pos += 1
    # MSVC has no VLAs; a block is at most 64 samples here
    return re.sub(r'\[size\]', '[64]', snare[m.start():pos].replace('IN_ITCM_RAM ', ''))


defines = '\n'.join(re.findall(r'#define SNARE_LAYER_\w+ \w+', header))
code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#define USE_REVERB 0
''' + defines + r'''
typedef struct {uint8_t waveform;float fmMod,pdKnee,pitchMod;uint32_t phase;} OscInfo;
typedef struct {int dummy;} ResonantFilter;
typedef struct {uint8_t waveform;float volume,pitch;} TransientGenerator;
typedef struct {int dummy;} SlopeEg2;
typedef struct {int dummy;} DecayEg;
typedef struct {int dummy;} SnapEg;
typedef struct {int dummy;} Distortion;
typedef struct {int dummy;} OnePoleFilter;
typedef struct {
 OscInfo osc,noiseOsc,layerOsc;
 float layerAmount,layerDepth;uint8_t layerMode,layerAmountControl,layerFreqControl,filterType;
 float vol,mix,velo;ResonantFilter filter;DecayEg oscPitchEg;float egPitchModAmount;TransientGenerator transGen;
 SlopeEg2 oscVolEg;float egValueOscVol;SlopeEg2 noiseVolEg;float noiseEgValue;uint8_t noiseEnvelopeEnabled;
 Distortion distortion;SnapEg snapEg;uint8_t volumeMod;float combinedVolume;OnePoleFilter FaderVolumeFilter;float pwm;
} SnareVoice;
SnareVoice snareVoice;
/* spies */
enum {CALL_OSC,CALL_LAYER,CALL_FM,CALL_EXPO,CALL_PD};
unsigned calls[5];float seenFmMod,layerGain;
void calcNoiseBlock(OscInfo *o,int16_t *b,uint8_t n,float g){(void)o;(void)g;for(uint8_t i=0;i<n;i++)b[i]=0;}
void SVF_calcBlockZDF(ResonantFilter *f,uint8_t t,int16_t *b,uint8_t n){(void)f;(void)t;(void)b;(void)n;}
void calcNextOscSampleBlock(OscInfo *o,int16_t *b,uint8_t n,float g,float pwm){(void)pwm;
 if(o==&snareVoice.layerOsc){calls[CALL_LAYER]++;layerGain=g;}else calls[CALL_OSC]++;
 for(uint8_t i=0;i<n;i++)b[i]=(int16_t)(1000*g);}
void calcNextOscSampleFmBlock(OscInfo *o,int16_t *m,int16_t *b,uint8_t n,float g,float pwm){(void)m;(void)pwm;calls[CALL_FM]++;seenFmMod=o->fmMod;for(uint8_t i=0;i<n;i++)b[i]=(int16_t)(1000*g);}
void calcExpoFmBlock(OscInfo *o,int16_t *m,int16_t *b,uint8_t n,float pwm){(void)pwm;calls[CALL_EXPO]++;seenFmMod=o->fmMod;
 for(uint8_t i=0;i<n;i++){if(m[i]!=1000){puts("FAIL expo gets the layer osc at full level");exit(1);}b[i]=2000;}}
void calcPhaseDistBlock(OscInfo *o,int16_t *b,uint8_t n){calls[CALL_PD]++;seenFmMod=o->fmMod;for(uint8_t i=0;i<n;i++)b[i]=3000;}
void transient_calcBlock(TransientGenerator *t,int16_t *b,uint8_t n){(void)t;for(uint8_t i=0;i<n;i++)b[i]=0;}
float calcOnePole(OnePoleFilter *f,float v){(void)f;(void)v;return 1.f;}
float adc_getFaderVolume(uint8_t v){(void)v;return 1.f;}
void calcDistBlock(Distortion *d,int16_t *b,uint8_t n){(void)d;(void)b;(void)n;}
float DecayEg_calc(DecayEg *e){(void)e;return 0.5f;}
float slopeEg2_calc(SlopeEg2 *e){(void)e;return 1.f;}
float SnapEg_calc(SnapEg *e,float p){(void)e;(void)p;return 0.f;}
void osc_setFreq(OscInfo *o){(void)o;}
static unsigned checks;
static void check(int ok,const char *what){checks++;if(!ok){printf("FAIL %s\n",what);exit(1);}}
'''
for name in ('Snare_setLayerMode', 'Snare_calcAsync', 'Snare_calcSyncBlock'):
    code += function(name) + '\n'
code += r'''
static int16_t run(uint8_t mode,uint8_t amount){
 for(int i=0;i<5;i++)calls[i]=0;seenFmMod=-1;
 snareVoice.layerMode=mode;snareVoice.layerAmountControl=amount;snareVoice.layerAmount=amount/127.f;
 snareVoice.mix=0.25f;snareVoice.vol=1.f;snareVoice.noiseEnvelopeEnabled=0;snareVoice.volumeMod=0;
 snareVoice.transGen.waveform=1;snareVoice.osc.fmMod=0.f;
 Snare_calcAsync();
 int16_t buf[16];Snare_calcSyncBlock(buf,16);
 return buf[0];
}
int main(void){
 Snare_setLayerMode(7);check(snareVoice.layerMode==SNARE_LAYER_MODE_MAX,"wmd clamps to pd");
 Snare_setLayerMode(SNARE_LAYER_EXP);check(snareVoice.layerMode==3,"wmd keeps exp");
 int16_t out=run(SNARE_LAYER_EXP,127);
 check(calls[CALL_LAYER]==1&&layerGain==1.f&&calls[CALL_EXPO]==1&&!calls[CALL_PD]&&!calls[CALL_FM]&&!calls[CALL_OSC],"exp runs the layer osc into expo FM");
 check(fabsf(seenFmMod-0.5f)<1e-6f,"exp depth is layer amount times the pitch EG");
 check(snareVoice.osc.fmMod==0.f,"exp gives fmMod back, FM keeps its own");
 check(out==1500,"exp keeps the osc level (1 - mix)");
 out=run(SNARE_LAYER_PD,64);
 check(calls[CALL_PD]==1&&!calls[CALL_LAYER]&&!calls[CALL_EXPO]&&!calls[CALL_OSC],"pd warps the snare osc without the layer osc");
 check(fabsf(seenFmMod-64.f/127.f*0.5f)<1e-6f,"pd depth is layer amount times the pitch EG");
 check(snareVoice.osc.fmMod==0.f,"pd gives fmMod back");
 check(out==2250,"pd keeps the osc level (1 - mix)");
 run(SNARE_LAYER_PD,0);
 check(calls[CALL_OSC]==1&&!calls[CALL_PD]&&!calls[CALL_LAYER],"layer amount 0 keeps the plain snare");
 run(1,100);
 check(calls[CALL_FM]==1&&calls[CALL_LAYER]==1&&fabsf(layerGain-100.f/127.f)<1e-6f&&!calls[CALL_EXPO]&&!calls[CALL_PD],"FM runs the layer osc at sla into the FM block");
 check(seenFmMod==1.f,"FM has depth (0.2.50: fmMod was 0)");
 check(snareVoice.osc.fmMod==0.f,"FM gives fmMod back");
 run(0,100);
 check(calls[CALL_OSC]==1&&calls[CALL_LAYER]==1&&!calls[CALL_EXPO]&&!calls[CALL_PD],"mix mode is unchanged");
 printf("SNARE LAYER PASS %u assertions\n",checks);return 0;
}
'''
trigger = re.search(r'void Snare_trigger\(.*?\n\}', snare, re.S)
assert trigger, 'Snare_trigger'
if 'snareVoice.osc.pdKnee = 0.f;' not in trigger.group(0):
    print('FAIL a snare trigger resets the PD knee')
    sys.exit(1)
(OUT / 'contract.c').write_text(code)
if os.name == 'nt':
    vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    r = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:contract.exe contract.c >build.log && contract.exe',
                       shell=True, cwd=OUT)
    if r.returncode and (OUT / 'build.log').exists():
        print((OUT / 'build.log').read_text(errors='replace')[-2000:])
    sys.exit(r.returncode != 0)
r = subprocess.run(['cc', '-std=c11', '-o', 'contract', 'contract.c', '-lm'], cwd=OUT)
sys.exit(r.returncode != 0 or subprocess.run([str(OUT / 'contract')], cwd=OUT).returncode != 0)
