/* SPDX-License-Identifier: GPL-3.0-only
 * Pattern divisions on a straight 96-PPQ clock. Twelve uses page slots 1-12.
 * sct is a live conversion chosen by the active rate. A quaternary rate drops
 * one step of four and runs 4/3 slower (3a/b/c); a ternary rate runs 3/4 of the
 * step time with one gap slot in four (4a/b/c). Each pair is an exact inverse.
 */
#include "Soundengine/Sequencer/PerformanceScale.h"
static const uint8_t divisions[8]={2,4,6,8,12,16,24,32};
static uint8_t active=16,pending,requested=16;
/* spd: octaves relative to the pattern rate, -3 (/8) to +2 (*4). */
static int8_t speed,requestedSpeed;
static uint8_t transform,transformRequested,transformPending,slot,gap;
/* Step index dropped by 3a/b/c and slot left empty by 4a/b/c, indexed by sct. */
/* Same letters as LXR1 Mutador 12a/12b/12c: a = 3rd, b = 2nd, c = 4th. */
static const uint8_t transformOffset[4]={0,2,1,3};
uint8_t perf_scaleIsTernary(void){return (uint8_t)(!(active%3u));}
static uint8_t perf_scaleDropping(void){return (uint8_t)(transform && !perf_scaleIsTernary());}
static uint8_t perf_scaleGapping(void){return (uint8_t)(transform && perf_scaleIsTernary());}
/* Six ticks is the floor: 64 steps a bar, or 48 on ternary rates. */
static uint16_t perf_scaleScaled(uint16_t ticksPerBar)
{
    uint16_t ticks=(uint16_t)(ticksPerBar/active);
    if(speed<0)return (uint16_t)(ticks<<(uint8_t)(-speed));
    for(int8_t i=0;i<speed && ticks>=12u;i++)ticks>>=1;
    return ticks;
}
void perf_transformSet(uint8_t mode,uint8_t running)
{
    transformRequested=mode<=3?mode:0;
    if(running)transformPending=1;
    else {transform=transformRequested;transformPending=0;}
}
uint8_t perf_transformCommit(void)
{
    const uint8_t changed=(uint8_t)(transformPending && transform!=transformRequested);
    if(transformPending)transform=transformRequested;
    transformPending=0;
    return changed;
}
/* Quarters only exist as group edges from twelve steps a bar upward. */
uint8_t perf_transformBoundary(uint16_t barFrame)
{
    uint16_t span=(uint16_t)(perf_scaleScaled(384u)*2u*(perf_scaleIsTernary()?3u:4u));
    if(span<192u)span=192u;
    if(span>768u)span=768u;
    return (uint8_t)(transformPending && !(barFrame%span));
}
void perf_scaleSlotReset(void){slot=0;gap=0;}
uint8_t perf_scaleSlotIsGap(void)
{
    gap=(uint8_t)(perf_scaleGapping() && slot==transformOffset[transform]);
    slot=(uint8_t)((slot+1u)&3u);
    return gap;
}
uint8_t perf_scaleInGap(void){return gap;}
uint8_t perf_scaleGroupMask(void){return (uint8_t)(perf_scaleIsTernary()?0u:3u);}
uint8_t perf_scaleDivision(uint8_t index){return divisions[index<8 ? index : 5];}
uint8_t perf_scaleIndex(uint8_t division)
{
    for(uint8_t i=0;i<8;i++)if(divisions[i]==division)return i;
    return 5;
}
void perf_scaleSetPattern(uint8_t division,uint8_t running)
{
    requested=perf_scaleDivision(perf_scaleIndex(division));
    if(running)pending=1;
    else {active=requested;speed=requestedSpeed;pending=0;}
}
void perf_speedSet(uint8_t index,uint8_t running)
{
    requestedSpeed=(int8_t)((index>5u?PERF_SPEED_NEUTRAL:index)-PERF_SPEED_NEUTRAL);
    if(running)pending=1;
    else {active=requested;speed=requestedSpeed;pending=0;}
}
uint8_t perf_scaleCommit(void)
{
    uint8_t changed=(uint8_t)(pending&&(active!=requested||speed!=requestedSpeed));
    if(pending){active=requested;speed=requestedSpeed;}
    pending=0;
    return changed;
}
uint8_t perf_scaleMode(void){return active;}
uint16_t perf_scaleTicks(void){return perf_scaleScaled(perf_scaleDropping()?512u:perf_scaleGapping()?288u:384u);}
uint16_t perf_scaleMidiClocks(void){return (uint16_t)(perf_scaleTicks()/4u);}
uint16_t perf_scaleFrames(void){return (uint16_t)(perf_scaleTicks()*2u);}
uint8_t perf_scaleAllowed(uint8_t step)
{
    if(active==12 && (step&15u)>=12)return 0;
    return (uint8_t)(!perf_scaleDropping() || (step&3u)!=transformOffset[transform]);
}
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
uint8_t perf_scaleCommitOnBar(uint16_t frame)
{
    return frame==0 ? perf_scaleCommit() : 0;
}
uint8_t perf_scaleHasPending(void){return (uint8_t)(pending && (active!=requested||speed!=requestedSpeed));}
