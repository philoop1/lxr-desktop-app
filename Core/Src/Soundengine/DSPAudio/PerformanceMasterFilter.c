/* Mutador 7319e19b master-filter behavior, adapted to the desktop block API.
 * Source: mainboard/LxrStm32/src/DSPAudio/mixer.c; original LXR mixer by
 * Julian Schmidt / Sonic Potions, with Mutador performance modifications.
 */
#include "Soundengine/DSPAudio/PerformanceMasterFilter.h"
#include "Soundengine/config.h"
#include "Soundengine/cpuDiag.h"
#include "Soundengine/DSPAudio/ResonantFilter.h"
#include "Soundengine/MIDI/valueShaper.h"
static uint8_t mixer_masterFilterMode;	/**< FILTER_LP or FILTER_HP*/
static uint8_t mixer_masterFilterValue;
static uint8_t mixer_masterFilterTargetValue;
static uint16_t mixer_masterFilterSwitchFade;
static uint16_t mixer_masterFilterSwitchFadeMax;
static uint8_t mixer_masterFilterSwitchState;
static uint8_t mixer_masterFilterCoefficientsDirty;
static float mixer_masterFilterCoefficientF;
static float mixer_masterFilterCoefficientQ;
static float mixer_masterFilterWet;
static uint8_t mixer_masterFilterEnabled;
#define MASTER_FILTER_BYPASS_FADE_SAMPLES 128.f
#define MASTER_FILTER_SWITCH_IDLE       0
#define MASTER_FILTER_SWITCH_FADE_OUT   1
#define MASTER_FILTER_SWITCH_FADE_IN    2
#define MASTER_FILTER_SWITCH_MIN_SAMPLES  256
#define MASTER_FILTER_SWITCH_MAX_SAMPLES 2048
#define MASTER_FILTER_CLIP_LUT_SIZE      257

static ResonantFilter mixer_masterFilterL,mixer_masterFilterR;
static float mixer_masterFilterClipLut[MASTER_FILTER_CLIP_LUT_SIZE];
static void mixer_rebuildMasterFilterClipLut(float drive);

