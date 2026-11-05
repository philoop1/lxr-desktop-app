/*
 * saveDiag.h
 *
 * Mutador 0.2.57 measurement build: timing counters while a pattern, kit or
 * project is written to the SD card. All times are DWT cycle counts.
 *
 * SPDX-License-Identifier: GPL-3.0-only
 */
#ifndef INC_SOUNDENGINE_SAVEDIAG_H_
#define INC_SOUNDENGINE_SAVEDIAG_H_

#include <stdint.h>
#include "stm32f7xx.h"

typedef struct {
	uint32_t lastBlock;
	uint32_t lastSeq;
	uint32_t lastOut;
	uint32_t maxBlock;   /* longest gap between two calculated audio blocks */
	uint32_t maxSeq;     /* longest gap between two seq_tick calls */
	uint32_t maxClock;   /* longest delay from MIDI clock byte to sync_tick */
	uint32_t maxOut;     /* longest gap between two main output (SPI2) DMA restarts */
	uint16_t late;       /* audio blocks not ready when the DMA swapped buffers */
	uint8_t active;
} SaveDiag;

extern volatile SaveDiag saveDiag;

static inline void saveDiag_begin(void)
{
	const uint32_t now = DWT->CYCCNT;
	saveDiag.lastBlock = now;
	saveDiag.lastSeq = now;
	saveDiag.lastOut = now;
	saveDiag.maxOut = 0;
	saveDiag.maxBlock = 0;
	saveDiag.maxSeq = 0;
	saveDiag.maxClock = 0;
	saveDiag.late = 0;
	saveDiag.active = 1;
}

static inline void saveDiag_gap(volatile uint32_t *last, volatile uint32_t *max)
{
	const uint32_t now = DWT->CYCCNT;
	const uint32_t gap = now - *last;
	if(gap > *max) *max = gap;
	*last = now;
}

static inline void saveDiag_block(void)
{
	if(saveDiag.active) saveDiag_gap(&saveDiag.lastBlock, &saveDiag.maxBlock);
}

static inline void saveDiag_seq(void)
{
	if(saveDiag.active) saveDiag_gap(&saveDiag.lastSeq, &saveDiag.maxSeq);
}

static inline void saveDiag_out(void)
{
	if(saveDiag.active) saveDiag_gap(&saveDiag.lastOut, &saveDiag.maxOut);
}

static inline void saveDiag_late(void)
{
	if(saveDiag.active && saveDiag.late < 0xffff) saveDiag.late++;
}

static inline void saveDiag_clock(uint32_t arrivalCycles)
{
	if(!saveDiag.active) return;
	const uint32_t delay = DWT->CYCCNT - arrivalCycles;
	if(delay > saveDiag.maxClock) saveDiag.maxClock = delay;
}

/* Closes the window; the gaps up to the end of the save count too. */
static inline void saveDiag_end(void)
{
	if(!saveDiag.active) return;
	saveDiag_gap(&saveDiag.lastBlock, &saveDiag.maxBlock);
	saveDiag_gap(&saveDiag.lastSeq, &saveDiag.maxSeq);
	saveDiag.active = 0;
}

static inline uint32_t saveDiag_us(uint32_t cycles)
{
	const uint32_t us = cycles / (SystemCoreClock / 1000000u);
	return us > 99999u ? 99999u : us;
}

#endif /* INC_SOUNDENGINE_SAVEDIAG_H_ */
