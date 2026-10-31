"""Real-source tests for step groups, global grid, half-closed HH and sidecar IO."""
from pathlib import Path
import os,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/edit-scale-hat-audit';OUT.mkdir(parents=True,exist_ok=True)
def clean(text):
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    return re.sub(r'^\s*#include[^\n]*','',text,flags=re.M).replace('IN_ITCM_RAM','')
def read(path):return clean(path.read_text())
def function(code,name):
    m=re.search(r'^.*\b'+name+r'\([^)]*\)\s*\{',code,re.M);assert m,name
    p=m.end();depth=1
    while depth:depth+=(code[p]=='{')-(code[p]=='}');p+=1
    return code[m.start():p]
prelude=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "Parameters.h"
#define PERFORMANCE_EXTRA_BYTES 20
#define NUM_PATTERN 64
static unsigned checks;
static void check(int ok,const char *what){checks++;if(!ok){fprintf(stderr,"FAIL %s\n",what);exit(1);}}
'''
prelude+=read(ROOT/'Core/Inc/Preset/SeqStep.h')
prelude+=r'''
struct {Step seq_subStepPattern[64][7][64];StepTiming seq_stepTiming[64][7][64];uint8_t flamProbability[64][7][64];struct{uint8_t scale;}seq_patternSettings[64];}seq_patternSet;
typedef struct {uint16_t param;} ModTarg;
const ModTarg modTargets[3]={{0},{5},{130}};
uint8_t getNumModTargets(void){return 3;}
uint8_t activeParameters[NUM_PARAMS];
static uint8_t isRunning,fxOutput,fxMode,sendValues[7],vcaValues[7],enabled,cutoff,reso,drive;
uint8_t seq_isRunning(void){return isRunning;}
uint8_t mixer_handleFxSendCc(uint8_t cc,uint8_t value){sendValues[cc-30]=value;return 1;}
uint8_t mixer_handleVcaCc(uint8_t cc,uint8_t value){vcaValues[cc-20]=value;return 1;}
void mixer_setFxSendMode(uint8_t v){fxMode=v;}
void mixer_setFxOutputMode(uint8_t v){fxOutput=v;for(int i=0;i<7;i++)sendValues[i]=v?64:0;}
uint8_t mixer_getFxOutputMode(void){return fxOutput;}
void mixer_setMasterFilterEnabled(uint8_t v){enabled=v;}
void mixer_setMasterFilter(uint8_t v){cutoff=v;}
void mixer_setMasterFilterResonance(uint8_t v){reso=v>105?105:v;}
void mixer_setMasterFilterDrive(uint8_t v){drive=v;}
static uint8_t clockCoarse,clockFine;
void sync_setClockOffset(uint8_t coarse,uint8_t fine){clockCoarse=coarse;clockFine=fine;}
typedef unsigned UINT;
typedef int FRESULT;
typedef int FIL;
enum {FR_OK=0,FR_DISK_ERR=1,FR_NO_FILE=4,FA_OPEN_EXISTING=0,FA_READ=1,FA_CREATE_ALWAYS=8,FA_WRITE=2};
int SDFile;
static uint8_t disk[128];static unsigned fileLength,present,shortWrite,closed;
static FRESULT f_open(FIL*f,const char*name,unsigned flags){(void)f;check(!strcmp(name,"MUTA.CFG"),"sidecar filename");if(flags&FA_CREATE_ALWAYS){present=1;fileLength=0;return FR_OK;}return present?FR_OK:FR_NO_FILE;}
static FRESULT f_read(FIL*f,void*dst,unsigned count,UINT*bytes){(void)f;*bytes=count<fileLength?count:fileLength;memcpy(dst,disk,*bytes);return FR_OK;}
static FRESULT f_write(FIL*f,const void*src,unsigned count,UINT*bytes){(void)f;*bytes=shortWrite?count-1:count;memcpy(disk,src,*bytes);fileLength=*bytes;return FR_OK;}
static FRESULT f_close(FIL*f){(void)f;closed++;return FR_OK;}
enum {SINE,TRI,SAW,REC};
typedef struct {uint32_t phase;uint8_t waveform,note;} HatOsc;
typedef struct {uint8_t waveform;float volume;} Transient;
typedef struct {float decay;} HatEnvelope;
typedef struct {HatOsc osc,modOsc,modOsc2;Transient transGen;HatEnvelope oscVolEg;float decayClosed,decayOpen,velo;uint8_t isOpen;int snapEg;} TestHat;
TestHat hatVoice,ref_hatVoice;
static uint32_t systick_ticks,hatTriggerTick,ref_hatTriggerTick;
static uint8_t hatTriggerMask,hatTriggerVelocity,hatTriggerTickValid,ref_hatTriggerMask,ref_hatTriggerVelocity,ref_hatTriggerTickValid;
static unsigned panUpdates;
int velocityModulators[6];
void lfo_retrigger(uint8_t n){(void)n;}
void modNode_updateValue(int*n,float value){(void)n;(void)value;}
void osc_setBaseNote(HatOsc*n,uint8_t value){n->note=value;}
void slopeEg2_trigger(HatEnvelope*n){(void)n;}
void transient_trigger(Transient*n){(void)n;}
void SnapEg_trigger(int*n){(void)n;}
void HiHat_updatePan(void){panUpdates++;}
static uint8_t seq_globalScaleMode;
'''
code=read(ROOT/'Core/Src/menu/StepSelection.c')+'\n'+read(ROOT/'Core/Src/Soundengine/Sequencer/PerformanceScale.c')+'\n'+read(ROOT/'Core/Src/menu/PerformanceControls.c')
preset=read(ROOT/'Core/Src/Preset/presetManager.c')
code+='\n'+function(preset,'preset_loadPerformanceExtension')+'\n'+function(preset,'preset_savePerformanceExtension')
hat=function(read(ROOT/'Core/Src/Soundengine/DSPAudio/HiHat.c'),'HiHat_trigger')
refhat=function(read(ROOT.parent/'mutador/mainboard/LxrStm32/src/DSPAudio/HiHat.c'),'HiHat_trigger')
refhat=refhat.replace('HiHat_trigger','ref_HiHat_trigger').replace('hatVoice','ref_hatVoice').replace('hatTrigger','ref_hatTrigger')
code+='\n'+hat+'\n'+refhat
ref=read(ROOT.parent/'mutador/mainboard/LxrStm32/src/Sequencer/sequencer.c')
code+='\n'+'\n'.join(function(ref,n) for n in ('seq_getPlaybackScale','seq_scaleAllowsMainStep','seq_scaleAllowedMainCount','seq_scaleOrdinalToMain'))
tests=r'''
int main(void){
 // Non-contiguous, cross-bar selection; first press after release starts afresh.
 check(stepEdit_press(2,3,1,1),"first group anchor");
 check(!stepEdit_press(2,3,3,3)&&!stepEdit_press(2,3,0,16)&&!stepEdit_press(2,3,15,63),"add held chord across bars");
 uint64_t expected=((uint64_t)1<<1)|((uint64_t)1<<3)|((uint64_t)1<<16)|((uint64_t)1<<63);
 check(stepEdit_mask(2,3)==expected&&!stepEdit_mask(2,4),"selection context and full 64-bit mask");
 stepEdit_release(1);stepEdit_release(3);stepEdit_release(0);stepEdit_release(15);
 check(stepEdit_mask(2,3)==expected,"selection remains latched after release");
 memset(&seq_patternSet,0,sizeof(seq_patternSet));
 for(int i=0;i<64;i++)seq_patternSet.seq_subStepPattern[2][3][i].volume=133;
 const uint16_t parameters[10]={PAR_STEP_NOTE,PAR_STEP_VOLUME,PAR_STEP_PROB,PAR_STEP_FLAM_PROB,PAR_STEP_FLAM,PAR_STEP_SHIFT,PAR_P1_DEST,PAR_P2_DEST,PAR_P1_VAL,PAR_P2_VAL};
 const uint8_t values[10]={72,42,80,37,5,14,1,2,91,92};
 for(int p=0;p<10;p++)check(stepEdit_apply(2,3,parameters[p],values[p]),"all ten group-edit fields handled");
 for(unsigned i=0;i<64;i++) {
   Step*x=&seq_patternSet.seq_subStepPattern[2][3][i];int selected=(expected>>i)&1;
   check(x->volume==(selected?170:133),"group volume preserves active flag and unselected steps");
   check(x->note==(selected?72:0)&&x->prob==(selected?80:0),"group note/probability");
   check(x->param1Nr==(selected?6:0)&&x->param2Nr==(selected?130:0),"group destination storage encoding");
   check(x->param1Val==(selected?91:0)&&x->param2Val==(selected?92:0),"group automation values");
   check(seq_patternSet.seq_stepTiming[2][3][i].flam==(selected?5:0)&&seq_patternSet.seq_stepTiming[2][3][i].shift==(selected?14:0)&&seq_patternSet.flamProbability[2][3][i]==(selected?37:0),"group timing and flam probability");
 }
 check(!stepEdit_apply(2,3,PAR_BPM,120)&&!stepEdit_apply(2,4,PAR_STEP_NOTE,1),"group never edits globals or another voice");
 check(stepEdit_press(2,3,5,5)&&stepEdit_mask(2,3)==((uint64_t)1<<5),"new unheld press replaces latched group");
 stepEdit_clear();check(!stepEdit_mask(2,3),"mode/context reset clears group");
 // The new grid keeps all steps except the last four slots of each page at /12.
 for(unsigned mode=1;mode<=8;mode++)for(unsigned length=1;length<=64;length++) {
   perf_scaleSet((uint8_t)mode,0);
   unsigned count=0;
   for(unsigned i=0;i<length;i++) {
     unsigned allowed=mode!=5 || (i%16)<12;
     check(perf_scaleAllowed((uint8_t)i)==allowed,"new scale allowed slots");count+=allowed;
   }
   check(perf_scaleCount((uint8_t)length)==count,"new scale count");
   for(unsigned i=0;i<count;i++) {
     uint8_t source=perf_scaleToSource((uint8_t)i,(uint8_t)length);
     check(perf_scaleToOrdinal(source,(uint8_t)length)==i,"new scale round trip");
     check(perf_scaleNext(source,(uint8_t)length)==perf_scaleToSource((uint8_t)((i+1)%count),(uint8_t)length),"new scale wrap");
   }
 }
 perf_scaleSet(6,0);perf_scaleSet(5,1);check(perf_scaleMode()==16,"running scale waits for confirmation boundary");
 check(!perf_scaleCommitOnBar(767)&&perf_scaleMode()==16,"scale waits until downbeat");
 check(perf_scaleCommitOnBar(0)&&perf_scaleMode()==12,"pending scale commits on downbeat");
 // Same-tick open/closed hits must match original in both orders and every velocity pair.
 for(unsigned order=0;order<2;order++)for(unsigned v1=0;v1<128;v1++)for(unsigned v2=0;v2<128;v2++) {
   memset(&hatVoice,0,sizeof(hatVoice));hatVoice.decayClosed=.2f;hatVoice.decayOpen=.8f;ref_hatVoice=hatVoice;
   hatTriggerTickValid=ref_hatTriggerTickValid=0;systick_ticks=100;
   HiHat_trigger((uint8_t)v1,(uint8_t)order,60);ref_HiHat_trigger((uint8_t)v1,(uint8_t)order,60);
   HiHat_trigger((uint8_t)v2,(uint8_t)!order,63);ref_HiHat_trigger((uint8_t)v2,(uint8_t)!order,63);
   check(hatVoice.oscVolEg.decay==ref_hatVoice.oscVolEg.decay&&fabsf(hatVoice.oscVolEg.decay-.4f)<1e-6f,"half-closed geometric decay reference");
   check(hatVoice.velo==ref_hatVoice.velo&&hatVoice.velo==(float)(v1>v2?v1:v2)/127.f,"half-closed higher velocity reference");
   systick_ticks++;HiHat_trigger(20,(uint8_t)order,60);ref_HiHat_trigger(20,(uint8_t)order,60);
   check(hatVoice.oscVolEg.decay==ref_hatVoice.oscVolEg.decay&&hatVoice.oscVolEg.decay==(order?.8f:.2f),"half-closed state expires next tick");
 }
 // Round trip the actual sidecar functions, including CRC/short-file recovery.
 present=0;memset(activeParameters,255,sizeof(activeParameters));preset_loadPerformanceExtension();
 check(activeParameters[PAR_MASTER_FILTER]==63&&activeParameters[PAR_VCA7]==127&&fxOutput==0,"missing sidecar defaults");
 check(activeParameters[PAR_PERF_RANDOM_VELO]==100&&activeParameters[PAR_PERF_AVL]==100,"old/missing sidecar neutral velocity defaults");
 performance_set(PAR_PERF_RANDOM_VELO,255);performance_set(PAR_PERF_AVL,255);
 check(activeParameters[PAR_PERF_RANDOM_VELO]==100&&activeParameters[PAR_PERF_AVL]==200,"velocity controls clamp to legal ranges");
 performance_set(PAR_PERF_RANDOM_VELO,37);performance_set(PAR_PERF_AVL,163);
 activeParameters[PAR_PATTERN_SCALE]=7;
 activeParameters[PAR_FX_OUTPUT_MODE]=1;
 for(unsigned i=1;i<PERFORMANCE_EXTRA_BYTES;i++)activeParameters[PAR_FX_OUTPUT_MODE+i]=(uint8_t)(i*7%128);
 activeParameters[PAR_CLOCK_OFFSET]=37;activeParameters[PAR_CLOCK_OFFSET_FINE]=4;
 uint8_t saved[PERFORMANCE_EXTRA_BYTES];memcpy(saved,&activeParameters[PAR_FX_OUTPUT_MODE],sizeof(saved));
 check(preset_savePerformanceExtension()==FR_OK&&fileLength==31,"versioned 31-byte sidecar saved");
 memset(&activeParameters[PAR_FX_OUTPUT_MODE],0,PERFORMANCE_EXTRA_BYTES);fxOutput=0;activeParameters[PAR_PERF_RANDOM_VELO]=activeParameters[PAR_PERF_AVL]=0;
 preset_loadPerformanceExtension();check(!memcmp(saved,&activeParameters[PAR_FX_OUTPUT_MODE],sizeof(saved)),"sidecar exact round trip");
 check(activeParameters[PAR_PERF_RANDOM_VELO]==37&&activeParameters[PAR_PERF_AVL]==163&&activeParameters[PAR_PATTERN_SCALE]==7,"v4 velocity round trip leaves pattern-preview byte untouched");
 for(unsigned i=0;i<PERFORMANCE_EXTRA_BYTES;i++)performance_set((uint16_t)(PAR_FX_OUTPUT_MODE+i),activeParameters[PAR_FX_OUTPUT_MODE+i]);
 for(unsigned i=0;i<7;i++)check(sendValues[i]==saved[4+i]&&vcaValues[i]==saved[11+i],"restored mode does not replace saved sends/VCAs");
 check(clockCoarse==37&&clockFine==4,"clock offset restored");
 disk[7]='3';fileLength=29;uint8_t v3sum=0;for(unsigned i=8;i<28;i++)v3sum=(uint8_t)(v3sum+disk[i]);disk[28]=v3sum;
 activeParameters[PAR_GLOBAL_SCALE]=6;
 preset_loadPerformanceExtension();check(activeParameters[PAR_PERF_RANDOM_VELO]==100&&activeParameters[PAR_PERF_AVL]==100&&activeParameters[PAR_GLOBAL_SCALE]==6,"v3 preserves scale and defaults both new velocity controls");
 disk[7]='4';fileLength=31;disk[28]=255;disk[29]=255;uint8_t v4sum=0;for(unsigned i=8;i<30;i++)v4sum=(uint8_t)(v4sum+disk[i]);disk[30]=v4sum;
 preset_loadPerformanceExtension();check(activeParameters[PAR_PERF_RANDOM_VELO]==100&&activeParameters[PAR_PERF_AVL]==100,"v4 invalid velocity fields default neutral");
 disk[7]='1';fileLength=27;uint8_t oldSum=0;for(unsigned i=8;i<26;i++)oldSum=(uint8_t)(oldSum+disk[i]);disk[26]=oldSum;
 preset_loadPerformanceExtension();check(activeParameters[PAR_VCA7]==saved[17]&&activeParameters[PAR_CLOCK_OFFSET]==50&&activeParameters[PAR_CLOCK_OFFSET_FINE]==0,"v1 sidecar retains controls and defaults clock");
 disk[7]='2';fileLength=29;disk[26]=saved[18];disk[27]=saved[19];uint8_t newSum=0;for(unsigned i=8;i<28;i++)newSum=(uint8_t)(newSum+disk[i]);disk[28]=newSum;
 disk[12]^=1;preset_loadPerformanceExtension();check(activeParameters[PAR_MASTER_FILTER]==63&&activeParameters[PAR_VCA1]==127,"bad checksum uses safe defaults");
 fileLength=8;preset_loadPerformanceExtension();check(activeParameters[PAR_VCA7]==127,"truncated sidecar safe defaults");
 shortWrite=1;check(preset_savePerformanceExtension()==FR_DISK_ERR,"short sidecar write reported");
 printf("EDIT/SCALE/HAT/STORAGE PASS %u assertions\n",checks);return 0;
}
'''
(OUT/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
(OUT/'contract.c').write_text(prelude+code+'\n'+tests)
if os.name=='nt':
    vs=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /I. /I"{ROOT/"Core/Inc"}" /Fe:contract.exe contract.c && contract.exe',shell=True,cwd=OUT,check=True)
else:
    subprocess.run(['cc','-O2','-std=c11','-I.','-I'+str(ROOT/'Core/Inc'),'contract.c','-lm','-o','contract'],cwd=OUT,check=True)
    subprocess.run([str(OUT/'contract')],cwd=OUT,check=True)
