/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef STEP_LOCKS_H
#define STEP_LOCKS_H
#include <stdint.h>
#include "Preset/SeqStep.h"

#define PLOCK_MAX 16u	/* 0.2.72: bounds the per-trigger CC work (was 63) */
#define PLOCK_CAPACITY 2048u	/* 0.2.73: 12 KB RAM (was 4096) */
#define PLOCK_NONE 255u
typedef struct { uint8_t destination, value; } StepLock;

/* Step remains seven bytes. Never copy its four lock bytes directly or write
 * them to disk: three or more locks contain an owning pool reference. */
void plock_init(void); /* once, before initializing the sequencer */
uint8_t plock_read(const Step *step, StepLock out[PLOCK_MAX]);
uint8_t plock_count(const Step *step);
uint16_t plock_available(void);
uint8_t plock_replace(Step *step, const StepLock *locks, uint8_t count);
uint8_t plock_set(Step *step, uint8_t destination, uint8_t value);
uint8_t plock_remove(Step *step, uint8_t destination);
void plock_clear(Step *step);
void plock_copy(Step *dst, const Step *src);
void plock_copyLocks(Step *dst, const Step *src);
void plock_copySteps(Step *dst, const Step *src, uint16_t count);
void plock_import(Step *dst, const Step *legacy);
void plock_export(const Step *src, Step *legacy);
/* Legacy P1/P2 editor: replace only one destination/value, keeping other locks. */
uint8_t plock_slot(Step *step, uint8_t slot, uint8_t destinationField, uint8_t value);
#endif
