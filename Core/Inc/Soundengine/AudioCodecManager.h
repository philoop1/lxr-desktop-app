/*
 * AudioCodecManager.h
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#ifndef AUDIOCODECMANAGER_H_
#define AUDIOCODECMANAGER_H_

#include "stm32f7xx_hal.h"
#include "config.h"
#include "globals.h"
#include "cs4344_cs5343.h"
#include "Soundengine/cpuDiag.h"

#define DMA_MODE_ACTIVE 1
//-----------------------------------
int CodecInit();
void audioCodec_initCpuMeter(void);
void audioCodec_beginCpuMeter(void);
void audioCodec_endCpuMeter(void);
uint8_t audioCodec_getCpuUsePercent(void);
/* 0.2.98 the CPU value is the time from the DMA asking for a block until the
 * block is ready (sequencer step and main loop included), in % of one block.
 * Over 100 the block came too late: a click. lateBlocks counts those. */
extern volatile uint32_t audioCodec_blockRequest;
extern volatile uint16_t audioCodec_lateBlocks;
static inline void audioCodec_blockRequested(void)
{
	if(bCurrentSampleValid != SAMPLE_VALID && audioCodec_lateBlocks < 0xffffu) audioCodec_lateBlocks++;
	if(bCurrentSampleValid != SAMPLE_VALID) CPU_DIAG_FLAG(CPU_DIAG_LATE);	// 0.2.104
	CPU_DIAG_REQUEST();	// 0.2.104 where the main loop was
	audioCodec_blockRequest = DWT->CYCCNT;
}

#endif /* AUDIOCODECMANAGER_H_ */
