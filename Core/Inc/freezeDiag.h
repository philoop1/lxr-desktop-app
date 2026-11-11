/*
 * freezeDiag.h
 *
 * Mutador 0.2.85d freeze diagnosis build (CMake -DLXR_FREEZE_DIAG=ON).
 * Catches a stuck audio interrupt, a stuck main loop, a fault and (via the
 * hardware watchdog) a lockup with interrupts off, keeps where it happened in
 * backup SRAM across the reset and shows it on the display at the next boot.
 *
 * SPDX-License-Identifier: GPL-3.0-only
 */
#ifndef INC_FREEZEDIAG_H_
#define INC_FREEZEDIAG_H_

#include <stdint.h>

#if LXR_FREEZE_DIAG

typedef struct {
	uint32_t magic;
	uint32_t check;      /* ~magic, so random power-on content is ignored */
	uint8_t kind;        /* 'A' audio stuck, 'M' main loop stuck, 'F' fault, 0 none */
	uint8_t armed;       /* main loop reached: a watchdog reset means 'W' */
	uint8_t inSetDest;   /* inside modNode_setDestination (interrupts off) */
	uint8_t inMenuTick;  /* inside the display timer interrupt */
	uint8_t lastStatus;  /* last message given to midiParser_ccHandler */
	uint8_t lastData1;
	uint16_t lastDest;   /* last modulation destination being set */
	uint32_t pc, lr;     /* interrupted code when the freeze was caught */
	uint32_t cfsr, hfsr;
	uint32_t sample[4];  /* PCs sampled by the 1 ms tick, newest at sampleIdx-1 */
	uint32_t sampleIdx;
	uint32_t mainBeat, audioBeat;
} FreezeDiag;

#define FREEZE_DIAG ((volatile FreezeDiag *)(0x40024000UL + 0x0F00UL)) /* backup SRAM */
#define FREEZE_MARK(field, v) (FREEZE_DIAG->field = (v))
#define FREEZE_BEAT(field) (FREEZE_DIAG->field++)

void freezeDiag_boot(void);  /* show a recorded freeze, wait for the encoder */
void freezeDiag_arm(void);   /* start watching at main loop entry */

#else
#define FREEZE_MARK(field, v) ((void)0)
#define FREEZE_BEAT(field) ((void)0)
#endif

#endif /* INC_FREEZEDIAG_H_ */
