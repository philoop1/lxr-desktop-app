/* SPDX-License-Identifier: GPL-3.0-only
 * InsertFx.c - Mutador 0.2.79 per-voice insert effects (own code).
 *
 * dst: shaper (soft x/(1+|x|), hard clip, or triangle fold) on g*x + bias,
 *      minus the shaper of the bias alone (no DC from the bias), then a
 *      one-pole lowpass for tone. 0.2.83: the level is matched at -12 dBFS:
 *      a -12 dBFS hit leaves as loud as it came in at every drive, so drive
 *      changes the colour and not the loudness; out trims +-12 dB.
 * rng: ring modulation with a parabolic sine (no table, no sinf).
 * cmp: peak envelope per sample, gain computed every 8 samples (powf) and
 *      ramped; threshold/ratio/attack/release/makeup.
 * pha: the Phaser.c chain, mono, one instance per voice.
 * fln: Flanger.c, up to 25 ms (0.2.82, 25 ms from 0.2.86).
 * ph2: 4, 8 or 12 allpass stages, rounded (parabolic) sine LFO, feedback
 *      positive or negative (0.2.82).
 * All work in float on the mono int16 voice block, in place.
 */
#include "Soundengine/DSPAudio/FX/InsertFx.h"
#include <math.h>
#include <string.h>

#define INSERT_FS 44100.f
#define COMP_SUBBLOCK 8u

InsertFxParams insertFx_params;
static InsertFxVoice voices[INSERT_FX_VOICES];
/* 0.2.107 the stored settings (clamped) and the per-voice modulation */
static uint8_t ins_values[INS_VALUE_COUNT];
float insertFx_mod[INSERT_FX_VOICES][INS_MOD_SLOTS];
/* the settings the running block uses: the shared ones, or a modulated copy */
static const InsertFxParams *ins_p = &insertFx_params;

static inline int16_t ins_sat16(float v)
{
	return (int16_t)(v > 32767.f ? 32767.f : v < -32768.f ? -32768.f : v);
}

void InsertFx_reset(uint8_t voice)
{
	if(voice >= INSERT_FX_VOICES) return;
	InsertFxVoice *v = &voices[voice];
	Phaser_reset(&v->phaser);
	Flanger_reset(&v->flanger);
	memset(v->phaser2.z, 0, sizeof(v->phaser2.z));
	v->phaser2.last = 0.f;
	v->distLp = 0.f;
	v->compEnv = 0.f;
	v->compGain = 1.f;
}

void InsertFx_init(void)
{
	InsertFxParams *p = &insertFx_params;
	/* measurement defaults: clearly audible, typical load */
	p->mix[INSERT_FX_DIST] = 1.f;
	p->mix[INSERT_FX_RING] = 0.5f;
	p->mix[INSERT_FX_COMP] = 1.f;
	p->mix[INSERT_FX_PHASER] = 0.5f;
	p->distDrive = 0.5f;
	p->distTone = 0.7f;
	p->ringFreq = 440.f;
	p->compThreshold = 0.25f;
	p->compRatio = 4.f;
	p->compAttack = 1.f - expf(-1.f / (0.002f * INSERT_FS));	// 2 ms
	p->compRelease = 1.f - expf(-1.f / (0.120f * INSERT_FS));	// 120 ms
	p->compMakeup = 2.f;
	for(uint8_t i = 0; i < INSERT_FX_VOICES; i++)
	{
		Phaser_init(&voices[i].phaser);
		Flanger_init(&voices[i].flanger);
		memset(&voices[i].phaser2, 0, sizeof(voices[i].phaser2));
		voices[i].ringPhase = 0u;
		voices[i].lastType = INSERT_FX_COUNT;
		InsertFx_reset(i);
	}
	uint8_t values[INS_VALUE_COUNT];
	InsertFx_defaultValues(values);
	for(uint8_t i = 0; i < INS_VALUE_COUNT; i++) InsertFx_setValue(i, values[i]);
}

