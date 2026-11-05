/*
 * Oscillator.c
 *
 *  Created on: 02.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#include "Soundengine/DSPAudio/Oscillator.h"
#include "Soundengine/DSPAudio/random.h"
#include "Soundengine/DSPAudio/Samples.h"
#include "Soundengine/DSPAudio/WaveBank.h"
#include "Soundengine/DSPAudio/SampleBank.h"
#include "Soundengine/MIDI/MidiParser.h"
#include "Soundengine/MIDI/MidiNoteNumbers.h"
#include "Soundengine/Sequencer/sequencer.h"

static __inline uint32_t freq2PhaseIncr(const float f) //4096
{
	return (((TABLESIZE*f)/REAL_FS))*1048576 ; // 1048576 <-> (<<20)
}
//TODO die phaseInc berechnung kann man doch sicher per LUT machen!
//-----------------------------------------------------------
static __inline uint8_t fast_log2 (const uint32_t val)
{
	return 31-__CLZ(val);
}
//-----------------------------------------------------------
static __inline int freqToMidiNote(const float f)
{
	return (12*fast_log2((uint32_t)(f/440.f)))+70;
}
//-----------------------------------------------------------
static __inline uint8_t freqToTableIndex(const float f)
{
	return freqToMidiNote(f)/12;
}
//-----------------------------------------------------------

//-----------------------------------------------------------
static __inline uint32_t freq2PhaseIncr1024(const float f)
{
	return (((1024*f)/REAL_FS))*4194304 ; //(<<22)
}
//-----------------------------------------------------------
static __inline uint32_t freq2PhaseIncr32767(const float f)
{
	return (((1024*f)/REAL_FS))*131072 ; //(<<17)
}
//-----------------------------------------------------------
IN_ITCM_RAM void calcSineBlock(OscInfo* osc, int16_t* buf, const uint8_t size ,const float gain)
{
	//tablesize 4096 => 0b111111111111 -> 12 bits
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		int16_t oscOut;

		const uint32_t index =  oscPhase;
		uint32_t  itg	= index>>20; // 12 msb as itg index

		#if INTERPOLATE_OSC
			oscOut = sine_table[itg++];

			//const float frac = (index&0x7ffff)*0.0000019073486328125f;  // 1/0x7ffff = 0.0000019073486328125f
			//oscOut += frac*(sine_table[itg] - oscOut);
			//a + t * (b - a);
			uint32_t frac = index&0xFFFFF;
			oscOut = oscOut + (int16_t)(((int64_t)(sine_table[itg] - oscOut) * frac)   >>20);
		#else
			oscOut = sine_table[itg];
		#endif

		osc->phase = oscPhase + osc->phaseInc;

		buf[i] = oscOut * gain;
	}
}
//-----------------------------------------------------------
int16_t calcSine(OscInfo* osc)
{
	const uint32_t oscPhase = osc->phase;
	int16_t oscOut;

	const uint32_t index =  oscPhase;
	uint32_t  itg	= index>>20;

#if INTERPOLATE_OSC
	oscOut = sine_table[itg++];
	//float frac	= (index&0x7ffff)*0.0000019073486328125f;
	//oscOut += frac*(sine_table[itg] - oscOut);
	uint32_t frac = index&0xFFFFF;
	oscOut = oscOut + (int16_t)(((int64_t)(sine_table[itg] - oscOut) * frac)   >>20);
#else
	oscOut = sine_table[itg];
#endif

	osc->phase = oscPhase + osc->phaseInc;
	osc->output = oscOut;
	return oscOut;
}

//-----------------------------------------------------------
IN_ITCM_RAM void calcFmSineBlock(OscInfo* osc, int16_t* modBuffer, int16_t* buf, uint8_t size,const float gain)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		int16_t oscOut ;

		const uint32_t index =  oscPhase + (((uint32_t)(modBuffer[i]*osc->fmMod))<<17);
		uint32_t  itg	= index>>20;

	#if INTERPOLATE_FM_OSC
		oscOut = sine_table[itg++];
		//const float frac	= (index&0x7ffff)*0.0000019073486328125f;
		//oscOut += frac*(sine_table[itg] - oscOut);
		uint32_t frac = index&0xFFFFF;
		oscOut = oscOut + (int16_t)(((int64_t)(sine_table[itg] - oscOut) * frac)   >>20);
	#else
		oscOut = sine_table[itg];
	#endif

		osc->phase = oscPhase + osc->phaseInc;
		buf[i] =  oscOut * gain;
	}
}
//-----------------------------------------------------------
int16_t calcFmSine(OscInfo* osc, OscInfo* modOsc)
{
	const uint32_t oscPhase 	= osc->phase;
	int16_t oscOut ;

	const uint32_t index =  oscPhase + (((uint32_t)(modOsc->output*osc->fmMod))<<17);
	uint32_t  itg	= index>>20;

#if INTERPOLATE_FM_OSC
	oscOut = sine_table[itg++];
	//const float frac	= (index&0x7ffff)*0.0000019073486328125f;
	//oscOut += frac*(sine_table[itg] - oscOut);
	uint32_t frac = index&0xFFFFF;
	oscOut = oscOut + (int16_t)(((int64_t)(sine_table[itg] - oscOut) * frac)   >>20);
#else
	oscOut = sine_table[itg];
#endif

	osc->phase = oscPhase + osc->phaseInc;
	osc->output = oscOut;
	return oscOut;
};
//---------------------------------------------------------------
IN_ITCM_RAM void calcFmBlock(OscInfo* osc, const int16_t table[][1024], int16_t* modBuffer, int16_t* buf, uint8_t size ,const float gain)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		int16_t oscOut ;
		const uint32_t index =  oscPhase + (((uint32_t)(modBuffer[i]*osc->fmMod))<<19);

		uint32_t  itg	= index>>22; //10 bit index, 22 bit fractional part

	#if INTERPOLATE_FM_OSC
		oscOut = table[osc->tableOffset][itg++];
		//const float frac	= (index&0x003FFFFF)*2.38418579101562e-07f;
		//oscOut += frac*(table[osc->tableOffset][itg] - oscOut);
		uint32_t frac = index & 0x3FFFFF;
		oscOut = oscOut + (int16_t)(((int64_t)(table[osc->tableOffset][itg] - oscOut) * frac)   >>22);

	#else
		oscOut = table[overtoneIndex][itg];
	#endif

		osc->phase = oscPhase + osc->phaseInc;
		osc->output = oscOut;
		buf[i] = oscOut * gain;
	}
}
//-----------------------------------------------------------
void calcPwmFmBlock(OscInfo* osc, int16_t* modBuffer, int16_t* buf, uint8_t size ,const float gain, const float pwm)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		int16_t oscOut ;
		const uint32_t index =  oscPhase + (((uint32_t)(modBuffer[i]*osc->fmMod))<<19);
		const uint32_t index2 = index + pwm * (UINT32_MAX/2);

		 uint32_t  itg	 = index>>22;
		 uint32_t  itg2 = index2>>22;

	#if INTERPOLATE_FM_OSC
		oscOut = sawTable[osc->tableOffset][itg++];
		//const float frac	= (index&0x003FFFFF)*2.38418579101562e-07f;
		//oscOut += frac*(sawTable[osc->tableOffset][itg] - oscOut);
		uint32_t frac = index & 0x3FFFFF;
		oscOut = oscOut + (int16_t)(((int64_t)(sawTable[osc->tableOffset][itg] - oscOut) * frac)   >>22);

		int16_t osc2Out = sawTable[osc->tableOffset][itg2++];// * -1;
		//const float frac	= (index&0x003FFFFF)*2.38418579101562e-07f;
		frac = index2 & 0x3FFFFF;
		//osc2Out += frac*(sawTable[osc->tableOffset][itg2] * -1 - osc2Out);
		osc2Out = osc2Out + (int16_t)(((int64_t)(sawTable[osc->tableOffset][itg2] - osc2Out) * frac)   >>22);

		oscOut =  __QSUB16(oscOut,osc2Out);


	#else
		oscOut = sawTable[overtoneIndex][itg];
	#endif

		osc->phase = oscPhase + osc->phaseInc;
		osc->output = oscOut;
		buf[i] = oscOut * gain;
	}
}
//-----------------------------------------------------------
int16_t calcFm(OscInfo* osc, OscInfo* modOsc, const int16_t table[][1024])
{

	const uint32_t oscPhase = osc->phase;
	int16_t oscOut ;

	const uint32_t index =  oscPhase + (((uint32_t)(modOsc->output*osc->fmMod))<<19);

	uint32_t  itg	= index>>22;

#if INTERPOLATE_FM_OSC
	oscOut = table[osc->tableOffset][itg++];
	//const float frac	= (index&0x003FFFFF)*2.38418579101562e-07f;
	//oscOut += frac*(table[osc->tableOffset][itg] - oscOut);
	uint32_t frac = index & 0x3FFFFF;
	oscOut = oscOut + (int16_t)(((int64_t)(table[osc->tableOffset][itg] - oscOut) * frac)   >>22);
#else
	oscOut = table[overtoneIndex][itg];
#endif

	osc->phase = oscPhase + osc->phaseInc;
	osc->output = oscOut;
	return oscOut;
}
//-----------------------------------------------------------
// 2^octaves for |octaves|<=EXPO_FM_OCTAVES; exact at whole octaves, so no modulation keeps the tuning
static inline float osc_expoRatio(const float octaves)
{
	const int32_t whole = (int32_t)(octaves + EXPO_FM_OCTAVES + 1) - (EXPO_FM_OCTAVES + 1);
	const float frac = octaves - whole;
	union { float f; uint32_t i; } ratio = { 1.f + frac*(0.69582f + frac*(0.22543f + frac*0.07875f)) };
	ratio.i += (uint32_t)whole << 23;
	return ratio.f;
}
//-----------------------------------------------------------
static inline int16_t osc_readTable(const int16_t table[][1024], const uint8_t offset, const uint32_t index)
{
	const uint32_t itg = index>>22;
	const int32_t a = table[offset][itg];
	const int32_t b = table[offset][(itg+1)&1023];
	return (int16_t)(a + (int32_t)(((int64_t)(b - a) * (index&0x3FFFFF))>>22));
}
//-----------------------------------------------------------
// User wavetables. Waveform picks the wavetable, PWM scans its frames from the
// first to the last; both frames are read at the octave level of the pitch.
typedef struct
{
	const int16_t* from;	// the frame, all levels
	const int16_t* to;		// 0 when no blend is needed
	int32_t mix;			// share of `to`, 0..32767
	int32_t levelMix;		// share of the next octave level, 0..32767
	uint16_t offset;		// the level inside the frame
	uint16_t nextOffset;
	uint8_t bits;			// the level holds 2^bits samples
	uint8_t nextBits;
} WaveBankScan;

// Level j covers 27.5 Hz * 2^j up to 55 Hz * 2^j; the next level fades in over
// it, so a pitch sweep does not switch the partials at once
static inline uint16_t osc_levelMix(const float freq, const uint8_t level)
{
	if(level >= WAVEBANK_LEVELS-1) return 0;
	const float mix = freq/(27.5f*(float)(1u<<level)) - 1.f;
	return mix <= 0.f ? 0 : mix >= 1.f ? 32767 : (uint16_t)(mix*32767.f);
}
//-----------------------------------------------------------
// A wavetable scans its frames; a single wave scans on through the single
// waves in the slots after it
static uint8_t osc_waveBankScan(OscInfo* osc, const float pwm, WaveBankScan* scan)
{
	const uint8_t table = (uint8_t)(osc->waveform-NUM_OSC_WAVEFORMS);
	const uint8_t frames = waveBank_frames(table);
	if(!frames) return 0;
	const float target = pwm < 0.f ? 0.f : pwm > 1.f ? 1.f : pwm;
	osc->scanPos += (target-osc->scanPos)*OSC_SCAN_GLIDE;
	uint8_t span = frames;
	if(frames == 1)
		while(table+span < WAVEBANK_MAX && waveBank_frames((uint8_t)(table+span)) == 1) span++;
	const float position = osc->scanPos*(span-1);
	uint8_t step = (uint8_t)position;
	int32_t mix = (int32_t)((position-step)*32768.f);
	if(mix >= 32768)
	{
		step++;
		mix = 0;
	}
	if(step >= span-1)
	{
		step = (uint8_t)(span-1);
		mix = 0;
	}
	const uint8_t level = osc->tableOffset < WAVEBANK_LEVELS ? osc->tableOffset : WAVEBANK_LEVELS-1;
	scan->offset = waveBank_levelOffset(level);
	scan->bits = waveBank_levelBits(level);
	scan->nextOffset = waveBank_levelOffset((uint8_t)(level+1));
	scan->nextBits = waveBank_levelBits((uint8_t)(level+1));
	scan->levelMix = level < WAVEBANK_LEVELS-1 ? osc->levelMix : 0;
	if(frames == 1)
	{
		scan->from = waveBank_frame((uint8_t)(table+step),0);
		scan->to = mix ? waveBank_frame((uint8_t)(table+step+1),0) : 0;
	}
	else
	{
		scan->from = waveBank_frame(table,step);
		scan->to = mix ? waveBank_frame(table,(uint8_t)(step+1)) : 0;
	}
	scan->mix = mix;
	return 1;
}
//-----------------------------------------------------------
static inline int16_t osc_readLevel(const int16_t* level, const uint8_t bits, const uint32_t index)
{
	const uint32_t itg = index>>(32-bits);
	const int32_t a = level[itg];
	const int32_t b = level[(itg+1)&((1u<<bits)-1)];
	const uint32_t frac = (index<<bits)>>10;	// 22 bit
	return (int16_t)(a + (int32_t)(((int64_t)(b - a) * frac)>>22));
}
//-----------------------------------------------------------
static inline int16_t osc_readFrame(const WaveBankScan* scan, const int16_t* frame, const uint32_t index)
{
	const int32_t a = osc_readLevel(frame+scan->offset,scan->bits,index);
	if(!scan->levelMix) return (int16_t)a;
	const int32_t b = osc_readLevel(frame+scan->nextOffset,scan->nextBits,index);
	return (int16_t)(a + (((b-a)*scan->levelMix)>>15));
}
//-----------------------------------------------------------
static inline int16_t osc_readScan(const WaveBankScan* scan, const uint32_t index)
{
	const int32_t a = osc_readFrame(scan,scan->from,index);
	if(!scan->to) return (int16_t)a;
	const int32_t b = osc_readFrame(scan,scan->to,index);
	return (int16_t)(a + (((b-a)*scan->mix)>>15));
}
//-----------------------------------------------------------
// silent when the slot has no table
void calcWaveBankBlock(OscInfo* osc, int16_t* buf, const uint8_t size, const float gain, const float pwm)
{
	WaveBankScan scan;
	if(!osc_waveBankScan(osc,pwm,&scan))
	{
		for(uint8_t i=0;i<size;i++) buf[i] = 0;
		osc->output = 0;
		return;
	}
	for(uint8_t i=0;i<size;i++)
	{
		const int16_t oscOut = osc_readScan(&scan,osc->phase);
		osc->phase += osc->phaseInc;
		osc->output = oscOut;
		buf[i] = oscOut * gain;
	}
}
//-----------------------------------------------------------
void calcWaveBankFmBlock(OscInfo* osc, int16_t* modBuffer, int16_t* buf, uint8_t size, const float gain, const float pwm)
{
	WaveBankScan scan;
	if(!osc_waveBankScan(osc,pwm,&scan))
	{
		calcWaveBankBlock(osc,buf,size,gain,pwm);
		return;
	}
	for(uint8_t i=0;i<size;i++)
	{
		const uint32_t index = osc->phase + (((uint32_t)(modBuffer[i]*osc->fmMod))<<19);
		const int16_t oscOut = osc_readScan(&scan,index);
		osc->phase += osc->phaseInc;
		osc->output = oscOut;
		buf[i] = oscOut * gain;
	}
}
//-----------------------------------------------------------
// User samples (waveform >= SAMPLEBANK_FIRST_WAVE): one shot from the trigger,
// silent after the last frame. The phase holds the frame in its upper 20
// bits and the fraction in the lower 12; the pitch comes from osc_calcSampleBankFreq.
typedef char SampleBankFirstWave[(SAMPLEBANK_FIRST_WAVE == NUM_OSC_WAVEFORMS + WAVEBANK_MAX) ? 1 : -1];
#define OSC_SAMPLE_FRAC ((1u << SAMPLEBANK_PHASE_BITS) - 1u)
#define OSC_SAMPLE_FM_SHIFT 9	// a full modulator moves the read point by 4096 frames, as on the LXR1

static inline uint8_t osc_isSample(const OscInfo* osc)
{
	return osc->waveform >= SAMPLEBANK_FIRST_WAVE;
}

static inline int16_t osc_readSample(const int16_t* data, const uint32_t index)
{
	const uint32_t pos = index >> SAMPLEBANK_PHASE_BITS;
	const int32_t a = data[pos];
	const int32_t b = data[pos+1];
	return (int16_t)(a + (((b - a) * (int32_t)(index & OSC_SAMPLE_FRAC)) >> SAMPLEBANK_PHASE_BITS));
}

static inline uint32_t osc_sampleStep(const uint32_t phase, const uint32_t inc, const uint32_t end)
{
	const uint32_t next = phase + inc;
	return (next < phase || next > end) ? end : next;
}

void calcSampleBankBlock(OscInfo* osc, int16_t* buf, const uint8_t size, const float gain)
{
	const uint8_t sample = (uint8_t)(osc->waveform - SAMPLEBANK_FIRST_WAVE);
	const int16_t* data = sampleBank_data(sample);
	if(!data)
	{
		for(uint8_t i=0;i<size;i++) buf[i] = 0;
		osc->output = 0;
		return;
	}
	const uint32_t end = (sampleBank_frames(sample) - 1u) << SAMPLEBANK_PHASE_BITS;
	for(uint8_t i=0;i<size;i++)
	{
		int16_t oscOut = 0;
		if(osc->phase < end)
		{
			oscOut = osc_readSample(data, osc->phase);
			osc->phase = osc_sampleStep(osc->phase, osc->phaseInc, end);
		}
		osc->output = oscOut;
		buf[i] = oscOut * gain;
	}
}

void calcSampleBankFmBlock(OscInfo* osc, int16_t* modBuffer, int16_t* buf, const uint8_t size, const float gain)
{
	const uint8_t sample = (uint8_t)(osc->waveform - SAMPLEBANK_FIRST_WAVE);
	const int16_t* data = sampleBank_data(sample);
	if(!data)
	{
		calcSampleBankBlock(osc, buf, size, gain);
		return;
	}
	const uint32_t end = (sampleBank_frames(sample) - 1u) << SAMPLEBANK_PHASE_BITS;
	for(uint8_t i=0;i<size;i++)
	{
		int16_t oscOut = 0;
		if(osc->phase < end)
		{
			int64_t index = (int64_t)osc->phase + ((int64_t)(int32_t)(modBuffer[i]*osc->fmMod) << OSC_SAMPLE_FM_SHIFT);
			if(index < 0) index = 0;
			else if(index >= end) index = end - 1u;
			oscOut = osc_readSample(data, (uint32_t)index);
			osc->phase = osc_sampleStep(osc->phase, osc->phaseInc, end);
		}
		osc->output = oscOut;
		buf[i] = oscOut * gain;
	}
}
//-----------------------------------------------------------
static inline int16_t osc_readSine(const uint32_t index)
{
	const uint32_t itg = index>>20;
	const int32_t a = sine_table[itg];
	const int32_t b = sine_table[itg+1];
	return (int16_t)(a + (int32_t)(((int64_t)(b - a) * (index&0xFFFFF))>>20));
}
//-----------------------------------------------------------
// Exponential FM: the modulator acts in octaves on the rate of the osc, like a V/Oct input.
IN_ITCM_RAM void calcExpoFmBlock(OscInfo* osc, int16_t* modBuffer, int16_t* buf, uint8_t size, const float pwm)
{
	if(osc->waveform==NOISE)
	{
		calcNoiseBlock(osc,buf,size,1.f);
		return;
	}
	if(osc_isSample(osc))
	{
		calcSampleBankBlock(osc,buf,size,1.f);
		return;
	}
	WaveBankScan scan = {0};
	const uint8_t user = osc->waveform>PWM;
	if(user && !osc_waveBankScan(osc,pwm,&scan))
	{
		calcWaveBankBlock(osc,buf,size,1.f,pwm);
		return;
	}
	const float depth = osc->fmMod*EXPO_FM_OCTAVES/32768.f;
	const float baseInc = osc->phaseInc;
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		int16_t oscOut;
		switch(osc->waveform)
		{
		case SINE:
			oscOut = osc_readSine(oscPhase);
			break;
		case TRI:
			oscOut = osc_readTable(triTable,osc->tableOffset,oscPhase);
			break;
		case SAW:
			oscOut = osc_readTable(sawTable,osc->tableOffset,oscPhase);
			break;
		case REC:
			oscOut = osc_readTable(recTable,osc->tableOffset,oscPhase);
			break;
		default:
		{
			if(user)
			{
				oscOut = osc_readScan(&scan,oscPhase);
				break;
			}
			const uint32_t oscPhase2 = oscPhase + pwm * (UINT32_MAX/2);
			oscOut = __QSUB16(osc_readTable(sawTable,osc->tableOffset,oscPhase),
				osc_readTable(sawTable,osc->tableOffset,oscPhase2));
			break;
		}
		}
		float inc = baseInc*osc_expoRatio(modBuffer[i]*depth);
		if(inc>OSC_MAX_PHASE_INC) inc = OSC_MAX_PHASE_INC;
		osc->phase = oscPhase + (uint32_t)inc;
		osc->output = oscOut;
		buf[i] = oscOut;
	}
}
//-----------------------------------------------------------
// Casio style phase distortion: amount warps the read speed of one sine cycle, from pure sine to saw.
IN_ITCM_RAM void calcPhaseDistBlock(OscInfo* osc, int16_t* buf, uint8_t size)
{
	// user wavetables and samples have no sine to warp; they play plain
	if(osc->waveform>PWM)
	{
		calcNextOscSampleBlock(osc,buf,size,1.f,0.f);
		return;
	}
	float amount = osc->fmMod;
	if(amount<0.f) amount = 0.f;
	else if(amount>1.f) amount = 1.f;
	// keep the steep part at least two samples long
	float minKnee = osc->phaseInc*(2.f/4294967296.f);
	if(minKnee<PD_MIN_KNEE) minKnee = PD_MIN_KNEE;
	else if(minKnee>0.5f) minKnee = 0.5f;
	// the amount follows the pitch EG once a block; the knee glides to it within
	// the block, so the shape does not step every block and click
	const float target = 0.5f - amount*(0.5f-minKnee);
	const float start = osc->pdKnee > 0.f ? osc->pdKnee : target;
	const float kneeStep = (target-start)/size;
	osc->pdKnee = target;
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const float knee = start + kneeStep*(i+1);
		const float riseSlope = 0.5f/knee;
		const float fallSlope = 0.5f/(1.f-knee);
		const uint32_t oscPhase = osc->phase;
		// a quarter cycle back, so no warp reads the plain sine from phase 0
		const float phase = (oscPhase+0xC0000000u)*(1.f/4294967296.f);
		float warped = phase<knee ? phase*riseSlope : 0.5f+(phase-knee)*fallSlope;
		if(warped>1.f) warped = 1.f;
		const int16_t oscOut = osc_readSine((uint32_t)(warped*4294967040.f)+0x40000000u);
		osc->phase = oscPhase + osc->phaseInc;
		osc->output = oscOut;
		buf[i] = oscOut;
	}
}
//-----------------------------------------------------------
IN_ITCM_RAM void calcNextOscSampleFmBlock(OscInfo* osc, int16_t* modBuffer, int16_t* buf, uint8_t size ,const float gain, const float pwm)
{
	switch(osc->waveform)
		{
		case SINE:
			calcFmSineBlock(osc,modBuffer,buf,size,gain);
			break;

		case SAW:
			calcFmBlock(osc,sawTable,modBuffer,buf,size,gain);
			break;

		case TRI:
			calcFmBlock(osc, triTable, modBuffer,buf,size,gain);
			break;

		case REC:
			calcFmBlock(osc, recTable, modBuffer,buf,size,gain);
			break;

		case NOISE:
			//TODO FM noise - needed since its tuned digi noise!
			calcNoiseBlock(osc,buf,size,gain);
			break;

		case PWM:
			calcPwmFmBlock(osc,modBuffer,buf,size,gain, pwm);//calcSampleOscFmBlock(osc,modBuffer,buf,size,gain);
			break;

		default:
			if(osc_isSample(osc)) calcSampleBankFmBlock(osc,modBuffer,buf,size,gain);
			else calcWaveBankFmBlock(osc,modBuffer,buf,size,gain,pwm);
			break;

		}
}
//-----------------------------------------------------------
/*
int16_t calcNextOscSampleFm(OscInfo* osc,OscInfo* modOsc)
{
	switch(osc->waveform)
	{
	case SINE:
		return calcFmSine(osc,modOsc);
		break;

	case SAW:
		return calcFm(osc,modOsc,sawTable);
		break;

	case TRI:
		return calcFm(osc,modOsc, triTable);
		break;

	case REC:
		return calcFm(osc,modOsc,recTable);
		break;

	case NOISE:
		return calcNoise(osc);
		break;

	case PWM:
		return calcSampleOscFm(osc,modOsc);
		break;

	default:

		return 0;
		break;

	}
	return 0;
}
*/
//-----------------------------------------------------------
IN_ITCM_RAM void calcNoiseBlock(OscInfo* osc, int16_t* buf, const uint8_t size ,const float gain)
{
	int i;
	for(i=0;i<size;i++)
	{
		const uint32_t lastPhase = osc->phase;
		osc->phase += osc->phaseInc;

		if(lastPhase > osc->phase)
		{
			//overflow happened -> phaseWrapped
			osc->output = GetRngValue(); //normal pitched white noise
		}

		buf[i] = osc->output * gain;
	}
}
//-----------------------------------------------------------
int16_t calcNoise(OscInfo* osc)
{
	osc->phase += osc->phaseInc;

	//check overflow flag, ( if osc->phase == osc->phaseInc a reset occured ==> retrigger, too
	APSR_Type apsr;
	apsr.w = __get_APSR();
	if(apsr.b.V ||  (osc->phase == osc->phaseInc))
	{
		//overflow happened -> phaseWrapped

		uint16_t rnd = GetRngValue();
		if( rnd > 0x00ff)
		{
			if( rnd > 0x000f)
			{
				osc->output = 32767;
			}
			else
			{
				osc->output = -32768;
			}

		}
	}
	else
	{
			osc->output = 0;
	}
	return osc->output;
}
//-----------------------------------------------------------
IN_ITCM_RAM void calcNextOscSampleBlock(OscInfo* osc, int16_t* buf, const uint8_t size, const float gain, const float pwm)
{
	switch(osc->waveform)
		{
		case SINE:
			calcSineBlock(osc,buf,size, gain);
			break;

		case SAW:
			calcWavetableOscBlock(osc,sawTable,buf,size, gain);
			break;

		case TRI:
			calcWavetableOscBlock(osc,triTable,buf,size, gain);
			break;

		case REC:
			calcWavetableOscBlock(osc,recTable,buf,size, gain);
			break;

		case NOISE:
			calcNoiseBlock(osc,buf,size, gain);
			break;

		case PWM:
			calcPwmBlock(osc,buf,size, gain, pwm);
			break;

		default:
			if(osc_isSample(osc)) calcSampleBankBlock(osc,buf,size,gain);
			else calcWaveBankBlock(osc,buf,size,gain,pwm);
			break;
		}
}
//-----------------------------------------------------------
/*
int16_t calcNextOscSample(OscInfo* osc)
{
	switch(osc->waveform)
	{
	case SINE:
		return calcSine(osc);
		break;

	case SAW:
		return calcWavetableOsc(osc,sawTable);
		break;

	case TRI:
		return calcWavetableOsc(osc,triTable);
		break;

	case REC:
		return calcWavetableOsc(osc,recTable);
		break;

	case NOISE:
		return calcNoise(osc);
		break;

	case CRASH:
		return calcSampleOsc(osc);
		break;

	default:

		return 0;
		break;

	}
	return 0;
};
*/
//---------------------------------------------------------------
IN_ITCM_RAM void calcWavetableOscBlock(OscInfo* osc, const int16_t table[][1024], int16_t* buf, const uint8_t size ,const float gain)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
			int16_t oscOut ;
			uint32_t  itg	= oscPhase>>22;
		#if INTERPOLATE_OSC
			//todo use ldm instead of ldr to load multiple values from memory
			oscOut = table[osc->tableOffset][itg++];
			//const float frac = (itg&0x003FFFFF)*2.38418579101562e-07f; //2.38... => 1.f/0x3fffff
			//oscOut += frac*(table[osc->tableOffset][itg] - oscOut);
			uint32_t frac = oscPhase & 0x3FFFFF;
			oscOut = oscOut + (int16_t)(((int64_t)(table[osc->tableOffset][itg] - oscOut) * frac)   >>22);
		#else
			oscOut = table[osc->tableOffset][itg];
		#endif

			osc->phase = oscPhase + osc->phaseInc;
			buf[i] = oscOut * gain;
	}
}

