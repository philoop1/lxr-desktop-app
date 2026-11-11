/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LXR_TRIG_CONDITIONS_H
#define LXR_TRIG_CONDITIONS_H

#include <stdint.h>
#include <string.h>
#ifdef STM32F765xx
#include "stm32f7xx.h"
#endif

/* In each group, steps 0..2 occupy the low six bits of their own byte.
 * Step 3 uses the two high bits of each byte. Most playback reads need
 * only a single byte. CND3 stores these groups in track order. */
typedef struct {
    uint8_t group[16][3];
} TrigTrack;

/* Playback can interrupt front-panel edits and pattern copies on the MCU. */
static inline uint32_t trigTrackLock(void)
{
#ifdef STM32F765xx
    const uint32_t state = __get_PRIMASK();
    __disable_irq();
    return state;
#else
    return 0;
#endif
}

static inline void trigTrackUnlock(uint32_t state)
{
#ifdef STM32F765xx
    __set_PRIMASK(state);
#else
    (void)state;
#endif
}

static inline uint8_t trigTrackGet(const TrigTrack *track, uint8_t step)
{
    const uint8_t *group = track->group[step / 4u];
    const unsigned lane = step % 4u;
    if(lane < 3u) return group[lane] & 63u;

    const uint32_t state = trigTrackLock();
    const uint8_t value = (group[0] >> 6) | ((group[1] >> 6) << 2) | ((group[2] >> 6) << 4);
    trigTrackUnlock(state);
    return value;
}

static inline void trigTrackSet(TrigTrack *track, uint8_t step, uint8_t value)
{
    uint8_t *group = track->group[step / 4u];
    const unsigned lane = step % 4u;
    const uint32_t state = trigTrackLock();
    if(lane < 3u) {
        group[lane] = (group[lane] & 0xc0u) | (value & 63u);
    } else {
        for(unsigned i = 0; i < 3; i++) {
            group[i] = (group[i] & 63u) | ((value & 3u) << 6);
            value >>= 2;
        }
    }
    trigTrackUnlock(state);
}

static inline void trigTrackCopy(TrigTrack *dst, const TrigTrack *src)
{
    const uint32_t state = trigTrackLock();
    *dst = *src;
    trigTrackUnlock(state);
}

static inline void trigTrackClear(TrigTrack *track)
{
    const uint32_t state = trigTrackLock();
    memset(track, 0, sizeof(*track));
    trigTrackUnlock(state);
}
#endif
