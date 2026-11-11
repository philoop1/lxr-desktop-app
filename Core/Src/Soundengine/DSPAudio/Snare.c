/*
 * Snare.c
 *
 *  Created on: 17.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */



#include "Soundengine/DSPAudio/Snare.h"
#include "Soundengine/DSPAudio/FilterEnv.h" // 0.2.93
#include "Soundengine/DSPAudio/squareRootLut.h"
#include "Soundengine/DSPAudio/modulationNode.h"
#include "Soundengine/TriggerOut.h"
#include "Soundengine/MIDI/MidiVoiceControl.h"
#include "IO/adcPots.h"
#include "Soundengine/FxBus.h"
// 0.2.67 hpd for the snare, see DrumVoice.c
extern float drum_highGain[4];
extern void drum_updateHighGainOsc(const uint8_t voiceNr,const OscInfo *osc);
//instance of the snare voice
INDTCMZ SnareVoice snareVoice;

static void Snare_updateNoiseEnvelopeEnabled(void)
{
	snareVoice.noiseEnvelopeEnabled = snareVoice.noiseAttackControl != 0 ||
		snareVoice.noiseDecayControl != 127 || snareVoice.noiseSlopeControl != 64;
	if(!snareVoice.noiseEnvelopeEnabled) snareVoice.noiseEgValue=1.f;
}
void Snare_setNoiseAttack(uint8_t value)
{
	snareVoice.noiseAttackControl=value;
	slopeEg2_setAttack(&snareVoice.noiseVolEg,value,false);
	Snare_updateNoiseEnvelopeEnabled();
}
void Snare_setNoiseDecay(uint8_t value)
{
	snareVoice.noiseDecayControl=value;
	slopeEg2_setDecay(&snareVoice.noiseVolEg,value,false);
	Snare_updateNoiseEnvelopeEnabled();
}
void Snare_setNoiseSlope(uint8_t value)
{
	snareVoice.noiseSlopeControl=value;
	slopeEg2_setSlope(&snareVoice.noiseVolEg,value);
	Snare_updateNoiseEnvelopeEnabled();
}
void Snare_setLayerWave(uint8_t value){snareVoice.layerOsc.waveform=value;}
void Snare_setLayerAmount(uint8_t value){snareVoice.layerAmountControl=value;snareVoice.layerAmount=value/127.f;}
void Snare_setLayerFreq(uint8_t value){snareVoice.layerFreqControl=value;}
void Snare_setLayerMode(uint8_t value){snareVoice.layerMode=value>SNARE_LAYER_MODE_MAX?SNARE_LAYER_MODE_MAX:value;}

