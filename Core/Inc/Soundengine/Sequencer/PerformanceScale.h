/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef PERFORMANCE_SCALE_H
#define PERFORMANCE_SCALE_H
#include <stdint.h>
void perf_scaleSet(uint8_t mode,uint8_t running);
uint8_t perf_scaleCommit(void);
uint8_t perf_scaleCommitOnBar(uint16_t frame);
uint8_t perf_scaleHasPending(void);
void perf_scaleSetPattern(uint8_t mode,uint8_t running);
uint8_t perf_scaleMode(void);
uint8_t perf_scaleDivision(uint8_t index);
uint8_t perf_scaleIndex(uint8_t division);
uint8_t perf_scaleMidiClocks(void);
uint8_t perf_scaleTicks(void);
uint16_t perf_scaleFrames(void);
uint8_t perf_scaleLegacyOverride(uint8_t value);
uint8_t perf_scaleAllowed(uint8_t mainStep);
uint8_t perf_scaleCount(uint8_t length);
uint8_t perf_scaleToSource(uint8_t ordinal,uint8_t length);
uint8_t perf_scaleToOrdinal(uint8_t source,uint8_t length);
uint8_t perf_scaleNext(int16_t source,uint8_t length);
#endif
