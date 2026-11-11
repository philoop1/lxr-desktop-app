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
#include "menu/CcNr2Text.h"
#include "Parameters.h"
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
	lfo->shot=LFO_SHOT_DONE;
	lfo->modNodeValue	= 1;

	modNode_init(&lfo->modTarget);
}
//-------------------------------------------------------------
static inline uint8_t lfo_isOneShot(uint8_t waveform)
{
	return (uint8_t)(waveform>=LFO_ONESHOT_FIRST && waveform<NUM_LFO_WAVEFORMS);
}
/* The looping shape at a phase, for the one-shots (they run from flash, the
 * looping waves stay in lfo_calc in ITCM). The one-shot square is on first. */
static float lfo_shapeAt(uint8_t base, uint32_t phase)
{
	const float x = phase/(float)0xffffffff;
	switch(base)
	{
	case LFO_SINE:		return ((sine_table[phase>>20]/32767.f) + 1)/2.f;
	case LFO_TRI:		return 1.f-fabsf(x*2-1);
	case LFO_SAW_UP:	return x;
	case LFO_SAW_DOWN:	return (0xffffffff-phase) / (float)0xffffffff;
	case LFO_REC:		return phase > 0x7fffffff ? 0.f : 1.f;
	case LFO_EXP_UP:	return x*x*x;
	case LFO_EXP_DOWN:	{ const float y = (0xffffffff-phase) / (float)0xffffffff; return y*y*y; }
	case LFO_EXP_TRI:	{ const float t = 1.f-fabsf(x*2-1); return t*t*t; }
	default:			return 0.f;
	}
}
// noinline: lfo_calc lives in ITCM, the one-shots stay in flash
static __attribute__((noinline)) float lfo_calcOneShot(Lfo *lfo)
{
	const uint8_t shape = (uint8_t)(lfo->waveform-LFO_ONESHOT_FIRST);
	const uint8_t base = shape<=LFO_EXP_DOWN ? shape : LFO_EXP_TRI;
	const uint32_t inc = (uint32_t)(lfo->phaseInc*lfo->modNodeValue);
	const uint32_t oldPhase = lfo->phase;
	if(lfo->shot==LFO_SHOT_WAIT)
	{
		// the offset is the start delay; the phase counts it
		lfo->phase += inc;
		if(lfo->phase>=lfo->phaseOffset || lfo->phase<oldPhase)
		{
			lfo->phase = 0;
			lfo->shot = LFO_SHOT_RUN;
			if(base==LFO_NOISE) lfo_setRandomValue(lfo);
		}
		if(base==LFO_NOISE) return lfo->rnd;
		return base==LFO_REC ? 0.f : lfo_shapeAt(base,0);
	}
	if(lfo->shot==LFO_SHOT_RUN)
	{
		lfo->phase += inc;
		if(lfo->phase<oldPhase) lfo->shot = LFO_SHOT_DONE;
	}
	if(base==LFO_NOISE) return lfo->rnd;
	return lfo_shapeAt(base, lfo->shot==LFO_SHOT_DONE ? 0xffffffff : lfo->phase);
}
IN_ITCM_RAM float lfo_calc(Lfo *lfo)
{
	if(lfo_isOneShot(lfo->waveform)) return lfo_calcOneShot(lfo);
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
		case LFO_EXP_TRI:
			{
				const float t = 1.f-fabsf( (lfo->phase/(float)0xffffffff)*2-1 );
				return t*t*t;
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
		else value=0.25f+source*0.5f; /* bipolar: half range, about -64..+63 at full amount */
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
	// rps is not an LFO wave any more; LFO_RANDOM_STEP is internal
	if(waveform >= NUM_LFO_WAVEFORMS)
		waveform = LFO_SINE;

	if((waveform != lfo->waveform)
		&& ((waveform == LFO_STRAY) || (waveform == LFO_GLIDE)))
	{
		lfo->rnd = 0.5f;
		lfo_setSmoothRandomTarget(lfo,waveform);
	}
	// a newly chosen one-shot runs once, also without a retrigger voice
	if(waveform!=lfo->waveform && lfo_isOneShot(waveform)) {
		lfo->phase=0;
		lfo->shot=LFO_SHOT_RUN;
		if(waveform==LFO_ONESHOT_NOISE) lfo_setRandomValue(lfo);
	}

	lfo->waveform = waveform;
	lfo_updateHeldRandomFromOffset(lfo);
}
void lfo_setPhaseOffset(Lfo *lfo, uint8_t offset)
{
	lfo->phaseOffset = offset>=127 ? UINT32_MAX : (uint32_t)(offset / 127.f * 0xffffffff);
	lfo_updateHeldRandomFromOffset(lfo);
}
/* 0.2.100 out of ITCM: only MIDI/menu set the sync, the audio fast paths need the room */
void lfo_setSync(Lfo* lfo, uint8_t sync)
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
	if(lfo_isOneShot(lfo->waveform)) {
		lfo->phase = 0;
		lfo->shot = lfo->phaseOffset ? LFO_SHOT_WAIT : LFO_SHOT_RUN;
		if(lfo->shot==LFO_SHOT_RUN && lfo->waveform==LFO_ONESHOT_NOISE) lfo_setRandomValue(lfo);
		return;
	}
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
static Lfo randomStepLfos[6];
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
		Lfo *nodes[2]={&randomStepLfos[voice],lfo_byVoice(voice)};
		for(uint8_t n=0;n<2;n++) {
			Lfo *lfo=nodes[n];
			if(lfo->waveform!=LFO_RANDOM_STEP || lfo->retrigger!=sourceVoice+1u)continue;
			float value=lfo_random01();
			if(lfo->phaseOffset) value+=(lfo->phaseOffset/(float)UINT32_MAX)*2.f-1.f;
			if(value<0.f)value=0.f;
			if(value>1.f)value=1.f;
			lfo->rndTarget=value;
			if(!lfo->stepSlew)lfo->stepValue=value;
		}
	}
}
//-------------------------------------------------------------