//---------------------------------------------------
void Snare_setPan(const uint8_t pan)
{
	//snareVoice.panL = squareRootLut[127-pan];
	//snareVoice.panR = squareRootLut[pan];
	snareVoice.pan = pan;
}
//---------------------------------------------------
void Snare_init()
{
	initOnePole(&snareVoice.FaderVolumeFilter);
	setOnePoleCoef(&snareVoice.FaderVolumeFilter,0.1);

	SnapEg_init(&snareVoice.snapEg);
	Snare_setPan(0);
	snareVoice.vol = 0.8f;

	//snareVoice.panModifier = 1.f;

	snareVoice.noiseOsc.freq = 440;
	snareVoice.noiseOsc.waveform = 1;
	snareVoice.noiseOsc.fmMod = 0;
	snareVoice.noiseOsc.midiFreq = 70<<8 | 64;
	snareVoice.noiseOsc.pitchMod = 1.0f;
	snareVoice.noiseOsc.modNodeValue = 1;

	snareVoice.osc.freq = 440;
	snareVoice.osc.waveform = 1;
	snareVoice.osc.fmMod = 0;
	snareVoice.osc.midiFreq = 70<<8 | 64;
	snareVoice.osc.modNodeValue = 1;
	snareVoice.layerOsc=snareVoice.osc;
	Snare_setLayerWave(0);
	Snare_setLayerAmount(0);
	Snare_setLayerFreq(25);
	Snare_setLayerMode(0);

	setDistortionShape(&snareVoice.distortion, 0.f);

	snareVoice.volumeMod = 1;

	transient_init(&snareVoice.transGen);

	DecayEg_init(&snareVoice.oscPitchEg);
	snareVoice.egPitchModAmount = 0.5f;

	slopeEg2_init(&snareVoice.oscVolEg);
	slopeEg2_init(&snareVoice.noiseVolEg);
	snareVoice.noiseEgValue=1.f;
	Snare_setNoiseAttack(0);
	Snare_setNoiseDecay(127);
	Snare_setNoiseSlope(64);



	SVF_init(&snareVoice.filter);

	lfo_init(&snareVoice.lfo);
}
//---------------------------------------------------
void Snare_updatePan()
{
	snareVoice.triggeredPanL = sqrtf((127-snareVoice.pan)/127.f);
	snareVoice.triggeredPanR = sqrtf(snareVoice.pan/127.f);
}
//---------------------------------------------------
void Snare_trigger(const uint8_t vel, const uint8_t note)
{
	lfo_retrigger(3);
	//update velocity modulation
	modNode_updateValue(&velocityModulators[3],vel/127.f);

	float offset = 1;
	if(snareVoice.transGen.waveform==1) //offset mode
	{
		offset -= snareVoice.transGen.volume;
	}
	if(snareVoice.osc.waveform == SINE)
		snareVoice.osc.phase = (0x3ff<<20)*offset;//voiceArray[voiceNr].osc.startPhase ;
	else if(snareVoice.osc.waveform > SINE && snareVoice.osc.waveform <= REC)
		snareVoice.osc.phase = (0xff<<22)*offset;
	else
		snareVoice.osc.phase = 0;
	snareVoice.layerOsc.phase=0;
	snareVoice.osc.pdKnee = 0.f; // a new note starts at its own PD shape
	osc_setBaseNote(&snareVoice.layerOsc,note);

	DecayEg_trigger(&snareVoice.oscPitchEg);
	slopeEg2_trigger(&snareVoice.oscVolEg);
	if(snareVoice.noiseEnvelopeEnabled)
		slopeEg2_trigger(&snareVoice.noiseVolEg);
	snareVoice.velo = vel/127.f;

	osc_setBaseNote(&snareVoice.osc,note);
	//TODO noise muss mit transponiert werden

	transient_trigger(&snareVoice.transGen);

	SnapEg_trigger(&snareVoice.snapEg);

	Snare_updatePan();
}
//---------------------------------------------------
IN_ITCM_RAM void Snare_calcAsync()
{
	//add modulation eg to osc freq (1 = no change. a+eg = original freq + modulation
	const float egPitchVal = DecayEg_calc(&snareVoice.oscPitchEg);
	const float pitchEgValue = egPitchVal*snareVoice.egPitchModAmount;
	// like the Drum exp/pd modes, the depth follows the pitch EG
	snareVoice.layerDepth = snareVoice.layerAmount*egPitchVal;
	snareVoice.osc.pitchMod = 1+pitchEgValue;

	//calc the osc  vol eg
	snareVoice.egValueOscVol = slopeEg2_calc(&snareVoice.oscVolEg);
	if(fenv_on[3]) fenv_tick(3, snareVoice.egValueOscVol); // 0.2.93 filter env
	snareVoice.noiseEgValue = snareVoice.noiseEnvelopeEnabled ?
		slopeEg2_calc(&snareVoice.noiseVolEg) : 1.f;

	//turn off trigger signal if trigger gate mode is on and volume == 0
	/*
	if(trigger_isGateModeOn())
	{
		if(!snareVoice.egValueOscVol) {
			//trigger_triggerVoice(TRIGGER_4, TRIGGER_OFF);
			//voiceControl_noteOff(TRIGGER_4);
		}
	}
	*/

	//calc snap EG if transient sample 0 is activated
	if(snareVoice.transGen.waveform == 0)
	{
		const float snapVal = SnapEg_calc(&snareVoice.snapEg, snareVoice.transGen.pitch);
		snareVoice.osc.pitchMod += snapVal*snareVoice.transGen.volume;;
	}

	osc_setFreq(&snareVoice.osc);
	snareVoice.layerOsc.pitchMod=snareVoice.osc.pitchMod*(0.25f+snareVoice.layerFreqControl/33.9f);
	osc_setFreq(&snareVoice.layerOsc);
	osc_setFreq(&snareVoice.noiseOsc);
	drum_updateHighGainOsc(3,&snareVoice.osc);


}
//---------------------------------------------------
/* 0.2.102 silent-voice sleep (Mutador): body EG at 0 (and the noise EG when it
 * runs its own) gives 0 in every sample. Skip the work, keep the phases and
 * the fader smoothing moving, clear the filter once. */
