/*
 * cpuDiag.h
 *
 * Mutador 0.2.104 peak diagnosis (freeze diagnosis builds only): what made the
 * highest audio block of each 0.5 s CPU window. The CPU value runs from the
 * DMA request to the ready block; this splits it into
 *   wait   request until the block starts (main loop busy, minus seq)
 *   seq    seq_tick time since the last block (step, triggers)
 *   render the block itself: voices, then the master stage (FX bus,
 *          master filter, compressor)
 * and notes where the main loop was at the request and what happened since
 * the last block (step, repaint, master filter fade, late block).
 *
 * SPDX-License-Identifier: GPL-3.0-only
 */
#ifndef INC_SOUNDENGINE_CPUDIAG_H_
#define INC_SOUNDENGINE_CPUDIAG_H_

#include <stdint.h>
#include "stm32f7xx.h"

#if LXR_FREEZE_DIAG

#define CPU_DIAG_STEP		0x01u	/* a sequencer step since the last block */
#define CPU_DIAG_REPAINT	0x02u	/* a menu repaint since the last block */
#define CPU_DIAG_FILTER		0x04u	/* master filter in its fade/glide loop */
#define CPU_DIAG_LATE		0x08u	/* the block came too late (click) */

typedef struct {
	uint8_t total;		/* % of one block, request to ready (not capped) */
	uint8_t wait;
	uint8_t seq;
	uint8_t render;
	uint8_t voices;
	uint8_t master;
	int8_t loc;			/* main loop marker (checkMainLoc) at the request */
	uint8_t flags;
} CpuPeakDiag;

extern volatile uint8_t cpuDiag_flags;
extern volatile uint32_t cpuDiag_seqCycles;
extern volatile uint32_t cpuDiag_masterStart;
extern volatile int8_t cpuDiag_locAtRequest;
extern volatile int8_t checkMainLoc;

#define CPU_DIAG_FLAG(f)			(cpuDiag_flags |= (uint8_t)(f))
#define CPU_DIAG_MASTER_START()		(cpuDiag_masterStart = DWT->CYCCNT)
#define CPU_DIAG_REQUEST()			(cpuDiag_locAtRequest = checkMainLoc)
/* around seq_tick: its time, and a step when the master step counter moved */
#define CPU_DIAG_SEQ_BEGIN()		const uint32_t cpuDiagSeqT0 = DWT->CYCCNT; \
									const uint8_t cpuDiagStep0 = seq_getMasterStepCnt()
#define CPU_DIAG_SEQ_END()			do { cpuDiag_seqCycles += DWT->CYCCNT - cpuDiagSeqT0; \
									if(seq_getMasterStepCnt() != cpuDiagStep0) CPU_DIAG_FLAG(CPU_DIAG_STEP); } while(0)

/* copies the peak of the window, starts a new one; 0 when no block ran */
uint8_t audioCodec_takePeakDiag(CpuPeakDiag *out);

#else

#define CPU_DIAG_FLAG(f)			((void)0)
#define CPU_DIAG_MASTER_START()		((void)0)
#define CPU_DIAG_REQUEST()			((void)0)
#define CPU_DIAG_SEQ_BEGIN()		((void)0)
#define CPU_DIAG_SEQ_END()			((void)0)

#endif

#endif /* INC_SOUNDENGINE_CPUDIAG_H_ */
