/*
 * DrumVoice.h
 *
 *  Created on: 03.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#ifndef DRUMVOICE_H_
#define DRUMVOICE_H_

#include "Soundengine/DSPAudio/Oscillator.h"
#include "Soundengine/config.h"
#include "Soundengine/DSPAudio/ResonantFilter.h"
#include "Soundengine/DSPAudio/distortion.h"
#include "Soundengine/DSPAudio/SlopeEg2.h"
#include "Soundengine/DSPAudio/Decay.h"
#include "Soundengine/DSPAudio/modulationNode.h"
#include "Soundengine/DSPAudio/lfo.h"
#include "Soundengine/DSPAudio/1PoleLp.h"
#include "Soundengine/DSPAudio/transientGenerator.h"
#include "Soundengine/DSPAudio/snapEg.h"
#include "Soundengine/DSPAudio/dither.h"
//------------------------------------------------------------------------
enum
{
	IS_PLAYING = 0x1,
};
//------------------------------------------------------------------------
typedef struct VoiceStruct
{
	OscInfo 	osc;		// the main fm oscillator
	OscInfo 	modOsc;		// the mod osc

	float		fmModAmount;

	float	 	vol;		// volume of the voice
	float 		velo;
	uint8_t 	pan;
	float 	triggeredPanL; //only updated with the latest pan value when triggered
	float 	triggeredPanR;
	//float 		panModifier;

	int16_t 	oscSample;

	DecayEg		oscPitchEg;
	float		egPitchModAmount;
	float 		offset;				//the start offset for the waveform - used to generate clicks

	TransientGenerator transGen;
	Lfo 		lfo;
	SlopeEg2	oscVolEg;
	float 		egValueOscVol;
	float 		volEgValueBlock[OUTPUT_DMA_SIZE];
	Distortion distortion;

#if ENABLE_DRUM_SVF
	ResonantFilter filter;
	uint8_t		filterType; // bit 0 = lp, bit 1 = hp, bit 3 = bp on/off
#endif

#ifdef USE_AMP_FILTER
	OnePoleFilter ampFilter;
#endif

#if (AMP_EG_SYNC==0)
	double ampFilterInput;
	double lastGain;
#endif

#if ENABLE_MIX_OSC
	uint8_t mixOscs;
#endif

	float decimationCnt;
	float decimationRate;
	SnapEg snapEg;

	uint8_t volumeMod;	//modulate volume by midi velocity if 1

	Dither dither;
	float combinedVolume;
	OnePoleFilter FaderVolumeFilter;

#if SMOOTH_MIXER_VOL_PAN_DRIVE
	OnePoleFilter MixerPageFilter[2];
#endif

	float pwm;
} DrumVoice;
//------------------------------------------------------------------------


//array holding all the voices
extern DrumVoice voiceArray[NUM_DRUM_VOICES];

//initialize all the parameters to sane values
void initDrumVoice();

void Drum_trigger(const uint8_t voiceNr, const uint8_t vol, const uint8_t note);

/* 0.2.90 glide of voices 1-3. off: no glide, slide steps play normally;
 * on: every note glides from the last one, the EGs always restart;
 * leg: only slide steps glide, without new EGs while the voice still sounds. */
enum { GLIDE_OFF, GLIDE_ON, GLIDE_LEGATO, GLIDE_MODES };
#define GLIDE_PARAMS 6	// mode 1-3, time 1-3, same order as PAR_GLIDE_MODE1..PAR_GLIDE_TIME3
#define GLIDE_TIME_DEFAULT 40
typedef struct
{
	float log2Ratio;	// distance to the target pitch in octaves, 0 = arrived
	float coef;			// per block decay of log2Ratio
	uint8_t mode;
	uint8_t time;
	uint8_t slideNext;	// set by the sequencer for the next trigger
} DrumGlide;
extern DrumGlide drum_glide[NUM_DRUM_VOICES];
void Drum_setGlideParameter(uint8_t index, uint8_t value);
uint8_t Drum_getGlideParameter(uint8_t index);
void Drum_setSlideNext(uint8_t voiceNr, uint8_t on);
uint8_t drum_glideTrigger(uint8_t voiceNr, uint8_t note);
void drum_glideTick(uint8_t voiceNr);

void Drum_updatePan(const uint8_t voiceNr);

/** block based calculation*/
void calcDrumVoiceSyncBlock(const uint8_t voiceNr, int16_t* buf, const uint8_t size);

/** calculate envelopes etc (all 16 samples */
void calcDrumVoiceAsync(const uint8_t voiceNr);

//-0.5 = left 0=both max 0.5=right*/
void setPan(const uint8_t voiceNr, const uint8_t pan);

/** set the oscillator start phase for all OSCs*/
void drum_setPhase(const uint8_t phase, const uint8_t voiceNr);

#endif /* DRUMVOICE_H_ */
