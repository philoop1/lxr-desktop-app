/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef PERFORMANCE_GROOVE_H
#define PERFORMANCE_GROOVE_H
#include <stdint.h>
/* 192 PPQ preserves Mutador's half-96-PPQ-tick offsets exactly. */
typedef struct { int16_t offset[4]; } PerfGroove;
void perf_grooveConfigure(PerfGroove *groove, uint8_t amount,
                          uint8_t sh2, uint8_t sh3, uint8_t sh4);
int32_t perf_grooveEvent(const PerfGroove *groove, int32_t straightTick,
                        uint8_t sourceMainStep);
uint32_t perf_grooveRepeat(const PerfGroove *groove, uint16_t period96,
                          uint8_t *lane);
uint8_t perf_grooveActive(const PerfGroove *groove);
uint8_t perf_grooveDue(const PerfGroove *groove,uint32_t pattern,
                       int8_t shift,uint8_t lane,int8_t neighbor,uint8_t frame);
uint8_t perf_groovePulse(const PerfGroove *groove,uint8_t lane,
                         int8_t neighbor,uint8_t frame);
#endif
