/* SPDX-License-Identifier: GPL-3.0-only
 * InsertFx.h - Mutador 0.2.79 per-voice insert effects (own code).
 *
 * A voice whose audio out is set to an effect name (dst, rng, cmp, pha) runs
 * through its own instance of that effect before pan and sends, then goes to
 * St1. The settings exist once per effect type and are shared by all voices
 * using it; the state (filters, LFO, envelope) is per voice.
 *
 * 0.2.79 was a measurement build with fixed settings. 0.2.81: the settings are
 * 16 values 0..127 (PAR_INS_DST_MIX..PAR_INS_PHA_FEEDBACK order), edited on the
 * FX page and stored in the kit (INS1 block).
 */
#ifndef INC_SOUNDENGINE_DSPAUDIO_FX_INSERTFX_H_
#define INC_SOUNDENGINE_DSPAUDIO_FX_INSERTFX_H_

#include <stdint.h>
#include "Soundengine/DSPAudio/FX/Phaser.h"
#include "Soundengine/DSPAudio/FX/Flanger.h"

#define INSERT_FX_VOICES 6

enum InsertFxTypeEnum
{
	INSERT_FX_DIST,
	INSERT_FX_RING,
	INSERT_FX_COMP,
	INSERT_FX_PHASER,
	INSERT_FX_FLANGER,	// 0.2.82
	INSERT_FX_PHASER2,	// 0.2.82
	INSERT_FX_COUNT
};

typedef struct InsertFxParamsStruct
{
	float mix[INSERT_FX_COUNT];		// 0..1 dry/wet per effect type
	float distDrive;				// 0..1
	float distTone;					// 0..1, one-pole lowpass after the shaper
	uint8_t distType;				// 0.2.83: 0 soft, 1 hard, 2 fold
	float distBias;					// 0.2.83: -0.5..0.5 added before the shaper
	float distOut;					// 0.2.83: linear output gain, -12..+12 dB
	float ringFreq;					// Hz
	float compThreshold;			// linear, 0..1 of full scale
	float compRatio;				// >= 1
	float compAttack;				// one-pole coefficient per sample
	float compRelease;				// one-pole coefficient per sample
	float compMakeup;				// linear gain
	/* 0.2.82 ph2 */
	float ph2Rate;					// Hz
	float ph2Depth;					// octaves either side
	float ph2Centre;				// Hz
	float ph2Feedback;				// -PH2_FEEDBACK_MAX..PH2_FEEDBACK_MAX
	uint8_t ph2Stages;				// 4, 8 or 12
} InsertFxParams;

#define PH2_MAX_STAGES 12
#define PH2_FEEDBACK_MAX 0.85f
typedef struct Phaser2Struct
{
	float z[PH2_MAX_STAGES];
	float last;
	float a;						// coefficient at the end of the last block
	float phase;					// LFO 0..1
} Phaser2;

typedef struct InsertFxVoiceStruct
{
	Phaser phaser;					// only channel 0 is used
	Flanger flanger;				// 0.2.82
	Phaser2 phaser2;				// 0.2.82
	float distLp;
	uint32_t ringPhase;
	float compEnv;
	float compGain;
	uint8_t lastType;				// state is cleared when the type changes
	uint8_t modActive;				// 0.2.107 this voice ran with modulated settings
} InsertFxVoice;

extern InsertFxParams insertFx_params;

void InsertFx_init(void);
void InsertFx_reset(uint8_t voice);
/* type is an InsertFxTypeEnum; buf is the mono voice block */
void InsertFx_process(uint8_t voice, uint8_t type, int16_t *buf, uint16_t size);

/* 0.2.81 settings as stored values, in PAR_INS_* order */
enum InsertFxValueEnum
{
	INS_DST_MIX, INS_DST_DRIVE, INS_DST_TONE,
	INS_RNG_MIX, INS_RNG_FREQ,
	INS_CMP_MIX, INS_CMP_THRESH, INS_CMP_RATIO, INS_CMP_ATTACK, INS_CMP_RELEASE, INS_CMP_GAIN,
	INS_PHA_MIX, INS_PHA_RATE, INS_PHA_DEPTH, INS_PHA_FREQ, INS_PHA_FEEDBACK,
	INS1_VALUE_COUNT,				// the INS1 kit block holds the values above
	/* 0.2.82, kit block INS2 */
	INS_FLN_MIX = INS1_VALUE_COUNT, INS_FLN_RATE, INS_FLN_DEPTH, INS_FLN_TIME, INS_FLN_FEEDBACK,
	INS_PH2_MIX, INS_PH2_RATE, INS_PH2_DEPTH, INS_PH2_FREQ, INS_PH2_FEEDBACK, INS_PH2_STAGES,
	INS12_VALUE_COUNT,				// INS1 + INS2 blocks hold the values above
	/* 0.2.83, kit block INS3 */
	INS_DST_TYPE = INS12_VALUE_COUNT, INS_DST_BIAS, INS_DST_OUT,
	INS_VALUE_COUNT
};
#define INS_CMP_RATIO_STEPS 6	// 1:1 2:1 3:1 4:1 6:1 8:1, names from MENU_RATIO
#define INS_PH2_STAGE_STEPS 3	// 4, 8, 12 stages
#define INS2_VALUE_COUNT (INS12_VALUE_COUNT - INS1_VALUE_COUNT)
#define INS3_VALUE_COUNT (INS_VALUE_COUNT - INS12_VALUE_COUNT)
#define INS_DST_TYPE_STEPS 3	// sft hrd fld
void InsertFx_defaultValues(uint8_t values[INS_VALUE_COUNT]);
/* clamps and applies one stored value, returns the clamped value */
uint8_t InsertFx_setValue(uint8_t index, uint8_t value);

/* 0.2.107 per-voice modulation targets (LFO, velocity, random steps):
 * snd = the voice's send into the internal FX bus (i1..i6), mix = the dry/wet
 * of the voice's insert, I1..I4 = four settings of that insert, chosen by its
 * type (InsertFx_slotValue). Offsets are in 0..1 units of the stored value,
 * cleared at the start of each block and summed by the modulation nodes. */
enum InsertFxModSlotEnum
{
	INS_MOD_SND, INS_MOD_MIX, INS_MOD_I1, INS_MOD_I2, INS_MOD_I3, INS_MOD_I4,
	INS_MOD_SLOTS
};
#define INS_MOD_INSERT_SLOTS (INS_MOD_SLOTS - INS_MOD_MIX)	// mix, I1..I4
#define INS_SLOT_NONE 0xffu
extern float insertFx_mod[INSERT_FX_VOICES][INS_MOD_SLOTS];
void InsertFx_clearMod(void);
void InsertFx_addMod(uint8_t voice, uint8_t slot, float offset);
/* the stored value (InsertFxValueEnum) behind an insert slot (0 = mix,
 * 1..4 = I1..I4) of an insert type, INS_SLOT_NONE when the type has none */
uint8_t InsertFx_slotValue(uint8_t type, uint8_t slot);

#endif /* INC_SOUNDENGINE_DSPAUDIO_FX_INSERTFX_H_ */
