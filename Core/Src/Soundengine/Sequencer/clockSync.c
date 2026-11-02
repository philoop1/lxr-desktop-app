/*
 * clockSync.c
 *
 *  Created on: 03.02.2013
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */



#include "Soundengine/Sequencer/clockSync.h"
#include "Soundengine/Sequencer/PerformanceScale.h"

static float sync_window[WINDOW_SIZE];
float sync_timeLast = 0;
uint8_t sync_writePos = 0;
uint8_t sync_armed = 0;
static uint8_t sync_samples;
static uint32_t sync_lastClockTick;
static uint32_t sync_lastClockCycles;
static uint32_t sync_cycleWindow[WINDOW_SIZE];
static uint8_t sync_cycleSamples;
static uint8_t sync_cycleWritePos;
static uint32_t sync_nextLeadCycles;
static uint8_t sync_leadArmed;
static uint8_t sync_leadConsumed;
static uint8_t sync_barClockCnt;
static uint8_t sync_barPhaseValid;
/* Clock alone gives a pulse count, not a bar: only MIDI START places the downbeat. */
static uint8_t sync_barPhaseFromStart;
#define SYNC_CLOCK_LOST_TICKS 4000u // 1 s
static uint8_t sync_startOnNextBar;
static uint8_t sync_startLeadArmed;
static uint32_t sync_nextStartCycles;
static uint8_t sync_clockOffsetTenths=50;
static uint8_t sync_clockOffsetHundredths=0;

uint16_t sync_clockCnt = 0;
static uint8_t sync_stepFlip;

uint32_t sync_delayedStepTimer = 0;


