/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only
 * Tempo-synced tape delay in the Delay's FX_BUFFER. The delay time glides to
 * each new target like a tape machine, so time changes bend the pitch.
 */
#ifndef TAPEDELAY_H_
#define TAPEDELAY_H_

#include "stm32f7xx_hal.h"
#include "Soundengine/config.h"
#include "Soundengine/DSPAudio/FX/FxRamBuffer.h"

// Divisions in repeatSyncNames order, from "1" (whole) to "128"
#define TAPE_DIVISIONS 16
// Fine moves the time by up to +-20 %
#define TAPE_FINE_SPAN 320.f
// feedback knob range; above 1 the repeats grow into the tape saturation
#define TAPE_FEEDBACK_MAX 1.25f

typedef struct TapeDelayStruct
{
	uint32_t write;
	uint32_t valid;		// samples written since the last reset; older reads are muted
	float delay;		// current delay in samples, gliding to target
	float rate;			// 0..1 from FX P1, selects the division
	float fine;			// 0..1 from FX P2, 0.5 is exact
	float tone;			// one-pole coefficient
	float feedback;
	float lpL, lpR;
	uint8_t pingPong;
	uint8_t primed;		// 0 until the first block jumps to its target
} TapeDelay;

void TapeDelay_init(TapeDelay *d);
// Mute the buffer content of other effects and start without glide
void TapeDelay_reset(TapeDelay *d);
void TapeDelay_setPingPong(TapeDelay *d, uint8_t pingPong);
void TapeDelay_setRate(TapeDelay *d, float rate);
void TapeDelay_setFine(TapeDelay *d, float fine);
void TapeDelay_setTone(TapeDelay *d, float tone);
void TapeDelay_setFeedback(TapeDelay *d, float fb);
// Division index into repeatSyncNames that the delay plays: the rate's
// division, or the next shorter one that fits the buffer at this tempo
uint8_t TapeDelay_division(float rate, float fine, float bpm, uint8_t pingPong);
float TapeDelay_targetSamples(float rate, float fine, float bpm, uint8_t pingPong);
void TapeDelay_process(TapeDelay *d, int16_t *fxBuffer, int16_t* outL, uint16_t size, uint8_t channels, float dryWet, float bpm);

#endif /* TAPEDELAY_H_ */
