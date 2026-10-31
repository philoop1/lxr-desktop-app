/* SPDX-License-Identifier: GPL-3.0-only
 * Mutador's held-chord/latched step edit gesture, adapted to 64 desktop steps.
 */
#include "menu/StepSelection.h"
#include "Parameters.h"
#include "menu/menu.h"
#include "menu/CcNr2Text.h"
#include "Soundengine/Sequencer/sequencer.h"
static uint64_t selection;
static uint16_t held;
static uint8_t selectedPattern,selectedVoice;
void stepEdit_clear(void) { selection=0;held=0; }
uint64_t stepEdit_mask(uint8_t pattern,uint8_t voice)
{
    return pattern==selectedPattern&&voice==selectedVoice?selection:0;
}
uint8_t stepEdit_press(uint8_t pattern,uint8_t voice,uint8_t key,uint8_t step)
{
    if(pattern>=64||voice>=7||key>=16||step>=64)return 0;
    if(pattern!=selectedPattern||voice!=selectedVoice)stepEdit_clear();
    uint8_t first=(uint8_t)!held;
    if(first)selection=0;
    selectedPattern=pattern;selectedVoice=voice;
    selection|=(uint64_t)1u<<step;
    held|=(uint16_t)(1u<<key);
    return first;
}
void stepEdit_release(uint8_t key) { if(key<16)held&=(uint16_t)~(1u<<key); }
uint8_t stepEdit_apply(uint8_t pattern,uint8_t voice,uint16_t parameter,uint8_t value)
{
    uint64_t mask=stepEdit_mask(pattern,voice);
    if(!mask)return 0;
    switch(parameter) {
    case PAR_STEP_NOTE:case PAR_STEP_VOLUME:case PAR_STEP_PROB:
    case PAR_STEP_FLAM:case PAR_STEP_SHIFT:case PAR_P1_DEST:case PAR_P2_DEST:
    case PAR_P1_VAL:case PAR_P2_VAL:break;
    default:return 0;
    }
    if(parameter==PAR_P1_DEST||parameter==PAR_P2_DEST) {
        if(value>=getNumModTargets())return 1;
        value=(uint8_t)modTargets[value].param;
        if(value&&value<128)value++;
    }
    for(uint8_t i=0;i<64;i++)if(mask&((uint64_t)1u<<i)) {
        Step *step=&seq_patternSet.seq_subStepPattern[pattern][voice][i];
        switch(parameter) {
        case PAR_STEP_NOTE:step->note=value;break;
        case PAR_STEP_VOLUME:step->volume=(uint8_t)((step->volume&128u)|(value&127u));break;
        case PAR_STEP_PROB:step->prob=value;break;
        case PAR_STEP_FLAM:seq_patternSet.seq_stepTiming[pattern][voice][i].flam=value;break;
        case PAR_STEP_SHIFT:seq_patternSet.seq_stepTiming[pattern][voice][i].shift=value;break;
        case PAR_P1_DEST:step->param1Nr=value;break;
        case PAR_P2_DEST:step->param2Nr=value;break;
        case PAR_P1_VAL:step->param1Val=value;break;
        case PAR_P2_VAL:step->param2Val=value;break;
        default:break;
        }
    }
    return 1;
}
