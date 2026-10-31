/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef PERFORMANCE_MASTER_FILTER_H
#define PERFORMANCE_MASTER_FILTER_H
#include <stdint.h>
void masterFilter_init(void);
void mixer_setMasterFilter(uint8_t value);
void mixer_setMasterFilterResonance(uint8_t value);
void mixer_setMasterFilterDrive(uint8_t value);
void mixer_setMasterFilterEnabled(uint8_t value);
void masterFilter_process(int16_t *stereo,uint32_t frames);
#endif
