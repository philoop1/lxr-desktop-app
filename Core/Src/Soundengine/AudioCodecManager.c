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
	uint32_t cycles = DWT->CYCCNT - cpuBlockStart;
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
