/*
 * DrumVoice.c
 *
 *  Created on: 03.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#include "Soundengine/DSPAudio/DrumVoice.h"
#include "Soundengine/DSPAudio/FilterEnv.h" // 0.2.93
#include "Soundengine/DSPAudio/Oscillator.h"
#include "Soundengine/DSPAudio/SampleBank.h"
#include "Soundengine/DSPAudio/random.h"
#include "math.h"
#include "Soundengine/DSPAudio/squareRootLut.h"
#include "Soundengine/DSPAudio/BufferTools.h"
#include "Soundengine/MIDI/ParameterArray.h"
#include "Soundengine/DSPAudio/modulationNode.h"
#include "Soundengine/TriggerOut.h"
static float drum_glideCoef(uint8_t time); // 0.2.90
#include "Soundengine/MIDI/MidiVoiceControl.h"
#include "IO/adcPots.h"

INDTCM static float ampSmoothValue = 0.1f;
//---------------------------------------------------
INDTCMZ DrumVoice voiceArray[NUM_DRUM_VOICES];
//---------------------------------------------------
/*IN_ITCM_RAM 0.2.103 control rate, flash*/ void setPan(const uint8_t voiceNr, const uint8_t pan)
{
	voiceArray[voiceNr].pan = pan;
}
//---------------------------------------------------
void drum_setPhase(const uint8_t phase, const uint8_t voiceNr)
{
	const uint32_t startPhase = (phase/127.f)*0xffffffff;
	voiceArray[voiceNr].osc.startPhase = startPhase;
	voiceArray[voiceNr].modOsc.startPhase = startPhase;
}
//---------------------------------------------------
void initDrumVoice()
{
	fenv_init(); // 0.2.93
	ampSmoothValue = 0.1f;




	int i;
	for(i=0;i<NUM_DRUM_VOICES;i++)
	{

		initOnePole(&voiceArray[i].FaderVolumeFilter);
		setOnePoleCoef(&voiceArray[i].FaderVolumeFilter,0.01);

#if SMOOTH_MIXER_VOL_PAN_DRIVE
		for(uint8_t j=0;j<2;j++)
		{
			initOnePole(&voiceArray[i].MixerPageFilter[j]);
			setOnePoleCoef(&voiceArray[i].MixerPageFilter[j],0.01);
		}
		initOnePole(&voiceArray[i].distortion.DriveParamFilter);
		setOnePoleCoef(&voiceArray[i].distortion.DriveParamFilter,0.01);

#endif

		SnapEg_init(&voiceArray[i].snapEg);
		setPan(i,0.f);
		voiceArray[i].vol = 0.8f;
		//voiceArray[i].panModifier = 1.f;
		voiceArray[i].fmModAmount = 0.5f;
		transient_init(&voiceArray[i].transGen);
#if ENABLE_DRUM_SVF
		SVF_init(&voiceArray[i].filter);
		voiceArray[i].filterType = 0x01;
#endif
		lfo_init(&voiceArray[i].lfo);

		voiceArray[i].modOsc.freq = 440;
		voiceArray[i].modOsc.waveform = 1;
		voiceArray[i].modOsc.fmMod = 0;
		voiceArray[i].modOsc.midiFreq = 70<<8 | 64;
		voiceArray[i].modOsc.pitchMod = 1.0f;
		drum_glide[i].mode = GLIDE_OFF;
		drum_glide[i].log2Ratio = 0.f;
		drum_glide[i].slideNext = 0;
		drum_glide[i].time = GLIDE_TIME_DEFAULT;
		drum_glide[i].coef = drum_glideCoef(GLIDE_TIME_DEFAULT);
		voiceArray[i].modOsc.modNodeValue = 1;

		voiceArray[i].volumeMod = 1;

		voiceArray[i].osc.freq = 440;
		voiceArray[i].osc.modNodeValue = 1;
		voiceArray[i].osc.waveform = TRI+i; //for testing init to tri,saw,rec
		voiceArray[i].osc.fmMod = 0;
		voiceArray[i].osc.fmFloor = -65536.f; // 0.2.87 full-wave FM
		voiceArray[i].osc.midiFreq = 70<<8 | 64;

		DecayEg_init(&voiceArray[i].oscPitchEg);
		voiceArray[i].egPitchModAmount = 0.5f;

		slopeEg2_init(&voiceArray[i].oscVolEg);
		setDistortionShape(&voiceArray[i].distortion, 0.f);

#ifdef USE_AMP_FILTER
		initOnePole(&voiceArray[i].ampFilter);
		setOnePoleCoef(&voiceArray[i].ampFilter,ampSmoothValue);
#endif

#if ENABLE_MIX_OSC
		voiceArray[i].mixOscs = true;
#endif
		voiceArray[i].decimationCnt = 0;
		voiceArray[i].decimationRate = 1;

	}
}
//---------------------------------------------------
void Drum_updatePan(const uint8_t voiceNr)
{
	voiceArray[voiceNr].triggeredPanL = sqrtf((127-voiceArray[voiceNr].pan)/127.f);
	voiceArray[voiceNr].triggeredPanR = sqrtf(voiceArray[voiceNr].pan/127.f);
}
//---------------------------------------------------
/* 0.2.90 glide, kept in flash: ITCM is full */
#define GLIDE_DONE 0.0005f		// octaves, below one cent
#define GLIDE_MAX_OCT 8.f
#define GLIDE_SOUNDING 0.01f	// amp EG level a legato or slide note needs
DrumGlide drum_glide[NUM_DRUM_VOICES];
/* time 0..127 = 10 ms .. 1 s to reach 95 % of the way (3 time constants) */
static float drum_glideCoef(uint8_t time)
{
	const float seconds = 0.01f*exp2f((float)time*(6.643856f/127.f));
	return expf(-3.f*(float)OUTPUT_DMA_SIZE/(REAL_FS*seconds));
}
__attribute__((noinline)) void Drum_setGlideParameter(uint8_t index, uint8_t value)
{
	if(index>=GLIDE_PARAMS)return;
	DrumGlide *g=&drum_glide[index%NUM_DRUM_VOICES];
	if(index<NUM_DRUM_VOICES) g->mode = value<GLIDE_MODES ? value : GLIDE_OFF;
	else { g->time = value>127 ? 127 : value; g->coef = drum_glideCoef(g->time); }
}
__attribute__((noinline)) uint8_t Drum_getGlideParameter(uint8_t index)
{
	if(index>=GLIDE_PARAMS)return 0;
	const DrumGlide *g=&drum_glide[index%NUM_DRUM_VOICES];
	return index<NUM_DRUM_VOICES ? g->mode : g->time;
}
__attribute__((noinline)) void Drum_setSlideNext(uint8_t voiceNr, uint8_t on)
{
	if(voiceNr<NUM_DRUM_VOICES)drum_glide[voiceNr].slideNext = on ? 1 : 0;
}
/* Sets the new note on both oscillators. Returns 1 when the note slides in
 * (slide step in leg mode while the voice still sounds): no EG retrigger. */
