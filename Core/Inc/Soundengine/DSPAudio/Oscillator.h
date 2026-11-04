/*
 * Oscillator.h
 *
 *  Created on: 01.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#ifndef OSCILLATOR_H_
#define OSCILLATOR_H_

#include "stm32f7xx_hal.h"
#include "Soundengine/datatypes.h"
#include "Soundengine/DSPAudio/wavetable.h"
#include "Soundengine/config.h"
//#include "../SampleRom/SampleMemory.h"
//-----------------------------------------------------------

//the available osc waveforms
enum OscWaveforms
{
	SINE,
	TRI,
	SAW,
	REC,
	NOISE,
	PWM,
	NUM_OSC_WAVEFORMS
};


#define phaseShift 1000

#define EXPO_FM_OCTAVES		4
#define OSC_MAX_PHASE_INC	2147483648.f	// half the sample rate
#define PD_MIN_KNEE			0.02f
#define OSC_SCAN_GLIDE		0.1f	// share of the way to the PWM value per block

//-----------------------------------------------------------

typedef struct OscStruct
{
	int16_t 	output;
	uint32_t	phaseInc;
	uint32_t	phase;		// the current phase of the osc 8bit indexing 24 interpolation
	float	 	freq;		// frequency in [Hz]
	uint8_t		waveform;	// the selected waveform of the osc

	uint8_t		tableOffset;	//overtone table
	uint16_t	levelMix;		// user wavetables: share of the next octave level, 0..32767
	float		scanPos;		// user wavetables: PWM scan position, glides to the PWM value
	float		pdKnee;			// phase distortion: knee of the last block, 0 after a trigger


	float		pitchMod;	// modulation value for frequency
	float 		fmMod;

	float		modNodeValue;

	//for midi
	uint16_t	midiFreq;  //upper 8 bit coarse, lower 8 bit fine -> the sound edit freq offset
	float pitchBend; // per-voice bend in semitones, combined with master pitch
	uint8_t baseNote;		// the last played midi note
	uint32_t startPhase;		// the OSC is reset to this phase on retrigger
} OscInfo;
//-----------------------------------------------------------

//extern OscInfo osc1;
//extern OscInfo osc2;

void initOsc();
//-----------------------------------------------------------

//-----------------------------------------------------------
void calcSineBlock(OscInfo* osc, int16_t* buf, const uint8_t size ,const float gain);
//-----------------------------------------------------------
int16_t calcSine(OscInfo* osc);
//-----------------------------------------------------------
void calcFmSineBlock(OscInfo* osc, int16_t* modBuffer, int16_t* buf, uint8_t size ,const float gain);
//-----------------------------------------------------------
int16_t calcFmSine(OscInfo* osc, OscInfo* modOsc);
//-----------------------------------------------------------
void calcFmBlock(OscInfo* osc, const int16_t table[][1024], int16_t* modBuffer, int16_t* buf, uint8_t size ,const float gain);
//-----------------------------------------------------------
int16_t calcFm(OscInfo* osc, OscInfo* modOsc,  const int16_t table[][1024]);
//-----------------------------------------------------------
void calcWavetableOscBlock(OscInfo* osc, const int16_t table[][1024], int16_t* buf, const uint8_t size ,const float gain);
//-----------------------------------------------------------
int16_t calcWavetableOsc(OscInfo* osc, const int16_t table[][1024]);
//-----------------------------------------------------------
void calcNoiseBlock(OscInfo* osc, int16_t* buf, const uint8_t size ,const float gain);
//-----------------------------------------------------------
int16_t calcNoise(OscInfo* osc);
//-----------------------------------------------------------
//int16_t calcSampleOscFm(OscInfo* osc, OscInfo* modOsc);
//-----------------------------------------------------------
//used to play back the crash cymbal sample
//void calcSampleOscFmBlock(OscInfo* osc,int16_t* modBuffer, int16_t* buf, uint8_t size ,const float gain);
//-----------------------------------------------------------
void calcNextOscSampleBlock(OscInfo* osc, int16_t* buf, const uint8_t size ,const float gain, const float pwm);
//-----------------------------------------------------------
// calculate an oscillator
//int16_t calcNextOscSample(OscInfo* osc);
 //-----------------------------------------------------------
void osc_setFreq(OscInfo* osc);
//-----------------------------------------------------------
void calcNextOscSampleFmBlock(OscInfo* osc, int16_t* modBuffer, int16_t* buf, uint8_t size ,const float gain, const float pwm);
//-----------------------------------------------------------
void calcExpoFmBlock(OscInfo* osc, int16_t* modBuffer, int16_t* buf, uint8_t size, const float pwm);
//-----------------------------------------------------------
void calcPhaseDistBlock(OscInfo* osc, int16_t* buf, uint8_t size);
 //-----------------------------------------------------------
// calculate an fm oscillator
//int16_t calcNextOscSampleFm(OscInfo* osc, OscInfo* modOsc);
void calcPwmBlock(OscInfo* osc, int16_t* buf, uint8_t size ,const float gain, const float pwm);
//-----------------------------------------------------------
//void calcSampleOscBlock(OscInfo* osc, int16_t* buf, const uint8_t size ,const float gain);
//-----------------------------------------------------------
// user wavetables (waveform > PWM); pwm scans the frames of the selected wavetable,
// or from a single wave on through the single waves in the slots after it
void calcWaveBankFmBlock(OscInfo* osc, int16_t* modBuffer, int16_t* buf, uint8_t size, const float gain, const float pwm);
//-----------------------------------------------------------
void calcWaveBankBlock(OscInfo* osc, int16_t* buf, const uint8_t size, const float gain, const float pwm);
//-----------------------------------------------------------
//int16_t calcSampleOsc(OscInfo* osc);
//-----------------------------------------------------------
/** set the played midi note.*/
// Live performance-note transpose, -63..64 semitones.
void osc_setNotePitchOffset(int8_t offset);
void osc_setGlobalPitchOffset(uint8_t value);
void osc_setGlobalPitchBend(int16_t bend, uint8_t range);
void osc_setPitchBend(OscInfo* osc, int16_t bend, uint8_t range);
void osc_setBaseNote(OscInfo* osc, uint8_t baseNote);
//-----------------------------------------------------------
/** recalculate the frequency if either the base note or the offset note value changed*/
void osc_recalcFreq(OscInfo* osc);

#endif /* OSCILLATOR_H_ */
