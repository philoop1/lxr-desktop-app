/*
 * lfo.c
 *
 *  Created on: 14.01.2013
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

//-------------------------------------------------------------
#include "Soundengine/DSPAudio/lfo.h"
#include "Soundengine/DSPAudio/random.h"
#include <math.h>

#include "Soundengine/DSPAudio/DrumVoice.h"
#include "Soundengine/DSPAudio/CymbalVoice.h"
#include "Soundengine/DSPAudio/HiHat.h"
#include "Soundengine/DSPAudio/Snare.h"
#include "Soundengine/MIDI/valueShaper.h"
//-------------------------------------------------------------
static inline float lfo_random01(void)
{
	return GetRngValue() / (float)0xffffffff;
}
static inline void lfo_setRandomValue(Lfo *lfo)
{
	lfo->rnd = lfo_random01();
}
static inline float lfo_reflectUnitRange(float value)
{
	if(value < 0.f)
		return -value;
	if(value > 1.f)
		return 2.f-value;
	return value;
}
static inline void lfo_setSmoothRandomTarget(Lfo *lfo, uint8_t waveform)
{
	if(waveform == LFO_STRAY)
	{
		const float step = (lfo_random01()*2.f-1.f)*0.35f;
		lfo->rndTarget = lfo_reflectUnitRange(lfo->rnd+step);
	}
	else
	{
		lfo->rndTarget = lfo_random01();
	}
}
static inline void lfo_advanceSmoothRandom(Lfo *lfo)
{
	lfo->rnd = lfo->rndTarget;
	lfo_setSmoothRandomTarget(lfo,lfo->waveform);
}
static inline float lfo_calcSmoothRandom(Lfo *lfo)
{
	const float phase = lfo->phase/(float)0xffffffff;
	const float smoothPhase = phase*phase*(3.f-2.f*phase);
	return lfo->rnd+(lfo->rndTarget-lfo->rnd)*smoothPhase;
}
static inline float lfo_applySmoothRandomBias(Lfo *lfo, float value)
{
	const float control = (lfo->phaseOffset/(float)0xffffffff)*127.f;
	const float bias = (control-63.f)/64.f;
	float bipolar = value*2.f-1.f;
	bipolar += bias*(1.f-fabsf(bipolar));

	if(bipolar < -1.f)
		bipolar = -1.f;
	else if(bipolar > 1.f)
		bipolar = 1.f;

	return bipolar+1.f;
}
static inline void lfo_setRandomValueFromOffset(Lfo *lfo)
{
	lfo->rnd = lfo->phaseOffset / (float)0xffffffff;
}
static inline void lfo_updateHeldRandomFromOffset(Lfo *lfo)
{
	if((lfo->waveform == LFO_NOISE) && (lfo->phaseInc == 0))
		lfo_setRandomValueFromOffset(lfo);
}
void lfo_init(Lfo *lfo)
{
	lfo->phase 			= 0;
	lfo->phaseInc 		= 1;
	lfo->phaseOffset	= 0;
	lfo->retrigger		= 0;
	lfo->waveform		= SINE;
	lfo->sync			= 0;
	lfo->freq			= 1;
	lfo->rnd=0.5f;
	lfo->rndTarget=0.5f;
	lfo->stepValue=0.5f;
	lfo->stepSlew=0;
	lfo->stepPolarity=2;
	lfo->modNodeValue	= 1;

	modNode_init(&lfo->modTarget);
}
//-------------------------------------------------------------
IN_ITCM_RAM float lfo_calc(Lfo *lfo)
{
	uint32_t oldPhase 		= lfo->phase;
	float inc = lfo->phaseInc*lfo->modNodeValue;
	uint32_t incInt = inc;
	lfo->phase 			   += incInt;//lfo->phaseInc*lfo->modNodeValue;
	const uint8_t overflow 	= oldPhase>lfo->phase;

	switch(lfo->waveform)
	{
	//---
		case LFO_SINE:
			return ((sine_table[(lfo->phase>>20)]/32767.f) + 1)/2.f;
		break;
	//---
		case LFO_TRI:
			return (1.f-fabsf( (lfo->phase/(float)0xffffffff)*2-1 ) );
			break;
	//---
		case LFO_SAW_UP:
		return lfo->phase/(float)0xffffffff ;
		break;
	//---
		case LFO_REC:
		if(lfo->phase > 0x7fffffff)
		{
			return 1.f;
		}
		else
		{
			return 0.f;
		}
		break;
	//---
		case LFO_NOISE:
        if(overflow)lfo_setRandomValue(lfo);
        return lfo->rnd;
        break;
    //---
		case LFO_SAW_DOWN:
		return (0xffffffff-(lfo->phase)) / (float)0xffffffff;
		break;
	//---
		case LFO_EXP_UP:
			{
				float x = lfo->phase/(float)0xffffffff;
				return x*x*x;
			}
			break;
	//---
		case LFO_EXP_DOWN:
			{
				float x = (0xffffffff-(lfo->phase)) / (float)0xffffffff;
				return x*x*x;//valueShaperF2F(x,-0.9f);
			}
			break;
	//---
        case LFO_STRAY:
        case LFO_GLIDE:
            if(overflow)lfo_advanceSmoothRandom(lfo);
            return lfo_calcSmoothRandom(lfo);
        break;
	case LFO_RANDOM_STEP: {
		if(!lfo->stepSlew) lfo->stepValue=lfo->rndTarget;
		else {
			const float tau=(lfo->stepSlew/127.f)*2.f;
			const float alpha=1.f/(1.f+tau*LFO_SR);
			lfo->stepValue+=(lfo->rndTarget-lfo->stepValue)*alpha;
		}
		return lfo->stepValue;
	}
		default:
		return 0;
		break;
	}
	return 0;
}
//-------------------------------------------------------------
void lfo_dispatchNextValue(Lfo* lfo)
{
	const float source=lfo_calc(lfo);
    if(lfo->waveform==LFO_STRAY || lfo->waveform==LFO_GLIDE) {
        // Mutador bias returns 0..2; desktop modulation accepts 0..1.
        modNode_updateValue(&lfo->modTarget,lfo_applySmoothRandomBias(lfo,source)*0.5f);
    } else if(lfo->waveform==LFO_RANDOM_STEP) {
		float value=source;
		if(lfo->stepPolarity==0) value=source*0.5f;
		else if(lfo->stepPolarity==1) value=0.5f+source*0.5f;
		modNode_updateValue(&lfo->modTarget,value);
	} else modNode_updateValue(&lfo->modTarget,source);
}
//-------------------------------------------------------------
IN_ITCM_RAM uint32_t lfo_calcPhaseInc(float freq, uint8_t sync)
{
	if(freq<=0.f)return 0;
	if(sync==0)//no sync
	{
		return freq/(LFO_SR) * 0xffffffff;
	}

	//sync is on

	float bpm =  seq_getBpm();

	float tempoAsFrequency = bpm > 0.0 ? bpm / 60.f /4: 0.0f; //bpm/60 = beat duration /4 = bar duration

	float scaler;

	switch(sync)
	{
		default: //no sync

		return freq/(LFO_SR) * 0xffffffff;
		break;

		case 1: // 4/1
		scaler = 0.25f;//NoteTypeScalers[Quadruple] * NoteDivisionScalers[Whole];
		break;

		case 2: // 2/1
		scaler = 0.5f;//NoteTypeScalers[Double] * NoteDivisionScalers[Whole];
		break;

		case 3: // 1/1
		scaler = 1;//NoteTypeScalers[Regular] * NoteDivisionScalers[Whole];
		break;

		case 4: // 1/2
		scaler = 2;// NoteTypeScalers[Regular] * NoteDivisionScalers[Half];
		break;

		case 5: //1/3
		scaler = 3;// NoteTypeScalers[Regular] * NoteDivisionScalers[Third];
		break;

		case 6: // 1/4
		scaler = 4;// NoteTypeScalers[Regular] * NoteDivisionScalers[Quarter];
		break;

		case 7: // 1/6
		scaler = 6;// NoteTypeScalers[Regular] * NoteDivisionScalers[Sixth];
		break;

		case 8: // 1/8
		scaler = 8;// NoteTypeScalers[Regular] * NoteDivisionScalers[Eighth];
		break;

		case 9: // 1/12
		scaler = 12;//NoteTypeScalers[Regular] * NoteDivisionScalers[Twelfth];
		break;

		case 10: // 1/16
		scaler = 16;//NoteTypeScalers[Regular] * NoteDivisionScalers[Sixteenth];
		break;

		case 11: // 1/32
		scaler = 32;//NoteTypeScalers[Regular] * NoteDivisionScalers[Sixteenth];
		break;
	}

	float lfoSyncfreq = tempoAsFrequency * scaler;
	return (lfoSyncfreq / (LFO_SR)) * 0xffffffff;
}
//-------------------------------------------------------------
IN_ITCM_RAM void lfo_setFreq(Lfo *lfo, float f)
{
	if(f<=0.f){lfo->freq=0;lfo->phaseInc=0;lfo_updateHeldRandomFromOffset(lfo);return;}
    //f += 1;
	//f = f/128.f;
	f = 0.0078125f + f* (1.f-0.0078125f); //to prevent f from being zero
	f = f*f*f;
	lfo->freq = f*LFO_MAX_F;
	lfo->phaseInc = lfo_calcPhaseInc(lfo->freq,lfo->sync);
	lfo_updateHeldRandomFromOffset(lfo);
}
//-------------------------------------------------------------
void lfo_setWaveform(Lfo *lfo, uint8_t waveform)
{
	if(waveform > LFO_RANDOM_STEP)
		waveform = LFO_SINE;

	if((waveform != lfo->waveform)
		&& ((waveform == LFO_STRAY) || (waveform == LFO_GLIDE)))
	{
		lfo->rnd = 0.5f;
		lfo_setSmoothRandomTarget(lfo,waveform);
	}
	if(waveform!=lfo->waveform && waveform==LFO_RANDOM_STEP) {
		lfo->stepValue=0.5f;
		lfo->rndTarget=0.5f;
	}

	lfo->waveform = waveform;
	lfo_updateHeldRandomFromOffset(lfo);
}
void lfo_setPhaseOffset(Lfo *lfo, uint8_t offset)
{
	lfo->phaseOffset = offset>=127 ? UINT32_MAX : (uint32_t)(offset / 127.f * 0xffffffff);
	lfo_updateHeldRandomFromOffset(lfo);
}
IN_ITCM_RAM void lfo_setSync(Lfo* lfo, uint8_t sync)
{
	lfo->sync = sync;
	lfo->phaseInc = lfo_calcPhaseInc(lfo->freq,lfo->sync);
	lfo_updateHeldRandomFromOffset(lfo);
}
//-------------------------------------------------------------
void lfo_recalcSync()
{
	Lfo* lfo = &voiceArray[0].lfo;
	lfo->phaseInc = lfo_calcPhaseInc(lfo->freq,lfo->sync);

	lfo = &voiceArray[1].lfo;
	lfo->phaseInc = lfo_calcPhaseInc(lfo->freq,lfo->sync);

	lfo = &voiceArray[2].lfo;
	lfo->phaseInc = lfo_calcPhaseInc(lfo->freq,lfo->sync);

	lfo = &snareVoice.lfo;
	lfo->phaseInc = lfo_calcPhaseInc(lfo->freq,lfo->sync);

	lfo = &cymbalVoice.lfo;
	lfo->phaseInc = lfo_calcPhaseInc(lfo->freq,lfo->sync);

	lfo = &hatVoice.lfo;
	lfo->phaseInc = lfo_calcPhaseInc(lfo->freq,lfo->sync);
}
//-------------------------------------------------------------
static inline void lfo_retriggerVoice(Lfo *lfo)
{
	if(lfo->waveform==LFO_RANDOM_STEP) return;
	if((lfo->waveform == LFO_STRAY) || (lfo->waveform == LFO_GLIDE))
		lfo->phase = 0; // phaseOffset is the bipolar bias for smooth random modes.
	else
		lfo->phase = lfo->phaseOffset;
	if((lfo->waveform == LFO_NOISE) && (lfo->phaseInc == 0))
		lfo_setRandomValue(lfo);
}
void lfo_retrigger(uint8_t voice)
{
	if(voiceArray[0].lfo.retrigger == voice+1)
	{
		lfo_retriggerVoice(&voiceArray[0].lfo);
	}
	if(voiceArray[1].lfo.retrigger == voice+1)
	{
		lfo_retriggerVoice(&voiceArray[1].lfo);
	}
	if(voiceArray[2].lfo.retrigger == voice+1)
	{
		lfo_retriggerVoice(&voiceArray[2].lfo);
	}
	if(snareVoice.lfo.retrigger == voice+1)
	{
		lfo_retriggerVoice(&snareVoice.lfo);
	}
	if(cymbalVoice.lfo.retrigger == voice+1)
	{
		lfo_retriggerVoice(&cymbalVoice.lfo);
	}
	if(hatVoice.lfo.retrigger == voice+1)
	{
		lfo_retriggerVoice(&hatVoice.lfo);
	}
}
static Lfo *lfo_byVoice(uint8_t voice)
{
	if(voice<3)return &voiceArray[voice].lfo;
	if(voice==3)return &snareVoice.lfo;
	if(voice==4)return &cymbalVoice.lfo;
	if(voice==5)return &hatVoice.lfo;
	return 0;
}
void lfo_setStepSlew(uint8_t voice,uint8_t value)
{
	Lfo *lfo=lfo_byVoice(voice);
	if(lfo)lfo->stepSlew=value>127 ? 127 : value;
}
void lfo_setStepPolarity(uint8_t voice,uint8_t value)
{
	Lfo *lfo=lfo_byVoice(voice);
	if(lfo)lfo->stepPolarity=value>2 ? 2 : value;
}
void lfo_stepTrigger(uint8_t sourceVoice)
{
	if(sourceVoice==6)sourceVoice=5; /* both hi-hat tracks use voice 6 */
	for(uint8_t voice=0;voice<6;voice++) {
		Lfo *lfo=lfo_byVoice(voice);
		if(lfo->waveform!=LFO_RANDOM_STEP || lfo->retrigger!=sourceVoice+1u)continue;
		float value=lfo_random01();
		if(lfo->phaseOffset) value+=(lfo->phaseOffset/(float)UINT32_MAX)*2.f-1.f;
		if(value<0.f)value=0.f;
		if(value>1.f)value=1.f;
		lfo->rndTarget=value;
		if(!lfo->stepSlew)lfo->stepValue=value;
	}
}
//-------------------------------------------------------------
