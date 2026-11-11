/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only
 * Mutador 0.2.93 filter envelope and accent of every voice filter.
 *
 * Filter page, 2nd screen, per filter (voices 1-3, snare, cymbal, hihat):
 *  env  0..127 shown -63..+63: octaves (up to FENV_OCTAVES) the envelope
 *       moves the cutoff up or down, around the LFO/velocity modulated cutoff
 *  fdc  0 = the amp EG is the envelope (as aef in 0.2.91/0.2.92),
 *       1..127 = an own decay envelope, 10 ms .. 2 s, restarted on each hit
 *  acc  0..127 accent strength. An accent step (step page acc) plays louder
 *       (velocity), adds a filter sweep that builds up on accents in a row and
 *       runs the own decay short (0.2 s, or fdc if shorter), like the TB-303.
 *       0.2.95: a legato slide keeps the env running (the accent only charges
 *       the sweep), the resonance shapes the sweep, and the sweep left from
 *       earlier accents makes the next accent louder.
 * Kept in flash: the voices only test fenv_on[] in ITCM. */
#ifndef FILTERENV_H_
#define FILTERENV_H_
#include <stdint.h>

#define FENV_SLOTS 6	// voices 1-3, snare, cymbal, hihat (closed and open share it)
enum { FENV_AMOUNT, FENV_DECAY, FENV_ACCENT, FENV_KINDS };
#define FENV_CENTER 64
#define FENV_OCTAVES 6.f
#define FENV_ACC_DEFAULT 64
#define FENV_ACC_OCTAVES 3.f	// filter sweep of one full accent
#define FENV_ACC_SECONDS 0.2f	// accented own decay at most this long
#define FENV_ATTACK_SECONDS 0.003f	// 0.2.97 short attack of the own decay on voices 1-3, like the 303
/* 0.2.95 the filter resonance shapes the accent sweep like the 303's
 * dual resonance pot: low = short and spiky, high = soft and long. */
#define FENV_PULSE_MIN 0.05f	// sweep charge time at resonance 0 ..
#define FENV_PULSE_SPAN 0.15f	// .. plus this at full resonance
#define FENV_LEAK_MIN 0.04f		// sweep leak time constant at resonance 0 ..
#define FENV_LEAK_SPAN 0.11f	// .. plus this at full resonance (5 % after ~0.45 s)
#define FENV_DONE 0.001f
#define FENV_MIN_F 0.0002f
/* parameters PAR_AEF_AMT4.. in kit order: env 4-6, fdc 1-6, acc 1-6 */
#define FENV_EXTRA_VALUES 15

typedef struct
{
	float base;		// cutoff before the envelope (LFO/velocity modulated)
	float amount;	// octaves at envelope 1
	float env;		// own decay envelope
	float coef;		// own decay per block
	float accAmount;// sweep octaves of one accent
	float accEnv;	// accent pulse
	float sweep;	// accent sweep in octaves
	float pulseCoef;// accent pulse per block (from the resonance)
	float att;		// 0.2.97 attack ramp of the own decay, 0..1
	float leak;		// sweep leak per block (from the resonance)
	uint8_t value[FENV_KINDS];
	uint8_t accentNext;	// set by the sequencer for the next hit
	uint8_t accentNote;	// the sounding note is accented
	uint8_t slide;		// 0.2.95 the next hit slides in legato: no env restart
} FilterEnv;

extern FilterEnv fenv[FENV_SLOTS];
extern uint8_t fenv_on[FENV_SLOTS];

void fenv_init(void);
uint8_t fenv_slot(uint8_t voice);
void fenv_setParam(uint8_t kind, uint8_t slot, uint8_t value);
uint8_t fenv_getParam(uint8_t kind, uint8_t slot);
/* kit order index 0..FENV_EXTRA_VALUES-1 -> kind and slot */
void fenv_extraIndex(uint8_t index, uint8_t *kind, uint8_t *slot);
void fenv_setBase(uint8_t slot, float value);
uint8_t fenv_accentVelocity(uint8_t voice, uint8_t accent, uint8_t vel);
void fenv_slide(uint8_t voice);	// Drum_trigger: this hit is a legato slide
void fenv_trigger(uint8_t voice, uint8_t vel);
void fenv_tick(uint8_t slot, float amp);

#endif /* FILTERENV_H_ */