//---------------------------------------------------------------
int16_t calcWavetableOsc(OscInfo* osc,  const int16_t table[][1024])
{
	const uint32_t oscPhase = osc->phase;
	int16_t oscOut ;

	uint32_t  itg	= oscPhase>>22;

#if INTERPOLATE_OSC
	//todo use ldm instead of ldr to laod multiple values from memory
	oscOut = table[osc->tableOffset][itg++];
	//const float frac = (itg&0x003FFFFF)*2.38418579101562e-07f; //2.38... => 1.f/0x3fffff
	//oscOut += frac*(table[osc->tableOffset][itg] - oscOut);
	uint32_t frac = oscPhase & 0x3FFFFF;
	oscOut = oscOut + (int16_t)(((int64_t)(table[osc->tableOffset][itg] - oscOut) * frac)   >>22);
#else
	oscOut = table[osc->tableOffset][itg];
#endif

	osc->phase = oscPhase + osc->phaseInc;
	osc->output = oscOut;
	return oscOut;

};

//------------------------------------------------------------------
/*
void calcSampleOscFmBlock(OscInfo* osc,int16_t* modBuffer, int16_t* buf, uint8_t size ,const float gain)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase 	= osc->phase;
		int16_t oscOut ;

		const uint32_t index =  oscPhase + (((uint32_t)(modBuffer[i]*osc->fmMod))<<14);
		uint32_t  itg	= index>>17;

	#if INTERPOLATE_FM_OSC
		oscOut = crashSample[itg++];
		const float frac	= (index&20000)*0.00000762939453125f;//=> * 1/0x20000
		oscOut += frac*(crashSample[itg] - oscOut);
	#else
		oscOut = crashSample[itg];
	#endif

		oscOut = (oscOut - 127)*256;

		osc->phase = oscPhase + osc->phaseInc;
		osc->output = oscOut;
		buf[i] = oscOut * gain;
	}
}
*/
//------------------------------------------------------------------
/*
int16_t calcSampleOscFm(OscInfo* osc, OscInfo* modOsc)
{

	const uint32_t oscPhase 	= osc->phase;
	int16_t oscOut ;

	const uint32_t index =  oscPhase + (((uint32_t)(modOsc->output*osc->fmMod))<<14);
	uint32_t  itg	= index>>17;

#if INTERPOLATE_FM_OSC
	oscOut = crashSample[itg++];
	const float frac	= (index&20000)*0.00000762939453125f;//=> * 1/0x20000
	oscOut += frac*(crashSample[itg] - oscOut);
#else
	oscOut = crashSample[itg];
#endif

	oscOut = (oscOut - 127)*256;

	osc->phase = oscPhase + osc->phaseInc;
	osc->output = oscOut;
	return oscOut;
};
*/
//------------------------------------------------------------------
//---------------------------------------------------------------
/*
void calcSampleOscBlock(OscInfo* osc, int16_t* buf, const uint8_t size ,const float gain)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		int16_t oscOut ;
		uint32_t  itg	= oscPhase>>17;


	#if INTERPOLATE_OSC
		//todo use ldm instead of ldr to laod multiple values from memory
		oscOut = crashSample[itg++];
		const float frac = (oscPhase&20000)*0.00000762939453125f;//=> * 1/0x20000
		oscOut += frac*(crashSample[itg] - oscOut);
	#else
		oscOut = crashSample[itg];
	#endif
		oscOut = (oscOut - 127)*256;

		osc->phase = oscPhase + osc->phaseInc;
		buf[i] = oscOut * gain;
	}
}
*/
//-----------------------------------------------------------
IN_ITCM_RAM void calcPwmBlock(OscInfo* osc, int16_t* buf, uint8_t size ,const float gain, const float pwm)
{



	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		const uint32_t oscPhase2 = osc->phase + pwm * (UINT32_MAX/2);
		int16_t oscOut ;
		uint32_t  itg	= oscPhase>>22;
		uint32_t  itg2	= oscPhase2>>22;


		#if INTERPOLATE_FM_OSC
			oscOut = sawTable[osc->tableOffset][itg++];
			//const float frac	= (oscPhase&0x003FFFFF)*2.38418579101562e-07f;
			//const float frac = (itg&0x003FFFFF)*2.38418579101562e-07f;
			//oscOut += frac*(sawTable[osc->tableOffset][itg] - oscOut);
			uint32_t frac = oscPhase & 0x3FFFFF;
			oscOut = oscOut + (int16_t)(((int64_t)(sawTable[osc->tableOffset][itg] - oscOut) * frac)   >>22);

			int16_t osc2Out = sawTable[osc->tableOffset][itg2++] ;//* -1;
			//const float frac	= (index&0x003FFFFF)*2.38418579101562e-07f;
			//osc2Out += frac*(sawTable[osc->tableOffset][itg2] * -1 - osc2Out);
			frac = oscPhase2 & 0x3FFFFF;
			osc2Out = osc2Out + (int16_t)(((int64_t)(sawTable[osc->tableOffset][itg2++] - osc2Out) * frac)   >>22);

			oscOut =  __QSUB16(oscOut,osc2Out);

		#else
			oscOut = sawTable[overtoneIndex][itg];
		#endif

			osc->phase = oscPhase + osc->phaseInc;
			osc->output = oscOut;
			buf[i] = oscOut * gain;
	}
}
//---------------------------------------------------------------
/*
int16_t calcSampleOsc(OscInfo* osc)
{
	const uint32_t oscPhase = osc->phase;
	int16_t oscOut ;

	uint32_t  itg	= oscPhase>>17;

#if INTERPOLATE_OSC
	//todo use ldm instead of ldr to laod multiple values from memory
	oscOut = crashSample[itg++];
	const float frac = (oscPhase&20000)*0.00000762939453125f;//=> * 1/0x20000
	oscOut += frac*(crashSample[itg] - oscOut);
#else
	oscOut = crashSample[itg];
#endif
	oscOut = (oscOut - 127)*256;

	osc->phase = oscPhase + osc->phaseInc;
	osc->output = oscOut;
	return oscOut;

};
*/
 //-----------------------------------------------------------
