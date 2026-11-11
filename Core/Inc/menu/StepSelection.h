/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef STEP_SELECTION_H
#define STEP_SELECTION_H
#include <stdint.h>
void stepEdit_clear(void);
/* 0.2.89: the sequencer moved on (pattern link, song): the selection follows */
void stepEdit_follow(uint8_t pattern);
uint8_t stepEdit_press(uint8_t pattern,uint8_t voice,uint8_t key,uint8_t step);
void stepEdit_release(uint8_t key);
uint64_t stepEdit_mask(uint8_t pattern,uint8_t voice);
uint8_t stepEdit_apply(uint8_t pattern,uint8_t voice,uint16_t parameter,uint8_t value);
/* 0.2.96 moves the notes of the selected steps; returns the first new note + 1, 0 = no selection */
uint8_t stepEdit_transpose(uint8_t pattern,uint8_t voice,int8_t semitones);
#endif
