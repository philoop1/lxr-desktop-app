/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only
 * Mutador RST/CSR and 606 loop behavior, plus LXR2BC per-step Scarcity,
 * adapted to desktop's 64 main steps and shifted/flammed lookahead events.
 */
#include "Soundengine/Sequencer/PerformanceSteps.h"
#include <string.h>

static PerfTrack tracks[7];
static uint8_t rst, csr, psc=100, pst=100;
static uint8_t loopActive, loopStart, loopEnd;
static uint8_t cnt=100;

void perf_setNoteProbability(uint8_t amount) { cnt=amount>100?100:amount; }
uint8_t perf_scaleProbability(uint8_t probability)
{
    return (uint8_t)(((uint16_t)probability*cnt+50u)/100u);
}

void perf_resetSteps(void) { memset(tracks, 0, sizeof(tracks)); }

void perf_configure(uint8_t randomStep, uint8_t repeatChance,
                    uint8_t scarcity, uint8_t probability)
{
    randomStep = randomStep > 100 ? 100 : randomStep;
    repeatChance = repeatChance > 127 ? 127 : repeatChance;
    scarcity = scarcity > 100 ? 100 : scarcity;
    probability = probability > 100 ? 100 : probability;
    if(rst != randomStep || csr != repeatChance || psc != scarcity)
        for(uint8_t i=0;i<7;i++) tracks[i].valid=0;
    rst=randomStep; csr=repeatChance; psc=scarcity; pst=probability;
}

static PerfStep plan(PerfTrack *track, uint8_t timeline, uint8_t length,
                     uint64_t active, uint32_t (*randomValue)(void))
{
    PerfStep step = {timeline, 0, 0, timeline};
    if(rst && randomValue()%100u < rst)
        step.source = (uint8_t)(randomValue()%length);
    // Mutador: CSR replays the previous active Main Step; a failed choice
    // replaces the history with the new source and its active flag.
    if(csr && track->hasLast && (csr==127 || (randomValue()&127u)<csr))
        step.source=track->lastSource;
    else {
        track->lastSource=step.source;
        track->hasLast=(uint8_t)((active >> step.source)&1u);
    }
    // BC Scarcity: one decision per Main Step, shared by all its sub-events.
    step.drop=(uint8_t)(psc<100 && randomValue()%100u >= psc);
    uint32_t roll=randomValue();
    step.probability=(uint8_t)(roll%100u + 1u);
    step.flamRoll=(uint8_t)((roll/100u)%100u + 1u);
    static uint32_t nextEventId=0;
    step.eventId=++nextEventId;
    if(!step.eventId) step.eventId=++nextEventId;
    return step;
}

const PerfTrack *perf_advance(uint8_t trackNr, uint8_t timeline, uint8_t length,
                            uint64_t active, uint32_t (*randomValue)(void))
{
    if(trackNr>=7) return 0;
    if(!length || length>64) length=16;
    timeline=(uint8_t)(timeline%length);
    PerfTrack *track=&tracks[trackNr];
    if(track->length!=length || track->next.timeline!=timeline) {
        memset(track,0,sizeof(*track));
        track->prev2=plan(track,(uint8_t)((timeline+2u*length-2u)%length),length,active,randomValue);
        track->prev=plan(track, timeline ? timeline-1 : length-1, length,active,randomValue);
        track->hasLast=0; // a pre-roll event is not a previously played note
        track->current=plan(track,timeline,length,active,randomValue);
        track->next=plan(track,(uint8_t)((timeline+1u)%length),length,active,randomValue);
    } else {
        track->prev2=track->prev;
        track->prev=track->current;
        if(track->valid) {
            track->current=track->next;
            track->next=track->next2;
        } else {
            // A live knob change replans the next boundary, but CSR must
            // remember the source that actually played, not a discarded
            // lookahead choice. Preserve previous shifted/flammed tails too.
            track->lastSource=track->prev.source;
            track->hasLast=(uint8_t)((active >> track->prev.source)&1u);
            track->current=plan(track,timeline,length,active,randomValue);
            track->next=plan(track,(uint8_t)((timeline+1u)%length),length,active,randomValue);
        }
    }
    track->next2=plan(track,(uint8_t)((timeline+2u)%length),length,active,randomValue);
    track->length=length; track->valid=1;
    return track;
}

uint8_t perf_allowHit(uint32_t (*randomValue)(void))
{
    return (uint8_t)(pst==100 || (pst && randomValue()%100u < pst));
}

void perf_setLoop(uint8_t start, uint8_t end)
{
    if(start>63) start=63;
    if(end>63) end=63;
    if(start>end) { uint8_t tmp=start; start=end; end=tmp; }
    loopStart=start; loopEnd=end; loopActive=1;
}
void perf_clearLoop(void) { loopActive=0; }
uint8_t perf_getLoop(uint8_t *start, uint8_t *end)
{
    if(start) *start=loopStart;
    if(end) *end=loopEnd;
    return loopActive;
}
uint8_t perf_nextPattern(uint8_t active)
{
    if(!loopActive) return active;
    if(active<loopStart || active>=loopEnd) return loopStart;
    return (uint8_t)(active+1);
}

// Mutador's random attenuation: minimum percent up to unchanged velocity.
uint8_t perf_randomVelocity(uint8_t velocity,uint8_t minimum,uint32_t (*randomValue)(void))
{
    if(minimum>=100 || !velocity)return velocity;
    uint8_t scale=(uint8_t)(minimum+randomValue()%(101u-minimum));
    return (uint8_t)(((uint16_t)velocity*scale+50u)/100u);
}
// Stored 0..200 represents -100..+100 percent; 100 is neutral.
uint8_t perf_adjustVelocity(uint8_t velocity,uint8_t gain)
{
    if(velocity>127)velocity=127;
    if(gain>200)gain=200;
    uint16_t scaled=(uint16_t)(((uint16_t)velocity*gain+50u)/100u);
    return scaled>127 ? 127 : (uint8_t)scaled;
}
void perf_formatVelocityGain(char text[4],uint8_t gain)
{
    if(gain>200)gain=200;
    int16_t value=(int16_t)gain-100;
    uint8_t magnitude=(uint8_t)(value<0 ? -value : value);
    memset(text,' ',4);
    text[3]=(char)('0'+magnitude%10);
    uint8_t position=3;
    if(magnitude>=10)text[--position]=(char)('0'+(magnitude/10)%10);
    if(magnitude>=100)text[--position]='1';
    if(value)text[position-1]=value<0 ? '-' : '+';
}