/* the 0.2.79 measurement settings */
void InsertFx_defaultValues(uint8_t values[INS_VALUE_COUNT])
{
	static const uint8_t defaults[INS_VALUE_COUNT] = {
		127, 64, 89,				// dst: mix, drive, tone 0.7
		64, 71,						// rng: mix, 440 Hz
		127, 89, 3, 61, 69, 32,		// cmp: mix, -12 dB, 4:1, 2 ms, 120 ms, +6 dB
		64, 51, 89, 51, 64,			// pha: mix, rate, depth, centre, feedback
		127, 40, 90, 64, 90,		// fln: mix, 0.17 Hz, depth, 2.8 ms, feedback +0.37
		64, 40, 89, 51, 40, 2,		// ph2: mix, rate, depth, centre, feedback -0.33, 12 stages
		0, 63, 63					// dst: soft, no bias, 0 dB
	};
	memcpy(values, defaults, sizeof(defaults));
}

/* 0.2.107 applies one setting in stored units (value may be fractional when
 * modulated): p gets the shared settings, the phaser and flanger keep theirs
 * per voice, for all voices (voice >= INSERT_FX_VOICES) or just one */
static void ins_apply(InsertFxParams *p, uint8_t voice, uint8_t index, float value)
{
	static const float ratios[INS_CMP_RATIO_STEPS] = {1.f, 2.f, 3.f, 4.f, 6.f, 8.f};
	const uint8_t first = voice < INSERT_FX_VOICES ? voice : 0u;
	const uint8_t last = voice < INSERT_FX_VOICES ? (uint8_t)(voice + 1u) : INSERT_FX_VOICES;
	const float v = value / 127.f;
	switch(index)
	{
	case INS_DST_MIX: p->mix[INSERT_FX_DIST] = v; break;
	case INS_DST_DRIVE: p->distDrive = v; break;
	case INS_DST_TONE: p->distTone = v; break;
	case INS_RNG_MIX: p->mix[INSERT_FX_RING] = v; break;
	case INS_RNG_FREQ: p->ringFreq = 20.f * exp2f(v * 8.f); break;					// 20 Hz .. 5.1 kHz
	case INS_CMP_MIX: p->mix[INSERT_FX_COMP] = v; break;
	case INS_CMP_THRESH: p->compThreshold = powf(10.f, (-40.f + 40.f * v) / 20.f); break;	// -40 .. 0 dB
	case INS_CMP_RATIO: p->compRatio = ratios[(uint8_t)value]; break;
	case INS_CMP_ATTACK: {
		const float ms = 0.1f * powf(500.f, v);										// 0.1 .. 50 ms
		p->compAttack = 1.f - expf(-1.f / (ms * 0.001f * INSERT_FS)); break; }
	case INS_CMP_RELEASE: {
		const float ms = 10.f * powf(100.f, v);										// 10 .. 1000 ms
		p->compRelease = 1.f - expf(-1.f / (ms * 0.001f * INSERT_FS)); break; }
	case INS_CMP_GAIN: p->compMakeup = powf(10.f, 24.f * v / 20.f); break;			// 0 .. +24 dB
	case INS_PHA_MIX: p->mix[INSERT_FX_PHASER] = v; break;
	case INS_PHA_RATE: for(uint8_t i = first; i < last; i++) Phaser_setRate(&voices[i].phaser, v); break;
	case INS_PHA_DEPTH: for(uint8_t i = first; i < last; i++) Phaser_setDepth(&voices[i].phaser, v); break;
	case INS_PHA_FREQ: for(uint8_t i = first; i < last; i++) Phaser_setCentre(&voices[i].phaser, v); break;
	case INS_PHA_FEEDBACK: for(uint8_t i = first; i < last; i++) Phaser_setFeedback(&voices[i].phaser, v); break;
	case INS_FLN_MIX: p->mix[INSERT_FX_FLANGER] = v; break;
	case INS_FLN_RATE: for(uint8_t i = first; i < last; i++) Flanger_setRate(&voices[i].flanger, v); break;
	case INS_FLN_DEPTH: for(uint8_t i = first; i < last; i++) Flanger_setDepth(&voices[i].flanger, v); break;
	case INS_FLN_TIME: for(uint8_t i = first; i < last; i++) Flanger_setTime(&voices[i].flanger, v); break;
	case INS_FLN_FEEDBACK: {	/* shown -63..+64, 63 = none */
		const float fb = ((float)value - 63.f) / 64.f;
		for(uint8_t i = first; i < last; i++) Flanger_setFeedback(&voices[i].flanger, 0.5f + 0.5f * fb);
		break; }
	case INS_PH2_MIX: p->mix[INSERT_FX_PHASER2] = v; break;
	case INS_PH2_RATE: p->ph2Rate = 0.03f * exp2f(v * 8.f); break;						// 0.03 .. 7.7 Hz
	case INS_PH2_DEPTH: p->ph2Depth = v * 3.f; break;									// up to 3 octaves
	case INS_PH2_FREQ: p->ph2Centre = 100.f * exp2f(v * 5.5f); break;					// 100 Hz .. 4.5 kHz
	case INS_PH2_FEEDBACK: {
		float fb = ((float)value - 63.f) / 64.f;
		p->ph2Feedback = fb * PH2_FEEDBACK_MAX; break; }
	case INS_PH2_STAGES: p->ph2Stages = (uint8_t)(4u + 4u * (uint8_t)value); break;
	case INS_DST_TYPE: p->distType = (uint8_t)value; break;
	case INS_DST_BIAS: p->distBias = 0.5f * ((float)value - 63.f) / 64.f; break;		// shown -63..+64
	case INS_DST_OUT: p->distOut = powf(10.f, 12.f * ((float)value - 63.f) / 64.f / 20.f); break;
	default: break;
	}
}

