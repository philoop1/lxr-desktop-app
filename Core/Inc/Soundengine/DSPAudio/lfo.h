/*
 * lfo.h
 *
 *  Created on: 14.01.2013
 *
 *      Non bandlimited low freq. oscillator
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#ifndef LFO_H_
#define LFO_H_
//-------------------------------------------------------------
#include "stm32f7xx_hal.h"
#include "Soundengine/DSPAudio/Oscillator.h"
#include "Soundengine/DSPAudio/wavetable.h"	//sine
#include "Soundengine/config.h"
#include "Soundengine/Sequencer/sequencer.h"
#include "Soundengine/DSPAudio/modulationNode.h"
//-------------------------------------------------------------
enum
{
	LFO_SINE,
	LFO_TRI,
	LFO_SAW_UP,
	LFO_SAW_DOWN,
	LFO_REC,
	LFO_NOISE,
	LFO_EXP_UP,
	LFO_EXP_DOWN,
	LFO_STRAY,
	LFO_GLIDE,
	LFO_EXP_TRI,		// xtr: exponential up, then exponential down (this slot was rps until 0.2.48)
	// One-shots: one cycle after a retrigger, then they hold the end value.
	// The offset delays the start by up to one cycle. Same order as the looping waves.
	LFO_ONESHOT_SINE,
	LFO_ONESHOT_TRI,
	LFO_ONESHOT_SAW_UP,
	LFO_ONESHOT_SAW_DOWN,
	LFO_ONESHOT_REC,	// on first, then off
	LFO_ONESHOT_NOISE,	// one new random value per retrigger
	LFO_ONESHOT_EXP_UP,
	LFO_ONESHOT_EXP_DOWN,
	LFO_ONESHOT_EXP_TRI,
	NUM_LFO_WAVEFORMS,
	// internal: the Random per Step modulators, not selectable as an LFO wave
	LFO_RANDOM_STEP = NUM_LFO_WAVEFORMS
};
#define LFO_ONESHOT_FIRST LFO_ONESHOT_SINE
// one-shot state in Lfo.shot
#define LFO_SHOT_DONE 0
#define LFO_SHOT_WAIT 1
#define LFO_SHOT_RUN 2


#define LFO_MAX_F 		200 //[Hz]
#define LFO_SR 			(REAL_FS/(float)OUTPUT_DMA_SIZE)
//-------------------------------------------------------------
typedef struct LfoStruct
{
	uint32_t 	phase;		// the current phase of the LFO (upper bits cnt 0-255)
	uint32_t 	phaseInc;	// the phase increment controls the LFO frequency
	uint8_t 	waveform;	// selects the waveform
	uint8_t 	retrigger;	// defines the voice nr that retriggers the LFO (0=no retrigger)
	uint32_t 	phaseOffset;// the phase value to which the LFO is retriggered
	float 		rnd;
	float rndTarget;
	float stepValue;
	uint8_t stepSlew;
	uint8_t stepPolarity;
	uint8_t shot;			// one-shot state, LFO_SHOT_*
	uint8_t 	sync;
	float 		freq;
	ModulationNode modTarget;
	float		modNodeValue;
} Lfo;
//-------------------------------------------------------------
void lfo_init(Lfo *lfo);
void lfo_dispatchNextValue(Lfo* lfo);
void lfo_setFreq(Lfo *lfo, float f);
void lfo_setSync(Lfo* lfo, uint8_t sync);
void lfo_recalcSync();
void lfo_setWaveform(Lfo *lfo,uint8_t waveform);
void lfo_setPhaseOffset(Lfo *lfo,uint8_t offset);
void lfo_retrigger(uint8_t voiceNr);
void lfo_stepTrigger(uint8_t sourceVoice);
void lfo_setStepSlew(uint8_t voice,uint8_t value);
void lfo_setStepPolarity(uint8_t voice,uint8_t value);
void lfo_initRandomSteps(void);
void lfo_applyRandomStepSettings(uint8_t voice);
void lfo_dispatchRandomSteps(void);
void lfo_resetRandomStepTargets(void);
uint8_t lfo_randomStepTargetVoice(const ModulationNode *node);	// 0.2.107
void lfo_randomStepOriginalValueChanged(uint16_t idx);

#endif /* LFO_H_ */
