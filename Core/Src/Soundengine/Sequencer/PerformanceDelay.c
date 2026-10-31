/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only
 * Mutador-style repeat chains, adapted from 8 substeps to desktop 96 PPQ.
 * Bounce, velocity target and per-repeat pitch are captured per chain.
 */
#include "Soundengine/Sequencer/PerformanceDelay.h"
#include <string.h>

typedef struct {
    uint8_t source, remain, total, target, bounce, exponent, lane;
    int8_t pitch;
    uint16_t period;
    uint32_t countdown;
} DelayChain;
static DelayChain chains[7][4];
static PerfDelayConfig config={0,6,0,63,5,0,64,127,0};
static PerfGroove groove;
void perf_delaySetGroove(const PerfGroove *next) { groove=*next; }

void perf_delayReset(void) { memset(chains,0,sizeof(chains)); }
void perf_delayConfigure(PerfDelayConfig next)
{
    if(next.chance>100) next.chance=100;
    if(next.sync>15) next.sync=15;
    if(next.count>32) next.count=32;
    if(next.target>10) next.target=10;
    next.poly=(uint8_t)!!next.poly;
    next.mask &= 127;
    if(next.pitch < -12) next.pitch=-12;
    if(next.pitch > 12) next.pitch=12;
    if(config.poly!=next.poly) perf_delayReset();
    config=next;
}
uint8_t perf_delayIsPoly(void) { return config.poly; }

static uint32_t nextPeriod(const DelayChain *chain)
{
    uint32_t period=chain->period;
    int16_t bounce=(int16_t)chain->bounce-63;
    uint8_t done=(uint8_t)(chain->total-chain->remain);
    if(!bounce || !done) return period;
    uint32_t amount=(uint32_t)(bounce<0?-bounce:bounce);
    uint32_t shape;
    if(chain->exponent>=64) {
        uint32_t curve=(uint32_t)done*done-done;
        shape=done+(curve*(chain->exponent-64)+31u)/63u;
    } else
        shape=1u+(((uint32_t)done-1u)*chain->exponent+32u)/64u;
    uint32_t scale=4096u+amount*amount*shape;
    // Use 64-bit multiplication before bounding; avoid source uint16 wrap.
    if(bounce>0) period=(uint32_t)(((uint64_t)period*4096u+scale/2u)/scale);
    else period=(uint32_t)(((uint64_t)period*scale+2048u)/4096u);
    if(!period) period=1;
    if(period>65535) period=65535;
    return period;
}

void perf_delayFineTick(void (*emit)(uint8_t,uint8_t,uint8_t,int16_t))
{
    for(uint8_t track=0;track<7;track++) for(uint8_t slot=0;slot<4;slot++) {
        DelayChain *chain=&chains[track][slot];
        if(!chain->remain) continue;
        if(chain->countdown) chain->countdown--;
        if(chain->countdown) continue;
        uint8_t done=(uint8_t)(chain->total-chain->remain+1);
        uint8_t target=(uint8_t)(chain->target*10u);
        uint8_t scale=(uint8_t)(100u-((uint16_t)(100u-target)*done)/chain->total);
        emit(track,chain->source,scale,(int16_t)chain->pitch*done);
        chain->remain--;
        chain->countdown=perf_grooveRepeat(&groove,(uint16_t)nextPeriod(chain),&chain->lane);
    }
}

void perf_delayTick(void (*emit)(uint8_t,uint8_t,uint8_t,int16_t))
{
    perf_delayFineTick(emit);
    perf_delayFineTick(emit);
}

static void startChain(uint8_t track,uint8_t source,uint8_t lane)
{
    // Exact desktop 96-PPQ periods for Mutador's named rate divisions.
    // Do not multiply its rounded 8-substep triplets by three: that drifts.
    static const uint16_t ticks[16]={384,288,192,144,128,96,72,64,48,36,32,24,16,12,6,3};
    uint8_t limit=config.poly?4:1;
    for(uint8_t slot=0;slot<limit;slot++) if(!chains[track][slot].remain) {
        DelayChain *chain=&chains[track][slot];
        chain->source=source;
        chain->remain=chain->total=config.count;
        chain->target=config.target;
        chain->bounce=config.bounce;
        chain->exponent=config.exponent;
        chain->pitch=config.pitch;
        chain->period=ticks[config.sync];
        chain->lane=lane&3u;
        chain->countdown=perf_grooveRepeat(&groove,chain->period,&chain->lane);
        return;
    }
}

void perf_delayOfferAt(uint8_t candidates,const uint8_t sources[7],const uint8_t lanes[7],uint32_t (*randomValue)(void))
{
    candidates &= config.mask;
    if(!candidates || !config.count || !config.chance) return;
    if(config.poly) {
        for(uint8_t track=0;track<7;track++) if(candidates&(1u<<track))
            if(config.chance==100 || randomValue()%100u < config.chance)
                startChain(track,sources[track],lanes[track]);
    } else {
        for(uint8_t track=0;track<7;track++)
            for(uint8_t slot=0;slot<4;slot++) if(chains[track][slot].remain) return;
        if(config.chance<100 && randomValue()%100u>=config.chance) return;
        uint8_t count=0;
        for(uint8_t track=0;track<7;track++) if(candidates&(1u<<track)) count++;
        uint8_t chosen=(uint8_t)(randomValue()%count);
        for(uint8_t track=0;track<7;track++) if(candidates&(1u<<track)) {
            if(!chosen) {startChain(track,sources[track],lanes[track]);return;}
            chosen--;
        }
    }
}

void perf_delayOffer(uint8_t candidates,const uint8_t sources[7],uint32_t (*randomValue)(void))
{
    perf_delayOfferAt(candidates,sources,sources,randomValue);
}
