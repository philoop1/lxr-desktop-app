/* SPDX-License-Identifier: GPL-3.0-only
 * Phaser.c - Mutador 0.2.78 send FX "pha" (own code).
 *
 * Each channel runs the input plus feedback through six first-order allpass
 * stages, y = a*x + z, z = x - a*y. Mixing the result with the dry signal
 * (d/w around the middle) gives the moving notches. The coefficient follows a
 * triangle LFO that sweeps the stage frequency exponentially around the centre;
 * it is computed once per block and ramped linearly across the block, so the
 * cost per sample is only the multiply-adds. The right channel runs 90 degrees
 * ahead for width. Plain C saturation keeps the file host-testable.
 */
#include "Soundengine/DSPAudio/FX/Phaser.h"
#include <math.h>
#include <string.h>

static inline int16_t ph_sat16(int32_t v)
{
	return (int16_t)(v > 32767 ? 32767 : v < -32768 ? -32768 : v);
}

void Phaser_reset(Phaser *p)
{
	memset(p->z, 0, sizeof(p->z));
	p->last[0] = p->last[1] = 0.f;
}

void Phaser_init(Phaser *p)
{
	Phaser_reset(p);
	p->phase = 0.f;
	Phaser_setRate(p, 0.4f);
	Phaser_setDepth(p, 0.7f);
	Phaser_setCentre(p, 0.4f);
	Phaser_setFeedback(p, 0.5f);
	p->a[0] = p->a[1] = Phaser_coefficient(p, 0.f);
}

/* 0.03 Hz .. 7.7 Hz */
void Phaser_setRate(Phaser *p, float v)
{
	v = v < 0.f ? 0.f : v > 1.f ? 1.f : v;
	p->rate = 0.03f * exp2f(v * 8.f);
}
/* up to 2.5 octaves either side */
void Phaser_setDepth(Phaser *p, float v)
{
	v = v < 0.f ? 0.f : v > 1.f ? 1.f : v;
	p->depth = v * 2.5f;
}
/* 150 Hz .. 4.8 kHz */
void Phaser_setCentre(Phaser *p, float v)
{
	v = v < 0.f ? 0.f : v > 1.f ? 1.f : v;
	p->centre = 150.f * exp2f(v * 5.f);
}
void Phaser_setFeedback(Phaser *p, float v)
{
	v = v < 0.f ? 0.f : v > 1.f ? 1.f : v;
	p->feedback = v * PHASER_FEEDBACK_MAX;
}

float Phaser_coefficient(const Phaser *p, float lfo)
{
	float f = p->centre * exp2f(p->depth * lfo);
	if(f < 30.f) f = 30.f;
	if(f > 15000.f) f = 15000.f;
	const float t = tanf(3.14159265f * f / PHASER_FS);
	return (t - 1.f) / (t + 1.f);
}

static inline float ph_triangle(float phase)
{
	if(phase >= 1.f) phase -= 1.f;
	return phase < 0.5f ? 4.f * phase - 1.f : 3.f - 4.f * phase;
}

static inline float ph_chain(Phaser *p, uint8_t ch, float x, float a)
{
	float *z = p->z[ch];
	float s = x + p->feedback * p->last[ch];
	for(uint8_t k = 0; k < PHASER_STAGES; k++)
	{
		const float y = a * s + z[k];
		z[k] = s - a * y;
		s = y;
	}
	p->last[ch] = s;
	return s;
}

void Phaser_process(Phaser *p, int16_t *fxBuffer, int16_t *outL, uint16_t size, uint8_t channels, float dryWet)
{
	if(!size) return;
	p->phase += p->rate * (float)size / PHASER_FS;
	if(p->phase >= 1.f) p->phase -= 1.f;

	const uint8_t nch = channels == 2 ? 2 : 1;
	float a[2], step[2];
	const float inv = 1.f / (float)size;
	for(uint8_t ch = 0; ch < nch; ch++)
	{
		const float target = Phaser_coefficient(p, ph_triangle(p->phase + (ch ? 0.25f : 0.f)));
		a[ch] = p->a[ch];
		step[ch] = (target - a[ch]) * inv;
		p->a[ch] = target;
	}

	for(uint16_t i = 0; i < size; i++)
	{
		const uint16_t idx = (uint16_t)(i * 2u);
		for(uint8_t ch = 0; ch < nch; ch++)
		{
			a[ch] += step[ch];
			const float dry = (float)fxBuffer[idx + ch];
			const float wet = ph_chain(p, ch, dry * (1.f / 32768.f), a[ch]) * 32768.f;
			const int32_t mixed = (int32_t)(dry + (wet - dry) * dryWet);
			/* interleaved output: mono uses the left slot of each pair */
			outL[idx + ch] = ph_sat16((int32_t)outL[idx + ch] + ph_sat16(mixed));
		}
	}
}

/* 0.2.79: one mono channel in place, for the per-voice insert */
void Phaser_processMono(Phaser *p, int16_t *buf, uint16_t size, float mix)
{
	if(!size) return;
	p->phase += p->rate * (float)size / PHASER_FS;
	if(p->phase >= 1.f) p->phase -= 1.f;
	const float target = Phaser_coefficient(p, ph_triangle(p->phase));
	float a = p->a[0];
	const float step = (target - a) / (float)size;
	p->a[0] = target;
	for(uint16_t i = 0; i < size; i++)
	{
		a += step;
		const float dry = (float)buf[i];
		const float wet = ph_chain(p, 0, dry * (1.f / 32768.f), a) * 32768.f;
		buf[i] = ph_sat16((int32_t)(dry + (wet - dry) * mix));
	}
}
