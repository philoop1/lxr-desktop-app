/*
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#include "Soundengine/AudioCodecManager.h"

#include <string.h>
#include "Soundengine/datatypes.h"
//------------------------------------------------------------------
#if DMA_MODE_ACTIVE
INDTCMZ int16_t dma_buffer[OUTPUT_DMA_SIZE*4];
INDTCMZ int16_t dma_buffer2[OUTPUT_DMA_SIZE*4];
#endif

volatile INDTCMZ uint8_t bCurrentSampleValid = 0;
static uint32_t cpuBlockBudget = 1;
static uint32_t cpuBlockStart;
static volatile uint8_t cpuUsePercent;
static volatile uint8_t cpuUsePeakPercent;
volatile uint32_t audioCodec_blockRequest;
volatile uint16_t audioCodec_lateBlocks;
#if LXR_FREEZE_DIAG
volatile uint8_t cpuDiag_flags;
volatile uint32_t cpuDiag_seqCycles;
volatile uint32_t cpuDiag_masterStart;
volatile int8_t cpuDiag_locAtRequest;
static CpuPeakDiag cpuDiag_peak;
static uint16_t cpuDiag_peakKey;	/* percent, late blocks first; 0 = window empty */

static uint8_t cpuDiag_percent(uint32_t cycles)
{
	const uint32_t p = (cycles * 100u + cpuBlockBudget / 2u) / cpuBlockBudget;
	return (uint8_t)(p > 255u ? 255u : p);
}

/* 0.2.104 keep the parts of the highest block of the window */
static void cpuDiag_record(uint32_t cycles, uint32_t render, uint32_t now)
{
	const uint8_t flags = cpuDiag_flags;
	uint32_t seq = cpuDiag_seqCycles;
	uint32_t master = now - cpuDiag_masterStart;
	uint32_t wait = cycles - render;	// cycles >= render (see endCpuMeter)
	cpuDiag_flags = 0;
	cpuDiag_seqCycles = 0;
	if(seq > wait) seq = wait;	// seq time before the request is not in the value
	if(master > render) master = render;
	const uint8_t total = cpuDiag_percent(cycles);
	const uint16_t key = (uint16_t)(total + 1u + ((flags & CPU_DIAG_LATE) ? 256u : 0u));
	if(key < cpuDiag_peakKey) return;
	cpuDiag_peakKey = key;
	cpuDiag_peak.total = total;
	cpuDiag_peak.wait = cpuDiag_percent(wait - seq);
	cpuDiag_peak.seq = cpuDiag_percent(seq);
	cpuDiag_peak.render = cpuDiag_percent(render);
	cpuDiag_peak.voices = cpuDiag_percent(render - master);
	cpuDiag_peak.master = cpuDiag_percent(master);
	cpuDiag_peak.loc = cpuDiag_locAtRequest;
	cpuDiag_peak.flags = flags;
}

uint8_t audioCodec_takePeakDiag(CpuPeakDiag *out)
{
	uint8_t any;
	__disable_irq();	// a save renders in the TIM2 interrupt
	any = cpuDiag_peakKey != 0;
	*out = cpuDiag_peak;
	cpuDiag_peakKey = 0;
	__enable_irq();
	return any;
}
#endif

void audioCodec_initCpuMeter(void)
{
	CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
	DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
	cpuBlockBudget = (uint32_t)(((float)SystemCoreClock * OUTPUT_DMA_SIZE) / REAL_FS);
	if(cpuBlockBudget == 0) cpuBlockBudget = 1;
}

void audioCodec_beginCpuMeter(void)
{
	cpuBlockStart = DWT->CYCCNT;
}

void audioCodec_endCpuMeter(void)
{
	/* 0.2.98 from the DMA request, so the sequencer step counts too */
	const uint32_t now = DWT->CYCCNT;
	uint32_t cycles = now - audioCodec_blockRequest;
	const uint32_t render = now - cpuBlockStart;
	if(cycles < render || cycles > cpuBlockBudget * 4u) cycles = render; // first block, interrupt mode
#if LXR_FREEZE_DIAG
	cpuDiag_record(cycles, render, now);
#endif
	uint32_t percent = (cycles * 100u + cpuBlockBudget / 2u) / cpuBlockBudget;
	if(percent > 100u) percent = 100u;
	cpuUsePercent = (uint8_t)percent;
	if(cpuUsePercent > cpuUsePeakPercent) cpuUsePeakPercent = cpuUsePercent;
}

uint8_t audioCodec_getCpuUsePercent(void)
{
	uint8_t peak = cpuUsePeakPercent;
	cpuUsePeakPercent = cpuUsePercent;
	return peak;
}
//int16_t audioOutBuffer[2];
//------------------------------------------------------------------
int CodecInit()
{
    dma_buffer[0] = 32756;
    codec_initCsCodec((uint32_t)dma_buffer, OUTPUT_DMA_SIZE*2,(uint32_t)dma_buffer2, OUTPUT_DMA_SIZE*2);
    return 0;
}
//------------------------------------------------------------------
