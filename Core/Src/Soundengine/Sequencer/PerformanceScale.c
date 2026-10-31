/* SPDX-License-Identifier: GPL-3.0-only
 * Pattern divisions on a straight 96-PPQ clock. Twelve uses page slots 1-12.
 */
#include "Soundengine/Sequencer/PerformanceScale.h"
static const uint8_t divisions[8]={2,4,6,8,12,16,24,32};
static uint8_t active=16,selected,pending,patternMode=16,requested=16;
uint8_t perf_scaleDivision(uint8_t index){return divisions[index<8 ? index : 5];}
uint8_t perf_scaleIndex(uint8_t division)
{
    for(uint8_t i=0;i<8;i++)if(divisions[i]==division)return i;
    return 5;
}
void perf_scaleSet(uint8_t mode,uint8_t running)
{
    selected=mode>8 ? 0 : mode;
    requested=selected ? perf_scaleDivision((uint8_t)(selected-1)) : patternMode;
    if(running)pending=1;
    else {active=requested;pending=0;}
}
void perf_scaleSetPattern(uint8_t division,uint8_t running)
{
    patternMode=perf_scaleDivision(perf_scaleIndex(division));
    perf_scaleSet(selected,running);
}
uint8_t perf_scaleCommit(void)
{
    uint8_t changed=(uint8_t)(pending&&active!=requested);
    if(pending)active=requested;
    pending=0;
    return changed;
}
uint8_t perf_scaleMode(void){return active;}
uint8_t perf_scaleMidiClocks(void){return (uint8_t)(96u/active);}
uint8_t perf_scaleTicks(void){return (uint8_t)(384u/active);}
uint16_t perf_scaleFrames(void){return (uint16_t)(768u/active);}
uint8_t perf_scaleAllowed(uint8_t step){return (uint8_t)(active!=12 || (step&15u)<12);}
uint8_t perf_scaleCount(uint8_t length)
{
    if(!length||length>64)length=16;
    uint8_t count=0;
    for(uint8_t i=0;i<length;i++)count+=perf_scaleAllowed(i);
    return count;
}
uint8_t perf_scaleToSource(uint8_t ordinal,uint8_t length)
{
    if(!length||length>64)length=16;
    for(uint8_t i=0;i<length;i++)if(perf_scaleAllowed(i)) {
        if(!ordinal)return i;
        ordinal--;
    }
    return 0;
}
uint8_t perf_scaleToOrdinal(uint8_t source,uint8_t length)
{
    if(!length||length>64)length=16;
    uint8_t ordinal=0;
    for(uint8_t i=0;i<source&&i<length;i++)ordinal+=perf_scaleAllowed(i);
    return ordinal;
}
uint8_t perf_scaleNext(int16_t source,uint8_t length)
{
    if(!length||length>64)length=16;
    do {source++;if(source>=length)source=0;}while(!perf_scaleAllowed((uint8_t)source));
    return (uint8_t)source;
}
/* Old override indices: pat/16/12a/12b/12c. */
uint8_t perf_scaleLegacyOverride(uint8_t value)
{
    return value==1 ? 6 : value>=2&&value<=4 ? 5 : 0;
}

uint8_t perf_scaleCommitOnBar(uint16_t frame)
{
    return frame==0 ? perf_scaleCommit() : 0;
}
uint8_t perf_scaleHasPending(void){return (uint8_t)(pending && active!=requested);}