void masterFilter_init(void)
{
    mixer_masterFilterMode=FILTER_LP;
    mixer_masterFilterValue=mixer_masterFilterTargetValue=63;
    mixer_masterFilterSwitchFade=0;
    mixer_masterFilterSwitchFadeMax=MASTER_FILTER_SWITCH_MIN_SAMPLES;
    mixer_masterFilterSwitchState=MASTER_FILTER_SWITCH_IDLE;
    mixer_masterFilterCoefficientsDirty=1;
    mixer_masterFilterCoefficientF=mixer_masterFilterCoefficientQ=0.f;
    mixer_masterFilterWet=0.f;
    mixer_masterFilterEnabled=0;
    SVF_init(&mixer_masterFilterL);
    SVF_init(&mixer_masterFilterR);
    mixer_masterFilterL.drive=mixer_masterFilterR.drive=0.5f;
    mixer_rebuildMasterFilterClipLut(mixer_masterFilterL.drive);
}
void mixer_setMasterFilter(uint8_t value)
{
	mixer_masterFilterTargetValue = (value > 127) ? 127 : value;
}
//-----------------------------------------------------------------------
void mixer_setMasterFilterResonance(uint8_t value)
{
	value = (value > 105) ? 105 : value;
	const float resonance = value / 127.f;
	SVF_setReso(&mixer_masterFilterL, resonance);
	SVF_setReso(&mixer_masterFilterR, resonance);
	mixer_masterFilterCoefficientsDirty = 1;
}
//-----------------------------------------------------------------------
void mixer_setMasterFilterDrive(uint8_t value)
{
	SVF_setDrive(&mixer_masterFilterL, value/127.f);
	SVF_setDrive(&mixer_masterFilterR, value/127.f);
	mixer_rebuildMasterFilterClipLut(mixer_masterFilterL.drive);
}
//-----------------------------------------------------------------------
void mixer_setMasterFilterEnabled(uint8_t value)
{
	mixer_masterFilterEnabled = value ? 1 : 0;
}
//-----------------------------------------------------------------------
static inline float mixer_softClip(float in)
{
	const float a = in * in;
	return in * (((a + 105) * a + 945) / ((15 * a + 420) * a + 945));
}
//-----------------------------------------------------------------------
static void mixer_rebuildMasterFilterClipLut(float drive)
{
	uint16_t i;
	for(i=0;i<MASTER_FILTER_CLIP_LUT_SIZE;i++)
	{
		const uint16_t sample = (i < MASTER_FILTER_CLIP_LUT_SIZE-1) ? (i << 7) : 32767;
		mixer_masterFilterClipLut[i] = mixer_softClip((sample / 32767.f) * drive);
	}
}
//-----------------------------------------------------------------------
static inline float mixer_lookupMasterFilterDrive(int16_t input)
{
	const int32_t signedSample = input;
	const uint32_t magnitude = signedSample < 0 ? (uint32_t)-signedSample : (uint32_t)signedSample;
	float value;

	if(magnitude >= 32767)
	{
		value = mixer_masterFilterClipLut[MASTER_FILTER_CLIP_LUT_SIZE-1];
	}
	else
	{
		const uint16_t index = magnitude >> 7;
		const float fraction = (magnitude & 0x7f) * (1.f / 128.f);
		const float first = mixer_masterFilterClipLut[index];
		value = first + (mixer_masterFilterClipLut[index+1] - first) * fraction;
	}

	return signedSample < 0 ? -value : value;
}
//-----------------------------------------------------------------------
static inline float mixer_runMasterFilterSample(ResonantFilter* filter, float input,
		float coefficientF, float coefficientQ)
{
	filter->a += coefficientF * ((input - filter->a) +
			coefficientQ * (filter->a - filter->b));
	if(filter->a > 1.f) filter->a = 1.f;
	else if(filter->a < -1.f) filter->a = -1.f;

	filter->b += coefficientF * (filter->a - filter->b);
	if(filter->b > 1.f) filter->b = 1.f;
	else if(filter->b < -1.f) filter->b = -1.f;

	return filter->b;
}
//-----------------------------------------------------------------------
static inline void mixer_updateMasterFilterCoefficients(void)
{
	ResonantFilter* filterL = &mixer_masterFilterL;
	ResonantFilter* filterR = &mixer_masterFilterR;
	float cutoff;
	float freq;
	float q;

	if(!mixer_masterFilterCoefficientsDirty)
		return;

	if(mixer_masterFilterValue <= 63)
	{
		const float distance = (63.f - mixer_masterFilterValue) / 63.f;
		cutoff = 1.f - distance * distance * distance;
	}
	else
		cutoff = (mixer_masterFilterValue - 64) / 63.f;

	freq = valueShaperF2F(cutoff,FILTER_SHAPER);
	SVF_directSetFilterValue(filterL, freq);
	filterR->f = filterL->f;
	filterR->g = filterL->g;

	mixer_masterFilterCoefficientF = filterL->f * 2.21f;
	q = (1-filterL->q) * 1.4f +
		(1-filterL->q) / (1.0f - mixer_masterFilterCoefficientF);
	mixer_masterFilterCoefficientQ = q;
	mixer_masterFilterCoefficientsDirty = 0;
}
//-----------------------------------------------------------------------
/* 0.2.103 the steady state (filter on, fully wet, no switch, no glide) runs
 * every block while the master filter is on: it lives in ITCM, the rarely
 * used fade/transition loop stays in flash. */
