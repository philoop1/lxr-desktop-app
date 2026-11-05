/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef PERFORMANCE_GROOVE_H
#define PERFORMANCE_GROOVE_H
#include <stdint.h>
/* 192 PPQ preserves Mutador's half-96-PPQ-tick offsets exactly. */
/* human[lane] 0..127: random timing per hit up to +-HUMANIZE_MAX_FRAMES (0.2.55) */
#define HUMANIZE_MAX_FRAMES 12
typedef struct { int16_t offset[4]; uint8_t human[4]; } PerfGroove;
int16_t perf_grooveHuman(const PerfGroove *groove,uint8_t lane,uint32_t eventId);
void perf_grooveConfigure(PerfGroove *groove, uint8_t amount,
                          uint8_t sh2, uint8_t sh3, uint8_t sh4);
int32_t perf_grooveEvent(const PerfGroove *groove, int32_t straightTick,
                        uint8_t sourceMainStep);
uint32_t perf_grooveRepeat(const PerfGroove *groove, uint16_t period96,
                          uint8_t *lane);
uint8_t perf_grooveActive(const PerfGroove *groove);
uint8_t perf_grooveDue(const PerfGroove *groove,uint32_t pattern,
                       int8_t shift,uint8_t lane,int8_t neighbor,uint8_t frame,int16_t human);
uint8_t perf_groovePulse(const PerfGroove *groove,uint8_t lane,
                         int8_t neighbor,uint8_t frame);
#endif
