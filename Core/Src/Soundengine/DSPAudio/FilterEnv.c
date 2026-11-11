/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only
 * Mutador 0.2.93 filter envelope and accent, see FilterEnv.h. */
#include "Soundengine/DSPAudio/FilterEnv.h"
#include "Soundengine/DSPAudio/DrumVoice.h"
#include "Soundengine/DSPAudio/Snare.h"
#include "Soundengine/DSPAudio/CymbalVoice.h"
#include "Soundengine/DSPAudio/HiHat.h"
#include "Soundengine/DSPAudio/ResonantFilter.h"
#include "Soundengine/config.h"
#include <math.h>

FilterEnv fenv[FENV_SLOTS];
uint8_t fenv_on[FENV_SLOTS];
static float fenv_accCoef;

static ResonantFilter *fenv_filter(uint8_t slot)
{
	switch(slot) {
	case 3: return &snareVoice.filter;
	case 4: return &cymbalVoice.filter;
	case 5: return &hatVoice.filter;
	default: return &voiceArray[slot].filter;
	}
}
/* per block (OUTPUT_DMA_SIZE frames) factor that falls to 5 % in seconds */
static float fenv_blockCoef(float seconds)
{
	return expf(-3.f*(float)OUTPUT_DMA_SIZE/(REAL_FS*seconds));
}
__attribute__((noinline)) void fenv_init(void)
{
	fenv_accCoef = fenv_blockCoef(FENV_ACC_SECONDS);
	for(uint8_t s=0;s<FENV_SLOTS;s++) {
		FilterEnv *e=&fenv[s];
		e->base=0.25f; e->amount=0.f; e->env=0.f; e->coef=0.f; e->accEnv=0.f; e->sweep=0.f; e->att=1.f;
		e->value[FENV_AMOUNT]=FENV_CENTER; e->value[FENV_DECAY]=0;
		e->value[FENV_ACCENT]=FENV_ACC_DEFAULT; e->accAmount=FENV_ACC_DEFAULT*(FENV_ACC_OCTAVES/127.f);
		e->accentNext=e->accentNote=e->slide=0;
		e->pulseCoef=fenv_blockCoef(FENV_PULSE_MIN+FENV_PULSE_SPAN);
		e->leak=expf(-(float)OUTPUT_DMA_SIZE/(REAL_FS*(FENV_LEAK_MIN+FENV_LEAK_SPAN)));
		fenv_on[s]=0;
	}
}
__attribute__((noinline)) uint8_t fenv_slot(uint8_t voice)
{
	return voice<5 ? voice : 5;
}
static void fenv_idle(uint8_t slot)
{
	FilterEnv *e=&fenv[slot];
	e->sweep=e->accEnv=0.f;
	fenv_on[slot]=0;
	SVF_directSetFilterValue(fenv_filter(slot), e->base);
}
__attribute__((noinline)) void fenv_setParam(uint8_t kind, uint8_t slot, uint8_t value)
{
	if(kind>=FENV_KINDS || slot>=FENV_SLOTS)return;
	FilterEnv *e=&fenv[slot];
	if(value>127)value=127;
	switch(kind) {
	case FENV_AMOUNT:
		if(value==0)value=1; // symmetric -63..+63
		e->amount=(float)((int)value-FENV_CENTER)*(FENV_OCTAVES/63.f);
		break;
	case FENV_DECAY:
		/* 1..127 = 10 ms .. 2 s */
		e->coef = value ? fenv_blockCoef(0.01f*exp2f((float)value*(7.643856f/127.f))) : 0.f;
		break;
	default:
		e->accAmount=(float)value*(FENV_ACC_OCTAVES/127.f);
		break;
	}
	e->value[kind]=value;
	if(e->amount!=0.f) fenv_on[slot]=1;
	else if(fenv_on[slot] && e->sweep<FENV_DONE && e->accEnv<FENV_DONE) fenv_idle(slot);
}
__attribute__((noinline)) uint8_t fenv_getParam(uint8_t kind, uint8_t slot)
{
	if(kind>=FENV_KINDS || slot>=FENV_SLOTS)return 0;
	return fenv[slot].value[kind];
}
__attribute__((noinline)) void fenv_extraIndex(uint8_t index, uint8_t *kind, uint8_t *slot)
{
	if(index<3) { *kind=FENV_AMOUNT; *slot=(uint8_t)(3+index); }
	else if(index<9) { *kind=FENV_DECAY; *slot=(uint8_t)(index-3); }
	else { *kind=FENV_ACCENT; *slot=(uint8_t)(index-9); }
}
__attribute__((noinline)) void fenv_setBase(uint8_t slot, float value)
{
	if(slot>=FENV_SLOTS)return;
	fenv[slot].base=value;
	SVF_directSetFilterValue(fenv_filter(slot), value); // the next block adds the envelope
}
/* sequencer: an accent step plays louder and marks the next hit */
__attribute__((noinline)) uint8_t fenv_accentVelocity(uint8_t voice, uint8_t accent, uint8_t vel)
{
	if(voice>6)return vel;
	FilterEnv *e=&fenv[fenv_slot(voice)];
	e->accentNext = accent && e->value[FENV_ACCENT];
	if(!e->accentNext)return vel;
	/* up to +50 %, and up to twice that while the sweep of earlier accents
	 * is still up: accents in a row get louder (the 303 accent cap feeds the VCA) */
	const float extra=(float)vel*(float)e->value[FENV_ACCENT]*(1.f/254.f)*(1.f+e->sweep*(1.f/(2.f*FENV_ACC_OCTAVES)));
	const float louder=(float)vel+extra+0.5f;
	return louder>=127.f ? 127u : (uint8_t)louder;
}
/* 0.2.95 Drum_trigger: the hit slides in legato, the env keeps running */
__attribute__((noinline)) void fenv_slide(uint8_t voice)
{
	if(voice<3) fenv[voice].slide=1;
}
__attribute__((noinline)) void fenv_trigger(uint8_t voice, uint8_t vel)
{
	if(voice>6)return;
	const uint8_t slot=fenv_slot(voice);
	FilterEnv *e=&fenv[slot];
	const uint8_t slide=e->slide;
	const uint8_t accent=e->accentNext;
	e->slide=0;
	e->accentNext=0;
	if(!vel)return;
	if(!slide) {
		/* a legato slide keeps the env and its decay running, like the 303 */
		e->env=1.f;
		e->att = slot<3 ? 0.f : 1.f; // 0.2.97 voices 1-3: the own decay rises in FENV_ATTACK_SECONDS
		e->accentNote=accent;
	}
	if(accent && e->accAmount>0.f) {
		/* resonance 0..1 (q = 1 - resonance) sets charge and leak of the sweep */
		float reso=1.f-fenv_filter(slot)->q;
		if(reso<0.f)reso=0.f; else if(reso>1.f)reso=1.f;
		e->pulseCoef=fenv_blockCoef(FENV_PULSE_MIN+FENV_PULSE_SPAN*reso);
		e->leak=expf(-(float)OUTPUT_DMA_SIZE/(REAL_FS*(FENV_LEAK_MIN+FENV_LEAK_SPAN*reso)));
		e->accEnv=1.f;
		fenv_on[slot]=1;
	}
}
__attribute__((noinline)) void fenv_tick(uint8_t slot, float amp)
{
	if(slot>=FENV_SLOTS)return;
	FilterEnv *e=&fenv[slot];
	float drive=amp;
	if(e->value[FENV_DECAY]) {
		if(e->att<1.f) {
			e->att+=(float)OUTPUT_DMA_SIZE/(REAL_FS*FENV_ATTACK_SECONDS);
			if(e->att>1.f)e->att=1.f;
		}
		drive=e->env*e->att;
		/* an accent runs the decay short: 0.2 s, or fdc if that is shorter */
		e->env*= e->accentNote && fenv_accCoef<e->coef ? fenv_accCoef : e->coef;
	}
	/* accent sweep: each accent charges it, it leaks slowly, so accents in a row build up */
	if(e->accEnv>FENV_DONE) {
		e->sweep+=e->accEnv*e->accAmount*(1.f-e->pulseCoef);
		e->accEnv*=e->pulseCoef;
	} else e->accEnv=0.f;
	e->sweep*=e->leak;
	if(e->sweep>2.f*FENV_ACC_OCTAVES)e->sweep=2.f*FENV_ACC_OCTAVES;
	if(e->amount==0.f && e->sweep<FENV_DONE && e->accEnv==0.f) { fenv_idle(slot); return; }
	float base=e->base;
	if(base<FENV_MIN_F)base=FENV_MIN_F;
	float f=base*exp2f(e->amount*drive+e->sweep);
	if(f>1.f)f=1.f; else if(f<FENV_MIN_F)f=FENV_MIN_F;
	SVF_directSetFilterValue(fenv_filter(slot), f);
}