__attribute__((noinline)) uint8_t drum_glideTrigger(uint8_t voiceNr, uint8_t note)
{
	DrumGlide *g=&drum_glide[voiceNr];
	DrumVoice *v=&voiceArray[voiceNr];
	const float oldFreq = v->osc.freq*exp2f(g->log2Ratio);
	const uint8_t sounding = v->oscVolEg.state!=EG_STOPPED && v->ampFilterInput>GLIDE_SOUNDING;
	const uint8_t legato = sounding && g->slideNext && g->mode==GLIDE_LEGATO;
	const uint8_t glide = legato || g->mode==GLIDE_ON;
	g->slideNext = 0;
	osc_setBaseNote(&v->osc,note);
	osc_setBaseNote(&v->modOsc,note);
	float ratio = 0.f;
	if(glide && oldFreq>0.f && v->osc.freq>0.f) {
		ratio = log2f(oldFreq/v->osc.freq);
		if(ratio>GLIDE_MAX_OCT) ratio=GLIDE_MAX_OCT;
		else if(ratio<-GLIDE_MAX_OCT) ratio=-GLIDE_MAX_OCT;
		if(fabsf(ratio)<GLIDE_DONE) ratio=0.f;
	}
	g->log2Ratio = ratio;
	v->modOsc.pitchMod = exp2f(ratio);
	return legato;
}
/* once per block after the pitch EG: both oscillators move to the new note */
__attribute__((noinline)) void drum_glideTick(uint8_t voiceNr)
{
	DrumGlide *g=&drum_glide[voiceNr];
	g->log2Ratio *= g->coef;
	if(fabsf(g->log2Ratio)<GLIDE_DONE) g->log2Ratio=0.f;
	const float f = exp2f(g->log2Ratio);
	voiceArray[voiceNr].osc.pitchMod *= f;
	voiceArray[voiceNr].modOsc.pitchMod = f;
}
//---------------------------------------------------
void Drum_trigger(const uint8_t voiceNr, const uint8_t vol, const uint8_t note)
{
	const uint8_t legato = drum_glideTrigger(voiceNr, note); // 0.2.90 also sets the note
	if(legato) fenv_slide(voiceNr); // 0.2.95 the filter env keeps running

	if(!legato) lfo_retrigger(voiceNr);

	//update velocity modulation
	modNode_updateValue(&velocityModulators[voiceNr],vol/127.f);

	//only reset phase if envelope is closed; a sliding note keeps its phase
	if(!legato)
#ifdef USE_AMP_FILTER
	if((voiceArray[voiceNr].volEgValueBlock[15]<=0.01f) || (voiceArray[voiceNr].transGen.waveform==1))
#else
		//if((voiceArray[voiceNr].ampFilterInput<=0.01f) || (voiceArray[voiceNr].transGen.waveform==1))
#endif
	{
		float offset = 1;
		if(voiceArray[voiceNr].transGen.waveform==1) //offset mode
		{
			offset -= voiceArray[voiceNr].transGen.volume;
#ifdef USE_AMP_FILTER
			setOnePoleCoef(&voiceArray[voiceNr].ampFilter,1.0f); //turn off amp filter for super snappy attack

		} else {
			setOnePoleCoef(&voiceArray[voiceNr].ampFilter,ampSmoothValue);
#endif
		}
		if(voiceArray[voiceNr].osc.waveform == SINE)
			voiceArray[voiceNr].osc.phase = 1024 + ( (0x3ff<<20) - 1024)*offset;//voiceArray[voiceNr].osc.startPhase ;
		else if(voiceArray[voiceNr].osc.waveform > SINE && voiceArray[voiceNr].osc.waveform <= REC)
			voiceArray[voiceNr].osc.phase = (0xff<<22)*offset;
		else
			voiceArray[voiceNr].osc.phase = 0;
		voiceArray[voiceNr].osc.pdKnee = 0.f; // a new note starts at its own PD shape
		voiceArray[voiceNr].osc.pdRes = 0.f;

		//reset mod osc phase
		if(voiceArray[voiceNr].modOsc.waveform == SINE)
			voiceArray[voiceNr].modOsc.phase = 1024 + ( (0x3ff<<20) - 1024);//voiceArray[voiceNr].osc.startPhase ;
		else if(voiceArray[voiceNr].modOsc.waveform > SINE && voiceArray[voiceNr].modOsc.waveform <= REC)
			voiceArray[voiceNr].modOsc.phase = (0xff<<22);
		else
			voiceArray[voiceNr].modOsc.phase = 0;

	}

	voiceArray[voiceNr].velo = vol/127.f;
	if(!legato) {
		DecayEg_trigger(&voiceArray[voiceNr].oscPitchEg);
		slopeEg2_trigger(&voiceArray[voiceNr].oscVolEg);

		transient_trigger(&voiceArray[voiceNr].transGen);

		SnapEg_trigger(&voiceArray[voiceNr].snapEg);

		//reset filter coeffs to prevent wrong transient
		SVF_reset(&voiceArray[voiceNr].filter);
	}

	//update pan value
	Drum_updatePan(voiceNr);
}
//---------------------------------------------------
/* 0.2.66 hpd (global, 0..100 %), from the LXR1 Mutador: high pitched drum voices
 * play quieter. Voice 1 above 120 Hz by 120/f (at least 10 %) before its filter,
 * voices 2 and 3 from 1 kHz down to 25 % at 16 kHz. Samples are not damped.
 * 0.2.67: the snare (slot 3) follows the rule of voices 2 and 3. */