static uint8_t snare_sleeping;
void Snare_calcSyncBlock(int16_t* buf, const uint8_t size)
{
	const float faderTarget = adc_getFaderVolume(3);
	if(snareVoice.egValueOscVol == 0.f &&
		(!snareVoice.noiseEnvelopeEnabled || snareVoice.noiseEgValue == 0.f))
	{
		if(!snare_sleeping)
		{
			SVF_reset(&snareVoice.filter);
			snare_sleeping = 1;
		}
		snareVoice.osc.phase += snareVoice.osc.phaseInc * size;
		snareVoice.layerOsc.phase += snareVoice.layerOsc.phaseInc * size;
		snareVoice.noiseOsc.phase += snareVoice.noiseOsc.phaseInc * size;
		for(uint8_t i=0;i<size;i++) calcOnePole(&snareVoice.FaderVolumeFilter, faderTarget);
		if(!snareVoice.noiseEnvelopeEnabled) snareVoice.combinedVolume = 0.f;
		bufferTool_clearBuffer(buf,size);
		return;
	}
	snare_sleeping = 0;
	int16_t transBuf[size];
	int16_t oscBuf[size];

	calcNoiseBlock(&snareVoice.noiseOsc,buf,size,0.9f);
#if USE_REVERB
	if(fxBus.fxType != FX_REVERB)
	{
#endif
		SVF_calcBlockZDF(&snareVoice.filter,snareVoice.filterType,buf,size);
#if USE_REVERB
	}
	else
	{
		SVF_calcBlockCheapZDF(&snareVoice.filter,snareVoice.filterType,buf,size);
	}
#endif




	//calc next osc sample
	const float oscGain=snareVoice.noiseEnvelopeEnabled ? 1.f : (1.f-snareVoice.mix);
	if(snareVoice.layerAmountControl && snareVoice.layerMode>=SNARE_LAYER_EXP) {
		/* exp: the layer osc bends the rate in octaves; pd: the snare osc warps
		 * itself. fmMod carries the depth only for this call, FM keeps its own. */
		const float fmMod=snareVoice.osc.fmMod;
		snareVoice.osc.fmMod=snareVoice.layerDepth;
		if(snareVoice.layerMode==SNARE_LAYER_EXP) {
			int16_t layerBuf[size];
			calcNextOscSampleBlock(&snareVoice.layerOsc,layerBuf,size,1.f,snareVoice.pwm);
			calcExpoFmBlock(&snareVoice.osc,layerBuf,oscBuf,size,snareVoice.pwm);
		} else {
			calcPhaseDistBlock(&snareVoice.osc,oscBuf,size);
		}
		snareVoice.osc.fmMod=fmMod;
		for(uint8_t i=0;i<size;i++)oscBuf[i]=(int16_t)(oscBuf[i]*oscGain);
	} else if(snareVoice.layerAmountControl && snareVoice.layerMode==1) {
		int16_t layerBuf[size];
		calcNextOscSampleBlock(&snareVoice.layerOsc,layerBuf,size,snareVoice.layerAmount,snareVoice.pwm);
		/* the layer level (sla) is the FM depth; fmMod stays 0 outside this call */
		const float fmMod=snareVoice.osc.fmMod;
		snareVoice.osc.fmMod=1.f;
		calcNextOscSampleFmBlock(&snareVoice.osc,layerBuf,oscBuf,size,oscGain,snareVoice.pwm);
		snareVoice.osc.fmMod=fmMod;
	} else {
	calcNextOscSampleBlock(&snareVoice.osc,oscBuf,size,oscGain,snareVoice.pwm);
	if(snareVoice.layerAmountControl) {
		int16_t layerBuf[size];
		const float amount=snareVoice.layerAmount;
		calcNextOscSampleBlock(&snareVoice.layerOsc,layerBuf,size,
			snareVoice.layerMode==0 ? oscGain : 1.f,snareVoice.pwm);
		for(uint8_t i=0;i<size;i++) {
			const float base=oscBuf[i];
			const float layer=layerBuf[i];
			float sample;
			if(snareVoice.layerMode==2) sample=base*(1.f-amount)+amount*(base*layer/32768.f);
			else sample=base*(1.f-amount)+layer*amount;
			if(sample>32767.f)sample=32767.f;
			else if(sample< -32768.f)sample= -32768.f;
			oscBuf[i]=(int16_t)sample;
		}
	}
	}
	// apply filter to synthesized sound as well here if desired, or combine code for more efficiency
	//SVF_calcBlockZDF(&snareVoice.filter,snareVoice.filterType,transBuf,size);


	//calc transient sample
	transient_calcBlock(&snareVoice.transGen,transBuf,size);


	uint8_t j;
	if(snareVoice.noiseEnvelopeEnabled)
	{
		const float bodyGain=snareVoice.egValueOscVol;
		const float noiseGain=snareVoice.noiseEgValue;
		const float velocity=snareVoice.volumeMod ? snareVoice.velo : 1.f;
		const float level=snareVoice.vol*velocity;
		for(j=0;j<size;j++)
		{
			const float body=oscBuf[j]*(1.f-snareVoice.mix)*bodyGain;
			const float noise=buf[j]*snareVoice.mix*noiseGain;
			const float click=transBuf[j]*bodyGain;
			buf[j]=level*(body+noise+click)*
				calcOnePole(&snareVoice.FaderVolumeFilter,faderTarget);
		}
		calcDistBlock(&snareVoice.distortion,buf,size);
		return;
	}
	if(snareVoice.volumeMod)
	{
		snareVoice.combinedVolume = snareVoice.vol * snareVoice.velo * snareVoice.egValueOscVol * drum_highGain[3];
		//const float vol = ;

		for(j=0;j<size;j++)
		{

#if 1
			//float fmaf(float a, float b, float c);
			//result = a × b + c
			float tmp = fmaf(buf[j], snareVoice.mix, oscBuf[j]);
			//add transient sample
			//tmp	= __QADD16(transBuf[j],(int16_t)tmp);
			tmp	+= transBuf[j];
			buf[j] =   snareVoice.combinedVolume  * tmp * calcOnePole( &snareVoice.FaderVolumeFilter, faderTarget);

#else

			//add filter to buffer
			buf[j] *= snareVoice.mix;
			buf[j] = (__QADD16(buf[j],transBuf[j])); //transBuf here is mod osc

			buf[j] *=  vol;
#endif
		}
	}
	else
	{
		snareVoice.combinedVolume = snareVoice.vol * snareVoice.egValueOscVol * drum_highGain[3];
		//const float vol = snareVoice.combinedVolume * ;

		for(j=0;j<size;j++)
		{

#if 1
			float tmp = fmaf(buf[j], snareVoice.mix, oscBuf[j]);
			//add transient sample
			//tmp	= __QADD16(transBuf[j],(int16_t)tmp);
			tmp	+= transBuf[j];
			buf[j] =  snareVoice.combinedVolume * tmp * calcOnePole( &snareVoice.FaderVolumeFilter, faderTarget);
#else
			//add filter to buffer
			buf[j] *= snareVoice.mix;
			buf[j] = (__QADD16(buf[j],transBuf[j]));
			buf[j] *=  vol;
#endif
		}
	}

	calcDistBlock(&snareVoice.distortion,buf,size);
}
//------------------------------------------------------------------------