void osc_calcSineFreq(OscInfo* osc)
{
	osc->phaseInc = freq2PhaseIncr(osc->freq* osc->pitchMod*osc->modNodeValue);
}
//-----------------------------------------------------------
void osc_calcNoiseFreq(OscInfo* osc)
{
	osc_calcSineFreq(osc);
}
//-----------------------------------------------------------
void osc_calcWavetableFreq(OscInfo* osc)
{
	const float currentFreq = osc->freq*osc->pitchMod*osc->modNodeValue;
	osc->phaseInc = freq2PhaseIncr1024(currentFreq);

	const uint8_t overtoneIndex = freqToTableIndex(currentFreq);
	osc->tableOffset = overtoneIndex>10?10:overtoneIndex;
}
//-----------------------------------------------------------
void osc_calcSampleFreq(OscInfo* osc)
{
	const float currentFreq = osc->freq*osc->pitchMod*osc->modNodeValue;
	osc->phaseInc = freq2PhaseIncr32767(currentFreq);
}
//-----------------------------------------------------------
void osc_calcUserSampleFreq(OscInfo* osc)
{
	const float currentFreq = osc->freq*osc->pitchMod*osc->modNodeValue;
	osc->phaseInc = freq2PhaseIncr1024(currentFreq);
	osc->tableOffset = waveBank_level(currentFreq);
	osc->levelMix = osc_levelMix(currentFreq,osc->tableOffset);
}
//-----------------------------------------------------------
// The root note (coarse 0, note 60) plays the sample at its own rate; one
// semitone per note, fine tune and the pitch modulation as for the oscillators
void osc_calcSampleBankFreq(OscInfo* osc)
{
	const float rate = (float)sampleBank_rate((uint8_t)(osc->waveform - SAMPLEBANK_FIRST_WAVE));
	const float speed = osc->freq*osc->pitchMod*osc->modNodeValue*rate/(REAL_FS*MidiNoteFrequencies[SAMPLEBANK_ROOT_NOTE]);
	float inc = speed*(float)(1u << SAMPLEBANK_PHASE_BITS);
	if(!(inc > 0.f)) inc = 0.f;
	else if(inc > (float)(64u << SAMPLEBANK_PHASE_BITS)) inc = (float)(64u << SAMPLEBANK_PHASE_BITS);
	osc->phaseInc = (uint32_t)(inc + 0.5f);
}
//-----------------------------------------------------------
 void osc_setFreq(OscInfo* osc)
 {
		switch(osc->waveform)
		{
		case SINE:
			osc_calcSineFreq(osc);
			break;

		case SAW:
			osc_calcWavetableFreq(osc);
			break;

		case TRI:
			osc_calcWavetableFreq(osc);
			break;

		case REC:
			osc_calcWavetableFreq(osc);
			break;

		case NOISE:
			osc_calcNoiseFreq(osc);
			break;


		case PWM:
			osc_calcWavetableFreq(osc);
			break;

		//user wavetables and samples
		default:
			if(osc_isSample(osc)) osc_calcSampleBankFreq(osc);
			else osc_calcUserSampleFreq(osc);
			break;

		}
 }
 //-----------------------------------------------------------
