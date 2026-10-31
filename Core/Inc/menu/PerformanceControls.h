/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef PERFORMANCE_CONTROLS_H
#define PERFORMANCE_CONTROLS_H
#include <stdint.h>
#define PERFORMANCE_EXTRA_BYTES 20
uint8_t performance_set(uint16_t parameter,uint8_t value);
void performance_resetExtended(void);
void performance_validateExtended(void);
void performance_prepareLoaded(void);
#endif
