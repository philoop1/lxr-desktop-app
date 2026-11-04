/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only
 * Tempo-synced tape delay. Mono uses the whole FX_BUFFER; ping pong splits it
 * into a left and a right line that feed each other.
 */
#include "Soundengine/DSPAudio/FX/TapeDelay.h"

// Glide time constant 150 ms
#define TAPE_GLIDE (1.f/(0.15f*REAL_FS))

// Length of each division in quarter notes, in repeatSyncNames order
static const float tapeQuarters[TAPE_DIVISIONS] =
{
	4.f, 3.f, 2.f, 1.5f, 4.f/3.f, 1.f, 0.75f, 2.f/3.f,
	0.5f, 0.375f, 1.f/3.f, 0.25f, 1.f/6.f, 0.125f, 0.0625f, 0.03125f
};

void TapeDelay_init(TapeDelay *d)
{
	d->rate = 0.5f;
	d->fine = 64.f/127.f;
	d->feedback = 0.5f;
	d->pingPong = 0;
	TapeDelay_setTone(d, 1.f);
	TapeDelay_reset(d);
}

void TapeDelay_reset(TapeDelay *d)
{
	d->write = 0;
	d->valid = 0;
	d->primed = 0;
	d->lpL = d->lpR = 0.f;
}

void TapeDelay_setPingPong(TapeDelay *d, uint8_t pingPong)
{
	pingPong = pingPong ? 1 : 0;
	if(pingPong != d->pingPong)
	{
		d->pingPong = pingPong;
		// the line layout changes, so the old content is no longer valid
		TapeDelay_reset(d);
	}
}

void TapeDelay_setRate(TapeDelay *d, float rate)
{
	d->rate = rate;
}

void TapeDelay_setFine(TapeDelay *d, float fine)
{
	d->fine = fine;
}

void TapeDelay_setTone(TapeDelay *d, float tone)
{
	d->tone = 0.01f + 0.99f*tone*tone;
}

void TapeDelay_setFeedback(TapeDelay *d, float fb)
{
	d->feedback = fb;
}

static float tapeSamples(uint8_t division, float fine, float bpm)
{
	const float factor = 1.f + (fine*127.f - 64.f)/TAPE_FINE_SPAN;
	return tapeQuarters[division]*60.f/(bpm > 1.f ? bpm : 1.f)*REAL_FS*factor;
}

static float tapeMaxSamples(uint8_t pingPong)
{
	return (float)((pingPong ? (FX_BUFFER_SIZE>>1) : FX_BUFFER_SIZE) - 1);
}

uint8_t TapeDelay_division(float rate, float fine, float bpm, uint8_t pingPong)
{
	const float max = tapeMaxSamples(pingPong);
	int32_t division = (int32_t)(rate*TAPE_DIVISIONS);
	if(division < 0) division = 0;
	if(division > TAPE_DIVISIONS-1) division = TAPE_DIVISIONS-1;
	while(division < TAPE_DIVISIONS-1 && tapeSamples((uint8_t)division, fine, bpm) > max)
		division++;
	return (uint8_t)division;
}

float TapeDelay_targetSamples(float rate, float fine, float bpm, uint8_t pingPong)
{
	const float max = tapeMaxSamples(pingPong);
	const float samples = tapeSamples(TapeDelay_division(rate, fine, bpm, pingPong), fine, bpm);
	return samples > max ? max : samples < 1.f ? 1.f : samples;
}

// soft clip like tape: unity gain for small signals, flat at +-1 from 1.5 on
static inline float tapeSaturate(float v)
{
	if(v > 1.5f) return 1.f;
	if(v < -1.5f) return -1.f;
	return v - v*v*v*(1.f/6.75f);
}

IN_ITCM_RAM void TapeDelay_process(TapeDelay *d, int16_t *fxBuffer, int16_t* outL, uint16_t size, uint8_t channels, float dryWet, float bpm)
{
	int32_t* stereoOut = (int32_t*)outL;
	const uint32_t mask = d->pingPong ? (FX_BUFFER_SIZE>>1) : FX_BUFFER_SIZE;
	const float len = (float)(mask + 1);
	// the right line of ping pong starts behind the left one
	volatile __fp16 *right = &FX_BUFFER[mask + 1];
	const float target = TapeDelay_targetSamples(d->rate, d->fine, bpm, d->pingPong);
	if(!d->primed)
	{
		d->delay = target;
		d->primed = 1;
	}
	float delay = d->delay;
	float lpL = d->lpL;
	float lpR = d->lpR;
	uint32_t write = d->write;
	uint32_t valid = d->valid;
	const float tone = d->tone;
	const float fb = d->feedback;

	for(uint8_t i=0;i<size;i++)
	{
		const int16_t dryL = fxBuffer[i*2];
		const int16_t dryR = fxBuffer[i*2+1];

		delay += (target - delay)*TAPE_GLIDE;
		float pos = (float)write - delay;
		if(pos < 0.f) pos += len;
		uint32_t i0 = (uint32_t)pos;
		const float frac = pos - (float)i0;
		i0 &= mask;
		const uint32_t i1 = (i0 + 1) & mask;
		// nothing older than the last reset may sound
		const float audible = (delay <= (float)valid) ? 1.f : 0.f;

		const float a = FX_BUFFER[i0];
		lpL += ((a + frac*((float)FX_BUFFER[i1] - a))*audible - lpL)*tone;

		// both channels summed like the Delay
		const float in = ((int32_t)dryL + dryR)/32768.f;
		float wetR;
		if(d->pingPong)
		{
			const float b = right[i0];
			lpR += ((b + frac*((float)right[i1] - b))*audible - lpR)*tone;
			FX_BUFFER[write] = (__fp16)tapeSaturate(in + fb*lpR);
			right[write] = (__fp16)tapeSaturate(fb*lpL);
			wetR = lpR;
		}
		else
		{
			FX_BUFFER[write] = (__fp16)tapeSaturate(in + fb*lpL);
			wetR = lpL;
		}
		write = (write + 1) & mask;
		if(valid <= mask) valid++;

		const int32_t wet = __SSAT((int32_t)(lpL*32767.f), 16);
		const int32_t wet2 = __SSAT((int32_t)(wetR*32767.f), 16);
		const int32_t x = __PKHBT(__SSAT(dryL + __SSAT((int32_t)((wet - dryL)*dryWet),16),16),
				__SSAT(dryR + __SSAT((int32_t)((wet2 - dryR)*dryWet),16),16), 16);
		if (channels == 2)
		{
			*stereoOut = __QADD16(*stereoOut, x);
			stereoOut++;
		}
		else
		{
			*(uint16_t*)stereoOut = __QADD16(*stereoOut, x);
			stereoOut++;
		}
	}

	d->delay = delay;
	d->lpL = lpL;
	d->lpR = lpR;
	d->write = write;
	d->valid = valid;
}