uint8_t drum_highDamp=0;
float drum_highGain[4]={1.f,1.f,1.f,1.f};
__attribute__((noinline)) void drum_updateHighGainOsc(const uint8_t voiceNr,const OscInfo *osc)
{
	float target=1.f;
	if(drum_highDamp && osc->waveform<SAMPLEBANK_FIRST_WAVE)
	{
		const float f=osc->freq*osc->pitchMod*osc->modNodeValue;
		float g=1.f;
		if(voiceNr==0)
		{
			if(f>120.f)g=120.f/f;
			if(g<0.1f)g=0.1f;
		}
		else if(f>=16000.f)g=0.25f;
		else if(f>1000.f)g=1.f-(f-1000.f)*0.00005f;
		target=1.f-(float)drum_highDamp*0.01f*(1.f-g);
	}
	drum_highGain[voiceNr]+=(target-drum_highGain[voiceNr])*0.25f;
}
static void drum_updateHighGain(const uint8_t voiceNr)
{
	drum_updateHighGainOsc(voiceNr,&voiceArray[voiceNr].osc);
}
//---------------------------------------------------
IN_ITCM_RAM void calcDrumVoiceAsync(const uint8_t voiceNr)
{


	//add modulation eg to osc freq (1 = no change. a+eg = original freq + modulation
	const float egPitchVal = DecayEg_calc(&voiceArray[voiceNr].oscPitchEg);
	const float pitchEgValue = egPitchVal*voiceArray[voiceNr].egPitchModAmount;
	voiceArray[voiceNr].osc.pitchMod = 1+pitchEgValue;

	//calc snap EG if transient sample 0 is activated
	if(voiceArray[voiceNr].transGen.waveform == 0)
	{
		const float snapVal = SnapEg_calc(&voiceArray[voiceNr].snapEg, voiceArray[voiceNr].transGen.pitch);
		voiceArray[voiceNr].osc.pitchMod += snapVal*voiceArray[voiceNr].transGen.volume;
	}
	if(drum_glide[voiceNr].log2Ratio != 0.f) drum_glideTick(voiceNr); // 0.2.90

	// fm amount with pitch eg
	voiceArray[voiceNr].osc.fmMod = voiceArray[voiceNr].fmModAmount * egPitchVal;

	//calc the osc + noise vol eg
#if (AMP_EG_SYNC==0)

	//check if in attack phase
	if( (voiceArray[voiceNr].oscVolEg.attack == 1 ) && ((voiceArray[voiceNr].oscVolEg.state == EG_A) || (voiceArray[voiceNr].oscVolEg.state == EG_REPEAT)) )
	{
			//if attack is set to 0 -> no interpolation
		voiceArray[voiceNr].ampFilterInput = slopeEg2_calc(&voiceArray[voiceNr].oscVolEg);
		voiceArray[voiceNr].lastGain = voiceArray[voiceNr].ampFilterInput;
	}
	else
	{
		voiceArray[voiceNr].lastGain = voiceArray[voiceNr].ampFilterInput;
		voiceArray[voiceNr].ampFilterInput = slopeEg2_calc(&voiceArray[voiceNr].oscVolEg);
	}

	//turn off trigger signal if trigger gate mode is on and volume == 0
	/*
	if(trigger_isGateModeOn())
	{
		if(!voiceArray[voiceNr].ampFilterInput) {
			//trigger_triggerVoice(TRIGGER_1 + voiceNr, TRIGGER_OFF);
			voiceControl_noteOff(TRIGGER_1 + voiceNr);
		}
	}
	*/
#endif

	if(fenv_on[voiceNr]) fenv_tick(voiceNr, voiceArray[voiceNr].ampFilterInput); // 0.2.93 filter env

	//update osc phaseInc
	osc_setFreq(&voiceArray[voiceNr].osc);
	osc_setFreq(&voiceArray[voiceNr].modOsc);
	drum_updateHighGain(voiceNr);



}

