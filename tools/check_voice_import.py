"""Exercise the Snare kit extensions and controls on the host."""
from pathlib import Path
import os,re,subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build'/'voice-import-audit'
OUT.mkdir(parents=True,exist_ok=True)
def read(path):return (ROOT/path).read_text()
def function(code,name):
    m=re.search(r'^.*\b'+name+r'\([^)]*\)\s*\{',code,re.M)
    assert m,name
    pos=m.end();depth=1
    while depth:
        depth+=(code[pos]=='{')-(code[pos]=='}');pos+=1
    return code[m.start():pos]

preset=read('Core/Src/Preset/presetManager.c')
snare=read('Core/Src/Soundengine/DSPAudio/Snare.c')
drum=read('Core/Src/Soundengine/DSPAudio/DrumVoice.c')
ring_start=drum.index('else if(voiceArray[voiceNr].mixOscs == 2)')
ring_open=drum.index('{',ring_start)
pos=ring_open+1;depth=1
while depth:
    depth+=(drum[pos]=='{')-(drum[pos]=='}');pos+=1
ring=drum[ring_start:pos].replace('else if','if',1)
code='\n'.join(re.findall(r'#define SNARE_LAYER_\w+ \w+',read('Core/Inc/Soundengine/DSPAudio/Snare.h')))+r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include "Parameters.h"
#define USE_SD_CARD 1
#define SNARE_NOISE_KIT_BYTES 4u
static const uint8_t snareNoiseKitMagic[4]={'S','N','E','2'};
static const uint8_t oldSnareNoiseKitMagic[4]={'S','N','E','1'};
typedef unsigned UINT;
typedef int FRESULT;
typedef int FIL;
enum {FR_OK=0,FA_READ=1,FA_WRITE=2};
int SDFile;
uint8_t mainParameters[NUM_KIT_SLOTS][END_OF_SOUND_PARAMETERS],activeParameters[NUM_PARAMS];
uint8_t *morphParameters=mainParameters[1];
uint8_t preset_activeKitNr=0xff;
static uint8_t mainLfoExtras[NUM_KIT_SLOTS][12],mainRpsExtras[NUM_KIT_SLOTS][42],mainInsExtras[NUM_KIT_SLOTS][16],mainGldExtras[NUM_KIT_SLOTS][6];
static void preset_defaultLfoExtras(uint8_t*d){(void)d;}
static void preset_defaultRpsExtras(uint8_t*d){(void)d;}
static void preset_applyLfoExtras(const uint8_t*d){(void)d;}
static void preset_applyRpsExtras(const uint8_t*d){(void)d;}
static void preset_writeLfoExtras(const uint8_t*d){(void)d;}
static void preset_writeRpsExtras(const uint8_t*d){(void)d;}
static void preset_readLfoExtras(uint8_t*d){(void)d;}
static void preset_readRpsExtras(uint8_t*d){(void)d;}
static void preset_defaultInsExtras(uint8_t*d){(void)d;}
static void preset_applyInsExtras(const uint8_t*d){(void)d;}
static void preset_writeInsExtras(const uint8_t*d){(void)d;}
static void preset_readInsExtras(uint8_t*d){(void)d;}
static void preset_defaultGldExtras(uint8_t*d){(void)d;}
static void preset_applyGldExtras(const uint8_t*d){(void)d;}
static void preset_writeGldExtras(const uint8_t*d){(void)d;}
static void preset_readGldExtras(uint8_t*d){(void)d;}
static void preset_captureGldExtras(uint8_t*d){(void)d;}
static uint8_t disk[512];static unsigned cursor,size,checks;
static void check(int ok,const char*name){checks++;if(!ok){fprintf(stderr,"FAIL %s\n",name);exit(1);}}
FRESULT f_read(FIL*f,void*dst,unsigned n,UINT*bytes){(void)f;*bytes=n<size-cursor?n:size-cursor;memcpy(dst,disk+cursor,*bytes);cursor+=*bytes;return FR_OK;}
FRESULT f_write(FIL*f,const void*src,unsigned n,UINT*bytes){(void)f;check(cursor+n<=sizeof(disk),"kit file capacity");memcpy(disk+cursor,src,n);cursor+=n;if(cursor>size)size=cursor;*bytes=n;return FR_OK;}
uint8_t getNumModTargets(void){return 127;}
uint8_t preset_getMorphValue(uint16_t i,uint8_t morph){(void)morph;return activeParameters[i];}
typedef struct {uint8_t attack,decay,slope;} SlopeEg2;
typedef struct {uint8_t waveform;} OscInfo;
typedef struct {SlopeEg2 noiseVolEg;float noiseEgValue;uint8_t noiseAttackControl,noiseDecayControl,noiseSlopeControl,noiseEnvelopeEnabled;OscInfo layerOsc;float layerAmount;uint8_t layerMode,layerAmountControl,layerFreqControl;} SnareVoice;
SnareVoice snareVoice;
void slopeEg2_setAttack(SlopeEg2*e,uint8_t v,uint8_t sync){(void)sync;e->attack=v;}
void slopeEg2_setDecay(SlopeEg2*e,uint8_t v,uint8_t sync){(void)sync;e->decay=v;}
void slopeEg2_setSlope(SlopeEg2*e,uint8_t v){e->slope=v;}
typedef struct {float fmModAmount,pwm;uint8_t mixOscs;int osc;} Drum;
Drum voiceArray[3];
static int16_t mainSamples[16];
void calcNextOscSampleBlock(int*osc,int16_t*buf,uint8_t n,float gain,float pwm){(void)osc;(void)pwm;check(gain==1.f,"ring main oscillator unity");memcpy(buf,mainSamples,n*sizeof(int16_t));}
void actualRing(int16_t*buf,int16_t*modBuf,uint8_t size){const uint8_t voiceNr=0;
'''+ring+r'''
}
'''
code+='\n'.join(function(preset,n) for n in ('preset_defaultSnareLayer','preset_defaultSnareNoise','preset_validateSnareExtension','preset_morphedKitValue','preset_writeDrumsetData','preset_readDrumsetData'))
code+='\n'.join(function(snare,n) for n in ('Snare_updateNoiseEnvelopeEnabled','Snare_setNoiseAttack','Snare_setNoiseDecay','Snare_setNoiseSlope','Snare_setLayerWave','Snare_setLayerAmount','Snare_setLayerFreq','Snare_setLayerMode'))
code+=r'''
int main(void){
 // An old 228-byte .snd has no marker; a v2 project has 0xFF padding.
 memset(disk,0,228);cursor=0;size=228;
 check(preset_readDrumsetData(0,0)==FR_OK,"legacy kit read");
 check(mainParameters[0][PAR_SNARE_NOISE_ATTACK]==0&&mainParameters[0][PAR_SNARE_NOISE_DECAY]==127&&mainParameters[0][PAR_SNARE_NOISE_SLOPE]==64,"legacy kit defaults");
 check(mainParameters[0][PAR_SNARE_LAYER_AMOUNT]==0&&mainParameters[0][PAR_SNARE_LAYER_FREQ]==25,"legacy layer defaults");
 memset(disk,255,sizeof(disk));cursor=0;size=512;
 check(preset_readDrumsetData(0,0)==FR_OK,"legacy project kit read");
 check(mainParameters[0][PAR_SNARE_NOISE_DECAY]==127&&cursor==END_OF_SOUND_PARAMETERS+4,"legacy project padding and alignment");
 memset(disk,255,sizeof(disk));memset(disk,0,PAR_SNARE_LAYER_WAVE);disk[PAR_SNARE_NOISE_ATTACK]=31;disk[PAR_SNARE_NOISE_DECAY]=79;disk[PAR_SNARE_NOISE_SLOPE]=102;memcpy(disk+PAR_SNARE_LAYER_WAVE,oldSnareNoiseKitMagic,4);cursor=0;size=512;
 check(preset_readDrumsetData(0,0)==FR_OK,"0.1.15 project read");
 check(mainParameters[0][PAR_SNARE_NOISE_DECAY]==79&&mainParameters[0][PAR_SNARE_LAYER_FREQ]==25,"0.1.15 noise preserved and layer defaulted");
 mainParameters[0][PAR_SNARE_NOISE_ATTACK]=31;mainParameters[0][PAR_SNARE_NOISE_DECAY]=79;mainParameters[0][PAR_SNARE_NOISE_SLOPE]=102;
 mainParameters[0][PAR_SNARE_LAYER_WAVE]=2;mainParameters[0][PAR_SNARE_LAYER_AMOUNT]=88;mainParameters[0][PAR_SNARE_LAYER_FREQ]=60;mainParameters[0][PAR_SNARE_LAYER_MODE]=2;
 cursor=size=0;preset_writeDrumsetData(0,0);
 check(size==END_OF_SOUND_PARAMETERS+4&&memcmp(disk+END_OF_SOUND_PARAMETERS,snareNoiseKitMagic,4)==0,"new kit marker and size");
 memset(mainParameters[0],0,END_OF_SOUND_PARAMETERS);cursor=0;
 check(preset_readDrumsetData(0,0)==FR_OK,"new kit read");
 check(mainParameters[0][PAR_SNARE_NOISE_ATTACK]==31&&mainParameters[0][PAR_SNARE_NOISE_DECAY]==79&&mainParameters[0][PAR_SNARE_NOISE_SLOPE]==102,"new kit exact round trip");
 check(mainParameters[0][PAR_SNARE_LAYER_WAVE]==2&&mainParameters[0][PAR_SNARE_LAYER_AMOUNT]==88&&mainParameters[0][PAR_SNARE_LAYER_FREQ]==60&&mainParameters[0][PAR_SNARE_LAYER_MODE]==2,"new layer exact round trip");
 disk[END_OF_SOUND_PARAMETERS+3]='X';cursor=0;preset_readDrumsetData(0,0);
 check(mainParameters[0][PAR_SNARE_NOISE_DECAY]==127,"bad marker gets safe defaults");
 Snare_setNoiseAttack(0);Snare_setNoiseDecay(127);Snare_setNoiseSlope(64);
 check(!snareVoice.noiseEnvelopeEnabled&&snareVoice.noiseEgValue==1.f,"neutral envelope is legacy path");
 Snare_setNoiseAttack(1);check(snareVoice.noiseEnvelopeEnabled,"attack enables envelope");
 Snare_setNoiseAttack(0);Snare_setNoiseDecay(126);check(snareVoice.noiseEnvelopeEnabled,"decay enables envelope");
 Snare_setNoiseDecay(127);Snare_setNoiseSlope(63);check(snareVoice.noiseEnvelopeEnabled,"slope enables envelope");
 Snare_setNoiseSlope(64);check(!snareVoice.noiseEnvelopeEnabled,"neutral values restore legacy path");
 Snare_setLayerWave(3);Snare_setLayerAmount(127);Snare_setLayerFreq(42);Snare_setLayerMode(7);
 check(snareVoice.layerOsc.waveform==3&&snareVoice.layerAmount==1.f&&snareVoice.layerFreqControl==42&&snareVoice.layerMode==SNARE_LAYER_MODE_MAX,"layer setters and mode clamp");
 // Check ring's actual production branch at dry, mixed and full wet.
 int16_t buf[16],mod[16];for(unsigned i=0;i<16;i++){mainSamples[i]=(int16_t)(i*3541-26000);mod[i]=(int16_t)(21000-i*3199);}
 for(unsigned value=0;value<=127;value++){
   voiceArray[0].mixOscs=2;voiceArray[0].fmModAmount=value/127.f;
   actualRing(buf,mod,16);
   const int32_t wet=(int32_t)(voiceArray[0].fmModAmount*32767.f+0.5f),dry=32767-wet;
   for(unsigned i=0;i<16;i++){
     const int32_t ring=((int32_t)mainSamples[i]*mod[i])>>15;
     const int16_t expected=(int16_t)(((int32_t)mainSamples[i]*dry+ring*wet)>>15);
     check(buf[i]==expected,"ring blend matches reference arithmetic");
   }
 }
 printf("VOICE IMPORT PASS %u assertions\n",checks);return 0;
}
'''
(OUT/'Parameters.h').write_text(read('Core/Inc/Parameters.h'))
(OUT/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
(OUT/'contract.c').write_text(code)
if os.name=='nt':
    vs=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:contract.exe contract.c && contract.exe',shell=True,cwd=OUT,check=True)
else:
    subprocess.run(['cc','-std=c11','-o','contract','contract.c'],cwd=OUT,check=True)
    subprocess.run([str(OUT/'contract')],cwd=OUT,check=True)
