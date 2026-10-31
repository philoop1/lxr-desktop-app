/* SPDX-License-Identifier: GPL-3.0-only
 * Mutador 7319e19b four-point groove, expressed exactly on a 192 PPQ grid.
 */
#include "Soundengine/Sequencer/PerformanceGroove.h"

uint8_t perf_grooveActive(const PerfGroove *groove)
{
    return (uint8_t)(groove->offset[1] || groove->offset[2] || groove->offset[3]);
}

uint8_t perf_grooveDue(const PerfGroove *groove,uint32_t pattern,
                       int8_t shift,uint8_t lane,int8_t neighbor,uint8_t frame)
{
    const int32_t position=(int32_t)frame-(int32_t)neighbor*48-
        groove->offset[lane&3u]-(int32_t)shift*6;
    if(position<0 || position>46 || (position&1)) return 0;
    return (uint8_t)((pattern>>(23-position/2))&1u);
}

uint8_t perf_groovePulse(const PerfGroove *groove,uint8_t lane,
                         int8_t neighbor,uint8_t frame)
{
    const int32_t position=(int32_t)frame-(int32_t)neighbor*48-groove->offset[lane&3u];
    return (uint8_t)(position>=0 && position<6);
}

void perf_grooveConfigure(PerfGroove *groove, uint8_t amount,
                          uint8_t sh2, uint8_t sh3, uint8_t sh4)
{
    const uint8_t shape[3]={sh2,sh3,sh4};
    if(amount>127) amount=127;
    groove->offset[0]=0;
    for(uint8_t i=0;i<3;i++) {
        int16_t centered=(shape[i]>127?127:shape[i])-63;
        if(centered==1) centered=0;
        int32_t scaled=(int32_t)centered*amount*12;
        scaled=(scaled>=0 ? scaled+(63*127/2) : scaled-(63*127/2))/(63*127);
        if(scaled < -12) scaled=-12;
        if(scaled > 12) scaled=12;
        groove->offset[i+1]=(int16_t)(scaled*3);
    }
}

int32_t perf_grooveEvent(const PerfGroove *groove, int32_t straightTick,
                        uint8_t sourceMainStep)
{
    return straightTick+groove->offset[sourceMainStep&3u];
}

uint32_t perf_grooveRepeat(const PerfGroove *groove, uint16_t period96,
                          uint8_t *lane)
{
    int32_t ticks=(int32_t)period96*2;
    /* Source repeat periods are rounded to main-step advances in Mutador.
     * Eight source substeps equal 24 desktop 96 PPQ ticks. */
    if(period96>=24) {
        uint8_t next=(uint8_t)((*lane+(period96+12u)/24u)&3u);
        ticks+=groove->offset[next]-groove->offset[*lane&3u];
        *lane=next;
        if(ticks<3) ticks=3;
    }
    /* Mutador clamps to one of its fine units: three 192 PPQ frames. */
    return ticks>0?(uint32_t)ticks:3u;
}
