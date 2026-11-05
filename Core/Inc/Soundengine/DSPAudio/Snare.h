/*
 * Snare.h
 *
 *  Created on: 16.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#ifndef SNARE_H_
#define SNARE_H_

#include "stm32f7xx_hal.h"
#include "Oscillator.h"
#include "config.h"
#include "ResonantFilter.h"
#include "distortion.h"
#include "Decay.h"
#include "SlopeEg2.h"
#include "transientGenerator.h"
#include "BufferTools.h"
#include "lfo.h"
#include "snapEg.h"
#include "Soundengine/DSPAudio/1PoleLp.h"

#define USE_PEAK 0
// wmd: 0 mix, 1 FM, 2 ring, 3 exp (expo FM from the layer osc), 4 pd (phase distortion)
#define SNARE_LAYER_EXP 3
#define SNARE_LAYER_PD 4
#define SNARE_LAYER_MODE_MAX SNARE_LAYER_PD
//------------------------------------------------------------------------
typedef struct SnareStruct
{
	OscInfo 	osc;		// the tonal oscillator
	OscInfo 	noiseOsc;	// the noise osc
	OscInfo layerOsc;
	float layerAmount;
	float layerDepth;		// exp/pd depth: layer amount times the pitch EG, once a block
	uint8_t layerMode;
	uint8_t layerAmountControl;
	uint8_t layerFreqControl;


	uint8_t		filterType; // bit 0 = lp, bit 1 = hp, bit 3 = bp on/off
	float	 	vol;		// volume of the voice
	//float		panL;		// [0:1]
	//float		panR;		// [0:1]
	uint8_t pan;
	float 	triggeredPanL; //only updated with the latest pan value when triggered
	float 	triggeredPanR;
	//float 		panModifier;

	float   	mix;		// defines the mix between osc and noise [0 = 100% osc: 1 = 100% noise]
	float 		velo;

	int16_t		oscSample;
	int32_t		noiseSample;

#if USE_PEAK
	PeakFilter  filter;
#else
	ResonantFilter filter;
#endif

	DecayEg		oscPitchEg;
	float		egPitchModAmount;

	Lfo 		lfo;
	TransientGenerator transGen;

	SlopeEg2		oscVolEg;
	float 		egValueOscVol;
	SlopeEg2		noiseVolEg;
	float		noiseEgValue;
	uint8_t		noiseAttackControl;
	uint8_t		noiseDecayControl;
	uint8_t		noiseSlopeControl;
	uint8_t		noiseEnvelopeEnabled;

	Distortion distortion;
	SnapEg snapEg;

	uint8_t volumeMod;	//modulate volume by midi velocity if 1

	float combinedVolume;
	OnePoleFilter FaderVolumeFilter;

	float pwm;

} SnareVoice;

//array holding all the voices
extern SnareVoice snareVoice;

//initialize all the parameters to sane values
void Snare_init();

void Snare_trigger(const uint8_t vel, const uint8_t note);
void Snare_updatePan();
/** claculate the oscillators and sample based stuff*/
void Snare_calcSyncBlock(int16_t* buf, const uint8_t size);

/** calculate envelopes etc (all 16 samples */
void Snare_calcAsync();

//-0.5 = left 0=both max 0.5=right*/
void Snare_setPan(const uint8_t pan);
void Snare_setNoiseAttack(uint8_t value);
void Snare_setNoiseDecay(uint8_t value);
void Snare_setNoiseSlope(uint8_t value);
void Snare_setLayerWave(uint8_t value);
void Snare_setLayerAmount(uint8_t value);
void Snare_setLayerFreq(uint8_t value);
void Snare_setLayerMode(uint8_t value);
#endif /* SNARE_H_ */
