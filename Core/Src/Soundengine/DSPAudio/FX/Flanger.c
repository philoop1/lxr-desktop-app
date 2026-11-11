/* SPDX-License-Identifier: GPL-3.0-only
 * Flanger.c - Mutador 0.2.82 flanger "fln" (own code).
 *
 * Delay line of FLANGER_BUFFER int16 samples per instance. The delay follows a
 * triangle LFO, d = time * (1 - depth * lfo), lfo 0..1; it is computed at the
 * block ends and ramped per sample, and read with linear interpolation. The
 * line is fed with input plus feedback times the delayed sample. Output is
 * x * (1 - mix/2) + delayed * mix/2: mix 1 is the equal blend with the
 * deepest notches, and correlated material keeps its level.
 */
#include "Soundengine/DSPAudio/FX/Flanger.h"
#include <math.h>
#include <string.h>

static inline int16_t fl_sat16(float v)
{
	return (int16_t)(v > 32767.f ? 32767.f : v < -32768.f ? -32768.f : v);
}

static inline float fl_clamp01(float v)
{
	return v < 0.f ? 0.f : v > 1.f ? 1.f : v;
}

void Flanger_reset(Flanger *f)
{
	memset(f->buf, 0, sizeof(f->buf));
	f->write = 0u;
	f->last = 0.f;
}

void Flanger_init(Flanger *f)
{
	Flanger_reset(f);
	f->phase = 0.f;
	Flanger_setRate(f, 0.3f);
	Flanger_setDepth(f, 0.7f);
	Flanger_setTime(f, 0.5f);
	Flanger_setFeedback(f, 0.5f);
}

/* 0.03 Hz .. 7.7 Hz, like the phaser */
void Flanger_setRate(Flanger *f, float v)
{
	f->rate = 0.03f * exp2f(fl_clamp01(v) * 8.f);
}
void Flanger_setDepth(Flanger *f, float v)
{
	f->depth = fl_clamp01(v);
}
/* longest delay 0.25 .. 25 ms (0.2.86, was 16 ms): 0.25 * 100^v */
void Flanger_setTime(Flanger *f, float v)
{
	const float ms = 0.25f * exp2f(fl_clamp01(v) * 6.643856f);
	f->time = ms * 0.001f * FLANGER_FS;
}
/* 0 = -0.9, 0.5 = none, 1 = +0.9 */
void Flanger_setFeedback(Flanger *f, float v)
{
	f->feedback = (fl_clamp01(v) * 2.f - 1.f) * FLANGER_FEEDBACK_MAX;
}

static inline float fl_delay(const Flanger *f, float phase)
{
	if(phase >= 1.f) phase -= 1.f;
	const float lfo = phase < 0.5f ? 2.f * phase : 2.f - 2.f * phase;	// 0..1..0
	float d = f->time * (1.f - f->depth * lfo);
	if(d < 1.f) d = 1.f;
	if(d > (float)(FLANGER_BUFFER - 2u)) d = (float)(FLANGER_BUFFER - 2u);
	return d;
}

void Flanger_processMono(Flanger *f, int16_t *buf, uint16_t size, float mix)
{
	if(!size) return;
	const float d0 = fl_delay(f, f->phase);
	f->phase += f->rate * (float)size / FLANGER_FS;
	if(f->phase >= 1.f) f->phase -= 1.f;
	const float d1 = fl_delay(f, f->phase);
	const float step = (d1 - d0) / (float)size;
	const float wet = 0.5f * fl_clamp01(mix);
	const float dry = 1.f - wet;
	float d = d0;
	uint16_t w = f->write;
	float last = f->last;
	for(uint16_t i = 0; i < size; i++)
	{
		d += step;
		float rp = (float)w - d;
		if(rp < 0.f) rp += (float)FLANGER_BUFFER;
		uint16_t i0 = (uint16_t)rp;
		if(i0 >= FLANGER_BUFFER) i0 = 0u;	// rounding guard
		const float frac = rp - (float)i0;
		const uint16_t i1 = (uint16_t)(i0 + 1u < FLANGER_BUFFER ? i0 + 1u : 0u);
		const float a = (float)f->buf[i0];
		const float del = a + ((float)f->buf[i1] - a) * frac;
		last = del;
		const float x = (float)buf[i];
		f->buf[w] = fl_sat16(x + f->feedback * del);
		if(++w >= FLANGER_BUFFER) w = 0u;
		buf[i] = fl_sat16(x * dry + del * wet);
	}
	f->write = w;
	f->last = last;
}
