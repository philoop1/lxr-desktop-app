/* SPDX-License-Identifier: GPL-3.0-only
 * Flanger.h - Mutador 0.2.82 flanger "fln" (own code), mono, in place.
 *
 * A delay of up to 50 ms (0.2.108) read with linear interpolation, swept by a triangle
 * LFO from the set time down towards zero, with feedback (positive or
 * negative). The output is dry plus delayed, so full mix gives the deepest
 * comb notches.
 */
#ifndef INC_SOUNDENGINE_DSPAUDIO_FX_FLANGER_H_
#define INC_SOUNDENGINE_DSPAUDIO_FX_FLANGER_H_

#include <stdint.h>

#define FLANGER_FS 44100.f
#define FLANGER_MAX_MS 50.f
/* 0.2.108: 50 ms = 2205 samples, plus room for the interpolation (was 25 ms) */
#define FLANGER_BUFFER 2215u
#define FLANGER_FEEDBACK_MAX 0.9f

typedef struct FlangerStruct
{
	int16_t buf[FLANGER_BUFFER];
	uint16_t write;
	float phase;		// LFO 0..1
	float rate;			// Hz
	float depth;		// 0..1 of the time swept
	float time;			// samples, longest delay
	float feedback;		// -FLANGER_FEEDBACK_MAX..FLANGER_FEEDBACK_MAX
	float last;			// delayed sample, for the feedback
} Flanger;

void Flanger_init(Flanger *f);
void Flanger_reset(Flanger *f);
/* all setters take 0..1; feedback 0.5 is none */
void Flanger_setRate(Flanger *f, float v);
void Flanger_setDepth(Flanger *f, float v);
void Flanger_setTime(Flanger *f, float v);
void Flanger_setFeedback(Flanger *f, float v);
void Flanger_processMono(Flanger *f, int16_t *buf, uint16_t size, float mix);

#endif /* INC_SOUNDENGINE_DSPAUDIO_FX_FLANGER_H_ */
