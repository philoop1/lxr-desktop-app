/*
 * Compressor.c
 *
 *  Created on: Aug 27, 2020
 *      Author: julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

#include "Soundengine/DSPAudio/FX/Compressor.h"
#include "math.h"
#include "main.h"


enum
{
	RATIO_1,
	RATIO_2,
	RATIO_3,
	RATIO_4,
	RATIO_6,
	RATIO_8
};

static const double DC_OFFSET = 1.0E-25;

void Compressor_init(Compressor *c)
{
	c->attack = 0.1;
	c->release = 300;

	//c->filter = 0.0;
	c->env = 0.0;
	c->tresh = 3;
	c->markupGain = 1.0f;

}

// linear -> dB conversion
static double lin2dB( double lin ) {
	static const double LOG_2_DB = 8.6858896380650365530225783783321;	// 20 / ln( 10 )
	return logf( lin ) * LOG_2_DB;
}

// dB -> linear conversion
static double dB2lin( double dB ) {
	static const double DB_2_LOG = 0.11512925464970228420089957273422;	// ln( 10 ) / 20
	return expf( dB * DB_2_LOG );
}

//att/release, time in ms to reach 63% of final value
void Compressor_setAttack(Compressor *c, float a)
{
	c->attack = 0.03f + a *100.f; //[ms]
	c->attack = exp( -1000.0 / ( c->attack * REAL_FS ) );
}
void Compressor_setTreshold(Compressor *c, float t)
{
	c->tresh = -96 + t*96; //[-96:0]dB
}

void Compressor_setGain(Compressor *c, float g)
{
	c->markupGain = 1.f + g*2;
}
void Compressor_setRelease(Compressor *c, float r)
{
	c->release = 25+r*175.f; //[ms]
	c->release = exp( -1000.0 / ( c->release * REAL_FS ) );
}

void Compressor_setRatio(Compressor *c, uint8_t r)
{
	switch(r)
	{
	default:
	case RATIO_1:
		c->ratio = 1.0f;
		break;

	case RATIO_2:
		c->ratio = 0.5f;
		break;
	case RATIO_3:
		c->ratio = 1.f/3.f;
		break;
	case RATIO_4:
		c->ratio = 0.25f;
		break;
	case RATIO_6:
		c->ratio = 1.f/6.f;
		break;
	case RATIO_8:
		c->ratio = 0.125f;
		break;
	}
}

void Compressor_process(Compressor *c, int16_t *fxBuffer,int16_t* outL, int16_t* outR, uint16_t size,  uint8_t channels, float dryWet)
{


	int32_t x;
	int32_t* stereoOut = (int32_t*)outL;

	int16_t left[size];
	int16_t right[size];

	if(channels==2)
	{

		for(uint8_t i=0; i<size;i++)
		{
			//--- Compressor ---
			float in = 0.5 * (fxBuffer[i*2]/32768.f) + 0.5 * (fxBuffer[i*2+1]/32768.f);
			double peak = fabs(in);

			//value over thresh
			peak += DC_OFFSET;
			double peakdB = lin2dB(peak);
			double overdB = peakdB - c->tresh;
			if ( overdB < 0.0 )
				overdB = 0.0;

			// dynamic selection: attack or release?
			double  coeff = overdB > c->env ? c->attack : c->release;
			c->env = overdB + coeff * (c->env - overdB);
			//c->env = c->env + (1-coeff) * (overdB -c->env); //should be the same as above, without 1-

			double gr = c->env * (c->ratio - 1.0);
			gr = dB2lin(gr);
			//debugWatch = gr;

			left[i]  = __SSAT(fxBuffer[i*2] * gr * c->markupGain, 16);//gain;
			right[i] = __SSAT(fxBuffer[i*2+1] * gr * c->markupGain, 16);//gain;


			//--- Output transfer ---
			//TODO can be optimized quite a bit with SIMD
			const uint8_t idx1 = i*2;
			const uint8_t idx2 = i*2+1;
			//int16_t wet = __SSAT((int32_t)(left[i] * 32768.0f), 16);
			//int16_t wet2 = __SSAT((int32_t)(right[i] * 32768.0f), 16);
			x = __PKHBT(fxBuffer[idx1] + __SSAT((left[i] - fxBuffer[idx1]) * dryWet,16), fxBuffer[idx2] + __SSAT((right[i] - fxBuffer[idx2]) * dryWet,16), 16);
			//int16_t dw = fxBuffer[i] + __SSAT((wet - fxBuffer[i]) * dryWet,16);
			*stereoOut = __QADD16(*stereoOut, x);
			stereoOut++;
		}
	}
	else
	{
		for(uint8_t i=0; i<size;i++)
		{
			const uint8_t idx1 = i*2;
			//--- Compressor ---
			float in = fxBuffer[idx1]/32768.f;
			double peak = fabs(in);

			//value over thresh
			peak += DC_OFFSET;
			double peakdB = lin2dB(peak);
			double overdB = peakdB - c->tresh;
			if ( overdB < 0.0 )
				overdB = 0.0;

			// dynamic selection: attack or release?
			double  coeff = overdB > c->env ? c->attack : c->release;
			c->env = overdB + coeff * (c->env - overdB);
			//c->env = c->env + (1-coeff) * (overdB -c->env); //should be the same as above, without 1-

			double gr = c->env * (c->ratio - 1.0);
			gr = dB2lin(gr);
			//debugWatch = gr;

			left[i]  = fxBuffer[idx1] * gr * c->markupGain;//gain;


			//--- Output transfer ---
			const int16_t dw = fxBuffer[idx1] + __SSAT((left[i] - fxBuffer[idx1]) * dryWet,16);
			*outL = __QADD16(*outL, dw);
			outL += 2;
		}
	}
}

//-----------------------------------------------------------------------
/* 0.2.71 master compressor. Same detector, ratio, attack/release and gain
 * mapping as the FX compressor, in float and with the gain computed once
 * per 4 frames (stereo-linked peak of the 4 frames, coefficients raised to the 4th power,
 * gain interpolated in between). Mix and the on/off switch fade per frame. */