static int8_t osc_globalPitchOffset = 0;
static int8_t osc_notePitchOffset = 0;
static float osc_globalPitchBend = 0.f;
static const float OSC_SEMITONE_UP = 1.0594630943592953f;

static float osc_calcMidiNoteFrequency(float note)
{
	float octaveScale = 1.f;

	while(note > 127)
	{
		note -= 12;
		octaveScale *= 2.f;
	}

	while(note < 0)
	{
		note += 12;
		octaveScale *= 0.5f;
	}

	const int16_t noteIndex = (int16_t)note;
	const float frac = note - (float)noteIndex;
	const float base = MidiNoteFrequencies[noteIndex];
	const float next = (noteIndex < 127) ? MidiNoteFrequencies[noteIndex + 1] : (base * OSC_SEMITONE_UP);

	return (base + ((next - base) * frac)) * octaveScale;
}

void osc_setBaseNote(OscInfo* osc, uint8_t baseNote)
 {

	 //get fine tune
	 const float cent = midiParser_calcDetune(osc->midiFreq&0xff);
	 //calc coarse tune
	 const float note =  (osc->midiFreq>>8) + (baseNote-SEQ_DEFAULT_NOTE) + osc_globalPitchOffset + osc_notePitchOffset + osc_globalPitchBend + osc->pitchBend;

	 osc->freq = osc_calcMidiNoteFrequency(note)*cent;
	 osc->baseNote = baseNote;
 }

