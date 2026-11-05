/*
 * SeqStep.h
 *
 * Created: 26.06.2012 16:46:31
 *  Author: Julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */ 


#ifndef SEQSTEP_H_
#define SEQSTEP_H_
#include "main.h"

/** a copy of the step struct from the sequencer.h file from the cortex src
used to load step data from sequencer and write it to the pattern preset*/
typedef struct StepStruct
{
	//uint8_t  	active;		// bit 0: on/off
	uint8_t 	volume;		// 0-127 volume -> 0x7f => lower 7 bit, upper bit => active <- active c an probably be removed
	uint8_t  	prob;		//step probability 7 bit [0:100]
	uint8_t		note;		// 7 bit

	//parameter automation
	uint8_t 	param1Nr;
	uint8_t 	param1Val; //probably 7

	uint8_t 	param2Nr;
	uint8_t 	param2Val; //probably 7
}Step;

typedef struct StepTiming
{
	uint8_t flam:4; // 0 = off, 1..15 = flam preset of the project (0.2.61)
	uint8_t shift:4; // [-7:7]
}StepTiming;

/* 2+1..8+1 play the x2..x8 roll plus one hit at the start of the following
 * step, when that step has no note and the step is not the last of the track. */
#define FLAM_PLUS_ONE_FIRST 6
#define FLAM_PLUS_ONE_LAST 10
/* flam velocity: 0..100 stands for -100..+100 %, 50 = all hits equal.
 * 0.2.61: it is a parameter of the flam preset, no longer of the step. */
#define FLAM_VELO_FLAT 50

/* 0.2.61 flam presets. A step's flam value 1..15 picks one of the project's
 * presets; presets 1..10 start as the former fixed flams x2..x8 and 2+1..8+1. */
#define NUM_FLAM_PRESETS 16	// index 0 = off
#define FLAM_PRESET_BYTES 6
#define FLAM_NUM_GRIDS 6	// x2 x3 x4 x6 x8 x12 hits per step
#define FLAM_MAX_REPEATS 12
#define FLAM_PITCH_ZERO 12	// pitch 0..24 = -12..+12 semitones per hit
#define FLAM_ACCEL_FLAT 50	// accel 0..100: below 50 the hits slow down, above they speed up
typedef struct FlamPresetStruct
{
	uint8_t repeats;	// 1..12 hits inside the step (main hit included)
	uint8_t grid;		// 0..FLAM_NUM_GRIDS-1
	uint8_t velo;		// 0..100, FLAM_VELO_FLAT = all hits equal
	uint8_t pitch;		// 0..24, FLAM_PITCH_ZERO = same note
	uint8_t plusOne;	// 1 = one more hit on the following empty step
	uint8_t accel;		// 0..100, FLAM_ACCEL_FLAT = even spacing
}FlamPreset;


typedef enum StepPositionEnum
{
	STEP_PREV,
	STEP_CURRENT,
	STEP_NEXT
}StepPosition;

/*
typedef union
{
	uint32_t completeData;
	struct
	{
		uint8_t unused;
		uint8_t prevStep;
		uint8_t currentStep;
		uint8_t nextStep;
	}StepData;
}StepPattern;
*/





#endif /* SEQSTEP_H_ */
