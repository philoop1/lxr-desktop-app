/* SPDX-License-Identifier: GPL-3.0-only
 * Phaser.h - Mutador 0.2.78 send FX "pha": six first-order allpass stages per
 * channel, triangle LFO (right channel 90 degrees ahead), feedback.
 */
#ifndef INC_SOUNDENGINE_DSPAUDIO_FX_PHASER_H_
#define INC_SOUNDENGINE_DSPAUDIO_FX_PHASER_H_

#include <stdint.h>

#define PHASER_STAGES 6
#define PHASER_FS 44100.f

typedef struct PhaserStruct
{
	float z[2][PHASER_STAGES];	// allpass states per channel
	float last[2];				// chain output for the feedback
	float a[2];					// allpass coefficient reached at the end of the last block
	float phase;				// LFO phase 0..1
	float rate;					// Hz
	float depth;				// octaves either side of the centre
	float centre;				// Hz
	float feedback;				// 0..PHASER_FEEDBACK_MAX
} Phaser;

#define PHASER_FEEDBACK_MAX 0.85f

void Phaser_init(Phaser *p);
void Phaser_reset(Phaser *p);
void Phaser_process(Phaser *p, int16_t *fxBuffer, int16_t *outL, uint16_t size, uint8_t channels, float dryWet);
void Phaser_processMono(Phaser *p, int16_t *buf, uint16_t size, float mix);
/* all setters take 0..1 */
void Phaser_setRate(Phaser *p, float v);
void Phaser_setDepth(Phaser *p, float v);
void Phaser_setCentre(Phaser *p, float v);
void Phaser_setFeedback(Phaser *p, float v);
/* allpass coefficient for a sweep position, exposed for the host test */
float Phaser_coefficient(const Phaser *p, float lfo);

#endif /* INC_SOUNDENGINE_DSPAUDIO_FX_PHASER_H_ */