IN_ITCM_RAM static __attribute__((noinline)) void masterFilter_steadyBlock(int16_t* output, uint32_t frames, uint8_t hp)
{
	uint32_t i;
	ResonantFilter* filterL = &mixer_masterFilterL;
	ResonantFilter* filterR = &mixer_masterFilterR;
	const float f = mixer_masterFilterCoefficientF;
	const float qUse = mixer_masterFilterCoefficientQ;

	if(hp)
	{
		for(i=0;i<frames;i++)
		{
			const float xL = mixer_lookupMasterFilterDrive(output[i * 2]);
			const float xR = mixer_lookupMasterFilterDrive(output[i * 2 + 1]);
			const float lowL = mixer_runMasterFilterSample(filterL,xL,f,qUse);
			const float lowR = mixer_runMasterFilterSample(filterR,xR,f,qUse);
			output[i * 2] = __SSAT((int32_t)((xL - lowL) * FILTER_GAIN),16);
			output[i * 2 + 1] = __SSAT((int32_t)((xR - lowR) * FILTER_GAIN),16);
		}
	}
	else
	{
		for(i=0;i<frames;i++)
		{
			const float xL = mixer_lookupMasterFilterDrive(output[i * 2]);
			const float xR = mixer_lookupMasterFilterDrive(output[i * 2 + 1]);
			const float lowL = mixer_runMasterFilterSample(filterL,xL,f,qUse);
			const float lowR = mixer_runMasterFilterSample(filterR,xR,f,qUse);
			output[i * 2] = __SSAT((int32_t)(lowL * FILTER_GAIN),16);
			output[i * 2 + 1] = __SSAT((int32_t)(lowR * FILTER_GAIN),16);
		}
	}
}
void masterFilter_process(int16_t* output,uint32_t frames)
{
	uint32_t i;
	ResonantFilter* filterL = &mixer_masterFilterL;
	ResonantFilter* filterR = &mixer_masterFilterR;
	const float wetStep = 1.f / MASTER_FILTER_BYPASS_FADE_SAMPLES;

	if(!mixer_masterFilterEnabled && mixer_masterFilterWet <= 0.f)
		return;

	mixer_updateMasterFilterCoefficients();

	if(mixer_masterFilterEnabled && mixer_masterFilterWet >= 1.f &&
		mixer_masterFilterSwitchState == MASTER_FILTER_SWITCH_IDLE &&
		mixer_masterFilterValue == mixer_masterFilterTargetValue)
	{
		masterFilter_steadyBlock(output, frames, mixer_masterFilterMode == FILTER_HP);
		return;
	}
	CPU_DIAG_FLAG(CPU_DIAG_FILTER);	// 0.2.104 the fade/glide loop (flash)

	for(i=0;i<frames;i++)
	{
		const int16_t dryL = output[i * 2];
		const int16_t dryR = output[i * 2 + 1];
		if(mixer_masterFilterSwitchState == MASTER_FILTER_SWITCH_IDLE &&
			mixer_masterFilterValue != mixer_masterFilterTargetValue)
		{
			const int16_t diff = (int16_t)mixer_masterFilterTargetValue - (int16_t)mixer_masterFilterValue;
			const uint8_t nextValue = (diff > 0) ?
				mixer_masterFilterValue + 1 : mixer_masterFilterValue - 1;
			const uint8_t nextMode = (nextValue <= 63) ? FILTER_LP : FILTER_HP;

			if(nextMode != mixer_masterFilterMode)
			{
				const float resonance = 1.f - filterL->q;
				uint16_t fadeSamples = (uint16_t)(MASTER_FILTER_SWITCH_MIN_SAMPLES +
					(resonance * (MASTER_FILTER_SWITCH_MAX_SAMPLES - MASTER_FILTER_SWITCH_MIN_SAMPLES)));
				if(fadeSamples < MASTER_FILTER_SWITCH_MIN_SAMPLES)
					fadeSamples = MASTER_FILTER_SWITCH_MIN_SAMPLES;
				else if(fadeSamples > MASTER_FILTER_SWITCH_MAX_SAMPLES)
					fadeSamples = MASTER_FILTER_SWITCH_MAX_SAMPLES;
				mixer_masterFilterSwitchFadeMax = fadeSamples;
				mixer_masterFilterSwitchState = MASTER_FILTER_SWITCH_FADE_OUT;
				mixer_masterFilterSwitchFade = fadeSamples;
				mixer_masterFilterCoefficientsDirty = 1;
			}
			else
			{
				mixer_masterFilterValue = nextValue;
				mixer_masterFilterCoefficientsDirty = 1;
			}
		}

		if(mixer_masterFilterSwitchState == MASTER_FILTER_SWITCH_FADE_OUT &&
			mixer_masterFilterSwitchFade == 0)
		{
			mixer_masterFilterMode = (mixer_masterFilterMode == FILTER_LP) ? FILTER_HP : FILTER_LP;
			mixer_masterFilterValue = (mixer_masterFilterMode == FILTER_LP) ? 63 : 64;
			SVF_reset(filterL);
			SVF_reset(filterR);
			mixer_masterFilterSwitchState = MASTER_FILTER_SWITCH_FADE_IN;
			mixer_masterFilterCoefficientsDirty = 1;
		}

		if(mixer_masterFilterSwitchState == MASTER_FILTER_SWITCH_FADE_IN &&
			mixer_masterFilterSwitchFade >= mixer_masterFilterSwitchFadeMax)
		{
			mixer_masterFilterSwitchState = MASTER_FILTER_SWITCH_IDLE;
			mixer_masterFilterSwitchFade = 0;
			mixer_masterFilterCoefficientsDirty = 1;
		}

		if(mixer_masterFilterSwitchState == MASTER_FILTER_SWITCH_IDLE)
		{
			const uint8_t targetMode = (mixer_masterFilterTargetValue <= 63) ? FILTER_LP : FILTER_HP;
			if(targetMode != mixer_masterFilterMode)
			{
				const float resonance = 1.f - filterL->q;
				uint16_t fadeSamples = (uint16_t)(MASTER_FILTER_SWITCH_MIN_SAMPLES +
					(resonance * (MASTER_FILTER_SWITCH_MAX_SAMPLES - MASTER_FILTER_SWITCH_MIN_SAMPLES)));
				if(fadeSamples < MASTER_FILTER_SWITCH_MIN_SAMPLES)
					fadeSamples = MASTER_FILTER_SWITCH_MIN_SAMPLES;
				else if(fadeSamples > MASTER_FILTER_SWITCH_MAX_SAMPLES)
					fadeSamples = MASTER_FILTER_SWITCH_MAX_SAMPLES;
				mixer_masterFilterSwitchFadeMax = fadeSamples;
				mixer_masterFilterSwitchState = MASTER_FILTER_SWITCH_FADE_OUT;
				mixer_masterFilterSwitchFade = fadeSamples;
				mixer_masterFilterCoefficientsDirty = 1;
			}
		}

		mixer_updateMasterFilterCoefficients();
		const float f = mixer_masterFilterCoefficientF;
		const float qUse = mixer_masterFilterCoefficientQ;
		const float xL = mixer_lookupMasterFilterDrive(output[i * 2]);
		const float xR = mixer_lookupMasterFilterDrive(output[i * 2 + 1]);
		const float lowL = mixer_runMasterFilterSample(filterL,xL,f,qUse);
		const float lowR = mixer_runMasterFilterSample(filterR,xR,f,qUse);
		int16_t drivenL = 0;
		int16_t drivenR = 0;

		if(mixer_masterFilterSwitchState != MASTER_FILTER_SWITCH_IDLE)
		{
			drivenL = __SSAT((int32_t)(xL * FILTER_GAIN),16);
			drivenR = __SSAT((int32_t)(xR * FILTER_GAIN),16);
		}

		if(mixer_masterFilterMode == FILTER_HP)
		{
			output[i * 2] = __SSAT((int32_t)((xL - lowL) * FILTER_GAIN),16);
			output[i * 2 + 1] = __SSAT((int32_t)((xR - lowR) * FILTER_GAIN),16);
		}
		else
		{
			output[i * 2] = __SSAT((int32_t)(lowL * FILTER_GAIN),16);
			output[i * 2 + 1] = __SSAT((int32_t)(lowR * FILTER_GAIN),16);
		}

		if(mixer_masterFilterSwitchState == MASTER_FILTER_SWITCH_FADE_OUT)
		{
			const float linearFade = mixer_masterFilterSwitchFade /
					(float)mixer_masterFilterSwitchFadeMax;
			const float fade = linearFade * linearFade * (3.f - 2.f * linearFade);
			output[i * 2] = (int16_t)(drivenL + ((float)output[i * 2] - drivenL) * fade);
			output[i * 2 + 1] = (int16_t)(drivenR + ((float)output[i * 2 + 1] - drivenR) * fade);
			mixer_masterFilterSwitchFade--;
		}
		else if(mixer_masterFilterSwitchState == MASTER_FILTER_SWITCH_FADE_IN)
		{
			const float linearFade = mixer_masterFilterSwitchFade /
					(float)mixer_masterFilterSwitchFadeMax;
			const float fade = linearFade * linearFade * (3.f - 2.f * linearFade);
			output[i * 2] = (int16_t)(drivenL + ((float)output[i * 2] - drivenL) * fade);
			output[i * 2 + 1] = (int16_t)(drivenR + ((float)output[i * 2 + 1] - drivenR) * fade);
			mixer_masterFilterSwitchFade++;
		}

		if(mixer_masterFilterEnabled)
		{
			if(mixer_masterFilterWet < 1.f)
			{
				mixer_masterFilterWet += wetStep;
				if(mixer_masterFilterWet > 1.f) mixer_masterFilterWet = 1.f;
			}
		}
		else
		{
			mixer_masterFilterWet -= wetStep;
			if(mixer_masterFilterWet < 0.f) mixer_masterFilterWet = 0.f;
		}

		if(mixer_masterFilterWet < 1.f)
		{
			output[i * 2] = (int16_t)(dryL + (output[i * 2] - dryL) * mixer_masterFilterWet);
			output[i * 2 + 1] = (int16_t)(dryR + (output[i * 2 + 1] - dryR) * mixer_masterFilterWet);
		}
	}
}
//-----------------------------------------------------------------------