uint8_t InsertFx_setValue(uint8_t index, uint8_t value)
{
	if(index >= INS_VALUE_COUNT) return value;
	if(index == INS_CMP_RATIO) { if(value >= INS_CMP_RATIO_STEPS) value = INS_CMP_RATIO_STEPS - 1; }
	else if(index == INS_PH2_STAGES) { if(value >= INS_PH2_STAGE_STEPS) value = INS_PH2_STAGE_STEPS - 1; }
	else if(index == INS_DST_TYPE) { if(value >= INS_DST_TYPE_STEPS) value = INS_DST_TYPE_STEPS - 1; }
	else if(value > 127) value = 127;
	ins_values[index] = value;
	ins_apply(&insertFx_params, INSERT_FX_VOICES, index, (float)value);
	return value;
}

/* 0.2.107 slot 0 = mix, 1..4 = I1..I4; switches (dst type, ph2 stages) and
 * the compressor release stay unmodulated */
static const uint8_t ins_slots[INSERT_FX_COUNT][INS_MOD_INSERT_SLOTS] = {
	[INSERT_FX_DIST]	= {INS_DST_MIX, INS_DST_DRIVE, INS_DST_TONE, INS_DST_BIAS, INS_DST_OUT},
	[INSERT_FX_RING]	= {INS_RNG_MIX, INS_RNG_FREQ, INS_SLOT_NONE, INS_SLOT_NONE, INS_SLOT_NONE},
	[INSERT_FX_COMP]	= {INS_CMP_MIX, INS_CMP_THRESH, INS_CMP_RATIO, INS_CMP_ATTACK, INS_CMP_GAIN},
	[INSERT_FX_PHASER]	= {INS_PHA_MIX, INS_PHA_RATE, INS_PHA_DEPTH, INS_PHA_FREQ, INS_PHA_FEEDBACK},
	[INSERT_FX_FLANGER]	= {INS_FLN_MIX, INS_FLN_RATE, INS_FLN_DEPTH, INS_FLN_TIME, INS_FLN_FEEDBACK},
	[INSERT_FX_PHASER2]	= {INS_PH2_MIX, INS_PH2_RATE, INS_PH2_DEPTH, INS_PH2_FREQ, INS_PH2_FEEDBACK},
};

uint8_t InsertFx_slotValue(uint8_t type, uint8_t slot)
{
	if(type >= INSERT_FX_COUNT || slot >= INS_MOD_INSERT_SLOTS) return INS_SLOT_NONE;
	return ins_slots[type][slot];
}

void InsertFx_clearMod(void)
{
	memset(insertFx_mod, 0, sizeof(insertFx_mod));
}

void InsertFx_addMod(uint8_t voice, uint8_t slot, float offset)
{
	if(voice >= INSERT_FX_VOICES || slot >= INS_MOD_SLOTS) return;
	insertFx_mod[voice][slot] += offset;
}

/* the largest stored value of a setting */
static float ins_valueMax(uint8_t index)
{
	if(index == INS_CMP_RATIO) return (float)(INS_CMP_RATIO_STEPS - 1);
	return 127.f;
}

/* 0.2.107 a modulated copy of the settings for one voice; the phaser and
 * flanger of that voice get the modulated (or, when it ends, the stored)
 * values. Returns the settings to run with. */
