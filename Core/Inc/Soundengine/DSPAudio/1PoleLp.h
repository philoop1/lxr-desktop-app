/*
 * 1PoleLp.h
 *
 *  Created on: 08.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#ifndef ONE_POLELP_H_
#define ONE_POLELP_H_
//-------------------------------------------------------------
#include "stm32f7xx_hal.h"
#include <math.h>
//-------------------------------------------------------------
#define CALC_FILTER_FREQ(f) (1-expf(-2.f*M_PI*f/(float)REAL_FS))

/* 0.2.103 float state: calcOnePole already rounded through fmaf in float */
typedef struct OnePoleStruct
{
	float r;
	float b;
} OnePoleFilter;
//-------------------------------------------------------------
void initOnePole(OnePoleFilter* filter);
/* 0.2.103 inline: it runs up to three times per voice and sample */
static inline float calcOnePole(OnePoleFilter* filter, float input)
{
	filter->b = fmaf(filter->r, input - filter->b, filter->b);
	return filter->b;
}
float calcOnePoleAdaptiveVolume(OnePoleFilter* filter, double input);
void calcOnePoleBlock(OnePoleFilter* filter, int16_t* buf, const uint8_t size);
void calcOnePoleBlockFixedInput(OnePoleFilter* filter, float input,float* output, const uint8_t size);
void setOnePoleCoef(OnePoleFilter* filter,double val);
void setOnePoleValue(OnePoleFilter* filter,double val);
void setOnePoleFreq(OnePoleFilter* filter,double f);

#endif /* ONE_POLELP_H_ */