void osc_recalcFreq(OscInfo* osc)
 {
	 //get fine tune
	 const float cent = midiParser_calcDetune(osc->midiFreq&0xff);
	 //calc coarse tune
	 const float note =  (osc->midiFreq>>8) + (osc->baseNote-SEQ_DEFAULT_NOTE) + osc_globalPitchOffset + osc_notePitchOffset + osc_globalPitchBend + osc->pitchBend;

	 osc->freq = osc_calcMidiNoteFrequency(note)*cent;
 }

void osc_setGlobalPitchOffset(uint8_t value)
 {
	 int16_t offset = (int16_t)value - 63;

	 if(offset < -63)
		 offset = -63;
	 else if(offset > 64)
		 offset = 64;

	 osc_globalPitchOffset = (int8_t)offset;
}

void osc_setNotePitchOffset(int8_t offset)
{
	if(offset < -63)
		offset = -63;
	else if(offset > 64)
		offset = 64;

	osc_notePitchOffset = offset;
}

void osc_setGlobalPitchBend(int16_t bend, uint8_t range)
{
	const float semitones = (bend / 8192.f) * range;
	osc_globalPitchBend = semitones;
}

void osc_setPitchBend(OscInfo* osc, int16_t bend, uint8_t range)
{
	osc->pitchBend = (bend / 8192.f) * range;
	osc_recalcFreq(osc);
}