static const InsertFxParams *ins_modulated(uint8_t voice, uint8_t type, InsertFxParams *local)
{
	InsertFxVoice *v = &voices[voice];
	const float *m = &insertFx_mod[voice][INS_MOD_MIX];
	uint8_t active = 0;
	for(uint8_t k = 0; k < INS_MOD_INSERT_SLOTS; k++) active |= (m[k] != 0.f);
	if(!active && !v->modActive) return &insertFx_params;
	*local = insertFx_params;
	for(uint8_t k = 0; k < INS_MOD_INSERT_SLOTS; k++)
	{
		const uint8_t index = ins_slots[type][k];
		if(index == INS_SLOT_NONE) continue;
		const float max = ins_valueMax(index);
		float value = (float)ins_values[index] + m[k] * max;
		if(index == INS_CMP_RATIO) value = (float)(int32_t)(value + 0.5f);	// steps
		value = value < 0.f ? 0.f : value > max ? max : value;
		ins_apply(local, voice, index, value);
	}
	v->modActive = active;
	return local;
}

/* the voice's phaser and flanger back on the stored settings */
static void ins_restoreVoice(uint8_t voice)
{
	InsertFxParams scratch;
	static const uint8_t own[] = {INS_PHA_RATE, INS_PHA_DEPTH, INS_PHA_FREQ, INS_PHA_FEEDBACK,
		INS_FLN_RATE, INS_FLN_DEPTH, INS_FLN_TIME, INS_FLN_FEEDBACK};
	for(uint8_t i = 0; i < sizeof(own); i++) ins_apply(&scratch, voice, own[i], (float)ins_values[own[i]]);
	voices[voice].modActive = 0;
}

#define DIST_REFERENCE 0.25f		// -12 dBFS keeps its level

static inline float ins_shape(uint8_t type, float d)
{
	if(type == 1) return d > 1.f ? 1.f : d < -1.f ? -1.f : d;
	if(type == 2)
	{
		/* triangle fold: identity up to +-1, then folds back */
		float t = d * 0.25f + 0.25f;
		t -= floorf(t);
		return 1.f - 4.f * fabsf(t - 0.5f);
	}
	return d / (1.f + fabsf(d));
}

static void ins_dist(InsertFxVoice *v, int16_t *buf, uint16_t size)
{
	const InsertFxParams *p = ins_p;
	const uint8_t type = p->distType;
	const float g = 1.f + p->distDrive * 24.f;
	const float bias = p->distBias;
	const float offset = ins_shape(type, bias);
	/* level match at the reference; limited so a fold null cannot explode */
	/* the fold peaks at 1 once the drive reaches the first fold, so its reference is that peak */
	float ref = type == 2 ? (g * DIST_REFERENCE < 1.f ? g * DIST_REFERENCE : 1.f)
	                      : ins_shape(type, g * DIST_REFERENCE + bias) - offset;
	if(fabsf(ref) < 0.05f) ref = ref < 0.f ? -0.05f : 0.05f;
	float norm = DIST_REFERENCE / ref;
	if(norm > 4.f) norm = 4.f;
	if(norm < -4.f) norm = -4.f;
	norm *= p->distOut;
	const float k = 0.05f + 0.95f * p->distTone * p->distTone;
	const float mix = p->mix[INSERT_FX_DIST];
	float lp = v->distLp;
	for(uint16_t i = 0; i < size; i++)
	{
		const float x = (float)buf[i] * (1.f / 32768.f);
		const float y = (ins_shape(type, x * g + bias) - offset) * norm;
		lp += k * (y - lp);
		buf[i] = ins_sat16(((float)buf[i]) + (lp * 32768.f - (float)buf[i]) * mix);
	}
	v->distLp = lp;
}

static void ins_ring(InsertFxVoice *v, int16_t *buf, uint16_t size)
{
	const InsertFxParams *p = ins_p;
	const uint32_t inc = (uint32_t)(p->ringFreq * (4294967296.f / INSERT_FS));
	const float mix = p->mix[INSERT_FX_RING];
	uint32_t ph = v->ringPhase;
	for(uint16_t i = 0; i < size; i++)
	{
		const float t = (float)(int32_t)ph * (1.f / 2147483648.f);	// -1..1
		const float s = 4.f * t * (1.f - fabsf(t));					// parabolic sine
		const float x = (float)buf[i];
		buf[i] = ins_sat16(x + (x * s - x) * mix);
		ph += inc;
	}
	v->ringPhase = ph;
}

