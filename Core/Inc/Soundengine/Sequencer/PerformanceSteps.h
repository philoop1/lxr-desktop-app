/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only */
#ifndef PERFORMANCE_STEPS_H
#define PERFORMANCE_STEPS_H
#include <stdint.h>

typedef struct {
    uint8_t source, probability, drop, timeline, flamRoll;
    uint32_t eventId;
} PerfStep;
typedef struct {
    PerfStep prev, current, next;
    PerfStep prev2, next2;
    uint8_t valid, length, lastSource, hasLast;
} PerfTrack;

void perf_configure(uint8_t randomStep, uint8_t repeatChance,
                    uint8_t scarcity, uint8_t probability);
void perf_resetSteps(void);
const PerfTrack *perf_advance(uint8_t track, uint8_t timeline, uint8_t length,
                            uint64_t active, uint32_t (*randomValue)(void));
uint8_t perf_allowHit(uint32_t (*randomValue)(void));
void perf_setNoteProbability(uint8_t amount);
uint8_t perf_scaleProbability(uint8_t probability);
uint8_t perf_randomVelocity(uint8_t velocity,uint8_t minimum,uint32_t (*randomValue)(void));
uint8_t perf_adjustVelocity(uint8_t velocity,uint8_t gain);
void perf_formatVelocityGain(char text[4],uint8_t gain);
void perf_setLoop(uint8_t start, uint8_t end);
void perf_clearLoop(void);
uint8_t perf_getLoop(uint8_t *start, uint8_t *end);
uint8_t perf_nextPattern(uint8_t active);
#endif
