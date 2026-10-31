/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only */
#ifndef PERFORMANCE_DELAY_H
#define PERFORMANCE_DELAY_H
#include <stdint.h>
#include "Soundengine/Sequencer/PerformanceGroove.h"
typedef struct {
    uint8_t chance, sync, count, bounce, target, poly, exponent, mask;
    int8_t pitch;
} PerfDelayConfig;
void perf_delayConfigure(PerfDelayConfig config);
void perf_delayReset(void);
uint8_t perf_delayIsPoly(void);
void perf_delayTick(void (*emit)(uint8_t track,uint8_t source,uint8_t scale,int16_t pitch));
void perf_delayOffer(uint8_t candidates,const uint8_t sources[7],uint32_t (*randomValue)(void));
void perf_delaySetGroove(const PerfGroove *groove);
void perf_delayFineTick(void (*emit)(uint8_t,uint8_t,uint8_t,int16_t));
void perf_delayOfferAt(uint8_t candidates,const uint8_t sources[7],
                       const uint8_t lanes[7],uint32_t (*randomValue)(void));
#endif