static void ins_comp(InsertFxVoice *v, int16_t *buf, uint16_t size)
{
	const InsertFxParams *p = ins_p;
	const float exponent = 1.f - 1.f / p->compRatio;
	const float mix = p->mix[INSERT_FX_COMP];
	float env = v->compEnv, gain = v->compGain;
	for(uint16_t i = 0; i < size; i += COMP_SUBBLOCK)
	{
		const uint16_t end = (uint16_t)(i + COMP_SUBBLOCK < size ? i + COMP_SUBBLOCK : size);
		for(uint16_t j = i; j < end; j++)
		{
			const float a = fabsf((float)buf[j]) * (1.f / 32768.f);
			env += (a > env ? p->compAttack : p->compRelease) * (a - env);
		}
		const float target = env > p->compThreshold ?
			powf(env / p->compThreshold, -exponent) * p->compMakeup : p->compMakeup;
		const float step = (target - gain) / (float)(end - i);
		for(uint16_t j = i; j < end; j++)
		{
			gain += step;
			const float x = (float)buf[j];
			buf[j] = ins_sat16(x + (x * gain - x) * mix);
		}
	}
	v->compEnv = env;
	v->compGain = gain;
}

static float ph2_coefficient(float lfo)
{
	const InsertFxParams *p = ins_p;
	float f = p->ph2Centre * exp2f(p->ph2Depth * lfo);
	if(f < 30.f) f = 30.f;
	if(f > 15000.f) f = 15000.f;
	const float t = tanf(3.14159265f * f / INSERT_FS);
	return (t - 1.f) / (t + 1.f);
}

static void ins_phaser2(Phaser2 *ph, int16_t *buf, uint16_t size)
{
	const InsertFxParams *p = ins_p;
	ph->phase += p->ph2Rate * (float)size / INSERT_FS;
	if(ph->phase >= 1.f) ph->phase -= 1.f;
	/* rounded sine from the phase: parabola per half, -1..1 */
	const float t = 2.f * ph->phase - 1.f;
	const float lfo = 4.f * t * (1.f - fabsf(t));
	const float target = ph2_coefficient(lfo);
	float a = ph->a;
	const float step = (target - a) / (float)size;
	ph->a = target;
	const uint8_t stages = p->ph2Stages > PH2_MAX_STAGES ? PH2_MAX_STAGES : p->ph2Stages;
	const float fb = p->ph2Feedback;
	const float mix = p->mix[INSERT_FX_PHASER2];
	float last = ph->last;
	for(uint16_t i = 0; i < size; i++)
	{
		a += step;
		const float dry = (float)buf[i];
		float s = dry * (1.f / 32768.f) + fb * last;
		for(uint8_t k = 0; k < stages; k++)
		{
			const float y = a * s + ph->z[k];
			ph->z[k] = s - a * y;
			s = y;
		}
		last = s;
		buf[i] = ins_sat16(dry + (s * 32768.f - dry) * mix);
	}
	ph->last = last;
}

void InsertFx_process(uint8_t voice, uint8_t type, int16_t *buf, uint16_t size)
{
	if(voice >= INSERT_FX_VOICES) return;
	InsertFxVoice *v = &voices[voice];
	if(type >= INSERT_FX_COUNT) return;
	if(v->lastType != type) { InsertFx_reset(voice); ins_restoreVoice(voice); v->lastType = type; }
	InsertFxParams local;
	ins_p = ins_modulated(voice, type, &local);	// 0.2.107
	switch(type)
	{
	case INSERT_FX_DIST: ins_dist(v, buf, size); break;
	case INSERT_FX_RING: ins_ring(v, buf, size); break;
	case INSERT_FX_COMP: ins_comp(v, buf, size); break;
	case INSERT_FX_PHASER:
		Phaser_processMono(&v->phaser, buf, size, ins_p->mix[INSERT_FX_PHASER]);
		break;
	case INSERT_FX_FLANGER:
		Flanger_processMono(&v->flanger, buf, size, ins_p->mix[INSERT_FX_FLANGER]);
		break;
	case INSERT_FX_PHASER2: ins_phaser2(&v->phaser2, buf, size); break;
	default: break;
	}
	ins_p = &insertFx_params;
}
