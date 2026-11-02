/* SPDX-License-Identifier: GPL-3.0-only */
#include "menu/PerformanceControls.h"
#include "Parameters.h"
#include "Soundengine/DSPAudio/mixer.h"
#include "Soundengine/DSPAudio/PerformanceMasterFilter.h"
#include "Soundengine/Sequencer/PerformanceScale.h"
#include "Soundengine/Sequencer/clockSync.h"
extern uint8_t activeParameters[NUM_PARAMS];
extern uint8_t seq_isRunning(void);
typedef char PerformanceGlobalsFit[(PAR_CPU_USE-PAR_BEGINNING_OF_GLOBALS==64)?1:-1];
typedef char PerformanceExtensionLayout[(PAR_CLOCK_OFFSET_FINE-PAR_FX_OUTPUT_MODE+1==PERFORMANCE_EXTRA_BYTES)?1:-1];
static const uint8_t defaults[PERFORMANCE_EXTRA_BYTES]={0,63,0,0,0,0,0,0,0,0,0,127,127,127,127,127,127,127,50,0};
void performance_resetExtended(void)
{
    for(uint8_t i=0;i<PERFORMANCE_EXTRA_BYTES;i++)activeParameters[PAR_FX_OUTPUT_MODE+i]=defaults[i];
    activeParameters[PAR_PERF_RANDOM_VELO]=100;
    activeParameters[PAR_PERF_AVL]=100;
}
void performance_validateExtended(void)
{
    if(activeParameters[PAR_PERF_RANDOM_VELO]>100)activeParameters[PAR_PERF_RANDOM_VELO]=100;
    if(activeParameters[PAR_PERF_AVL]>200)activeParameters[PAR_PERF_AVL]=100;
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
}
uint8_t performance_set(uint16_t parameter,uint8_t value)
{
    if(parameter>=PAR_VCA1&&parameter<=PAR_VCA7) {
        value=value>127?127:value;
        activeParameters[parameter]=value;
        mixer_handleVcaCc((uint8_t)(20+parameter-PAR_VCA1),value);
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
