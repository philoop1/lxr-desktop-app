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
void stepEdit_follow(uint8_t pattern) { if(pattern<64)selectedPattern=pattern; }
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
uint8_t stepEdit_transpose(uint8_t pattern,uint8_t voice,int8_t semitones)
{
    const uint64_t mask=stepEdit_mask(pattern,voice);
    uint8_t first=0;
    for(uint8_t i=0;i<64;i++)if(mask&((uint64_t)1u<<i)) {
        Step *step=&seq_patternSet.seq_subStepPattern[pattern][voice][i];
        int16_t note=(int16_t)(step->note+semitones);
        if(note<0)note=0; else if(note>127)note=127;
        step->note=(uint8_t)note;
        if(!first)first=(uint8_t)(note+1);
    }
    return first;
}
uint8_t stepEdit_apply(uint8_t pattern,uint8_t voice,uint16_t parameter,uint8_t value)
{
    uint64_t mask=stepEdit_mask(pattern,voice);
    if(!mask)return 0;
    switch(parameter) {
    case PAR_STEP_NOTE:case PAR_STEP_VOLUME:case PAR_STEP_PROB:case PAR_STEP_FLAM_PROB:case PAR_STEP_CONDITION:
    case PAR_STEP_FLAM:case PAR_STEP_SHIFT:case PAR_P1_DEST:case PAR_P2_DEST:
    case PAR_P1_VAL:case PAR_P2_VAL:break;
    default:return 0;
    }
    if(parameter==PAR_P1_DEST||parameter==PAR_P2_DEST) {
        if(value>=MOD_TARGET_SND)return 1;	// 0.2.107 no send/insert automation
        value=(uint8_t)modTargets[value].param;
        if(value&&value<128)value++;
    }
    for(uint8_t i=0;i<64;i++)if(mask&((uint64_t)1u<<i)) {
        Step *step=&seq_patternSet.seq_subStepPattern[pattern][voice][i];
        switch(parameter) {
        case PAR_STEP_NOTE:step->note=value;break;
        case PAR_STEP_VOLUME:step->volume=(uint8_t)((step->volume&128u)|(value&127u));break;
        case PAR_STEP_PROB:step->prob=value;break;
		case PAR_STEP_CONDITION:
			trigTrackSet(&seq_patternSet.trigCondition[pattern][voice], i,
			             value < TRIG_COND_COUNT ? value : TRIG_COND_ALWAYS);
			break;
        case PAR_STEP_FLAM_PROB:seq_patternSet.flamProbability[pattern][voice][i]=value;break;
        case PAR_STEP_FLAM:seq_patternSet.seq_stepTiming[pattern][voice][i].flam=value;break;
        case PAR_STEP_SHIFT:seq_patternSet.seq_stepTiming[pattern][voice][i].shift=value;break;
        case PAR_P1_DEST:plock_slot(step,0,1,value);break;
        case PAR_P2_DEST:plock_slot(step,1,1,value);break;
        case PAR_P1_VAL:plock_slot(step,0,0,value);break;
        case PAR_P2_VAL:plock_slot(step,1,0,value);break;
        default:break;
        }
    }
    return 1;
}