#define MCOMP_HOP 4
static Compressor masterComp;
static float masterComp_attack4 = 0.f, masterComp_release4 = 0.f;
static float masterComp_env = 0.f, masterComp_gain = 1.f;
static float masterComp_wet = 0.f, masterComp_wetTarget = 0.f;
static uint8_t masterComp_on = 0, masterComp_mix = 100, masterComp_ready = 0;

static void masterComp_initOnce(void)
{
	if(masterComp_ready) return;
	Compressor_init(&masterComp);
	Compressor_setRatio(&masterComp, RATIO_4);
	Compressor_setAttack(&masterComp, 10/127.f);
	Compressor_setRelease(&masterComp, 40/127.f);
	Compressor_setTreshold(&masterComp, 90/127.f);
	Compressor_setGain(&masterComp, 0.f);
	masterComp_attack4 = powf(masterComp.attack, MCOMP_HOP);
	masterComp_release4 = powf(masterComp.release, MCOMP_HOP);
	masterComp_ready = 1;
}

void masterComp_set(uint8_t idx, uint8_t value)
{
	masterComp_initOnce();
	const float v = (value > 127 ? 127 : value) / 127.f;
	switch(idx)
	{
	case 0: masterComp_on = value ? 1 : 0; break;
	case 1: Compressor_setRatio(&masterComp, value <= RATIO_8 ? value : RATIO_4); break;
	case 2: Compressor_setAttack(&masterComp, v); masterComp_attack4 = powf(masterComp.attack, MCOMP_HOP); break;
	case 3: Compressor_setRelease(&masterComp, v); masterComp_release4 = powf(masterComp.release, MCOMP_HOP); break;
	case 4: Compressor_setTreshold(&masterComp, v); break;
	case 5: Compressor_setGain(&masterComp, v); break;
	case 6: masterComp_mix = value > 100 ? 100 : value; break;
	default: break;
	}
	masterComp_wetTarget = masterComp_on ? masterComp_mix / 100.f : 0.f;
}

__attribute__((noinline)) void masterComp_process(int16_t *stereo, uint32_t frames)
{
	if(!masterComp_ready || (masterComp_wet <= 0.f && masterComp_wetTarget <= 0.f)) {
		masterComp_env = 0.f; masterComp_gain = 1.f; masterComp_wet = 0.f;
		return;
	}
	const float wetStep = 1.f / 256.f;	// about 6 ms fade for on/off and mix
	const float makeup = masterComp.markupGain;
	for(uint32_t f = 0; f + MCOMP_HOP <= frames; f += MCOMP_HOP)
	{
		int16_t *s = &stereo[f * 2];
		float peak = 0.f;
		for(uint32_t k = 0; k < MCOMP_HOP; k++) {
			/* stereo-linked peak: louder channel, so anti-phase content is seen too */
			const float l = fabsf(s[2*k] / 32768.f), r = fabsf(s[2*k+1] / 32768.f);
			const float in = l > r ? l : r;
			if(in > peak) peak = in;
		}
		float over = logf(peak + 1.0e-25f) * 8.6858896f - masterComp.tresh;
		if(over < 0.f) over = 0.f;
		const float coeff = over > masterComp_env ? masterComp_attack4 : masterComp_release4;
		masterComp_env = over + coeff * (masterComp_env - over);
		const float target = expf(masterComp_env * (masterComp.ratio - 1.f) * 0.11512925f) * makeup;
		const float startGain = masterComp_gain;
		const float gainStep = (target - startGain) / MCOMP_HOP;
		for(uint32_t k = 0; k < MCOMP_HOP; k++) {
			const float g = startGain + gainStep * (k + 1);
			if(masterComp_wet < masterComp_wetTarget) {
				masterComp_wet += wetStep; if(masterComp_wet > masterComp_wetTarget) masterComp_wet = masterComp_wetTarget;
			} else if(masterComp_wet > masterComp_wetTarget) {
				masterComp_wet -= wetStep; if(masterComp_wet < masterComp_wetTarget) masterComp_wet = masterComp_wetTarget;
			}
			const float mixGain = 1.f + (g - 1.f) * masterComp_wet;
			s[2*k]   = (int16_t)__SSAT((int32_t)(s[2*k]   * mixGain), 16);
			s[2*k+1] = (int16_t)__SSAT((int32_t)(s[2*k+1] * mixGain), 16);
		}
		masterComp_gain = target;
	}
}