void lfo_initRandomSteps(void)
{
    for(uint8_t voice=0;voice<6;voice++) {
        lfo_init(&randomStepLfos[voice]);
        randomStepLfos[voice].waveform=LFO_RANDOM_STEP; // internal wave, lfo_setWaveform refuses it
        randomStepLfos[voice].retrigger=voice+1u;
    }
}
void lfo_applyRandomStepSettings(uint8_t voice)
{
    if(voice>=6)return;
    Lfo *lfo=&randomStepLfos[voice];
    uint8_t target=activeParameters[PAR_RPS_DST1+voice];
    if(target>=getNumModTargets())target=0;
    lfo->retrigger=activeParameters[PAR_RPS_TRG1+voice];
    lfo->modTarget.amount=activeParameters[PAR_RPS_AMT1+voice]/127.f;
    lfo_setPhaseOffset(lfo,activeParameters[PAR_RPS_OFS1+voice]);
    lfo->stepSlew=activeParameters[PAR_RPS_SLW1+voice];
    lfo->stepPolarity=activeParameters[PAR_RPS_POL1+voice]>2?2:activeParameters[PAR_RPS_POL1+voice];
    if(lfo->modTarget.destination!=modTargets[target].param)
        modNode_setDestination(&lfo->modTarget,modTargets[target].param);
}
void lfo_dispatchRandomSteps(void)
{
    for(uint8_t voice=0;voice<6;voice++)
        lfo_dispatchNextValue(&randomStepLfos[voice]);
}

/* 0.2.107 the voice whose targets a random step node uses, 0xff if it is none */
uint8_t lfo_randomStepTargetVoice(const ModulationNode *node)
{
    for(uint8_t i=0;i<6;i++)
        if(node==&randomStepLfos[i].modTarget) {
            const uint8_t v=activeParameters[PAR_RPS_VOI1+i];
            return (v>=1 && v<=6) ? (uint8_t)(v-1) : 0xff;
        }
    return 0xff;
}

void lfo_resetRandomStepTargets(void)
{
    for(uint8_t voice=0;voice<6;voice++) {
        ModulationNode *node=&randomStepLfos[voice].modTarget;
        if(node->destination<END_OF_SOUND_PARAMETERS)
            paramArray_setParameter(node->destination,node->originalValue);
    }
}

void lfo_randomStepOriginalValueChanged(uint16_t idx)
{
    if(idx>=END_OF_SOUND_PARAMETERS || !parameterArray[idx].ptr)return;
    for(uint8_t voice=0;voice<6;voice++) {
        ModulationNode *node=&randomStepLfos[voice].modTarget;
        if(node->destination!=idx)continue;
        const Parameter *p=&parameterArray[idx];
        switch(p->type) {
            case TYPE_UINT8: node->originalValue.itg=*((uint8_t*)p->ptr); break;
            case TYPE_SPECIAL_P:
            case TYPE_SPECIAL_FILTER_F:
            case TYPE_FLT: node->originalValue.flt=*((float*)p->ptr); break;
            case TYPE_UINT32: node->originalValue.itg=*((uint32_t*)p->ptr); break;
            default: break;
        }
    }
}