//---------------------------------------------------------
uint16_t sync_calcBpm(float timePerPulse)
{
	// 1 Minute has 60 * 1000 [ms]
	//we have 24 pulses per quarter
	//120 bpm = 120 quarters per minute

	if(timePerPulse<=0.f) return seq_getBpm();
	float quarterDuration = 24 * (timePerPulse/4);
	float bpm = (60 * 1000) / quarterDuration;

	if(bpm>65535.f) return 65535;
	return bpm>0?(uint16_t)bpm:1;
}
//---------------------------------------------------------
//called by midi clock
void sync_tick()
{
    sync_tickAtCycles(DWT->CYCCNT);
}
void sync_tickAtCycles(uint32_t nowCycles)
{
    const uint32_t now=systick_ticks;
    const uint32_t cycleInterval=nowCycles-sync_lastClockCycles;
    if(now-sync_lastClockTick>SYNC_CLOCK_LOST_TICKS)sync_barPhaseFromStart=0;
    sync_lastClockTick=now;
    if(sync_armed && cycleInterval) {
        sync_cycleWindow[sync_cycleWritePos++]=cycleInterval;
        sync_cycleWritePos&=WINDOW_MASK;
        if(sync_cycleSamples<WINDOW_SIZE)sync_cycleSamples++;
        sync_window[sync_writePos++]=(float)cycleInterval*4000.f/(float)SystemCoreClock;
        sync_writePos&=WINDOW_MASK;
        if(sync_samples<WINDOW_SIZE) sync_samples++;
        float total=0.f;
        for(uint8_t i=0;i<sync_samples;i++) total+=sync_window[i];
        seq_setBpm(sync_calcBpm(total/sync_samples));
    }
    sync_lastClockCycles=nowCycles;
    sync_armed=1;
    if(!sync_barPhaseValid) {sync_barClockCnt=0;sync_barPhaseValid=1;}
    sync_barClockCnt=(uint8_t)((sync_barClockCnt+1u)%96u);
    if(sync_startOnNextBar && sync_barClockCnt==0) {
        sync_startOnNextBar=0;
        sync_startLeadArmed=0;
        sync_clockCnt=0;
        seq_setRunning(1);
    }
    if(sync_barClockCnt==0 && seq_applyPendingScale()) {
        sync_clockCnt=0;
        sync_leadArmed=sync_leadConsumed=0;
    }
    if(sync_clockCnt==0 && perf_transformBoundary((uint16_t)(sync_barClockCnt*8u)) &&
       seq_applyPendingTransform())
        sync_leadArmed=sync_leadConsumed=0;
    /* A six-tick step alternates one and two clocks. */
    const uint16_t clocksPerStep=(uint16_t)(perf_scaleMidiClocks()+((perf_scaleTicks()%4u)?sync_stepFlip:0u));
    if(sync_clockCnt==0) {
        if(sync_leadConsumed)sync_leadConsumed=0;
        else {seq_nextStep();seq_MidiSyncQueue(0);}
    }
    if(++sync_clockCnt>=clocksPerStep) {
        sync_clockCnt=0;
        sync_stepFlip^=1;
        sync_leadArmed=0;
        if(sync_cycleSamples && sync_clockOffsetTenths+sync_clockOffsetHundredths) {
            uint64_t total=0;
            for(uint8_t i=0;i<sync_cycleSamples;i++)total+=sync_cycleWindow[i];
            const uint32_t period=(uint32_t)(total/sync_cycleSamples);
            const uint32_t cyclesPerUs=SystemCoreClock/1000000u;
            const uint32_t offsetUs=(uint32_t)sync_clockOffsetTenths*100u+
                (uint32_t)sync_clockOffsetHundredths*10u;
            const uint32_t lead=offsetUs*cyclesPerUs;
            if(period>lead+250u*cyclesPerUs) {
                sync_nextLeadCycles=nowCycles+period-lead;
                sync_leadArmed=1;
            }
        }
    }
    if(sync_startOnNextBar && sync_barClockCnt==95 && sync_cycleSamples &&
            (sync_clockOffsetTenths || sync_clockOffsetHundredths)) {
        uint64_t total=0;
        for(uint8_t i=0;i<sync_cycleSamples;i++)total+=sync_cycleWindow[i];
        const uint32_t period=(uint32_t)(total/sync_cycleSamples);
        const uint32_t cyclesPerUs=SystemCoreClock/1000000u;
        const uint32_t offsetUs=(uint32_t)sync_clockOffsetTenths*100u+
            (uint32_t)sync_clockOffsetHundredths*10u;
        const uint32_t lead=offsetUs*cyclesPerUs;
        if(period>lead+250u*cyclesPerUs) {
            sync_nextStartCycles=nowCycles+period-lead;
            sync_startLeadArmed=1;
        }
    }
}
void sync_requestStartOnNextBar(void)
{
    sync_startLeadArmed=0;
    if(!sync_barPhaseFromStart) {
        /* The next clock becomes the downbeat. */
        sync_barPhaseValid=1;
        sync_barClockCnt=95;
        sync_startOnNextBar=0;
        sync_clockCnt=0;
        seq_setRunning(1);
    } else if(sync_barClockCnt==0) {
        sync_startOnNextBar=0;
        sync_clockCnt=0;
        seq_setRunning(1);
    } else sync_startOnNextBar=1;
}
uint8_t sync_processStartLead(void)
{
    if(!sync_startLeadArmed || (int32_t)(DWT->CYCCNT-sync_nextStartCycles)<0)return 0;
    sync_startLeadArmed=0;
    sync_startOnNextBar=0;
    sync_clockCnt=0;
    sync_leadArmed=0;
    sync_leadConsumed=1;
    seq_setRunning(1);
    seq_nextStep();
    seq_MidiSyncQueue(0);
    return 1;
}
void sync_setClockOffset(uint8_t tenths,uint8_t hundredths)
{
    sync_clockOffsetTenths=tenths>80?50:tenths;
    sync_clockOffsetHundredths=(hundredths>9 || sync_clockOffsetTenths==80)?0:hundredths;
    sync_leadArmed=0;
}
uint8_t sync_shouldLeadStep(void)
{
    return sync_leadArmed && !sync_leadConsumed &&
        (int32_t)(DWT->CYCCNT-sync_nextLeadCycles)>=0;
}
void sync_markLeadStep(void)
{
    if(sync_barClockCnt==95)seq_applyPendingScale();
    sync_leadArmed=0;
    sync_leadConsumed=1;
}
//---------------------------------------------------------
void sync_midiResetPosition()
{
	sync_clockCnt = 0;
	sync_barClockCnt=0;
	sync_barPhaseValid=1;
	sync_barPhaseFromStart=1;
	sync_lastClockTick=systick_ticks;
	sync_startOnNextBar=0;
	sync_startLeadArmed=0;
	sync_leadArmed=0;
	sync_leadConsumed=0;
	seq_resetPosition();
}
//---------------------------------------------------------
void sync_midiStartStop(uint8_t isStart)
{
	if(isStart) {
		sync_startOnNextBar=0;
		sync_startLeadArmed=0;
		// this message does NOT mean start immediately! it just 'arms' the seq to start at the next MIDI_CLOCK received

		seq_setRunning(1);
		sync_timeLast = systick_ticks;
		sync_armed=0;
		sync_samples=0;
		sync_writePos=0;
		sync_cycleSamples=0;
		sync_cycleWritePos=0;
		sync_leadArmed=0;
		sync_leadConsumed=0;
	} else {
		sync_startOnNextBar=0;
		sync_startLeadArmed=0;
		sync_leadArmed=0;
		sync_leadConsumed=0;
		seq_setRunning(0);
	}
}
//---------------------------------------------------------
uint16_t sync_getClockCnt()
{
	return sync_clockCnt;
}
//---------------------------------------------------------
