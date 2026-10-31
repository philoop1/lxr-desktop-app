/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef STEP_SELECTION_H
#define STEP_SELECTION_H
#include <stdint.h>
void stepEdit_clear(void);
uint8_t stepEdit_press(uint8_t pattern,uint8_t voice,uint8_t key,uint8_t step);
void stepEdit_release(uint8_t key);
uint64_t stepEdit_mask(uint8_t pattern,uint8_t voice);
uint8_t stepEdit_apply(uint8_t pattern,uint8_t voice,uint16_t parameter,uint8_t value);
#endif
