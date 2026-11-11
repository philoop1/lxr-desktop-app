/* SPDX-License-Identifier: GPL-3.0-only */
#include "menu/PerformanceControls.h"
#include "Parameters.h"
#include "Soundengine/DSPAudio/mixer.h"
#include "Soundengine/DSPAudio/PerformanceMasterFilter.h"
#include "Soundengine/Sequencer/PerformanceScale.h"
#include "Soundengine/Sequencer/clockSync.h"
/* 0.2.79 send page snd, FxBus.c (no header: the host checks link this file alone) */
void FxBus_selectType(uint8_t type);
uint8_t FxBus_sendType(uint8_t index);
uint8_t InsertFx_setValue(uint8_t index, uint8_t value); /* 0.2.81 */
void seq_storeIntSend(uint8_t voice,uint8_t value);	// 0.2.70, sequencer.c
void masterComp_set(uint8_t idx,uint8_t value);	// 0.2.71, Compressor.c
static const uint8_t mcompDefaults[7]={0,3,10,40,90,0,100};	// off, 4:1
static uint8_t mcompClamp(uint8_t i,uint8_t v){return i==0?(uint8_t)!!v:i==1?(v>5?3:v):i==6?(v>100?100:v):(v>127?127:v);}
extern uint8_t activeParameters[NUM_PARAMS];
extern uint8_t seq_isRunning(void);
extern void seq_setHumanize(uint8_t lane,uint8_t amount);
extern uint8_t drum_highDamp;
typedef char PerformanceGlobalsFit[(PAR_CPU_USE-PAR_BEGINNING_OF_GLOBALS==64)?1:-1];
typedef char PerformanceExtensionLayout[(PAR_CLOCK_OFFSET_FINE-PAR_FX_OUTPUT_MODE+1==PERFORMANCE_EXTRA_BYTES)?1:-1];
static const uint8_t defaults[PERFORMANCE_EXTRA_BYTES]={0,63,0,0,0,0,0,0,0,0,0,127,127,127,127,127,127,127,50,0};
void performance_resetExtended(void)
{
    for(uint8_t i=0;i<PERFORMANCE_EXTRA_BYTES;i++)activeParameters[PAR_FX_OUTPUT_MODE+i]=defaults[i];
    activeParameters[PAR_PERF_RANDOM_VELO]=100;
    activeParameters[PAR_PERF_AVL]=100;
    for(uint8_t i=0;i<4;i++)activeParameters[PAR_HUMANIZE1+i]=0;
    activeParameters[PAR_HIGH_DAMP]=0;
    activeParameters[PAR_LOAD_INT_SEND]=1;
    for(uint8_t i=0;i<7;i++)activeParameters[PAR_MCOMP_ON+i]=mcompDefaults[i];
}
void performance_validateExtended(void)
{
    if(activeParameters[PAR_PERF_RANDOM_VELO]>100)activeParameters[PAR_PERF_RANDOM_VELO]=100;
    if(activeParameters[PAR_PERF_AVL]>200)activeParameters[PAR_PERF_AVL]=100;
    for(uint8_t i=0;i<4;i++)if(activeParameters[PAR_HUMANIZE1+i]>127)activeParameters[PAR_HUMANIZE1+i]=0;
    if(activeParameters[PAR_HIGH_DAMP]>100)activeParameters[PAR_HIGH_DAMP]=0;
    if(activeParameters[PAR_LOAD_INT_SEND]>1)activeParameters[PAR_LOAD_INT_SEND]=1;
    for(uint8_t i=0;i<7;i++)activeParameters[PAR_MCOMP_ON+i]=mcompClamp(i,activeParameters[PAR_MCOMP_ON+i]);
    for(uint8_t i=0;i<PERFORMANCE_EXTRA_BYTES;i++)
        if(activeParameters[PAR_FX_OUTPUT_MODE+i]>(i?127:1))activeParameters[PAR_FX_OUTPUT_MODE+i]=defaults[i];
    if(activeParameters[PAR_CLOCK_OFFSET]>80)activeParameters[PAR_CLOCK_OFFSET]=50;
    if(activeParameters[PAR_CLOCK_OFFSET_FINE]>9 || activeParameters[PAR_CLOCK_OFFSET]==80)
        activeParameters[PAR_CLOCK_OFFSET_FINE]=0;
}
void performance_prepareLoaded(void)
{
    /* Establish output mode before applying saved sends, without replacing
     * loaded values with the mode-switch defaults used for live edits. */
    mixer_setFxOutputMode(activeParameters[PAR_FX_OUTPUT_MODE]);
    for(uint8_t i=0;i<4;i++)seq_setHumanize(i,activeParameters[PAR_HUMANIZE1+i]);
    drum_highDamp=activeParameters[PAR_HIGH_DAMP]>100?0:activeParameters[PAR_HIGH_DAMP];
    for(uint8_t i=0;i<7;i++)masterComp_set(i,activeParameters[PAR_MCOMP_ON+i]);
}
uint8_t performance_set(uint16_t parameter,uint8_t value)
{
    if(parameter>=PAR_VCA1&&parameter<=PAR_VCA7) {
        value=value>127?127:value;
        activeParameters[parameter]=value;
        mixer_handleVcaCc((uint8_t)(20+parameter-PAR_VCA1),value);
        return 1;
    }
    if(parameter>=PAR_HUMANIZE1&&parameter<=PAR_HUMANIZE4) {
        value=value>127?127:value;
        activeParameters[parameter]=value;
        seq_setHumanize((uint8_t)(parameter-PAR_HUMANIZE1),value);
        return 1;
    }
    if(parameter>=PAR_INT_SEND1&&parameter<=PAR_INT_SEND6) {
        value=value>127?127:value;
        activeParameters[parameter]=value;
        mixer_setIntSend((uint8_t)(parameter-PAR_INT_SEND1),value);
        /* 0.2.70: the edit belongs to the playing pattern, like a step edit */
        seq_storeIntSend((uint8_t)(parameter-PAR_INT_SEND1),value);
        return 1;
    }
    if(parameter>=PAR_INS_DST_MIX&&parameter<=PAR_INS_DST_OUT) {
        activeParameters[parameter]=InsertFx_setValue((uint8_t)(parameter-PAR_INS_DST_MIX),value);
        return 1;
    }
    if(parameter==PAR_SEND_FX) {
        /* 0.2.79: the send page picks the bus effect; typ follows so the kit stores it */
        value=value>3?0:value;
        activeParameters[PAR_SEND_FX]=value;
        const uint8_t type=FxBus_sendType(value);
        activeParameters[PAR_FX_TYPE]=type;
        FxBus_selectType(type);
        return 1;
    }
    if(parameter>=PAR_MCOMP_ON&&parameter<=PAR_MCOMP_MIX) {
        const uint8_t i=(uint8_t)(parameter-PAR_MCOMP_ON);
        value=mcompClamp(i,value);
        activeParameters[parameter]=value;
        masterComp_set(i,value);
        return 1;
    }
    if(parameter>=PAR_FX_SEND1&&parameter<=PAR_FX_SEND7) {
        value=value>127?127:value;
        activeParameters[parameter]=value;
        mixer_handleFxSendCc((uint8_t)(30+parameter-PAR_FX_SEND1),value);
        return 1;
    }
    switch(parameter) {
    case PAR_PERF_RANDOM_VELO:
        value=value>100?100:value;break;
    case PAR_PERF_AVL:
        value=value>200?200:value;break;
    case PAR_HIGH_DAMP:
        value=value>100?100:value;drum_highDamp=value;break;
    case PAR_MASTER_FILTER_ENABLE:
        value=(uint8_t)!!value;mixer_setMasterFilterEnabled(value);break;
    case PAR_GLOBAL_SCALE:
        value=value>5?PERF_SPEED_NEUTRAL:value;perf_speedSet(value,seq_isRunning());break;
    case PAR_SCALE_TRANSFORM:
        value=value>3?0:value;perf_transformSet(value,seq_isRunning());break;
    case PAR_FX_SEND_MODE:
        value=value>3?0:value;mixer_setFxSendMode(value);break;
    case PAR_FX_OUTPUT_MODE:
        value=(uint8_t)!!value;
        if(value!=mixer_getFxOutputMode()) {
            mixer_setFxOutputMode(value);
            for(uint8_t i=0;i<7;i++)activeParameters[PAR_FX_SEND1+i]=value?64:0;
        }
        break;
    case PAR_MASTER_FILTER:
        value=value>127?127:value;mixer_setMasterFilter(value);break;
    case PAR_MASTER_FILTER_RESO:
        value=value>127?127:value;mixer_setMasterFilterResonance(value);break;
    case PAR_MASTER_FILTER_DRIVE:
        value=value>127?127:value;mixer_setMasterFilterDrive(value);break;
    case PAR_CLOCK_OFFSET:
        value=value>80?80:value;
        if(value==80)activeParameters[PAR_CLOCK_OFFSET_FINE]=0;
        sync_setClockOffset(value,activeParameters[PAR_CLOCK_OFFSET_FINE]);
        break;
    case PAR_CLOCK_OFFSET_FINE:
        value=(value>9 || activeParameters[PAR_CLOCK_OFFSET]==80)?0:value;
        sync_setClockOffset(activeParameters[PAR_CLOCK_OFFSET],value);
        break;
    default:return 0;
    }
    activeParameters[parameter]=value;
    return 1;
}