//---------------------------------------------------
/* 0.2.102 silent-voice sleep (Mutador): with the amp EG at exactly 0 for the
 * whole block every sample ends as 0. Skip osc, filter and drive; keep the
 * phases and the per-sample volume/drive smoothing moving so a new trigger
 * wakes the voice as if it had run. The filter is cleared once on entry.
 * Lives in flash: a silent block has time, ITCM does not have room. */
static uint8_t drum_voiceSleeping[NUM_DRUM_VOICES];
static __attribute__((noinline)) void drum_sleepBlock(const uint8_t voiceNr, int16_t* buf, const uint8_t size, const float faderTarget)
{
	DrumVoice* v = &voiceArray[voiceNr];
	if(!drum_voiceSleeping[voiceNr])
	{
		SVF_reset(&v->filter);
		drum_voiceSleeping[voiceNr] = 1;
	}
	v->osc.phase += v->osc.phaseInc * size;
	v->modOsc.phase += v->modOsc.phaseInc * size;
	for(int i=0; i<size; i++)
	{
#if (USE_FILTER_DRIVE == 0) && SMOOTH_MIXER_VOL_PAN_DRIVE
		calcOnePole(&v->distortion.DriveParamFilter, v->distortion.shape);
#endif
#if SMOOTH_MIXER_VOL_PAN_DRIVE
		const float mixVol = calcOnePole(&v->MixerPageFilter[0], v->vol);
		v->combinedVolume = mixVol * calcOnePole(&v->FaderVolumeFilter, faderTarget);
#else
		v->combinedVolume = v->vol * calcOnePole(&v->FaderVolumeFilter, faderTarget);
#endif
	}
	bufferTool_clearBuffer(buf,size);
}
IN_ITCM_RAM void calcDrumVoiceSyncBlock(const uint8_t voiceNr, int16_t* buf, const uint8_t size)
{
	const float faderTarget = adc_getFaderVolume(voiceNr);
	if(voiceArray[voiceNr].ampFilterInput == 0.f && voiceArray[voiceNr].lastGain == 0.f)
	{
		drum_sleepBlock(voiceNr, buf, size, faderTarget);
		return;
	}
	drum_voiceSleeping[voiceNr] = 0;


	int16_t modBuf[size];

	//calc vol EG
#ifdef USE_AMP_FILTER
	calcOnePoleBlockFixedInput(&voiceArray[voiceNr].ampFilter, voiceArray[voiceNr].ampFilterInput,voiceArray[voiceNr].volEgValueBlock, size);
#endif

	/* 0.2.100 a built-in 2nd osc that is not heard (amount 0 in FM and mix, a dry
	 * ring) renders only zeros: move its phase and clear the buffer instead.
	 * Noise, wavetables and samples keep their own state, they always render. */
	const uint8_t modMode = voiceArray[voiceNr].mixOscs;
	const uint8_t modSilent = voiceArray[voiceNr].modOsc.waveform <= REC &&
		(((modMode == 0 || modMode == 1) && voiceArray[voiceNr].fmModAmount == 0.f) ||
		 (modMode == 2 && (int32_t)(voiceArray[voiceNr].fmModAmount * 32767.f + 0.5f) == 0));
	if(modSilent)
	{
		voiceArray[voiceNr].modOsc.phase += voiceArray[voiceNr].modOsc.phaseInc * size;
		bufferTool_clearBuffer(modBuf,size);
	}
	//calc next mod osc sampleBlock - int16_t processing, phase distortion has no modulator
	else if(modMode != 4)
		calcNextOscSampleBlock(&voiceArray[voiceNr].modOsc,modBuf,size,
			voiceArray[voiceNr].mixOscs >= 2 ? 1.f : voiceArray[voiceNr].fmModAmount,
			voiceArray[voiceNr].pwm);

	if(voiceArray[voiceNr].mixOscs == 4)
	{
		// a user wavetable or sample has no sine to warp: it plays plain, a wavetable keeps its PWM scan
		if(voiceArray[voiceNr].osc.waveform > PWM)
			calcNextOscSampleBlock(&voiceArray[voiceNr].osc,buf,size,1.f,voiceArray[voiceNr].pwm);
		else
		{
			// 0.2.88: a built-in 2nd osc sets the pd resonance (sync); at or below the main pitch plain PD
			const uint32_t mainInc = voiceArray[voiceNr].osc.phaseInc;
			voiceArray[voiceNr].osc.pdRatio = (mainInc && voiceArray[voiceNr].modOsc.waveform <= PWM) ? (float)voiceArray[voiceNr].modOsc.phaseInc/(float)mainInc : 0.f;
			calcPhaseDistBlock(&voiceArray[voiceNr].osc,buf,size);
		}
	}
	else if(voiceArray[voiceNr].mixOscs == 3)
	{
		calcExpoFmBlock(&voiceArray[voiceNr].osc,modBuf,buf,size,voiceArray[voiceNr].pwm);
	}
	else if(voiceArray[voiceNr].mixOscs == 1)
	{
		//calc main osc buffer - int16_t processing
		calcNextOscSampleBlock(&voiceArray[voiceNr].osc,buf,size, (1.f-voiceArray[voiceNr].fmModAmount), voiceArray[voiceNr].pwm);
		//add mod buffer to main osc buffer - int16_t processing
		bufferTool_addBuffersSaturating(buf,modBuf,size);
	}
	else if(voiceArray[voiceNr].mixOscs == 2)
	{
		const float amount = voiceArray[voiceNr].fmModAmount;
		const int32_t wet = (int32_t)(amount * 32767.f + 0.5f);
		const int32_t dry = 32767 - wet;
		calcNextOscSampleBlock(&voiceArray[voiceNr].osc,buf,size,1.f,voiceArray[voiceNr].pwm);
		for(uint8_t i=0;i<size;i++)
		{
			const int32_t ring = ((int32_t)buf[i] * modBuf[i]) >> 15;
			buf[i] = (int16_t)(((int32_t)buf[i] * dry + ring * wet) >> 15);
		}
	}
	else
	{
		calcNextOscSampleFmBlock(&voiceArray[voiceNr].osc,modBuf,buf,size,1.0f, voiceArray[voiceNr].pwm);
	}

	//calc transient sample - int16_t processing
	transient_calcBlock(&voiceArray[voiceNr].transGen,modBuf,size);

	//Mix with transient buffer - int16_t processing
	bufferTool_addBuffersSaturating(buf,modBuf,size);

	// hpd: a high kick is damped before filter and drive, like on the LXR1 Mutador
	if(voiceNr==0 && drum_highGain[0]<0.999f)
		bufferTool_addGain(buf,drum_highGain[0],size);

	//calc filter block - float processing
	SVF_calcBlockZDF(&voiceArray[voiceNr].filter,voiceArray[voiceNr].filterType,buf,size);

	//attentuate main OSCs by amp EG
#ifdef USE_AMP_FILTER
	bufferTool_multiplyWithFloatBufferDithered(&voiceArray[voiceNr].dither, buf,voiceArray[voiceNr].volEgValueBlock,size);
#else
	//bufferTool_addGainInterpolatedDoubleDithered(&voiceArray[voiceNr].dither, buf,voiceArray[voiceNr].ampFilterInput, voiceArray[voiceNr].lastGain, size);
	//float
	bufferTool_addGainInterpolated(buf,voiceArray[voiceNr].ampFilterInput, voiceArray[voiceNr].lastGain, size);

	//buf[i] = dither_process(voiceArray[voiceNr].dither, buf[i]
#endif

	//MIDI velocity - float processing
	if(voiceArray[voiceNr].volumeMod)
	{
		bufferTool_addGain(buf,voiceArray[voiceNr].velo,size);
	}
	//distortion - float processing
#if (USE_FILTER_DRIVE == 0)
#if SMOOTH_MIXER_VOL_PAN_DRIVE
	calcDistBlockFiltered(&voiceArray[voiceNr].distortion,buf,size);
#else
	calcDistBlock(&voiceArray[voiceNr].distortion,buf,size);
#endif
#endif
	//channel volume
	//bufferTool_addGain(buf,voiceArray[voiceNr].combinedVolume  ,size);

	for(int i=0; i< size; i++)
	{
#if SMOOTH_MIXER_VOL_PAN_DRIVE

		float mixVol 	= calcOnePole( &voiceArray[voiceNr].MixerPageFilter[0], voiceArray[voiceNr].vol);
		voiceArray[voiceNr].combinedVolume = mixVol * calcOnePole( &voiceArray[voiceNr].FaderVolumeFilter, faderTarget);
#else
		voiceArray[voiceNr].combinedVolume = voiceArray[voiceNr].vol * calcOnePole( &voiceArray[voiceNr].FaderVolumeFilter, faderTarget);
#endif
		buf[i] *= voiceArray[voiceNr].combinedVolume*(voiceNr?drum_highGain[voiceNr]:1.f);
	}
}
//---------------------------------------------------


