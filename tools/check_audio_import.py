"""Native audio contracts against unmodified Mutador filter/send/hat functions.

Hardware and DMA are replaced by bounded buffers; no firmware or SD writes.
"""
from pathlib import Path
import os
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/audio-import-audit'
OUT.mkdir(parents=True,exist_ok=True)
def clean(text):
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    return re.sub(r'^\s*#include[^\n]*','',text,flags=re.M).replace('IN_ITCM_RAM','').replace('__attribute__((noinline))','')
def read(path):return clean(path.read_text())
def function(code,name):
    m=re.search(r'^.*\b'+name+r'\([^)]*\)\s*\{',code,re.M)
    assert m,name
    pos=m.end();depth=1
    while depth:
        depth+=(code[pos]=='{')-(code[pos]=='}');pos+=1
    return code[m.start():pos]
def renamed(text):
    text=re.sub(r'\bmixer_(\w+)',r'ref_mixer_\1',text)
    return text.replace('MixerOutputRoute','RefMixerOutputRoute')

original=read(ROOT.parent/'mutador/mainboard/LxrStm32/src/DSPAudio/mixer.c')
actual=read(ROOT/'Core/Src/Soundengine/DSPAudio/mixer.c')
master=read(ROOT/'Core/Src/Soundengine/DSPAudio/PerformanceMasterFilter.c')
refData=original[original.index('INCCMZ uint8_t mixer_masterFilterMode;'):original.index('#define MIXER_JACK_R2')].replace('INCCMZ','static')
refData+='\nstatic ResonantFilter mixer_masterFilterL,mixer_masterFilterR;\nstatic float mixer_masterFilterClipLut[MASTER_FILTER_CLIP_LUT_SIZE];\n'
refData+='static void mixer_rebuildMasterFilterClipLut(float drive);\n'
refCode=original[original.index('void mixer_setMasterFilter('):original.index('static inline void mixer_cacheOutputJackState')]
refCode=refCode.replace('SVF_setDrive(','ref_SVF_setDrive(')
refInit=function(original,'mixer_init')
assignments=[line for line in refInit.splitlines() if line.strip().startswith(('mixer_masterFilter','SVF_init(&mixer_masterFilter','mixer_rebuildMasterFilterClipLut'))]
refInit='void ref_masterFilter_init(void){\n'+'\n'.join(assignments)+'\n}\n'
refInit=renamed(refInit).replace('SVF_init(','ref_SVF_init(')
refCode=renamed(refData+refCode)
prelude=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "Soundengine/DSPAudio/mixer.h"
#define OUTPUT_DMA_SIZE 16
#define FILTER_GAIN 32767
#define FILTER_SHAPER -0.9f
enum {FILTER_LP=1,FILTER_HP};
typedef struct {float f,g,q,s1,s2,a,b,drive;} ResonantFilter;
static unsigned checks;
static void check(int ok,const char *label){checks++;if(!ok){fprintf(stderr,"FAIL %s\n",label);exit(1);}}
static int16_t sat16(int32_t x){return x>32767?32767:x< -32768?-32768:(int16_t)x;}
#define __SSAT(x,n) sat16(x)
#define CPU_DIAG_FLAG(f) ((void)0) /* 0.2.104 peak diagnosis, normal build */
static uint32_t __QADD16(uint32_t a,uint32_t b){return (uint16_t)sat16((int16_t)a+(int16_t)b)|((uint32_t)(uint16_t)sat16((int16_t)(a>>16)+(int16_t)(b>>16))<<16);}
static uint32_t __PKHBT(int16_t a,int16_t b,unsigned shift){(void)shift;return (uint16_t)a|((uint32_t)(uint16_t)b<<16);}
static void SVF_directSetFilterValue(ResonantFilter*f,float v){f->f=v*.45f;f->g=0;}
static void SVF_init(ResonantFilter*f){memset(f,0,sizeof(*f));f->q=.9f;f->drive=.315f;SVF_directSetFilterValue(f,.25f);}
static void ref_SVF_init(ResonantFilter*f){SVF_init(f);f->drive=.5f;}
static void SVF_setReso(ResonantFilter*f,float v){f->q=1-v;if(f->q<.1f)f->q=.02f;}
static void SVF_setDrive(ResonantFilter*f,float v){f->drive=.4f+v*v*6;}
static void ref_SVF_setDrive(ResonantFilter*f,uint8_t v){SVF_setDrive(f,v/127.f);}
static void SVF_reset(ResonantFilter*f){f->a=f->b=f->s1=f->s2=0;}
static float valueShaperF2F(float v,float shape){float k=2*shape/(1.0001f-shape);return (1+k)*v/(1+k*fabsf(v));}
static float mixer_voiceVca[7],mixer_masterVca;
static uint8_t mixer_fxSend[7],mixer_fxSendMode,mixer_fxOutputMode;
static uint8_t mixer_intSend[6];
static float ref_mixer_voiceVca[7],ref_mixer_masterVca;
static uint8_t ref_mixer_fxSend[7],ref_mixer_fxSendMode,ref_mixer_fxOutputMode;
static uint8_t mixer_checkOutJackAvailable(uint8_t route){return route;}
static uint8_t ref_mixer_checkOutJackAvailable(uint8_t route){return route;}
/* 0.2.79 inserts: not under test here, the routes above never select one */
static void InsertFx_process(uint8_t v,uint8_t t,int16_t*b,uint16_t n){(void)v;(void)t;(void)b;(void)n;}
/* 0.2.107 send/insert modulation offsets: none here, the send stays as set */
enum {INS_MOD_SND,INS_MOD_SLOTS=6};
static float insertFx_mod[6][INS_MOD_SLOTS];
'''
actualNames=['mixer_handleVcaCc','mixer_handleFxSendCc','mixer_setFxSendMode','mixer_setFxOutputMode',
             'mixer_configureOutputRoute','mixer_addSampleToRoute','mixer_getFxSendGain','mixer_getFxSendRoute',
             'mixer_mixVoiceBlock','mixer_addMasterFxSendAfterFilter']
refNames=actualNames
routeType='typedef struct {int16_t*left,*right;float leftGain,rightGain;} MixerOutputRoute;\n'
actualCode=function(actual,'mixer_addDataToOutput')+'\n'+routeType+'\n'.join(function(actual,n) for n in actualNames)
referenceCode=renamed(routeType+'\n'.join(function(original,n) for n in refNames))
tests=r'''
static uint32_t randomState=1;
static int16_t sample(void){randomState=randomState*1664525u+1013904223u;return (int16_t)(randomState>>16);}
int main(void){
 int16_t a[32],b[32];
 masterFilter_init();for(int i=0;i<32;i++)a[i]=b[i]=sample();masterFilter_process(a,16);
 check(!memcmp(a,b,sizeof(a)),"disabled filter is bit-exact bypass");
 const unsigned resonance[3]={0,64,127},drives[3]={0,63,127};
 for(unsigned cut=0;cut<128;cut++)for(unsigned r=0;r<3;r++)for(unsigned d=0;d<3;d++) {
   masterFilter_init();ref_masterFilter_init();
   mixer_setMasterFilter((uint8_t)cut);ref_mixer_setMasterFilter((uint8_t)cut);
   mixer_setMasterFilterResonance((uint8_t)resonance[r]);ref_mixer_setMasterFilterResonance((uint8_t)resonance[r]);
   mixer_setMasterFilterDrive((uint8_t)drives[d]);ref_mixer_setMasterFilterDrive((uint8_t)drives[d]);
   mixer_setMasterFilterEnabled(1);ref_mixer_setMasterFilterEnabled(1);
   for(unsigned block=0;block<256;block++) {
     for(int i=0;i<32;i++)a[i]=b[i]=sample();
     masterFilter_process(a,16);ref_mixer_applyMasterFilter(b);
     for(int i=0;i<32;i++)check(a[i]==b[i],"master filter exact reference samples");
     check(isfinite(mixer_masterFilterL.a)&&isfinite(mixer_masterFilterR.b),"master filter bounded state");
   }
   mixer_setMasterFilterEnabled(0);ref_mixer_setMasterFilterEnabled(0);
   for(unsigned block=0;block<9;block++) {
     for(int i=0;i<32;i++)a[i]=b[i]=sample();
     int16_t dry[32];memcpy(dry,a,sizeof(a));masterFilter_process(a,16);ref_mixer_applyMasterFilter(b);
     check(!memcmp(a,b,sizeof(a)),"filter bypass fade reference");
     if(block==8)check(!memcmp(a,dry,sizeof(a)),"disabled filter returns to dry");
   }
 }
 const unsigned send[7]={0,1,63,64,65,126,127};
 for(unsigned mode=0;mode<4;mode++)for(unsigned output=0;output<2;output++)
 for(unsigned si=0;si<7;si++)for(unsigned vg=0;vg<3;vg++)for(unsigned mg=0;mg<3;mg++)
 for(unsigned route=0;route<6;route++)for(unsigned pan=0;pan<3;pan++) {
   int16_t data[16],refData[16],out[64]={0},refOut[64]={0},fx[32]={0};
   for(int i=0;i<16;i++)data[i]=refData[i]=sample();
   mixer_setFxSendMode((uint8_t)mode);ref_mixer_setFxSendMode((uint8_t)mode);
   mixer_setFxOutputMode((uint8_t)output);ref_mixer_setFxOutputMode((uint8_t)output);
   mixer_handleFxSendCc(30,(uint8_t)send[si]);ref_mixer_handleFxSendCc(30,(uint8_t)send[si]);
   mixer_handleVcaCc(20,(uint8_t)(vg==2?127:vg*63));ref_mixer_handleVcaCc(20,(uint8_t)(vg==2?127:vg*63));
   mixer_handleVcaCc(26,(uint8_t)(mg==2?127:mg*63));ref_mixer_handleVcaCc(26,(uint8_t)(mg==2?127:mg*63));
   float right=pan*.5f,left=1.f-right;
   mixer_mixVoiceBlock(0,(uint8_t)route,left,right,data,out,out+1,out+32,out+33,fx);
   ref_mixer_mixVoiceBlock(0,(uint8_t)route,left,right,refData,refOut,refOut+1,refOut+32,refOut+33);
   for(unsigned i=0;i<64;i++)check(out[i]==refOut[i],"external send and VCA routing reference");
   for(unsigned i=0;i<32;i++)check(fx[i]==0,"external sends do not enter internal FX bus");
 }
 for(unsigned mode=0;mode<4;mode++)for(unsigned output=0;output<2;output++)for(unsigned si=0;si<7;si++) {
   int16_t master[32],refMaster[32],out[32],refOut[32];
   for(int i=0;i<32;i++){master[i]=refMaster[i]=sample();out[i]=refOut[i]=sample();}
   mixer_setFxSendMode((uint8_t)mode);ref_mixer_setFxSendMode((uint8_t)mode);
   mixer_setFxOutputMode((uint8_t)output);ref_mixer_setFxOutputMode((uint8_t)output);
   mixer_handleFxSendCc(36,(uint8_t)send[si]);ref_mixer_handleFxSendCc(36,(uint8_t)send[si]);
   mixer_addMasterFxSendAfterFilter(master,out,out+1);
   ref_mixer_addMasterFxSendAfterFilter(refMaster,refOut,refOut+1);
   for(int i=0;i<32;i++)check(master[i]==refMaster[i]&&out[i]==refOut[i],"master post-filter FX send reference");
 }
 // Preserve existing internal-FX routing as the dry destination in AFL/PFL.
 mixer_setFxSendMode(1);mixer_setFxOutputMode(0);mixer_handleFxSendCc(30,127);
 mixer_handleVcaCc(20,127);mixer_handleVcaCc(26,127);
 int16_t data[16],out[64]={0},fx[32]={0};for(int i=0;i<16;i++)data[i]=1000;
 mixer_mixVoiceBlock(0,MIXER_ROUTING_FX_BUS,1,0,data,out,out+1,out+32,out+33,fx);
 check(fx[0]==1000&&fx[1]==0&&out[0]==1000&&out[32]==0,"built-in FX bus remains a valid dry route");
 // 0.2.68 internal sends: parallel to the voice output, after the VCA, not twice
 mixer_intSend[0]=127;memset(fx,0,sizeof(fx));memset(out,0,sizeof(out));for(int i=0;i<16;i++)data[i]=1000;
 mixer_mixVoiceBlock(0,MIXER_ROUTING_FX_BUS,1,0,data,out,out+1,out+32,out+33,fx);
 check(fx[0]==1000&&fx[1]==0,"a voice routed to FX is not sent twice");
 mixer_setFxSendMode(0);memset(fx,0,sizeof(fx));memset(out,0,sizeof(out));for(int i=0;i<16;i++)data[i]=1000;
 mixer_mixVoiceBlock(0,MIXER_ROUTING_DAC1_STEREO,1,0,data,out,out+1,out+32,out+33,fx);
 check(fx[0]==1000&&fx[30]==1000&&fx[1]==0&&out[32]==1000,"internal send adds to the FX bus and keeps the dry output");
 mixer_intSend[0]=64;memset(fx,0,sizeof(fx));for(int i=0;i<16;i++)data[i]=1000;
 mixer_mixVoiceBlock(0,MIXER_ROUTING_DAC1_STEREO,1,0,data,out,out+1,out+32,out+33,fx);
 check(fx[0]>=495&&fx[0]<=505,"internal send level");
 mixer_intSend[0]=127;mixer_handleVcaCc(20,0);memset(fx,0,sizeof(fx));for(int i=0;i<16;i++)data[i]=1000;
 mixer_mixVoiceBlock(0,MIXER_ROUTING_DAC1_STEREO,1,0,data,out,out+1,out+32,out+33,fx);
 check(fx[0]==0,"internal send follows the VCA");
 mixer_handleVcaCc(20,127);mixer_setFxSendMode(3);mixer_handleFxSendCc(30,64);memset(fx,0,sizeof(fx));for(int i=0;i<16;i++)data[i]=1000;
 mixer_mixVoiceBlock(0,MIXER_ROUTING_FX_BUS,1,0,data,out,out+1,out+32,out+33,fx);
 check(fx[0]==1000,"in cfl a voice routed to FX reaches the bus through its internal send");
 mixer_intSend[0]=0;
 printf("AUDIO IMPORT PASS %u reference assertions\n",checks);return 0;
}
'''
(OUT/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
program=prelude+master+'\n'+refCode+'\n'+refInit+'\n'+actualCode+'\n'+referenceCode+'\n'+tests
(OUT/'audio.c').write_text(program)
if os.name=='nt':
    vs=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /I. /I"{ROOT/"Core/Inc"}" /Fe:audio.exe audio.c && audio.exe',shell=True,cwd=OUT,check=True)
else:
    subprocess.run(['cc','-O2','-std=c11','-I.','-I'+str(ROOT/'Core/Inc'),'audio.c','-lm','-o','audio'],cwd=OUT,check=True)
    subprocess.run([str(OUT/'audio')],cwd=OUT,check=True)
