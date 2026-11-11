#include "Soundengine/Sequencer/PerformanceScale.h"
#include "menu/PerformanceControls.h"
/*
 * presetManager.c
 *
 * Created: 09.05.2012 16:06:19
 *  Author: Julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */ 
//#include "../config.h"
#include <frontPanelParser_ui.h>
#include "Preset/PresetManager.h"
#include "Soundengine/Sequencer/PerformanceSteps.h"
//#include "../Hardware/SD/ff.h"
#include "ff.h"
#include <stdio.h>
#include "menu/CcNr2Text.h"
#include "menu/menu.h"
//#include <util/delay.h>
#include "lcd.h"
//#include <avr/pgmspace.h>
#include <stdlib.h>
//#include <util/atomic.h>
#include "IO/uart.h"
#include "IO/DIO.h"

#include "Soundengine/MIDI/MidiParser.h"
#include "Soundengine/Sequencer/sequencer.h"
#include "Soundengine/Soundengine.h"
#include "Soundengine/DSPAudio/FX/InsertFx.h"
#include "Soundengine/DSPAudio/DrumVoice.h" // 0.2.90 glide
#include "Soundengine/DSPAudio/FilterEnv.h" // 0.2.93




//#include "../Hardware/timebase.h"

//FATFS SDFatFS;		/* File system object for the logical drive */
//FIL SDFile;		/* place to hold 1 file*/
static uint8_t morph_state = 0; //flag for non blocking morph
static uint8_t morph_index = 0;
static uint8_t morph_again = 0; // morph changed while a pass runs: one more pass
/* Morph from MIDI CC glides to its target like on the LXR1 Mutador: every
 * 26 ms it moves half of the remaining distance. */
#define MORPH_SLEW_TICKS 104u // 26 ms at 4 kHz
static uint8_t morph_slewTarget = 0;
static uint8_t morph_slewActive = 0;
static uint32_t morph_slewLast = 0;
char savefileNames[NUM_KIT_SLOTS][NUM_SAVEFILE_NAMES][8];

char currentFolder[13];

//char presetNameBuffer[8];
//char currentName[8];
//uint8_t activePresetNr = 0;

#define FILE_VERSION 2
#define SNARE_NOISE_KIT_BYTES 4u
static const uint8_t snareNoiseKitMagic[SNARE_NOISE_KIT_BYTES]={'S','N','E','2'};
static const uint8_t oldSnareNoiseKitMagic[SNARE_NOISE_KIT_BYTES]={'S','N','E','1'};
#define RPS_EXTRA_BYTES 46u
static uint8_t mainRpsExtras[NUM_KIT_SLOTS][42];
static void preset_defaultRpsExtras(uint8_t *data)
{
    memset(data,0,42);
    for(uint8_t v=0;v<6;v++){data[v]=v+1;data[6+v]=v+1;data[36+v]=2;}
}
static void preset_captureRpsExtras(uint8_t *data)
{
    for(uint8_t v=0;v<6;v++){
        data[v]=activeParameters[PAR_RPS_TRG1+v];
        data[6+v]=activeParameters[PAR_RPS_VOI1+v];
        data[12+v]=activeParameters[PAR_RPS_DST1+v];
        data[18+v]=activeParameters[PAR_RPS_AMT1+v];
        data[24+v]=activeParameters[PAR_RPS_OFS1+v];
        data[30+v]=activeParameters[PAR_RPS_SLW1+v];
        data[36+v]=activeParameters[PAR_RPS_POL1+v];
    }
}
static void preset_applyRpsExtras(const uint8_t *data)
{
    for(uint8_t v=0;v<6;v++){
        activeParameters[PAR_RPS_TRG1+v]=data[v]>7?0:data[v];
        activeParameters[PAR_RPS_VOI1+v]=(data[6+v]<1||data[6+v]>6)?v+1:data[6+v];
        activeParameters[PAR_RPS_DST1+v]=data[12+v]>=getNumModTargets()?0:data[12+v];
        activeParameters[PAR_RPS_AMT1+v]=data[18+v]>127?127:data[18+v];
        activeParameters[PAR_RPS_OFS1+v]=data[24+v]>127?127:data[24+v];
        activeParameters[PAR_RPS_SLW1+v]=data[30+v]>127?127:data[30+v];
        activeParameters[PAR_RPS_POL1+v]=data[36+v]>2?2:data[36+v];
        lfo_applyRandomStepSettings(v);
    }
}
static void preset_writeRpsExtras(const uint8_t *data)
{
    UINT written;
    f_write((FIL*)&SDFile,"RPS2",4,&written);
    f_write((FIL*)&SDFile,data,42,&written);
}
static void preset_readRpsExtras(uint8_t *data)
{
    UINT read=0;uint8_t block[RPS_EXTRA_BYTES]={0};
    preset_defaultRpsExtras(data);
    if(f_read((FIL*)&SDFile,block,sizeof(block),&read)!=FR_OK ||
       read!=sizeof(block) || memcmp(block,"RPS2",4))return;
    memcpy(data,block+4,42);
}
/* 0.2.81 insert FX settings (dst/rng/cmp/pha), stored per kit after RPS2.
 * 0.2.82 adds fln and ph2 as a second block INS2 after INS1, so 0.2.81 kits
 * keep loading. A missing block gives its defaults. Not morphed. */
#define INS1_EXTRA_BYTES (4u + INS1_VALUE_COUNT)
#define INS2_EXTRA_BYTES (4u + INS2_VALUE_COUNT)
#define INS3_EXTRA_BYTES (4u + INS3_VALUE_COUNT)	/* 0.2.83 dst type, bias, out */
#define INS_EXTRA_BYTES (INS1_EXTRA_BYTES + INS2_EXTRA_BYTES + INS3_EXTRA_BYTES)
/* 0.2.86 project FX bus, see preset_isProjectFx */
#define PROJECT_FX_COUNT (PAR_FX_DELAY_TYPE - PAR_FX_TYPE + 1)
uint8_t preset_fxFromKit = 1;
static uint8_t mainInsExtras[NUM_KIT_SLOTS][INS_VALUE_COUNT];
static void preset_defaultInsExtras(uint8_t *data)
{
    InsertFx_defaultValues(data);
}
static void preset_captureInsExtras(uint8_t *data)
{
    for(uint8_t i=0;i<INS_VALUE_COUNT;i++) data[i]=activeParameters[PAR_INS_DST_MIX+i];
}
static void preset_applyInsExtras(const uint8_t *data)
{
    for(uint8_t i=0;i<INS_VALUE_COUNT;i++)
        activeParameters[PAR_INS_DST_MIX+i]=InsertFx_setValue(i,data[i]);
}
static void preset_writeInsExtras(const uint8_t *data)
{
    UINT written;
    f_write((FIL*)&SDFile,"INS1",4,&written);
    f_write((FIL*)&SDFile,data,INS1_VALUE_COUNT,&written);
    f_write((FIL*)&SDFile,"INS2",4,&written);
    f_write((FIL*)&SDFile,data+INS1_VALUE_COUNT,INS2_VALUE_COUNT,&written);
    f_write((FIL*)&SDFile,"INS3",4,&written);
    f_write((FIL*)&SDFile,data+INS12_VALUE_COUNT,INS3_VALUE_COUNT,&written);
}
static void preset_readInsExtras(uint8_t *data)
{
    UINT read=0;uint8_t block[INS1_EXTRA_BYTES]={0};
    preset_defaultInsExtras(data);
    /* both blocks are always read, so old project padding stays aligned */
    if(f_read((FIL*)&SDFile,block,INS1_EXTRA_BYTES,&read)==FR_OK &&
       read==INS1_EXTRA_BYTES && !memcmp(block,"INS1",4))
        memcpy(data,block+4,INS1_VALUE_COUNT);
    read=0;memset(block,0,sizeof(block));
    if(f_read((FIL*)&SDFile,block,INS2_EXTRA_BYTES,&read)==FR_OK &&
       read==INS2_EXTRA_BYTES && !memcmp(block,"INS2",4))
        memcpy(data+INS1_VALUE_COUNT,block+4,INS2_VALUE_COUNT);
    read=0;memset(block,0,sizeof(block));
    if(f_read((FIL*)&SDFile,block,INS3_EXTRA_BYTES,&read)==FR_OK &&
       read==INS3_EXTRA_BYTES && !memcmp(block,"INS3",4))
        memcpy(data+INS12_VALUE_COUNT,block+4,INS3_VALUE_COUNT);
}
/* 0.2.90 glide of voices 1-3 (mode 1-3, time 1-3), block GLD1 after INS3.
 * A kit without it (older firmware, or project padding) gets glide off. */
/* 0.2.91 the amp EG -> filter amounts follow as block AEF1 (3 bytes); the
 * glide functions carry both, GLD_KIT_VALUES = glide values + aef values. */
#define AEF_PARAMS 3
#define AEF_CENTER FENV_CENTER
/* 0.2.93 FEN1 follows AEF1: env 4-6, fdc 1-6, acc 1-6 (FENV_EXTRA_VALUES) */
#define GLD_KIT_VALUES (GLIDE_PARAMS + AEF_PARAMS + FENV_EXTRA_VALUES)
#define GLD_EXTRA_BYTES (4u + GLIDE_PARAMS + 4u + AEF_PARAMS + 4u + FENV_EXTRA_VALUES)
#define FEN_AT (GLIDE_PARAMS + AEF_PARAMS)
static uint8_t mainGldExtras[NUM_KIT_SLOTS][GLD_KIT_VALUES];
static void preset_defaultGldExtras(uint8_t *data)
{
    for(uint8_t i=0;i<NUM_DRUM_VOICES;i++) { data[i]=GLIDE_OFF; data[NUM_DRUM_VOICES+i]=GLIDE_TIME_DEFAULT; data[GLIDE_PARAMS+i]=AEF_CENTER; }
    for(uint8_t i=0;i<FENV_EXTRA_VALUES;i++) {
        uint8_t kind,slot; fenv_extraIndex(i,&kind,&slot);
        data[FEN_AT+i] = kind==FENV_AMOUNT ? FENV_CENTER : kind==FENV_DECAY ? 0 : FENV_ACC_DEFAULT;
    }
}
static void preset_captureGldExtras(uint8_t *data)
{
    for(uint8_t i=0;i<GLIDE_PARAMS;i++) data[i]=activeParameters[PAR_GLIDE_MODE1+i];
    for(uint8_t i=0;i<AEF_PARAMS;i++) data[GLIDE_PARAMS+i]=activeParameters[PAR_AEF_AMT1+i];
    for(uint8_t i=0;i<FENV_EXTRA_VALUES;i++) data[FEN_AT+i]=activeParameters[PAR_AEF_AMT4+i];
}
static void preset_applyGldExtras(const uint8_t *data)
{
    for(uint8_t i=0;i<GLIDE_PARAMS;i++) {
        Drum_setGlideParameter(i,data[i]);
        activeParameters[PAR_GLIDE_MODE1+i]=Drum_getGlideParameter(i);
    }
    for(uint8_t i=0;i<AEF_PARAMS;i++) {
        fenv_setParam(FENV_AMOUNT,i,data[GLIDE_PARAMS+i]);
        activeParameters[PAR_AEF_AMT1+i]=fenv_getParam(FENV_AMOUNT,i);
    }
    for(uint8_t i=0;i<FENV_EXTRA_VALUES;i++) {
        uint8_t kind,slot; fenv_extraIndex(i,&kind,&slot);
        fenv_setParam(kind,slot,data[FEN_AT+i]);
        activeParameters[PAR_AEF_AMT4+i]=fenv_getParam(kind,slot);
    }
}
static void preset_writeGldExtras(const uint8_t *data)
{
    UINT written;
    f_write((FIL*)&SDFile,"GLD1",4,&written);
    f_write((FIL*)&SDFile,data,GLIDE_PARAMS,&written);
    f_write((FIL*)&SDFile,"AEF1",4,&written);
    f_write((FIL*)&SDFile,data+GLIDE_PARAMS,AEF_PARAMS,&written);
    f_write((FIL*)&SDFile,"FEN1",4,&written);
    f_write((FIL*)&SDFile,data+FEN_AT,FENV_EXTRA_VALUES,&written);
}
static void preset_readGldExtras(uint8_t *data)
{
    UINT read=0;uint8_t block[4u+GLIDE_PARAMS]={0};
    preset_defaultGldExtras(data);
    if(f_read((FIL*)&SDFile,block,4u+GLIDE_PARAMS,&read)==FR_OK &&
       read==4u+GLIDE_PARAMS && !memcmp(block,"GLD1",4))
        memcpy(data,block+4,GLIDE_PARAMS);
    /* AEF1 is read like GLD1: fixed size, so project padding stays aligned */
    read=0;memset(block,0,sizeof block);
    if(f_read((FIL*)&SDFile,block,4u+AEF_PARAMS,&read)==FR_OK &&
       read==4u+AEF_PARAMS && !memcmp(block,"AEF1",4))
        memcpy(data+GLIDE_PARAMS,block+4,AEF_PARAMS);
    /* FEN1 the same way: fixed size, missing = defaults */
    {
        uint8_t fen[4u+FENV_EXTRA_VALUES]={0};
        read=0;
        if(f_read((FIL*)&SDFile,fen,sizeof fen,&read)==FR_OK &&
           read==sizeof fen && !memcmp(fen,"FEN1",4))
            memcpy(data+FEN_AT,fen+4,FENV_EXTRA_VALUES);
    }
}
#define LFO_EXTRA_BYTES 16u
static uint8_t mainLfoExtras[NUM_KIT_SLOTS][12];
static void preset_defaultLfoExtras(uint8_t *data)
{
	for(uint8_t voice=0;voice<6;voice++) { data[voice]=0; data[6+voice]=2; }
}
static void preset_captureLfoExtras(uint8_t *data)
{
	for(uint8_t voice=0;voice<6;voice++) {
		data[voice]=activeParameters[PAR_LFO_SLEW1+voice];
		data[6+voice]=activeParameters[PAR_LFO_POL1+voice];
	}
}
static void preset_applyLfoExtras(const uint8_t *data)
{
	for(uint8_t voice=0;voice<6;voice++) {
		activeParameters[PAR_LFO_SLEW1+voice]=data[voice];
		activeParameters[PAR_LFO_POL1+voice]=data[6+voice];
		menu_parseGlobalParam(PAR_LFO_SLEW1+voice,data[voice]);
		menu_parseGlobalParam(PAR_LFO_POL1+voice,data[6+voice]);
	}
}
static void preset_writeLfoExtras(const uint8_t *data)
{
	UINT written;
	f_write((FIL*)&SDFile,"LFX1",4,&written);
	f_write((FIL*)&SDFile,data,12,&written);
}
static void preset_readLfoExtras(uint8_t *data)
{
	UINT bytes=0;
	uint8_t block[LFO_EXTRA_BYTES]={0};
	preset_defaultLfoExtras(data);
	if(f_read((FIL*)&SDFile,block,sizeof(block),&bytes)!=FR_OK ||
	   bytes!=sizeof(block) || memcmp(block,"LFX1",4))return;
	memcpy(data,block+4,12);
	for(uint8_t voice=0;voice<6;voice++) {
		if(data[voice]>127)data[voice]=127;
		if(data[6+voice]>2)data[6+voice]=2;
	}
}
static void preset_writePatternScale(uint8_t pattern)
{
    UINT written;
    uint8_t scale=seq_patternSet.scale[pattern];
    scale=perf_scaleDivision(perf_scaleIndex(scale));
    uint8_t data[6]={'S','C','L','2',scale,(uint8_t)(scale^0xa5)};
    f_write((FIL*)&SDFile,data,sizeof(data),&written);
}
static void preset_readPatternScale(uint8_t pattern)
{
    UINT bytes=0;
    uint8_t data[6]={0};
    seq_patternSet.scale[pattern]=16;
    if(f_read((FIL*)&SDFile,data,sizeof(data),&bytes)==FR_OK && bytes==sizeof(data) &&
       !memcmp(data,"SCL2",4) && data[4]==perf_scaleDivision(perf_scaleIndex(data[4])) && data[5]==(uint8_t)(data[4]^0xa5))
        seq_patternSet.scale[pattern]=data[4];
}
/* Added after SCL2 so the original packed Step/StepTiming layout stays intact. */
static void preset_writeFlamProbability(uint8_t pattern)
{
    UINT written;
    static const uint8_t magic[4]={'F','L','P','1'};
    f_write((FIL*)&SDFile,magic,sizeof(magic),&written);
    f_write((FIL*)&SDFile,seq_patternSet.flamProbability[pattern],
            NUM_TRACKS*NUM_STEPS,&written);
}
static void preset_readFlamProbability(uint8_t pattern)
{
    UINT bytes=0;
    uint8_t magic[4]={0};
    memset(seq_patternSet.flamProbability[pattern],100,NUM_TRACKS*NUM_STEPS);
    if(f_read((FIL*)&SDFile,magic,sizeof(magic),&bytes)!=FR_OK ||
       bytes!=sizeof(magic) || memcmp(magic,"FLP1",4)) return;
    if(f_read((FIL*)&SDFile,seq_patternSet.flamProbability[pattern],
              NUM_TRACKS*NUM_STEPS,&bytes)!=FR_OK || bytes!=NUM_TRACKS*NUM_STEPS)
        memset(seq_patternSet.flamProbability[pattern],100,NUM_TRACKS*NUM_STEPS);
    for(uint8_t track=0;track<NUM_TRACKS;track++)
        for(uint8_t step=0;step<NUM_STEPS;step++)
            if(seq_patternSet.flamProbability[pattern][track][step]>100)
                seq_patternSet.flamProbability[pattern][track][step]=100;
}
static void preset_writeTrigConditions(uint8_t pattern)
{
    UINT written;
    if(f_write(&SDFile, "CND3", 4, &written) != FR_OK || written != 4) return;
    if(f_write(&SDFile, &seq_patternSet.transform[pattern], 1, &written) != FR_OK || written != 1) return;
    for(uint8_t track = 0; track < NUM_TRACKS; track++) {
        TrigTrack row;
        trigTrackCopy(&row, &seq_patternSet.trigCondition[pattern][track]);
        if(f_write(&SDFile, &row, sizeof(row), &written) != FR_OK || written != sizeof(row)) return;
    }
}

static void preset_readTrigConditions(uint8_t pattern)
{
    UINT read;
    uint8_t magic[4];
    seq_patternSet.transform[pattern] = 0;
    for(uint8_t track = 0; track < NUM_TRACKS; track++)
        trigTrackClear(&seq_patternSet.trigCondition[pattern][track]);
    if(f_read(&SDFile, magic, sizeof(magic), &read) != FR_OK || read != sizeof(magic)) return;
    const uint8_t packed = memcmp(magic, "CND3", 4) == 0;
    if(packed || memcmp(magic, "CND2", 4) == 0) {
        uint8_t transform;
        if(f_read(&SDFile, &transform, 1, &read) != FR_OK || read != 1) return;
        seq_patternSet.transform[pattern] = transform <= 3 ? transform : 0;
    } else if(memcmp(magic, "CND1", 4) != 0) return;

    for(uint8_t track = 0; track < NUM_TRACKS; track++) {
        TrigTrack row = {0};
        uint8_t legacy[NUM_STEPS];
        const UINT bytes = packed ? sizeof(row) : sizeof(legacy);
        if(f_read(&SDFile, packed ? (void *)&row : (void *)legacy, bytes, &read) != FR_OK || read != bytes) {
            for(uint8_t prior = 0; prior < track; prior++)
                trigTrackClear(&seq_patternSet.trigCondition[pattern][prior]);
            return;
        }
        for(uint8_t step = 0; step < NUM_STEPS; step++) {
            const uint8_t value = packed ? trigTrackGet(&row, step) : legacy[step];
            if(!packed || value >= TRIG_COND_COUNT)
                trigTrackSet(&row, step, value < TRIG_COND_COUNT ? value : TRIG_COND_ALWAYS);
        }
        trigTrackCopy(&seq_patternSet.trigCondition[pattern][track], &row);
    }
}
/* 0.2.61: the flam velocity belongs to the flam preset. A 0.2.56..0.2.60 pattern
 * still has the per-step FLV1 block after CND2: a step with its own velocity
 * then points at a preset with the same flam and that velocity. New presets
 * take F15..F11 while they are unchanged and no step uses them. */
static uint8_t preset_flamSlotUsed(uint8_t slot)
{
    const StepTiming *timing=&seq_patternSet.seq_stepTiming[0][0][0];
    for(uint32_t i=0;i<(uint32_t)NUM_PATTERN*NUM_TRACKS*NUM_STEPS;i++)
        if(timing[i].flam==slot)return 1;
    return 0;
}
static uint8_t preset_flamSameShape(const FlamPreset *a,const FlamPreset *b)
{
    return (uint8_t)(a->repeats==b->repeats && a->grid==b->grid && a->pitch==b->pitch &&
                     a->plusOne==b->plusOne && a->accel==b->accel && a->steps==b->steps);
}
static uint8_t preset_flamForVelocity(uint8_t flam,uint8_t velo)
{
    const FlamPreset *want=&seq_flamPresets[flam];
    uint8_t best=flam;
    uint8_t bestDiff=(uint8_t)(want->velo>velo ? want->velo-velo : velo-want->velo);
    for(uint8_t i=1;i<NUM_FLAM_PRESETS;i++)
        if(preset_flamSameShape(&seq_flamPresets[i],want) && seq_flamPresets[i].velo==velo)return i;
    for(uint8_t i=NUM_FLAM_PRESETS-1;i>10;i--) {
        FlamPreset factory;
        seq_flamDefaultPreset(i,&factory);
        if(memcmp(&seq_flamPresets[i],&factory,FLAM_PRESET_BYTES) || preset_flamSlotUsed(i))continue;
        seq_flamPresets[i]=*want;
        seq_flamPresets[i].velo=velo;
        seq_flamPresetsChanged();
        preset_touchFlamTimer();
        return i;
    }
    for(uint8_t i=1;i<NUM_FLAM_PRESETS;i++) {
        if(!preset_flamSameShape(&seq_flamPresets[i],want))continue;
        const uint8_t v=seq_flamPresets[i].velo;
        const uint8_t diff=(uint8_t)(v>velo ? v-velo : velo-v);
        if(diff<bestDiff){bestDiff=diff;best=i;}
    }
    return best;
}
/* PLK1 follows ISD1. The legacy step body always contains ordinary P1/P2.
 * Trailer: magic, LE16 record count, {track,step,count,{destination,value}[]}
 * records, LE16 CRC-16/CCITT (initial 0xffff, over count and records).
 * Only steps with >2 locks have records. Readers stage the entire trailer. */
static uint16_t preset_lockCrc(uint16_t crc,const uint8_t *data,UINT size)
{
    while(size--) {
        crc^=(uint16_t)*data++<<8;
        for(uint8_t bit=0;bit<8;bit++)crc=(uint16_t)((crc<<1)^((crc&0x8000)?0x1021:0));
    }
    return crc;
}
static FSIZE_t preset_lockBytes(uint8_t pattern)
{
    FSIZE_t bytes=0;
    for(uint8_t t=0;t<NUM_TRACKS;t++)for(uint8_t s=0;s<NUM_STEPS;s++) {
        uint8_t n=plock_count(&seq_patternSet.seq_subStepPattern[pattern][t][s]);
        if(n>2)bytes+=3u+2u*n;
    }
    return bytes?bytes+8u:0;
}
static FRESULT preset_lockWrite(const void *data,UINT size)
{
    UINT written=0;
    FRESULT r=f_write(&SDFile,data,size,&written);
    return r==FR_OK && written!=size?FR_DISK_ERR:r;
}
static FRESULT preset_writeLocks(uint8_t pattern)
{
    uint16_t records=0,crc=0xffff;
    for(uint8_t t=0;t<NUM_TRACKS;t++)for(uint8_t s=0;s<NUM_STEPS;s++)
        if(plock_count(&seq_patternSet.seq_subStepPattern[pattern][t][s])>2)++records;
    if(!records)return FR_OK;
    uint8_t count[2]={(uint8_t)records,(uint8_t)(records>>8)};
    FRESULT r=preset_lockWrite("PLK1",4);
    if(r!=FR_OK)return r;
    if((r=preset_lockWrite(count,2))!=FR_OK)return r;
    crc=preset_lockCrc(crc,count,2);
    for(uint8_t t=0;t<NUM_TRACKS;t++)for(uint8_t s=0;s<NUM_STEPS;s++) {
        StepLock locks[PLOCK_MAX];
        uint8_t n=plock_read(&seq_patternSet.seq_subStepPattern[pattern][t][s],locks);
        if(n<=2)continue;
        uint8_t header[3]={t,s,n};
        if((r=preset_lockWrite(header,3))!=FR_OK)return r;
        if((r=preset_lockWrite(locks,2u*n))!=FR_OK)return r;
        crc=preset_lockCrc(crc,header,3); crc=preset_lockCrc(crc,(const uint8_t *)locks,2u*n);
    }
    uint8_t checksum[2]={(uint8_t)crc,(uint8_t)(crc>>8)};
    return preset_lockWrite(checksum,2);
}
static uint8_t preset_lockRead(void *data,UINT size)
{
    UINT read=0;
    return f_read(&SDFile,data,size,&read)==FR_OK && read==size;
}
static uint8_t preset_readLocks(uint8_t pattern)
{
    static Step staged[NUM_TRACKS][NUM_STEPS];
    uint8_t magic[4],count[2],checksum[2],ok=0;
    UINT bytes=0;
    FSIZE_t start=f_tell(&SDFile);
    if(f_read(&SDFile,magic,4,&bytes)!=FR_OK)return 0;
    if(!bytes)return 1; /* normal legacy file */
    if(bytes!=4)return 0;
    if(memcmp(magic,"PLK1",4)) { f_lseek(&SDFile,start); return 1; }
    if(!preset_lockRead(count,2))return 0;
    uint16_t records=(uint16_t)(count[0]|((uint16_t)count[1]<<8));
    uint16_t crc=preset_lockCrc(0xffff,count,2);
    if(records>NUM_TRACKS*NUM_STEPS)return 0;
    for(uint16_t i=0;i<records;i++) {
        uint8_t header[3]; StepLock locks[PLOCK_MAX];
        if(!preset_lockRead(header,3))goto cleanup;
        uint8_t t=header[0],s=header[1],n=header[2];
        if(t>=NUM_TRACKS || s>=NUM_STEPS || n<3 || n>PLOCK_MAX)goto cleanup;
        if(plock_count(&staged[t][s])>2)goto cleanup; /* duplicate record */
        if(!preset_lockRead(locks,2u*n))goto cleanup;
        crc=preset_lockCrc(crc,header,3); crc=preset_lockCrc(crc,(const uint8_t *)locks,2u*n);
        if(!plock_replace(&staged[t][s],locks,n))goto cleanup;
    }
    if(!preset_lockRead(checksum,2) || checksum[0]!=(uint8_t)crc || checksum[1]!=(uint8_t)(crc>>8))goto cleanup;
    for(uint8_t t=0;t<NUM_TRACKS;t++)for(uint8_t s=0;s<NUM_STEPS;s++)
        if(plock_count(&staged[t][s])>2)
            plock_copyLocks(&seq_patternSet.seq_subStepPattern[pattern][t][s],&staged[t][s]);
    ok=1;
cleanup:
    for(uint8_t t=0;t<NUM_TRACKS;t++)for(uint8_t s=0;s<NUM_STEPS;s++)plock_clear(&staged[t][s]);
    return ok;
}
/* 0.2.90 SLD1 follows PLK1: magic and the 64 slide bits of tracks 1-3
 * (LE64 each). Written only when a step slides, so other patterns keep the
 * old layout; a file without it loads with slide off. */
#define SLIDE_BLOCK_BYTES (4u + 8u*SLIDE_TRACKS)
static FSIZE_t preset_slideBytes(uint8_t pattern)
{
    for(uint8_t t=0;t<SLIDE_TRACKS;t++)if(seq_patternSet.slide[pattern][t])return SLIDE_BLOCK_BYTES;
    return 0;
}
static FRESULT preset_writeSlide(uint8_t pattern)
{
    if(!preset_slideBytes(pattern))return FR_OK;
    uint8_t block[SLIDE_BLOCK_BYTES];
    memcpy(block,"SLD1",4);
    for(uint8_t t=0;t<SLIDE_TRACKS;t++)for(uint8_t b=0;b<8;b++)
        block[4u+8u*t+b]=(uint8_t)(seq_patternSet.slide[pattern][t]>>(8u*b));
    return preset_lockWrite(block,SLIDE_BLOCK_BYTES);
}
static void preset_readSlide(uint8_t pattern)
{
    uint8_t block[SLIDE_BLOCK_BYTES];
    UINT bytes=0;
    const FSIZE_t start=f_tell(&SDFile);
    memset(seq_patternSet.slide[pattern],0,sizeof(seq_patternSet.slide[pattern]));
    if(f_read(&SDFile,block,4,&bytes)!=FR_OK || !bytes)return;
    if(bytes!=4 || memcmp(block,"SLD1",4)) { f_lseek(&SDFile,start); return; }
    if(!preset_lockRead(block+4,SLIDE_BLOCK_BYTES-4u)) { f_lseek(&SDFile,start); return; }
    for(uint8_t t=0;t<SLIDE_TRACKS;t++) {
        uint64_t mask=0;
        for(uint8_t b=0;b<8;b++)mask|=(uint64_t)block[4u+8u*t+b]<<(8u*b);
        seq_patternSet.slide[pattern][t]=mask;
    }
}
/* 0.2.93 ACC1 follows SLD1: magic and the 64 accent bits of every track
 * (LE64 each), written only when a step has an accent. */
#define ACCENT_BLOCK_BYTES (4u + 8u*NUM_TRACKS)
static FSIZE_t preset_accentBytes(uint8_t pattern)
{
    for(uint8_t t=0;t<NUM_TRACKS;t++)if(seq_patternSet.accent[pattern][t])return ACCENT_BLOCK_BYTES;
    return 0;
}
static FRESULT preset_writeAccent(uint8_t pattern)
{
    if(!preset_accentBytes(pattern))return FR_OK;
    uint8_t block[ACCENT_BLOCK_BYTES];
    memcpy(block,"ACC1",4);
    for(uint8_t t=0;t<NUM_TRACKS;t++)for(uint8_t b=0;b<8;b++)
        block[4u+8u*t+b]=(uint8_t)(seq_patternSet.accent[pattern][t]>>(8u*b));
    return preset_lockWrite(block,ACCENT_BLOCK_BYTES);
}
static void preset_readAccent(uint8_t pattern)
{
    uint8_t block[ACCENT_BLOCK_BYTES];
    UINT bytes=0;
    const FSIZE_t start=f_tell(&SDFile);
    memset(seq_patternSet.accent[pattern],0,sizeof(seq_patternSet.accent[pattern]));
    if(f_read(&SDFile,block,4,&bytes)!=FR_OK || !bytes)return;
    if(bytes!=4 || memcmp(block,"ACC1",4)) { f_lseek(&SDFile,start); return; }
    if(!preset_lockRead(block+4,ACCENT_BLOCK_BYTES-4u)) { f_lseek(&SDFile,start); return; }
    for(uint8_t t=0;t<NUM_TRACKS;t++) {
        uint64_t mask=0;
        for(uint8_t b=0;b<8;b++)mask|=(uint64_t)block[4u+8u*t+b]<<(8u*b);
        seq_patternSet.accent[pattern][t]=mask;
    }
}
static void preset_readStepTrack(uint8_t pattern,uint8_t track,UINT *read)
{
    Step legacy[NUM_STEPS];
    *read=0;
    if(!preset_lockRead(legacy,sizeof(legacy)))return;
    for(uint8_t s=0;s<NUM_STEPS;s++)
        plock_import(&seq_patternSet.seq_subStepPattern[pattern][track][s],&legacy[s]);
    *read=sizeof(legacy);
}
static void preset_writeStepTrack(uint8_t pattern,uint8_t track,UINT *written)
{
    Step legacy[NUM_STEPS];
    for(uint8_t s=0;s<NUM_STEPS;s++)
        plock_export(&seq_patternSet.seq_subStepPattern[pattern][track][s],&legacy[s]);
    f_write(&SDFile,legacy,sizeof(legacy),written);
}


/* 0.2.70: i1..i6 of the pattern after CND3. Older firmware stops before it. */
static void preset_writeIntSends(uint8_t pattern)
{
    UINT written;
    f_write((FIL*)&SDFile,"ISD1",4,&written);
    f_write((FIL*)&SDFile,seq_patternSet.intSend[pattern],PATTERN_INT_SENDS,&written);
}
static void preset_readIntSends(uint8_t pattern,const uint8_t *magic)
{
    UINT read=0;
    uint8_t value[PATTERN_INT_SENDS];
    if(memcmp(magic,"ISD1",4)) { f_lseek(&SDFile,f_tell(&SDFile)-4); return; }
    if(f_read((FIL*)&SDFile,value,sizeof(value),&read)!=FR_OK || read!=sizeof(value))return;
    for(uint8_t i=0;i<PATTERN_INT_SENDS;i++)
        seq_patternSet.intSend[pattern][i]=value[i]>127?0:value[i];
}
static void preset_readFlamVelocity(uint8_t pattern)
{
    UINT read=0;
    uint8_t magic[4]={0};
    memset(seq_patternSet.intSend[pattern],0,PATTERN_INT_SENDS);
    if(f_read((FIL*)&SDFile,magic,4,&read)!=FR_OK || read!=4)return;
    if(memcmp(magic,"FLV1",4)) {preset_readIntSends(pattern,magic);return;}
    for(uint8_t track=0;track<NUM_TRACKS;track++) {
        uint8_t velo[NUM_STEPS];
        if(f_read((FIL*)&SDFile,velo,NUM_STEPS,&read)!=FR_OK || read!=NUM_STEPS)return;
        for(uint8_t step=0;step<NUM_STEPS;step++) {
            StepTiming *timing=&seq_patternSet.seq_stepTiming[pattern][track][step];
            if(timing->flam && timing->flam<NUM_FLAM_PRESETS && velo[step]<=100 &&
               velo[step]!=seq_flamPresets[timing->flam].velo)
                timing->flam=preset_flamForVelocity(timing->flam,velo[step]);
        }
    }
    if(f_read((FIL*)&SDFile,magic,4,&read)==FR_OK && read==4)
        preset_readIntSends(pattern,magic);
}
/* 0.2.61 flam presets of the project: in prj.nfo after the name, and as
 * /tmp/flam.cfg after an edit until the project is saved. */
static uint8_t preset_flamDirty=0;
static uint32_t preset_flamTimer=0;
#define FLAM_FILE_BYTES (4+(NUM_FLAM_PRESETS-1)*FLAM_PRESET_BYTES+1)
#define FLAM_FILE_V1_WIDTH 6	// FLM1 of 0.2.61/0.2.62 has no steps
void preset_touchFlamTimer(void)
{
    preset_flamTimer=HAL_GetTick();
    preset_flamDirty=1;
}
/* A full card can give FatFs FR_OK with a short write. The legacy writers
 * append fixed-format blocks, so verify their final length before publishing. */
static FRESULT preset_finishFile(FRESULT result, FSIZE_t expected)
{
	if(result == FR_OK) result = (FRESULT)f_error(&SDFile);
	if(result == FR_OK && f_tell(&SDFile) != expected) result = FR_DISK_ERR;
	const FRESULT closed = f_close(&SDFile);
	return result == FR_OK ? closed : result;
}

static FRESULT preset_writeFlamPresets(void)
{
    uint8_t data[FLAM_FILE_BYTES]={'F','L','M','2'};
    UINT written;
    uint8_t checksum=0;
    for(uint8_t i=1;i<NUM_FLAM_PRESETS;i++) {
        const FlamPreset *p=&seq_flamPresets[i];
        uint8_t *d=&data[4+(i-1)*FLAM_PRESET_BYTES];
        d[0]=p->repeats;d[1]=p->grid;d[2]=p->velo;d[3]=p->pitch;d[4]=p->plusOne;d[5]=p->accel;
        d[6]=p->steps;
    }
    for(uint8_t i=4;i<FLAM_FILE_BYTES-1;i++)checksum=(uint8_t)(checksum+data[i]);
    data[FLAM_FILE_BYTES-1]=checksum;
    FRESULT res = f_write(&SDFile, data, sizeof(data), &written);
    if(res == FR_OK && written != sizeof(data)) res = FR_DISK_ERR;
    return res;
}
static uint8_t preset_readFlamPresets(void)
{
    uint8_t data[FLAM_FILE_BYTES];
    UINT read=0;
    uint8_t checksum=0;
    if(f_read((FIL*)&SDFile,data,FLAM_FILE_BYTES,&read)!=FR_OK || read<4)return 0;
    /* FLM2 (0.2.63) has the steps, FLM1 is read with steps 1 */
    uint8_t width;
    if(!memcmp(data,"FLM2",4) && read==FLAM_FILE_BYTES)width=FLAM_PRESET_BYTES;
    else if(!memcmp(data,"FLM1",4) && read>=4+(NUM_FLAM_PRESETS-1)*FLAM_FILE_V1_WIDTH+1)width=FLAM_FILE_V1_WIDTH;
    else return 0;
    const uint16_t bytes=(uint16_t)(4u+(NUM_FLAM_PRESETS-1u)*width+1u);
    for(uint16_t i=4;i<bytes-1u;i++)checksum=(uint8_t)(checksum+data[i]);
    if(checksum!=data[bytes-1u])return 0;
    for(uint8_t i=1;i<NUM_FLAM_PRESETS;i++) {
        FlamPreset *p=&seq_flamPresets[i];
        const uint8_t *d=&data[4+(i-1)*width];
        p->repeats=d[0];p->grid=d[1];p->velo=d[2];p->pitch=d[3];p->plusOne=d[4];p->accel=d[5];
        p->steps=width>FLAM_FILE_V1_WIDTH ? d[6] : 1;
    }
    seq_flamPresetsChanged();
    return 1;
}
static void preset_flamShowEdited(void)
{
    menu_flamEditSelect((uint8_t)(activeParameters[PAR_FLAM_SLOT]+1u));
}
static FRESULT preset_saveTmpFlam(void)
{
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
    HAL_TIM_Base_Start_IT(&htim2);	//calc sample interrupt - prio 1
#endif
    FRESULT res = f_open(&SDFile, "/tmp/flam.new", FA_CREATE_ALWAYS | FA_WRITE);
    if(res == FR_OK) {
        res = preset_finishFile(preset_writeFlamPresets(), FLAM_FILE_BYTES);
        if(res == FR_OK) {
            FILINFO info;
            res = f_stat("/tmp/flam.cfg", &info);
            if(res == FR_OK) {
                res = f_unlink("/tmp/flam.bak");
                if(res == FR_NO_FILE) res = FR_OK;
                if(res == FR_OK) res = f_rename("/tmp/flam.cfg", "/tmp/flam.bak");
            } else if(res == FR_NO_FILE) {
                res = FR_OK;
            }
            if(res == FR_OK) res = f_rename("/tmp/flam.new", "/tmp/flam.cfg");
        }
    }
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
    HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#endif
    return res;
}
static void preset_loadTmpFlam(void)
{
    uint8_t valid = 0;
    if(f_open(&SDFile, "/tmp/flam.cfg", FA_READ) == FR_OK) {
        valid = preset_readFlamPresets();
        f_close(&SDFile);
    }
    if(!valid && f_open(&SDFile, "/tmp/flam.bak", FA_READ) == FR_OK) {
        preset_readFlamPresets();
        f_close(&SDFile);
    }
    preset_flamShowEdited();
}
static void preset_defaultSnareLayer(uint8_t *parameters)
{
	parameters[PAR_SNARE_LAYER_WAVE]=0;
	parameters[PAR_SNARE_LAYER_AMOUNT]=0;
	parameters[PAR_SNARE_LAYER_FREQ]=25;
	parameters[PAR_SNARE_LAYER_MODE]=0;
}
static void preset_defaultSnareNoise(uint8_t *parameters)
{
	parameters[PAR_SNARE_NOISE_ATTACK]=0;
	parameters[PAR_SNARE_NOISE_DECAY]=127;
	parameters[PAR_SNARE_NOISE_SLOPE]=64;
	preset_defaultSnareLayer(parameters);
}
static void preset_validateSnareExtension(uint8_t *parameters,UINT bytesRead,
		const uint8_t *magic,UINT magicBytes)
{
	if(bytesRead==END_OF_SOUND_PARAMETERS && magicBytes==SNARE_NOISE_KIT_BYTES &&
		!memcmp(magic,snareNoiseKitMagic,SNARE_NOISE_KIT_BYTES))return;
	if(bytesRead>=PAR_SNARE_LAYER_MODE+1 &&
		!memcmp(&parameters[PAR_SNARE_LAYER_WAVE],oldSnareNoiseKitMagic,SNARE_NOISE_KIT_BYTES)) {
		preset_defaultSnareLayer(parameters);
		return;
	}
	preset_defaultSnareNoise(parameters);
}

/*
#define NUM_TRACKS 7
#define NUM_PATTERN 8*/
#define STEPS_PER_PATTERN NUM_STEPS //64


#define FEXT_SOUND 	0
#define FEXT_PAT 	1
#define FEXT_ALL 	2
#define FEXT_PROJ 	3
#define FEXT_SONG 	4



// fill buffer (length 9 total) with a filename. type is one of above
// eg p001.snd
static void preset_makeFileNameOld(char *buf, uint8_t num, uint8_t type);

//load uses wildcard to find a name of the pattern 00-*.ext
static FRESULT preset_makeFileNameLoad(char *buf, uint8_t num, uint8_t type);
//save uses the kit name to create a filename eg 00-NAME.ext
static void preset_makeFileNameSave(char *buf, uint8_t num, uint8_t type, char *name);

//static void preset_makeFileNameTemp(char *buf, uint8_t num, uint8_t type);


#define PRESET_SAVE_TIME 2000
/* 0.2.88: the MUTA.CFG values (master filter and compressor, FX sends, hm, hpd,
 * project FX ...) are autosaved like the kit and pattern, as tmp.cfg in /tmp,
 * and restored at boot. preset_cfgExact loads them exactly (no lsh hold). */
static const char *preset_cfgName = "MUTA.CFG";
static uint8_t preset_cfgExact = 0;
/* 0.2.89: the pattern that played when the project was saved (MUTA.CFG v10) */
static uint8_t preset_projectPattern = 0;
static void preset_loadPerformanceExtension(void);
static FRESULT preset_savePerformanceExtension(void);

uint32_t preset_kitTimer = 0;
uint32_t preset_patTimer = 0;

uint8_t preset_kitDirty = 0;
uint8_t preset_patDirty = 0;

void preset_initTmpFolder()
{
	char folderName[13];
	sprintf(folderName, "/tmp");

	FRESULT res;
	FILINFO fno;

	res = f_stat(folderName, &fno);
	if(res == FR_NO_FILE)
	{
		res = f_mkdir(folderName);
		if(res == FR_OK)
		{
			f_chdir(folderName);
		}
	}
	else
	{
		f_chdir(folderName);
	}
}

void preset_resetAllSaveTimers()
{
	preset_kitDirty = 0;
	preset_patDirty = 0;
}

FRESULT loadTmpFolderFiles()
{
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	HAL_TIM_Base_Start_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

	FRESULT res;
	// 0.2.61: edited flam presets first, so old patterns convert against them
	preset_loadTmpFlam();
	//check tmp folder for *.snd and *.pat files and load them to RAM
	for(uint8_t i=0;i<NUM_KIT_SLOTS;i++)
	{

		//FR_NO_FILE just means an incomplete project and is no reason to abort!
		res = preset_loadDrumsetSD(i, 0);
		if ((res != FR_OK) && (res != FR_NO_FILE))
		{
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
			f_close((FIL*)&SDFile);
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
			return res;
		}
		res = preset_loadPatternSD(i);
		if ((res != FR_OK) && (res != FR_NO_FILE))
		{
			f_close((FIL*)&SDFile);
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
			return res;
		}
		res = preset_loadSongSD(i);
		if ((res != FR_OK) && (res != FR_NO_FILE))
		{
			f_close((FIL*)&SDFile);
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
			return res;
		}
	}

	return FR_OK;
}

void preset_touchTimer(PresetTimer type)
{
	if(type==PRESET_KIT_TIMER)
	{
		preset_kitTimer = HAL_GetTick();
		preset_kitDirty = 1;
	}
	else if(type==PRESET_PAT_TIMER)
	{
		preset_patTimer = HAL_GetTick();
		preset_patDirty = 1;
	}
	else if(type==PRESET_STOP_PAT_TIMER)
	{
		//abort pattern save timer, since seq is running again...
		preset_patDirty = 0;
	}

};


FRESULT preset_saveTmpKit()
{
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	HAL_TIM_Base_Start_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
	FRESULT res;
	unsigned int bytesWritten;

	//open the file
	res = f_open((FIL*)&SDFile,"tmp.snd",FA_CREATE_ALWAYS | FA_WRITE);
	if(res != FR_OK)
	{
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
		return res;
	}

	//write current preset nr to file
	res = f_write((FIL*)&SDFile,(void*)&menu_selectedPresetNr[SAVE_TYPE_KIT],1,&bytesWritten);
	if(res != FR_OK)
	{
		f_close((FIL*)&SDFile);
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
		return res;
	}
	//write the preset data
	f_write((FIL*)&SDFile,activeParameters,END_OF_SOUND_PARAMETERS,&bytesWritten);
	f_write((FIL*)&SDFile,snareNoiseKitMagic,SNARE_NOISE_KIT_BYTES,&bytesWritten);
	uint8_t lfoExtras[12];
	preset_captureLfoExtras(lfoExtras);
	preset_writeLfoExtras(lfoExtras);
	uint8_t rpsExtras[42];preset_captureRpsExtras(rpsExtras);preset_writeRpsExtras(rpsExtras);
	uint8_t insExtras[INS_VALUE_COUNT];preset_captureInsExtras(insExtras);preset_writeInsExtras(insExtras);
	uint8_t gldExtras[GLD_KIT_VALUES];preset_captureGldExtras(gldExtras);preset_writeGldExtras(gldExtras);

	//close the file
	f_close((FIL*)&SDFile);
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
	return FR_OK;
}

FRESULT preset_LoadTmpKit()
{
	FRESULT res;
	unsigned int bytesRead;
	uint8_t kitNr = 0;

	//open the file
	res = f_open((FIL*)&SDFile,"tmp.snd",FA_OPEN_EXISTING | FA_READ);
	if(res != FR_OK) return res;

	//first the preset nr
	res=f_read((FIL*)&SDFile,(void*)&kitNr,1,&bytesRead);
	if(bytesRead != 1) {
		res=FR_DISK_ERR;
		goto closeFile;
	}

	menu_selectedPresetNr[SAVE_TYPE_KIT] = kitNr;


	//read the file content
		bytesRead=1;
		int16_t i;
		uint8_t *para;
		bytesRead = 0;

		para=activeParameters;

		res=f_read((FIL*)&SDFile, para,END_OF_SOUND_PARAMETERS, &bytesRead);
		if(res==FR_OK) {
			// set to 0 for any that were not read from the file
			if(END_OF_SOUND_PARAMETERS-bytesRead)
				memset(para+bytesRead,0,END_OF_SOUND_PARAMETERS-bytesRead);
			uint8_t magic[SNARE_NOISE_KIT_BYTES]={0};
			UINT magicBytes=0;
			f_read((FIL*)&SDFile,magic,sizeof(magic),&magicBytes);
			preset_validateSnareExtension(para,bytesRead,magic,magicBytes);
			uint8_t lfoExtras[12];
			preset_readLfoExtras(lfoExtras);
			preset_applyLfoExtras(lfoExtras);
			uint8_t rpsExtras[42];preset_readRpsExtras(rpsExtras);preset_applyRpsExtras(rpsExtras);
			uint8_t insExtras[INS_VALUE_COUNT];preset_readInsExtras(insExtras);preset_applyInsExtras(insExtras);
			uint8_t gldExtras[GLD_KIT_VALUES];preset_readGldExtras(gldExtras);preset_applyGldExtras(gldExtras);

			//special case mod targets. normalize.
			const uint8_t nmt=getNumModTargets();
			for(i=0;i<6;i++) {
				// since I've changed the meaning of these, I'll ensure that it's valid for kits saved prior to the
				// change
				if(para[PAR_VEL_DEST_1+i] >= nmt )
					para[PAR_VEL_DEST_1+i] = 0;
				if(para[PAR_TARGET_LFO1+i] >= nmt )
					para[PAR_TARGET_LFO1+i] = 0;
			}
		}


	closeFile:
		//close the file handle
		f_close((FIL*)&SDFile);

		// update the soundengine with the new parameters
		if(res==FR_OK) {
			preset_sendDrumsetParameters();
			return FR_OK;
		}

		return res;
}

FRESULT preset_LoadTmpPat()
{

	uint8_t success=1; // start off succeeding
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	HAL_TIM_Base_Start_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
	//filename in 8.3  format
		//uint8_t fileVersion = 1;
		UINT bytesRead;
		FRESULT res;



		res = f_open((FIL*)&SDFile,"tmp.pat",FA_OPEN_EXISTING | FA_READ);
		if(res != FR_OK)
		{
		#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
					HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
		#else

		#endif
				return res;
		}

		//read current preset nr
		res = f_read((FIL*)&SDFile,(void*)&menu_playedPattern,1,&bytesRead);
		if(bytesRead != 1)
		{
			success = 0;
			goto closeFile;
		}

		if(menu_playedPattern >= NUM_PATTERN)
		{
			menu_playedPattern = 0;
			success = 0;
			goto closeFile;
		}

		menu_shownPattern = menu_playedPattern;
		seq_activePattern = menu_playedPattern;
		seq_pendingPattern = menu_playedPattern;
		menu_selectedPresetNr[SAVE_TYPE_PATTERN] = menu_playedPattern;

		frontPanel_sendData(SEQ_CC,SEQ_SET_SHOWN_PATTERN,menu_playedPattern);

		seq_copyPatternToBackupBuffer(seq_activePattern);
		//frontParser_shownPattern = menu_playedPattern;
		uint8_t patternNr = menu_playedPattern;

	//---------------- read pattern data -----------------------------

		// note that the pattern length data is no longer stored in the same way.
		// This means that loading old patterns with non-standard length, the length will be
		// ignored and a standard length used. I think it's acceptable as long as users are aware of this.

		uint8_t next=0;

		// ---------- Load step data first

		// load step data



		for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
		{

			preset_readStepTrack(patternNr,trk,&bytesRead);

			if(bytesRead!=sizeof(Step)*(STEPS_PER_PATTERN))
			{
				success=0;
				break; // file error, or we ran out of file (eof)
			}

			//Pattern V3 and up => flam added
			//if(dataVersion > 2)
			{
				f_read((FIL*)&SDFile,(void*)&seq_patternSet.seq_stepTiming[patternNr][trk][0],sizeof(uint8_t)*STEPS_PER_PATTERN,&bytesRead);

				if(bytesRead!=sizeof(uint8_t)*(STEPS_PER_PATTERN))
				{
					success=0;
					break; // file error, or we ran out of file (eof)
				}
			}

		}



		// ---------- load the main step data next
		uint16_t mainStepData;


			for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
			{
				for(uint8_t bar=0;bar<NUM_BARS; bar++)
				{
					f_read((FIL*)&SDFile,(void*)&mainStepData,sizeof(uint16_t),&bytesRead);

					if( bytesRead==sizeof(uint16_t)) {
						seq_patternSet.seq_mainSteps[bar][patternNr][trk] = mainStepData;
					}
					 else {
							success=0;
							break;
						}
				}
			}



		// ------------ shuffle settings
		if(success) {
			//load the shuffle settings
			f_read((FIL*)&SDFile,(void*)&seq_patternSet.shuffle[patternNr],sizeof(uint8_t),&bytesRead);
			//and update on cortex
			if(bytesRead)
			{

				//activeParameters[PAR_SHUFFLE] = seq_patternSet.shuffle[patternNr];
				//frontPanel_sendData(SEQ_CC,SEQ_SHUFFLE,parameter_values[PAR_SHUFFLE]);

				//seq_setShuffle(activeParameters[PAR_SHUFFLE]/127.f);
			}
			else {
				success=0;
			}
		}

		// ----------- Pattern/track lengths
		// -- AS this might not exist in the saved data file, we still want success
		if(success) {

				for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
				{
					f_read((FIL*)&SDFile,(void*)&next,sizeof(uint8_t),&bytesRead);
					seq_patternSet.length[patternNr][trk] = next;
				}

			success=1; // just to document that we don't consider this a failure, we just didn't read the bytes for this
		}

		//if(dataVersion > 1)
		{
			f_read((FIL*)&SDFile,(void*)&seq_patternSet.kitNr[patternNr],sizeof(uint8_t),&bytesRead);
		preset_readPatternScale(patternNr);
		preset_readFlamProbability(patternNr);
		preset_readTrigConditions(patternNr);
		preset_readFlamVelocity(patternNr);
        /* 0.2.72: a damaged PLK1 or a full pool keeps the two base locks of every
         * step and loads the pattern anyway; only the extra locks are lost. */
        if(success && !preset_readLocks(patternNr))menu_warnLocksDropped();
        preset_readSlide(patternNr);
        preset_readAccent(patternNr); // 0.2.93
			if(bytesRead == 0) success = 0;

		}

		if( success == 0)
		{


			f_close((FIL*)&SDFile);
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
			return FR_INT_ERR;
		}

		success=1;
		//close the file handle



	closeFile:
		f_close((FIL*)&SDFile);

		#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
					HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
		#else

		#endif


		// return success or failure
		if(success) return FR_OK;
		else return FR_INT_ERR;


}

static FRESULT preset_saveTmpPatNr(uint8_t presetNr);
FRESULT preset_saveTmpPat()
{
	return preset_saveTmpPatNr(menu_playedPattern);
}
static FRESULT preset_saveTmpPatNr(uint8_t presetNr)
{

	//don't save invalid pattern
	if(presetNr >= NUM_PATTERN) return FR_INVALID_PARAMETER;
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	HAL_TIM_Base_Start_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

	FRESULT res;
	UINT bytesWritten;
	//lcd_clear();
	//lcd_home();
	//lcd_string(PSTR("Saving pattern"));

	//open the file
	res = f_open((FIL*)&SDFile,"tmp.pat",FA_CREATE_ALWAYS | FA_WRITE);
	if(res != FR_OK)
	{
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
		return res;
	}

	//write current preset nr to file
	res = f_write((FIL*)&SDFile,(void*)&presetNr,1,&bytesWritten);
	if(res != FR_OK)
	{
		f_close((FIL*)&SDFile);
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
		return res;
	}

	//write pattern data
	//preset_writePatternData(presetNr);
#if 0
#else

		uint8_t length;

		//---------------  write the step data (note, vol, prob, autom.) ---------------
		for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
		{
			preset_writeStepTrack(presetNr,trk,&bytesWritten);

			f_write((FIL*)&SDFile,(const void*)&seq_patternSet.seq_stepTiming[presetNr][trk][0],sizeof(uint8_t)*STEPS_PER_PATTERN,&bytesWritten);
		}

		//--------------- now the main step data ---------------
		for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
		{
			for(uint8_t bar=0;bar<NUM_BARS; bar++)
			{
				const uint16_t mainStepData = seq_patternSet.seq_mainSteps[bar][presetNr][trk];
				f_write((FIL*)&SDFile,(const void*)&mainStepData,sizeof(uint16_t),&bytesWritten);
			}
		}

		//----- shuffle setting ------


		//f_write((FIL*)&SDFile,(const void*)&activeParameters[PAR_SHUFFLE],sizeof(uint8_t),&bytesWritten);
		f_write((FIL*)&SDFile,(const void*)&seq_patternSet.shuffle[presetNr],sizeof(uint8_t),&bytesWritten);

		//----- pattern/track lengths ------
		// we reuse the same call from above (when saving main step data)
		// but we only use the length info retrieved. We want to store it at the end
		// to avoid breaking compatibility with save file


		for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
		{
				length = seq_patternSet.length[presetNr][trk] ;//seq_patternSet.seq_mainSteps[bar][pat][trk];
				f_write((FIL*)&SDFile,(const void*)&length,sizeof(uint8_t),&bytesWritten);
		}

		//write associated kit nr
		f_write((FIL*)&SDFile,&seq_patternSet.kitNr[presetNr],sizeof(uint8_t),&bytesWritten);
		preset_writePatternScale(presetNr);
		preset_writeFlamProbability(presetNr);
		preset_writeTrigConditions(presetNr);
		preset_writeIntSends(presetNr);
        res=preset_writeLocks(presetNr);
        if(res==FR_OK)res=preset_writeSlide(presetNr);
        if(res==FR_OK)res=preset_writeAccent(presetNr); // 0.2.93

#endif

    const FSIZE_t expected=1u + NUM_TRACKS*(sizeof(Step)*NUM_STEPS+NUM_STEPS)
        + NUM_BARS*NUM_TRACKS*2u + 1u + NUM_TRACKS + 1u + 6u + 4u + 5u
        + sizeof(seq_patternSet.flamProbability[presetNr])
        + sizeof(seq_patternSet.trigCondition[presetNr]) + 4u + PATTERN_INT_SENDS
        + preset_lockBytes(presetNr) + preset_slideBytes(presetNr) + preset_accentBytes(presetNr);
    res=preset_finishFile(res,expected);

	//reset the lcd
//	menu_repaintAll();

#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

	return res;
}

/*------------------------------------------------------------/
/ Delete a sub-directory even if it contains any file
/-------------------------------------------------------------/
/ The delete_node() function is for R0.12+.
/ It works regardless of FF_FS_RPATH.
*/


static FRESULT delete_node (
    TCHAR* path,    /* Path name buffer with the sub-directory to delete */
    UINT sz_buff,   /* Size of path name buffer (items) */
    FILINFO* fno,   /* Name read buffer */
    uint8_t tagged   /* Remove the transaction tag last, so cleanup can resume. */
)
{
    UINT i, j;
    FRESULT fr;
    DIR dir;


    fr = f_opendir(&dir, path); /* Open the sub-directory to make it empty */
    if (fr != FR_OK) return fr;

    for (i = 0; path[i]; i++) ; /* Get current path length */
    if(i + 2 >= sz_buff) { f_closedir(&dir); return FR_INVALID_NAME; }
    path[i++] = _T('/');

    for (;;) {
        fr = f_readdir(&dir, fno);  /* Get a directory item */
        if (fr != FR_OK || !fno->fname[0]) break;   /* End of directory? */
        if(!strcmp(fno->fname, ".") || !strcmp(fno->fname, "..")) continue;
        if(tagged && !strcmp(fno->fname, "LXRSV1.ID")) continue;
        j = 0;
        do {    /* Make a path name */
            if (i + j >= sz_buff) { /* Buffer over flow? */
                fr = FR_INVALID_NAME; break;    /* Fails with 100 when buffer overflow */
            }
            path[i + j] = fno->fname[j];
        } while (fno->fname[j++]);
        if(fr != FR_OK) break;
        if (fno->fattrib & AM_DIR) {    /* Item is a sub-directory */
            fr = delete_node(path, sz_buff, fno, 0);
        } else {                        /* Item is a file */
            fr = f_unlink(path);
        }
        if (fr != FR_OK) break;
    }

    path[--i] = 0;  /* Restore the path name */
    f_closedir(&dir);

    if(fr == FR_OK && tagged) {
        char tagPath[32];
        snprintf(tagPath, sizeof(tagPath), "%s/LXRSV1.ID", path);
        fr = f_unlink(tagPath);
    }
    if (fr == FR_OK) fr = f_unlink(path);  /* Delete the empty sub-directory */
    return fr;
}

FRESULT preset_clearTmpFolder()
{
	FILINFO fno;
	FRESULT fr;
	TCHAR buff[256];

	f_chdir("/");

	/* Directory to be deleted */
	sprintf(buff, "/tmp");

	fr = delete_node(buff, sizeof buff / sizeof buff[0], &fno, 0);

	preset_initTmpFolder();

	return fr;
}


/* everything MUTA.CFG stores, to see when it changes */
#define PRESET_CFG_SNAP (PERFORMANCE_EXTRA_BYTES+2+4+1+1+7+PROJECT_FX_COUNT)
static uint8_t preset_cfgSnap[PRESET_CFG_SNAP];
static uint8_t preset_cfgSnapValid = 0, preset_cfgDirty = 0;
static uint32_t preset_cfgTimer = 0;
static void preset_cfgSnapshot(uint8_t *s)
{
	memcpy(s,&activeParameters[PAR_FX_OUTPUT_MODE],PERFORMANCE_EXTRA_BYTES);
	s+=PERFORMANCE_EXTRA_BYTES;
	*s++=activeParameters[PAR_PERF_RANDOM_VELO];
	*s++=activeParameters[PAR_PERF_AVL];
	for(uint8_t i=0;i<4;i++)*s++=activeParameters[PAR_HUMANIZE1+i];
	*s++=activeParameters[PAR_HIGH_DAMP];
	*s++=activeParameters[PAR_LOAD_INT_SEND];
	memcpy(s,&activeParameters[PAR_MCOMP_ON],7);
	memcpy(s+7,&activeParameters[PAR_FX_TYPE],PROJECT_FX_COUNT);
}
static void preset_processCfgTimer(void)
{
	uint8_t now[PRESET_CFG_SNAP];
	preset_cfgSnapshot(now);
	if(!preset_cfgSnapValid) {
		memcpy(preset_cfgSnap,now,sizeof(now));
		preset_cfgSnapValid=1;
	} else if(memcmp(preset_cfgSnap,now,sizeof(now))) {
		memcpy(preset_cfgSnap,now,sizeof(now));
		preset_cfgDirty=1;
		preset_cfgTimer=HAL_GetTick();
	}
	if(preset_cfgDirty && HAL_GetTick()-preset_cfgTimer >= PRESET_SAVE_TIME) {
		preset_cfgName="tmp.cfg";
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
		/* 0.2.98 the audio runs in the timer while the SD card is written,
		 * like the kit and pattern autosave: no dropout (click) */
		const uint8_t timerWasOn = (htim2.Instance->CR1 & TIM_CR1_CEN) && (htim2.Instance->DIER & TIM_IT_UPDATE);
		if(!timerWasOn) HAL_TIM_Base_Start_IT(&htim2);
#endif
		const FRESULT res=preset_savePerformanceExtension();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
		if(!timerWasOn) HAL_TIM_Base_Stop_IT(&htim2);
#endif
		preset_cfgName="MUTA.CFG";
		if(res==FR_OK) preset_cfgDirty=0;
		else preset_cfgTimer=HAL_GetTick();
	}
}
/* boot: the autosaved MUTA.CFG values of the last session */
void preset_loadTmpCfg(void)
{
	FILINFO fno;
	if(f_stat("tmp.cfg",&fno)==FR_OK) {
		preset_cfgName="tmp.cfg";
		preset_cfgExact=1;
		preset_loadPerformanceExtension();
		preset_cfgExact=0;
		preset_cfgName="MUTA.CFG";
		menu_sendAllGlobals();
	}
	preset_cfgSnapValid=0;
	preset_cfgDirty=0;
}

void preset_processTimer()
{
	if(preset_patDirty == 1)
	{
		if(HAL_GetTick()-preset_patTimer >= PRESET_SAVE_TIME )
		{
			preset_patDirty = 0;
			preset_saveTmpPat();
		}
	}

	if(preset_kitDirty == 1)
	{
		if(HAL_GetTick()-preset_kitTimer >= PRESET_SAVE_TIME )
		{
			preset_kitDirty = 0;
			preset_saveTmpKit();
		}
	}

	preset_processCfgTimer();
	if(preset_flamDirty && HAL_GetTick()-preset_flamTimer >= PRESET_SAVE_TIME)
	{
		if(preset_saveTmpFlam() == FR_OK)
			preset_flamDirty = 0;
		else
			preset_flamTimer = HAL_GetTick();
	}
}


/* 0.2.59: a real save also rewrites the autosave copy, so an older tmp.pat or
 * tmp.snd cannot overwrite the saved pattern or kit when the device starts. */
void preset_refreshTmpPat(uint8_t presetNr)
{
	preset_patDirty = 0;
	preset_saveTmpPatNr(presetNr);
}
void preset_refreshTmpKit(void)
{
	preset_kitDirty = 0;
	preset_saveTmpKit();
}

/*------------------------------------------------------------/
/ Remove all contents of a directory
/ This function works regardless of FF_FS_RPATH.
/------------------------------------------------------------*/




uint8_t preset_isNameEmpty(char* name)
{
	uint8_t isEmpty = 1;

	if( (name[0] != 'E') && (name[0] != 0) ) isEmpty = 0;
	if( (name[1] != 'm') && (name[1] != 0) ) isEmpty = 0;
	if( (name[2] != 'p') && (name[2] != 0) ) isEmpty = 0;
	if( (name[3] != 't') && (name[3] != 0) ) isEmpty = 0;
	if( (name[4] != 'y') && (name[4] != 0) ) isEmpty = 0;
	if( (name[5] != 0) ) isEmpty = 0;
	if( (name[6] != 0) ) isEmpty = 0;
	if( (name[7] != 0) ) isEmpty = 0;


	return isEmpty;
}
//----------------------------------------------------
//load init kit
void preset_init(uint8_t presetNr)
{

	//const uint8_t presetNr = menu_selectedPresetNr[SAVE_TYPE_KIT];

	//first the preset name
	memcpy(savefileNames[presetNr][KIT_NAMES],initKit,8*sizeof(uint8_t));


	if(preset_isNameEmpty(savefileNames[presetNr][KIT_NAMES]))
	{
		sprintf((void*)savefileNames[presetNr][KIT_NAMES], "Empty");
	}


	//then the data
	//read the file content

	int16_t i;
	uint8_t *para;


	para=mainParameters[presetNr];
	if(presetNr == preset_activeKitNr) preset_activeKitNr = 0xff;

	for(int i=8;i<END_OF_SOUND_PARAMETERS; i++)
	{
		para[i-8] = i<INIT_KIT_SIZE ? initKit[i] : 0;
	}
	preset_defaultSnareNoise(para);
	preset_defaultLfoExtras(mainLfoExtras[presetNr]);
	preset_defaultRpsExtras(mainRpsExtras[presetNr]);
	preset_defaultInsExtras(mainInsExtras[presetNr]);
	preset_defaultGldExtras(mainGldExtras[presetNr]);

	//special case mod targets. normalize.
	const uint8_t nmt=getNumModTargets();
	for(i=0;i<6;i++) {
		// since I've changed the meaning of these, I'll ensure that it's valid for kits saved prior to the
		// change
		if(para[PAR_VEL_DEST_1+i] >= nmt )
			para[PAR_VEL_DEST_1+i] = 0;
		if(para[PAR_TARGET_LFO1+i] >= nmt )
			para[PAR_TARGET_LFO1+i] = 0;
	}

	//copy parameters to edit buffer; 0.2.86 the project FX stays
	uint8_t liveFx[PROJECT_FX_COUNT];
	memcpy(liveFx, &activeParameters[PAR_FX_TYPE], PROJECT_FX_COUNT);
	memcpy(activeParameters, mainParameters[presetNr], sizeof(uint8_t) * END_OF_SOUND_PARAMETERS);
	if(!preset_fxFromKit) memcpy(&activeParameters[PAR_FX_TYPE], liveFx, PROJECT_FX_COUNT);
	preset_applyLfoExtras(mainLfoExtras[presetNr]);
	preset_applyRpsExtras(mainRpsExtras[presetNr]);
	preset_applyInsExtras(mainInsExtras[presetNr]);
	preset_applyGldExtras(mainGldExtras[presetNr]);
	preset_sendDrumsetParameters();
	//frontPanel_sendData(PRESET,PRESET_LOAD,presetNr);

}

//----------------------------------------------------
/* 0.2.86: the FX bus (PAR_FX_TYPE..PAR_FX_DELAY_TYPE) belongs to the project
 * (MUTA.CFG v9). Kits still store it, but loading or morphing a kit keeps the
 * live FX. A project without stored FX (older MUTA.CFG, new project) takes
 * it once from the first kit that is activated. */
static uint8_t preset_isProjectFx(uint16_t i)
{
	return i >= PAR_FX_TYPE && i <= PAR_FX_DELAY_TYPE;
}
//----------------------------------------------------
/* The kit you hear at the current Morph position. Same rule as the live Morph
 * (preset_morph_tick): selectors, audio routing, the bank change and the Morph
 * target slot are not morphed and come from the playing kit. */
static uint8_t preset_morphedKitValue(uint16_t i)
{
	if((i >= PAR_VEL_DEST_1 && i <= PAR_VEL_DEST_6) ||
	   (i >= PAR_TARGET_LFO1 && i <= PAR_TARGET_LFO6) ||
	   (i >= PAR_VOICE_LFO1 && i <= PAR_VOICE_LFO6) ||
	   (i >= PAR_AUDIO_OUT1 && i <= PAR_AUDIO_OUT6) ||
	   i == PAR_MORPH_KIT_DEST || i == PAR_BANK_CHANGE)
		return activeParameters[i];
	return preset_getMorphValue(i, activeParameters[PAR_MORPH]);
}
//----------------------------------------------------
static void preset_writeDrumsetData(uint8_t presetNr, uint8_t isMorph)
{
	uint16_t i;
	unsigned int bytesWritten;

	if(isMorph)
	{
		for(i=0;i<END_OF_SOUND_PARAMETERS;i++)
		{
			const uint8_t value = preset_morphedKitValue(i);					
			f_write((FIL*)&SDFile,&value,1,&bytesWritten);
		}
	} else {
		for(i=0;i<END_OF_SOUND_PARAMETERS;i++)
		{
			f_write((FIL*)&SDFile,&mainParameters[presetNr][i],1,&bytesWritten);
		}
	}
	f_write((FIL*)&SDFile,snareNoiseKitMagic,SNARE_NOISE_KIT_BYTES,&bytesWritten);
	preset_writeLfoExtras(mainLfoExtras[presetNr]);
	preset_writeRpsExtras(mainRpsExtras[presetNr]);
	preset_writeInsExtras(mainInsExtras[presetNr]);
	preset_writeGldExtras(mainGldExtras[presetNr]);
}

//----------------------------------------------------
// Kit slot whose values are in activeParameters, 0xff when unknown. The
// pattern change in kcm=aut skips the load when the new pattern uses it.
uint8_t preset_activeKitNr = 0xff;
//----------------------------------------------------
void preset_loadDrumsetRam(uint8_t presetNr, uint8_t isMorph, uint8_t sendImmediate)
{
	soundengine_process();
	if(isMorph)
	{
		morphParameters = mainParameters[presetNr];
	}
	else
	{
		// Keep the live master sample rate when kit loading is disabled for it.
		const uint8_t masterSampleRate = activeParameters[PAR_VOICE_DECIMATION_ALL];
		uint8_t liveFx[PROJECT_FX_COUNT];
		memcpy(liveFx, &activeParameters[PAR_FX_TYPE], PROJECT_FX_COUNT);
		memcpy(activeParameters, mainParameters[presetNr], sizeof(uint8_t) * END_OF_SOUND_PARAMETERS);
		if(!preset_fxFromKit) memcpy(&activeParameters[PAR_FX_TYPE], liveFx, PROJECT_FX_COUNT);
		preset_fxFromKit = 0;
		preset_activeKitNr = presetNr;
		preset_applyLfoExtras(mainLfoExtras[presetNr]);
	preset_applyRpsExtras(mainRpsExtras[presetNr]);
		preset_applyInsExtras(mainInsExtras[presetNr]);
		preset_applyGldExtras(mainGldExtras[presetNr]);
		if(!activeParameters[PAR_LOAD_SAMPLE_RATE])
			activeParameters[PAR_VOICE_DECIMATION_ALL] = masterSampleRate;
		if(activeParameters[PAR_LOAD_MORPH])
		{
			uint8_t morphKit = activeParameters[PAR_MORPH_KIT_DEST];
			if(morphKit >= NUM_KIT_SLOTS) morphKit = 0;
			activeParameters[PAR_MORPH_KIT_DEST] = morphKit;
			morphParameters = mainParameters[morphKit];
			menu_selectedPresetNr[SAVE_TYPE_MORPH] = morphKit;
			menu_loadedPresetNr[CURRENT_MORPH] = morphKit;
		}


	}
	soundengine_process();

	if(sendImmediate)
	{
		preset_sendDrumsetParametersImmediate();
		if(!isMorph && activeParameters[PAR_LOAD_MORPH] && activeParameters[PAR_MORPH])
			preset_morph(activeParameters[PAR_MORPH]);
	}
	else
	{
		//activePresetNr = menu_currentPresetNr[menu_saveOptions.category];
		preset_sendDrumsetParameters();
	}
}
//----------------------------------------------------
void preset_saveDrumsetRam(uint8_t presetNr, uint8_t isMorph)
{
	if(isMorph)
	{
		for(uint16_t i=0;i<END_OF_SOUND_PARAMETERS;i++)
		{
			const uint8_t value = preset_morphedKitValue(i);
			//f_write((FIL*)&SDFile,&value,1,&bytesWritten);
			mainParameters[presetNr][i] = value;
		}
		// LFO and rps extras are not morphed: take the playing kit's, like the mod targets
		preset_captureLfoExtras(mainLfoExtras[presetNr]);
		preset_captureRpsExtras(mainRpsExtras[presetNr]);
		preset_captureInsExtras(mainInsExtras[presetNr]);
		preset_captureGldExtras(mainGldExtras[presetNr]);
		if(presetNr == preset_activeKitNr) preset_activeKitNr = 0xff;
	}
	else
	{
		//copy edit buffer to parameter array
		memcpy(mainParameters[presetNr], activeParameters, sizeof(uint8_t) * END_OF_SOUND_PARAMETERS);
		preset_activeKitNr = presetNr;
		preset_captureLfoExtras(mainLfoExtras[presetNr]);
	preset_captureRpsExtras(mainRpsExtras[presetNr]);
		preset_captureInsExtras(mainInsExtras[presetNr]);
		preset_captureGldExtras(mainGldExtras[presetNr]);
	}
}
//----------------------------------------------------
FRESULT preset_saveDrumsetSD(uint8_t presetNr, uint8_t isMorph)
{
#if USE_SD_CARD
	FRESULT res;
	unsigned int bytesWritten;
	//filename in 8.3  format
	char filename[13];
	preset_makeFileNameSave(filename,presetNr,FEXT_SOUND, savefileNames[presetNr][KIT_NAMES]);
	//sprintf(filename,"p%03d.snd",presetNr);



	//open the file
	res = f_open((FIL*)&SDFile,filename,FA_CREATE_ALWAYS | FA_WRITE);
	if(res != FR_OK) return res;
	
	//write preset name to file

	res = f_write((FIL*)&SDFile,(void*)savefileNames[presetNr][KIT_NAMES],8,&bytesWritten);
	if(res == FR_OK) preset_writeDrumsetData(presetNr, isMorph);
	return preset_finishFile(res, 8u + END_OF_SOUND_PARAMETERS + SNARE_NOISE_KIT_BYTES
	                              + LFO_EXTRA_BYTES + RPS_EXTRA_BYTES + INS_EXTRA_BYTES + GLD_EXTRA_BYTES);
#else
#endif
};

//----------------------------------------------------

/* New performance values live outside the legacy reserved globals block. */
static void preset_loadPerformanceExtension(void)
{
    static const uint8_t magicV1[8]={'M','U','T','A','0','0','0','1'};
    static const uint8_t magicV2[8]={'M','U','T','A','0','0','0','2'};
    static const uint8_t magicV3[8]={'M','U','T','A','0','0','0','3'};
    static const uint8_t magicV4[8]={'M','U','T','A','0','0','0','4'};
    static const uint8_t magicV5[8]={'M','U','T','A','0','0','0','5'};
    static const uint8_t magicV6[8]={'M','U','T','A','0','0','0','6'};
    static const uint8_t magicV7[8]={'M','U','T','A','0','0','0','7'};
    static const uint8_t magicV8[8]={'M','U','T','A','0','0','0','8'};
    static const uint8_t magicV9[8]={'M','U','T','A','0','0','0','9'};
    static const uint8_t magicV10[8]={'M','U','T','A','0','0','1','0'};
    uint8_t modernScale=0;
    uint8_t data[8+PERFORMANCE_EXTRA_BYTES+2+4+1+1+7+PROJECT_FX_COUNT+1+1]={0};
    preset_projectPattern = 0; // older projects start at pattern 1
    preset_fxFromKit = 1;
    UINT bytes=0;
    // 0.2.86: humanize belongs to the groove and obeys lsh like sh2..sh4
    const uint8_t keepHumanize = !preset_cfgExact && activeParameters[PAR_SHUFFLE_LOAD] == 0;
    uint8_t liveHumanize[4];
    for(uint8_t i=0;i<4;i++)liveHumanize[i]=activeParameters[PAR_HUMANIZE1+i]>127?0:activeParameters[PAR_HUMANIZE1+i];
    performance_resetExtended();
    if(f_open((FIL*)&SDFile,preset_cfgName,FA_OPEN_EXISTING|FA_READ)==FR_OK) {
        FRESULT result=f_read((FIL*)&SDFile,data,sizeof(data),&bytes);
        f_close((FIL*)&SDFile);
        if(result==FR_OK) {
            uint8_t count=0;
            if(bytes==sizeof(data)&&!memcmp(data,magicV10,8))count=PERFORMANCE_EXTRA_BYTES+2+4+1+1+7+PROJECT_FX_COUNT+1;
            else if(bytes==sizeof(data)-1&&!memcmp(data,magicV9,8))count=PERFORMANCE_EXTRA_BYTES+2+4+1+1+7+PROJECT_FX_COUNT;
            else if(bytes==sizeof(data)-1-PROJECT_FX_COUNT&&!memcmp(data,magicV8,8))count=PERFORMANCE_EXTRA_BYTES+2+4+1+1+7;
            else if(bytes==sizeof(data)-1-PROJECT_FX_COUNT-7&&!memcmp(data,magicV7,8))count=PERFORMANCE_EXTRA_BYTES+2+4+1+1;
            else if(bytes==sizeof(data)-1-PROJECT_FX_COUNT-8&&!memcmp(data,magicV6,8))count=PERFORMANCE_EXTRA_BYTES+2+4+1;
            else if(bytes==sizeof(data)-1-PROJECT_FX_COUNT-9&&!memcmp(data,magicV5,8))count=PERFORMANCE_EXTRA_BYTES+2+4;
            else if(bytes==sizeof(data)-1-PROJECT_FX_COUNT-13&&!memcmp(data,magicV4,8))count=PERFORMANCE_EXTRA_BYTES+2;
            else if(bytes==8+PERFORMANCE_EXTRA_BYTES+1&&(!memcmp(data,magicV2,8)||!memcmp(data,magicV3,8)))count=PERFORMANCE_EXTRA_BYTES;
            else if(bytes==8+18+1&&!memcmp(data,magicV1,8))count=18;
            if(count) {
                uint8_t checksum=0;
                for(uint8_t i=8;i<8+count;i++)checksum=(uint8_t)(checksum+data[i]);
                if(checksum==data[8+count]) {
                    modernScale=(uint8_t)(!memcmp(data,magicV3,8)||!memcmp(data,magicV4,8)||!memcmp(data,magicV5,8)||!memcmp(data,magicV6,8)||!memcmp(data,magicV7,8)||!memcmp(data,magicV8,8)||!memcmp(data,magicV9,8)||!memcmp(data,magicV10,8));
                    memcpy(&activeParameters[PAR_FX_OUTPUT_MODE],&data[8],count>PERFORMANCE_EXTRA_BYTES ? PERFORMANCE_EXTRA_BYTES : count);
                    if(count>=PERFORMANCE_EXTRA_BYTES+2) {
                        activeParameters[PAR_PERF_RANDOM_VELO]=data[8+PERFORMANCE_EXTRA_BYTES];
                        activeParameters[PAR_PERF_AVL]=data[9+PERFORMANCE_EXTRA_BYTES];
                    }
                    if(count>=PERFORMANCE_EXTRA_BYTES+2+4)
                        for(uint8_t i=0;i<4;i++)activeParameters[PAR_HUMANIZE1+i]=data[10+PERFORMANCE_EXTRA_BYTES+i];
                    if(count>=PERFORMANCE_EXTRA_BYTES+2+4+1)
                        activeParameters[PAR_HIGH_DAMP]=data[14+PERFORMANCE_EXTRA_BYTES];
                    if(count>=PERFORMANCE_EXTRA_BYTES+2+4+1+1)
                        activeParameters[PAR_LOAD_INT_SEND]=data[15+PERFORMANCE_EXTRA_BYTES];
                    if(count>=PERFORMANCE_EXTRA_BYTES+2+4+1+1+7)
                        memcpy(&activeParameters[PAR_MCOMP_ON],&data[16+PERFORMANCE_EXTRA_BYTES],7);
                    if(count>=PERFORMANCE_EXTRA_BYTES+2+4+1+1+7+PROJECT_FX_COUNT) {
                        uint8_t fxOk=1;
                        for(uint8_t i=0;i<PROJECT_FX_COUNT;i++)if(data[23+PERFORMANCE_EXTRA_BYTES+i]>127)fxOk=0;
                        if(fxOk) {
                            memcpy(&activeParameters[PAR_FX_TYPE],&data[23+PERFORMANCE_EXTRA_BYTES],PROJECT_FX_COUNT);
                            preset_fxFromKit=0;
                        }
                    }
                    if(count>=PERFORMANCE_EXTRA_BYTES+2+4+1+1+7+PROJECT_FX_COUNT+1) {
                        const uint8_t pattern=data[23+PERFORMANCE_EXTRA_BYTES+PROJECT_FX_COUNT];
                        preset_projectPattern = pattern<NUM_PATTERN ? pattern : 0;
                    }
                    performance_validateExtended();
                }
            }
        }
    }
    (void)modernScale;
    if(keepHumanize)
        for(uint8_t i=0;i<4;i++)activeParameters[PAR_HUMANIZE1+i]=liveHumanize[i];
    activeParameters[PAR_GLOBAL_SCALE]=PERF_SPEED_NEUTRAL; // spd is live only
    performance_prepareLoaded();
}
static FRESULT preset_savePerformanceExtension(void)
{
    uint8_t data[8+PERFORMANCE_EXTRA_BYTES+2+4+1+1+7+PROJECT_FX_COUNT+1+1]={'M','U','T','A','0','0','1','0'};
    UINT bytes=0;
    memcpy(&data[8],&activeParameters[PAR_FX_OUTPUT_MODE],PERFORMANCE_EXTRA_BYTES);
    data[8+PERFORMANCE_EXTRA_BYTES]=activeParameters[PAR_PERF_RANDOM_VELO];
    data[9+PERFORMANCE_EXTRA_BYTES]=activeParameters[PAR_PERF_AVL];
    for(uint8_t i=0;i<4;i++)data[10+PERFORMANCE_EXTRA_BYTES+i]=activeParameters[PAR_HUMANIZE1+i];
    data[14+PERFORMANCE_EXTRA_BYTES]=activeParameters[PAR_HIGH_DAMP];
    data[15+PERFORMANCE_EXTRA_BYTES]=activeParameters[PAR_LOAD_INT_SEND];
    memcpy(&data[16+PERFORMANCE_EXTRA_BYTES],&activeParameters[PAR_MCOMP_ON],7);
    memcpy(&data[23+PERFORMANCE_EXTRA_BYTES],&activeParameters[PAR_FX_TYPE],PROJECT_FX_COUNT);
    data[23+PERFORMANCE_EXTRA_BYTES+PROJECT_FX_COUNT]=menu_playedPattern<NUM_PATTERN ? menu_playedPattern : 0; // 0.2.89
    uint8_t checksum=0;
    for(uint8_t i=8;i<sizeof(data)-1;i++)checksum=(uint8_t)(checksum+data[i]);
    data[sizeof(data)-1]=checksum;
    FRESULT result=f_open((FIL*)&SDFile,preset_cfgName,FA_CREATE_ALWAYS|FA_WRITE);
    if(result!=FR_OK)return result;
    result=f_write((FIL*)&SDFile,data,sizeof(data),&bytes);
    FRESULT closeResult=f_close((FIL*)&SDFile);
    if(result!=FR_OK)return result;
    if(bytes!=sizeof(data))return FR_DISK_ERR;
    return closeResult;
}
static void preset_writeGlobalData()
{
	unsigned int bytesWritten;
	int i;
	for(i=PAR_BEGINNING_OF_GLOBALS;(i<PAR_CPU_USE);i++)
	{
		f_write((FIL*)&SDFile,&activeParameters[i],1,&bytesWritten);
	}
}

//----------------------------------------------------
FRESULT preset_saveGlobals()
{
#if USE_SD_CARD
	FRESULT res;
/*
	res = f_mount((FATFS*)&SDFatFS, (TCHAR const*)SDPath,1);
	if( res != FR_OK)
	{
		return res;
	}
	*/
	//open the file
	res = f_open((FIL*)&SDFile,"glo.cfg",FA_CREATE_ALWAYS | FA_WRITE);
	if(res != FR_OK) return res;
	preset_writeGlobalData();
	res = preset_finishFile(FR_OK, PAR_CPU_USE - PAR_BEGINNING_OF_GLOBALS);
	if(res != FR_OK) return res;

	//f_unmount((TCHAR const*)SDPath);
	return preset_savePerformanceExtension();
#else
#endif	
}
//----------------------------------------------------
// returns 1 on success
static uint8_t preset_readGlobalData()
{
#if USE_SD_CARD

	UINT bytesRead;
#if 0
	int i;
	for(i=PAR_BEGINNING_OF_GLOBALS;(i<NUM_PARAMS) &&( bytesRead!=0);i++) {
		f_read((FIL*)&SDFile,&activeParameters[i],1,&bytesRead);
		if(!bytesRead)
			return 0;
	}
	if(!bytesRead)
		return 0;
	return 1;
#else
	const uint8_t legacyGlobals = PAR_MIDI_CHAN_PC - PAR_BEGINNING_OF_GLOBALS;
	const uint8_t storedGlobals = PAR_CPU_USE - PAR_BEGINNING_OF_GLOBALS;
	activeParameters[PAR_MASTER_FILTER_ENABLE]=0;
	activeParameters[PAR_GLOBAL_SCALE]=PERF_SPEED_NEUTRAL;
	activeParameters[PAR_FX_SEND_MODE]=0;
	const uint8_t keepLiveGroove = activeParameters[PAR_SHUFFLE_LOAD] == 0;
	uint8_t previousGroove[3];
	for(uint8_t i=0;i<3;i++) {
		const uint8_t value=activeParameters[PAR_GROOVE_SH2+i];
		previousGroove[i]=value>127?63:value;
	}
	activeParameters[PAR_GROOVE_SH2] = 63;
	activeParameters[PAR_GROOVE_SH3] = 63;
	activeParameters[PAR_GROOVE_SH4] = 63;
	activeParameters[PAR_MIDI_CHAN_PC] = 2;
	activeParameters[PAR_SHUFFLE_LOAD] = 1;
	activeParameters[PAR_LOAD_MORPH] = 0;
	activeParameters[PAR_LOAD_SAMPLE_RATE] = 1;
	activeParameters[PAR_GLOBAL_PITCH] = 63;
	activeParameters[PAR_PITCH_BEND_RANGE] = 12;
	activeParameters[PAR_GLOBAL_DECAY] = 63;
	activeParameters[PAR_RANDOM_STEP] = 0;
	activeParameters[PAR_PERF_NOTE_REPEAT_CHANCE] = 0;
	activeParameters[PAR_PERF_SCARCITY] = 100;
	activeParameters[PAR_PERF_PROB] = 100;
	activeParameters[PAR_PERF_NOTE_PROB] = 100;
	activeParameters[PAR_PERF_DELAY_CHANCE] = 0;
	activeParameters[PAR_PERF_DELAY_SYNC] = 6;
	activeParameters[PAR_PERF_DELAY_COUNT] = 0;
	activeParameters[PAR_PERF_DELAY_BOUNCE] = 63;
	activeParameters[PAR_PERF_DELAY_TARGET] = 5;
	activeParameters[PAR_PERF_DELAY_MODE] = 0;
	activeParameters[PAR_PERF_DELAY_EXP] = 64;
	activeParameters[PAR_PERF_DELAY_PITCH] = 64;
	activeParameters[PAR_PERF_DELAY_INPUT_MASK] = 127;
	activeParameters[PAR_PERF_VELO_DECAY] = 63;
	activeParameters[PAR_PERF_VELO_SAMPLE_RATE] = 63;
	activeParameters[PAR_PERF_VELO_FILTER] = 63;
	activeParameters[PAR_PERF_VELO_COARSE] = 63;
	activeParameters[PAR_PERF_VELO_SLOPE] = 63;
	activeParameters[PAR_PERF_VELO_MOD_AMOUNT] = 63;
	activeParameters[PAR_PERF_VELO_DRIVE] = 63;
	activeParameters[PAR_PERF_VELO_LEVEL] = 63;
	f_read((FIL*)&SDFile,&activeParameters[PAR_BEGINNING_OF_GLOBALS],storedGlobals,&bytesRead);
	if(bytesRead < legacyGlobals) return 0;
	// Old glo.cfg ends here; old project files contain 0xFF padding instead.
	if(bytesRead == legacyGlobals || activeParameters[PAR_MIDI_CHAN_PC] < 1 ||
	   activeParameters[PAR_MIDI_CHAN_PC] > 16)
		activeParameters[PAR_MIDI_CHAN_PC] = 2;
	if(activeParameters[PAR_SHUFFLE_LOAD] > 1)
		activeParameters[PAR_SHUFFLE_LOAD] = 1;
	if(activeParameters[PAR_LOAD_MORPH] > 1)
		activeParameters[PAR_LOAD_MORPH] = 0;
	if(activeParameters[PAR_LOAD_SAMPLE_RATE] > 1)
		activeParameters[PAR_LOAD_SAMPLE_RATE] = 1;
	// 0.2.86: gpt and gdc are live only, every load starts neutral
	activeParameters[PAR_GLOBAL_PITCH] = 63;
	if(activeParameters[PAR_PITCH_BEND_RANGE] > 48)
		activeParameters[PAR_PITCH_BEND_RANGE] = 12;
	activeParameters[PAR_GLOBAL_DECAY] = 63;
	if(activeParameters[PAR_RANDOM_STEP] > 100)
		activeParameters[PAR_RANDOM_STEP] = 0;
	if(activeParameters[PAR_PERF_NOTE_REPEAT_CHANCE] > 127)
		activeParameters[PAR_PERF_NOTE_REPEAT_CHANCE] = 0;
	if(activeParameters[PAR_PERF_SCARCITY] > 100)
		activeParameters[PAR_PERF_SCARCITY] = 100;
	if(activeParameters[PAR_PERF_PROB] > 100)
		activeParameters[PAR_PERF_PROB] = 100;
	if(activeParameters[PAR_PERF_NOTE_PROB] > 100)
		activeParameters[PAR_PERF_NOTE_PROB] = 100;
	if(activeParameters[PAR_PERF_DELAY_CHANCE] > 100)
		activeParameters[PAR_PERF_DELAY_CHANCE] = 0;
	if(activeParameters[PAR_PERF_DELAY_SYNC] > 15)
		activeParameters[PAR_PERF_DELAY_SYNC] = 6;
	if(activeParameters[PAR_PERF_DELAY_COUNT] > 32)
		activeParameters[PAR_PERF_DELAY_COUNT] = 0;
	if(activeParameters[PAR_PERF_DELAY_BOUNCE] > 127)
		activeParameters[PAR_PERF_DELAY_BOUNCE] = 63;
	if(activeParameters[PAR_PERF_DELAY_TARGET] > 10)
		activeParameters[PAR_PERF_DELAY_TARGET] = 5;
	if(activeParameters[PAR_PERF_DELAY_MODE] > 1)
		activeParameters[PAR_PERF_DELAY_MODE] = 0;
	if(activeParameters[PAR_PERF_DELAY_EXP] > 127)
		activeParameters[PAR_PERF_DELAY_EXP] = 64;
	if(activeParameters[PAR_PERF_DELAY_PITCH] > 127)
		activeParameters[PAR_PERF_DELAY_PITCH] = 64;
	if(activeParameters[PAR_PERF_DELAY_INPUT_MASK] > 127)
		activeParameters[PAR_PERF_DELAY_INPUT_MASK] = 127;
	if(activeParameters[PAR_PERF_VELO_DECAY] > 127)
		activeParameters[PAR_PERF_VELO_DECAY] = 63;
	if(activeParameters[PAR_PERF_VELO_SAMPLE_RATE] > 127)
		activeParameters[PAR_PERF_VELO_SAMPLE_RATE] = 63;
	if(activeParameters[PAR_PERF_VELO_FILTER] > 127)
		activeParameters[PAR_PERF_VELO_FILTER] = 63;
	if(activeParameters[PAR_PERF_VELO_COARSE] > 127)
		activeParameters[PAR_PERF_VELO_COARSE] = 63;
	if(activeParameters[PAR_PERF_VELO_SLOPE] > 127)
		activeParameters[PAR_PERF_VELO_SLOPE] = 63;
	if(activeParameters[PAR_PERF_VELO_MOD_AMOUNT] > 127)
		activeParameters[PAR_PERF_VELO_MOD_AMOUNT] = 63;
	if(activeParameters[PAR_PERF_VELO_DRIVE] > 127)
		activeParameters[PAR_PERF_VELO_DRIVE] = 63;
	for(uint16_t p=PAR_GROOVE_SH2;p<=PAR_GROOVE_SH4;p++)
		if(activeParameters[p]>127) activeParameters[p]=63;
	if(activeParameters[PAR_MASTER_FILTER_ENABLE]>1)activeParameters[PAR_MASTER_FILTER_ENABLE]=0;
	activeParameters[PAR_GLOBAL_SCALE]=PERF_SPEED_NEUTRAL; // spd is live only
	if(activeParameters[PAR_FX_SEND_MODE]>3)activeParameters[PAR_FX_SEND_MODE]=0;
	// Save always includes the groove. Loading obeys the live load lock and
	// a stored OFF setting. A project change must not silently unlock it.
	if(keepLiveGroove) activeParameters[PAR_SHUFFLE_LOAD]=0;
	if(!activeParameters[PAR_SHUFFLE_LOAD])
		for(uint8_t i=0;i<3;i++) activeParameters[PAR_GROOVE_SH2+i]=previousGroove[i];


	return 1;

#endif
#endif
}
//----------------------------------------------------
uint8_t preset_loadGlobals()
{
	preset_fxFromKit = 1; // MUTA.CFG v9 clears it


	FRESULT res;
/*
	res = f_mount((FATFS*)&SDFatFS, (TCHAR const*)SDPath,1);
	if( res != FR_OK)
	{
		return res;
	}
	*/

	//open the file
	res = f_open((FIL*)&SDFile,"glo.cfg",FA_OPEN_EXISTING | FA_READ);
	
	if(res!=FR_OK)
		return 0; //file open error... maybe the file does not exist?

	if(!preset_readGlobalData())
	{
		f_close((FIL*)&SDFile);
		return 0;
	}
	f_close((FIL*)&SDFile);
	preset_loadPerformanceExtension();
	menu_sendAllGlobals();
	
	//f_unmount((TCHAR const*)SDPath);

	return 1;

}




//----------------------------------------------------
void preset_loadDefaultGlobals()
{
	preset_fxFromKit = 1;
	activeParameters[PAR_MASTER_FILTER_ENABLE]=0;
	activeParameters[PAR_GLOBAL_SCALE]=PERF_SPEED_NEUTRAL;
	activeParameters[PAR_FX_SEND_MODE]=0;
	performance_resetExtended();
	activeParameters[PAR_GROOVE_SH2] = 63;
	activeParameters[PAR_GROOVE_SH3] = 63;
	activeParameters[PAR_GROOVE_SH4] = 63;
	activeParameters[PAR_BPM] = 120;

	activeParameters[PAR_MIDI_CHAN_1] = 1;
	activeParameters[PAR_MIDI_CHAN_2] = 1;
	activeParameters[PAR_MIDI_CHAN_3] = 1;
	activeParameters[PAR_MIDI_CHAN_4] = 1;
	activeParameters[PAR_MIDI_CHAN_5] = 1;
	activeParameters[PAR_MIDI_CHAN_6] = 1;
	activeParameters[PAR_MIDI_CHAN_7] = 1;

	activeParameters[PAR_MIDI_NOTE1] = 48;
	activeParameters[PAR_MIDI_NOTE2] = 48;
	activeParameters[PAR_MIDI_NOTE3] = 48;
	activeParameters[PAR_MIDI_NOTE4] = 48;
	activeParameters[PAR_MIDI_NOTE5] = 48;
	activeParameters[PAR_MIDI_NOTE6] = 48;
	activeParameters[PAR_MIDI_NOTE7] = 48;


	activeParameters[PAR_FETCH] = 0;
	activeParameters[PAR_FOLLOW] = 0;

	activeParameters[PAR_QUANTISATION] = 0;

	activeParameters[PAR_SCREENSAVER_ON_OFF] = 1;

	activeParameters[PAR_MIDI_ROUTING] = 0;
	activeParameters[PAR_MIDI_FILT_TX] = 15;	//all
	activeParameters[PAR_MIDI_FILT_RX] = 15; //all

	activeParameters[PAR_PRESCALER_CLOCK_IN] = 0; //all
	activeParameters[PAR_PRESCALER_CLOCK_OUT1] = 0; //all
	activeParameters[PAR_PRESCALER_CLOCK_OUT2] = 0; //all
	activeParameters[PAR_TRIG_GATE_MODE] = 0; //all

	activeParameters[PAR_BAR_RESET_MODE] = 1; //all
	activeParameters[PAR_MIDI_CHAN_GLOBAL] = 0; //all

	activeParameters[PAR_PATTERN_MODE] = 1; //auto
	activeParameters[PAR_MIDI_CHAN_PC] = 2;
	activeParameters[PAR_SHUFFLE_LOAD] = 1;
	activeParameters[PAR_LOAD_MORPH] = 0;
	activeParameters[PAR_LOAD_SAMPLE_RATE] = 1;
	activeParameters[PAR_GLOBAL_PITCH] = 63;
	activeParameters[PAR_PITCH_BEND_RANGE] = 12;
	activeParameters[PAR_GLOBAL_DECAY] = 63;
	activeParameters[PAR_RANDOM_STEP] = 0;
	activeParameters[PAR_PERF_NOTE_REPEAT_CHANCE] = 0;
	activeParameters[PAR_PERF_SCARCITY] = 100;
	activeParameters[PAR_PERF_PROB] = 100;
	activeParameters[PAR_PERF_NOTE_PROB] = 100;
	activeParameters[PAR_PERF_DELAY_CHANCE] = 0;
	activeParameters[PAR_PERF_DELAY_SYNC] = 6;
	activeParameters[PAR_PERF_DELAY_COUNT] = 0;
	activeParameters[PAR_PERF_DELAY_BOUNCE] = 63;
	activeParameters[PAR_PERF_DELAY_TARGET] = 5;
	activeParameters[PAR_PERF_DELAY_MODE] = 0;
	activeParameters[PAR_PERF_DELAY_EXP] = 64;
	activeParameters[PAR_PERF_DELAY_PITCH] = 64;
	activeParameters[PAR_PERF_DELAY_INPUT_MASK] = 127;
	activeParameters[PAR_PERF_VELO_DECAY] = 63;
	activeParameters[PAR_PERF_VELO_SAMPLE_RATE] = 63;
	activeParameters[PAR_PERF_VELO_FILTER] = 63;
	activeParameters[PAR_PERF_VELO_COARSE] = 63;
	activeParameters[PAR_PERF_VELO_SLOPE] = 63;
	activeParameters[PAR_PERF_VELO_MOD_AMOUNT] = 63;
	activeParameters[PAR_PERF_VELO_DRIVE] = 63;
	activeParameters[PAR_PERF_VELO_LEVEL] = 63;
	activeParameters[PAR_CPU_USE] = 0;

}
//----------------------------------------------------
void preset_createGlobals()
{
	preset_loadDefaultGlobals();
	preset_saveGlobals();
}
//----------------------------------------------------
FRESULT preset_loadLastUsedProjectNrFromSD(uint8_t* projNr)
{
    FRESULT res;

    *projNr = 0;
    unsigned int bytesRead;

    res = f_open((FIL*)&SDFile,"/proj.idx",FA_OPEN_EXISTING | FA_READ);
    if(res != FR_OK)
    {
    	//close the file handle
    	f_close((FIL*)&SDFile);
    	return res;
    }

    res=f_read((FIL*)&SDFile, projNr,1, &bytesRead);
	//close the file handle
	f_close((FIL*)&SDFile);


	return res;
}
//----------------------------------------------------
FRESULT preset_saveLastUsedProjectNrToSD(uint8_t projNr)
{
#if USE_SD_CARD
    FRESULT res;

	//open the file
	res = f_open((FIL*)&SDFile,"/proj.idx",FA_CREATE_ALWAYS | FA_WRITE);
	if(res != FR_OK)
	{
		//close the file handle
		f_close((FIL*)&SDFile);
		return res;
	}

	unsigned int bytesWritten;
	res = f_write((FIL*)&SDFile,&projNr,1,&bytesWritten);
	if(res != FR_OK)
	{
		//close the file handle
		f_close((FIL*)&SDFile);
		return res;
	}

	//close the file
	f_close((FIL*)&SDFile);

	//f_unmount((TCHAR const*)SDPath);
	return res;
#else
#endif
}
//----------------------------------------------------
// read the data into either the main parameters or the morph parameters.
// fix some values, and set values to 0 that were not read in
static FRESULT preset_readDrumsetData(uint8_t presetNr, uint8_t isMorph)
{
	
#if USE_SD_CARD		
	//read the file content
	unsigned int bytesRead=1;
	int16_t i;
	uint8_t *para;
	bytesRead = 0;
	
	// TODO check: using this function for morph may be wrong
	if(isMorph)
		para=morphParameters;
	else
	{
		para=mainParameters[presetNr];
		if(presetNr == preset_activeKitNr) preset_activeKitNr = 0xff;
	}

	FRESULT res=f_read((FIL*)&SDFile, para,END_OF_SOUND_PARAMETERS, &bytesRead);
	if(res==FR_OK) {
		// set to 0 for any that were not read from the file
		if(END_OF_SOUND_PARAMETERS-bytesRead)
			memset(para+bytesRead,0,END_OF_SOUND_PARAMETERS-bytesRead);
		uint8_t magic[SNARE_NOISE_KIT_BYTES]={0};
		UINT magicBytes=0;
		FRESULT magicResult=f_read((FIL*)&SDFile,magic,sizeof(magic),&magicBytes);
		preset_validateSnareExtension(para,bytesRead,magic,magicResult==FR_OK?magicBytes:0);
		if(!isMorph){preset_readLfoExtras(mainLfoExtras[presetNr]);preset_readRpsExtras(mainRpsExtras[presetNr]);preset_readInsExtras(mainInsExtras[presetNr]);preset_readGldExtras(mainGldExtras[presetNr]);}
		
		//special case mod targets. normalize.
		const uint8_t nmt=getNumModTargets();
		for(i=0;i<6;i++) {
			// since I've changed the meaning of these, I'll ensure that it's valid for kits saved prior to the
			// change
			if(para[PAR_VEL_DEST_1+i] >= nmt )
				para[PAR_VEL_DEST_1+i] = 0;
			if(para[PAR_TARGET_LFO1+i] >= nmt )
				para[PAR_TARGET_LFO1+i] = 0;
		}
	}

	return res;

#endif
}

//----------------------------------------------------
FRESULT preset_loadDrumsetSD(uint8_t presetNr, uint8_t isMorph)
{
	//activePresetNr = presetNr;
	/* 0.2.81: a slot without a kit file must not keep zero insert settings */
	if(!isMorph && presetNr<NUM_KIT_SLOTS) { preset_defaultInsExtras(mainInsExtras[presetNr]); preset_defaultGldExtras(mainGldExtras[presetNr]); }
#if USE_SD_CARD
	//filename in 8.3  format
	char filename[13];
	unsigned int bytesRead;

#if !CALC_SAMPLES_IN_INTERRUPT
	while(!soundengine_calcNextSampleBlock())
	{
		//wait till new block is calculated
	}
#endif

	//sprintf(filename,"p%03d.snd",presetNr);
	/*
	preset_makeFileNameLoad(filename,presetNr,FEXT_SOUND);

	//open the file
	FRESULT res = f_open((FIL*)&SDFile,filename,FA_OPEN_EXISTING | FA_READ);
	*/
	FRESULT res = preset_makeFileNameLoad(filename,presetNr,FEXT_SOUND);
	if(res!=FR_OK)
	{
		//try old filename
		preset_makeFileNameOld(filename,presetNr,FEXT_SOUND);
		res = f_open((FIL*)&SDFile,filename,FA_OPEN_EXISTING | FA_READ);
		if(res!=FR_OK)
			goto error; //file open error... maybe the file does not exist?
	}

#if !CALC_SAMPLES_IN_INTERRUPT
	//to prevent audio dropouts
	soundengine_calcNextSampleBlock();
#endif
	//first the preset name
	res=f_read((FIL*)&SDFile,(void*)savefileNames[presetNr][KIT_NAMES],8,&bytesRead);
	if(bytesRead != 8) {
		res=FR_DISK_ERR;
		goto closeFile;
	}
	if(preset_isNameEmpty(savefileNames[presetNr][KIT_NAMES]))
	{
		sprintf((void*)savefileNames[presetNr][KIT_NAMES], "Empty");
	}



#if !CALC_SAMPLES_IN_INTERRUPT
	//to prevent audio dropouts
	soundengine_calcNextSampleBlock();
#endif
	//then the data
	res=preset_readDrumsetData(presetNr, isMorph);
#if !CALC_SAMPLES_IN_INTERRUPT
	//to prevent audio dropouts
	soundengine_calcNextSampleBlock();
#endif
closeFile:
	//close the file handle
	f_close((FIL*)&SDFile);

	// update the soundengine with the new parameters
	if(res==FR_OK) {
		preset_sendDrumsetParameters();
		return FR_OK;
	}
error:
	return res;
#else
	frontPanel_sendData(PRESET,PRESET_LOAD,presetNr);
#endif
}
//----------------------------------------------------
//val is interpolation value between 0 and 255
//uses bankers rounding
static uint8_t interpolate(uint8_t a, uint8_t b, uint8_t x)
{
	uint16_t fixedPointValue = (uint16_t)(((a*256) + (b-a)*x));
	uint8_t result = (uint8_t)(fixedPointValue/256);

	return (uint8_t)((fixedPointValue&0xff) < 0x7f ? result : result+1);
	//return ((a*255) + (b-a)*x)/255;
}

//----------------------------------------------------
void preset_sendDrumsetParametersImmediate()
{
		//special case mod targets
		for(uint8_t i=0;i<6;i++)
		{
			//**VELO load drumkit. translate to param value before sending
			// parameter_values[PAR_VEL_DEST_1+i] is an index into modTargets, we need to send
			// a parameter number
			uint8_t value = (uint8_t)pgm_read_word(&modTargets[activeParameters[PAR_VEL_DEST_1+i]].param);
			uint8_t upper,lower;
			upper = (uint8_t)(((value&0x80)>>7) | (((i)&0x3f)<<1));
			lower = value&0x7f;
			frontPanel_sendData(CC_VELO_TARGET,upper,lower);

			// ensure target voice # is valid
			if(activeParameters[PAR_VOICE_LFO1+i] < 1 || activeParameters[PAR_VOICE_LFO1+i] > 6 )
				activeParameters[PAR_VOICE_LFO1+i]=1;

			// **LFO par_target_lfo will be an index into modTargets, but we need a parameter number to send
			value = (uint8_t)pgm_read_word(&modTargets[activeParameters[PAR_TARGET_LFO1+i]].param);

			upper = (uint8_t)(((value&0x80)>>7) | (((i)&0x3f)<<1));
			lower = value&0x7f;
			frontPanel_sendData(CC_LFO_TARGET,upper,lower);
		}

		static MidiMsg msg = {0};
		//pre-send fx type to prevent clicks
		/*
		msg.status = CC_2;
		msg.data1 = PAR_FX_TYPE-128; //stupid offset only in CC not CC2
		msg.data2 = activeParameters[PAR_FX_TYPE];

		//	msg.data1 += 1;
		msg.data1 &= 0x7f;
		midiParser_ccHandler(msg,1, 0, 0.f);
		*/

		//try to prevent click by sending BD params first

		//stuff from the morph function
		for(uint32_t i=0;i<END_OF_SOUND_PARAMETERS; i++)
		{

			uint8_t paramNumber = parameterOrder[i];
			// Destinations were translated from stored menu indices above.
			// Sending those indices again through the voice CC map changes
			// their meaning to parameter IDs and may create recursive targets.
			if(paramNumber==PAR_NONE || paramNumber==PAR_BANK_CHANGE ||
			   (paramNumber>=PAR_VEL_DEST_1 && paramNumber<=PAR_VEL_DEST_6) ||
			   (paramNumber>=PAR_VOICE_LFO1 && paramNumber<=PAR_VOICE_LFO6) ||
			   (paramNumber>=PAR_TARGET_LFO1 && paramNumber<=PAR_TARGET_LFO6)) continue;

			//const uint8_t morph = activeParameters[PAR_MORPH];

			const uint8_t val = activeParameters[paramNumber];//interpolate(activeParameters[i],morphParameters[i],morph);

			if(paramNumber < 128)
			{
				/* comes from cortex midi handler
				 * stupid offset!
				 * TODO fix this stupid offset			 *
				 * 		frontParser_midiMsg.data1 += 1;

						//because hh slope on front is 127 and on cortex is 0 wrap data1 at 127
						frontParser_midiMsg.data1 &= 0x7f;
				 *
				 */
				msg.status = MIDI_CC;
				msg.data1 = paramNumber;
				msg.data2 = val;

				msg.data1 += 1;
				msg.data1 &= 0x7f;
				midiParser_ccHandler(msg,1, 0, 0.f);


			}
			else
			{
				msg.status = CC_2;
				msg.data1 = paramNumber-128; //stupid offset only in CC not CC2
				msg.data2 = val;

			//	msg.data1 += 1;
				msg.data1 &= 0x7f;
				midiParser_ccHandler(msg,1, 0, 0.f);

			}
			soundengine_process();
		}
}
//----------------------------------------------------
// send loaded parameters to back
void preset_sendDrumsetParameters()
{
	uint8_t i;
	//special case mod targets
	for(i=0;i<6;i++)
	{
		//**VELO load drumkit. translate to param value before sending
		// parameter_values[PAR_VEL_DEST_1+i] is an index into modTargets, we need to send
		// a parameter number
		uint8_t value = (uint8_t)pgm_read_word(&modTargets[activeParameters[PAR_VEL_DEST_1+i]].param);
		uint8_t upper,lower;
		upper = (uint8_t)(((value&0x80)>>7) | (((i)&0x3f)<<1));
		lower = value&0x7f;
		frontPanel_sendData(CC_VELO_TARGET,upper,lower);

		// ensure target voice # is valid
		if(activeParameters[PAR_VOICE_LFO1+i] < 1 || activeParameters[PAR_VOICE_LFO1+i] > 6 )
			activeParameters[PAR_VOICE_LFO1+i]=1;

		// **LFO par_target_lfo will be an index into modTargets, but we need a parameter number to send
		value = (uint8_t)pgm_read_word(&modTargets[activeParameters[PAR_TARGET_LFO1+i]].param);

		upper = (uint8_t)(((value&0x80)>>7) | (((i)&0x3f)<<1));
		lower = value&0x7f;
		frontPanel_sendData(CC_LFO_TARGET,upper,lower);
	}

	// todo will this morph (and fuck up) our modulation targets?
	// send parameters (possibly combined with morph parameters) to back
	preset_morph(activeParameters[PAR_MORPH]);



}
//----------------------------------------------------
/*
char* preset_loadName(uint8_t presetNr, uint8_t nameBufferIdx, uint8_t what)
{
	uint8_t type;

	switch(what) {
	case SAVE_TYPE_PATTERN:
		type=FEXT_PAT;
		break;
	case SAVE_TYPE_KIT:
	case SAVE_TYPE_MORPH:
		type=FEXT_SOUND;
		break;
	case SAVE_TYPE_ALL:
		type=FEXT_ALL;
		break;
	case SAVE_TYPE_PERFORMANCE:
		type=FEXT_PERF;
		break;
	default:
		return NULL; // for glo and sample we don't load a name
	}
	

#if USE_SD_CARD		
	//filename in 8.3  format
	char filename[9];
	preset_makeFileName(filename,presetNr,type);

	//try to open the file
	FRESULT res = f_open((FIL*)&SDFile,filename,FA_OPEN_EXISTING | FA_READ);
	


	if(res!=FR_OK)
	{
		//error opening the file
		memcpy((void*)savefileNames[nameBufferIdx][presetNr],PSTR("Empty   "),8);
		return NULL;	
	}
	
	//file opened correctly -> extract name (first 8 bytes)
	unsigned int bytesRead;
	f_read((FIL*)&SDFile,(void*)savefileNames[nameBufferIdx][presetNr],8,&bytesRead);
	


	//close the file handle
	f_close((FIL*)&SDFile);
	
	return (char*)savefileNames[nameBufferIdx][presetNr];
#else

return "ToDo";
#endif
}
*/

//----------------------------------------------------
/** request step data from the cortex via uart and save it in the provided step struct*/
/*
void preset_queryStepDataFromSeq(uint16_t stepNr)
{
	frontParser_newSeqDataAvailable = 0;

	//request step data
	//the max number for 14 bit data is 16383!!!
	//current max step nr is 128*7*8 = 7168
	frontPanel_sendByte((stepNr>>7)&0x7f);		//upper nibble 7 bit
	frontPanel_sendByte(stepNr&0x7f);			//lower nibble 7 bit

	//wait until data arrives
	uint8_t newSeqDataLocal = 0;
	uint16_t now = systick_ticks;
	while((newSeqDataLocal==0))
	{
		//we have to call the uart parser to handle incoming messages from the sequencer
		uart_checkAndParse();
		
		newSeqDataLocal = frontParser_newSeqDataAvailable;
		
		if(systick_ticks-now >= 31)
		{
			//timeout
			now = systick_ticks;
			//request step again
			frontPanel_sendByte((stepNr>>7)&0x7f);		//upper nibble 7 bit
			frontPanel_sendByte(stepNr&0x7f);
		}
	}
}
*/
//----------------------------------------------------
/*
static void preset_sendMainStepDataToSeq( uint16_t mainStepData)
{
	frontPanel_sendByte(mainStepData	& 0x7f);
	frontPanel_sendByte((mainStepData>>7)	& 0x7f);
	frontPanel_sendByte((uint8_t)((mainStepData>>14)	& 0x7f));
}
*/
//----------------------------------------------------
/** send step data from SD card to the sequencer*/
/*
static void preset_sendStepDataToSeq()
{
	frontPanel_sendByte(frontParser_stepData.volume	& 0x7f);
	frontPanel_sendByte(frontParser_stepData.prob	& 0x7f);
	frontPanel_sendByte(frontParser_stepData.note	& 0x7f);

	frontPanel_sendByte(frontParser_stepData.param1Nr	& 0x7f);
	frontPanel_sendByte(frontParser_stepData.param1Val	& 0x7f);

	frontPanel_sendByte(frontParser_stepData.param2Nr	& 0x7f);
	frontPanel_sendByte(frontParser_stepData.param2Val	& 0x7f);

	//now the MSBs from all 7 values
	frontPanel_sendByte((uint8_t) 	(((frontParser_stepData.volume 	& 0x80)>>7) |
							((frontParser_stepData.prob	 	& 0x80)>>6) |
							((frontParser_stepData.note	 	& 0x80)>>5) |
							((frontParser_stepData.param1Nr	& 0x80)>>4) |
							((frontParser_stepData.param1Val	& 0x80)>>3) |
							((frontParser_stepData.param2Nr	& 0x80)>>2) |
							((frontParser_stepData.param2Val	& 0x80)>>1))
							);
}	
*/
//----------------------------------------------------
void preset_queryPatternInfoFromSeq(uint8_t patternNr, uint8_t* next, uint8_t* repeat)
{
	frontParser_newSeqDataAvailable = 0;
	//request pattern info
	frontPanel_sendByte(patternNr);	

	//wait until data arrives
	uint8_t newSeqDataLocal = 0;
	uint16_t now = systick_ticks;
	while((newSeqDataLocal==0))
	{
		//we have to call the uart parser to handle incoming messages from the sequencer
		uart_checkAndParse();
		
		newSeqDataLocal = frontParser_newSeqDataAvailable;
		
		if(systick_ticks-now >= 31)
		{
			//timeout
			now = systick_ticks;
			//request step again
			frontPanel_sendByte(patternNr);	
		}
	}
	
	//the stepdata struct is used as buffer for the data
	*next = frontParser_stepData.volume; 
	*repeat =  frontParser_stepData.prob;
}
//----------------------------------------------------
void preset_queryMainStepDataFromSeq(uint16_t stepNr, uint16_t *mainStepData, uint8_t *length)
{
	frontParser_newSeqDataAvailable = 0;

	//request step data
	//the max number for 14 bit data is 16383!!!
	//current max step nr is 7*8 = 56
	frontPanel_sendByte((stepNr>>7)&0x7f);		//upper nibble 7 bit
	frontPanel_sendByte(stepNr&0x7f);	//lower nibble 7 bit

	//wait until data arrives
	uint8_t newSeqDataLocal = 0;
	uint16_t now = systick_ticks;
	while((newSeqDataLocal==0))
	{
		//we have to call the uart parser to handle incoming messages from the sequencer
		uart_checkAndParse();
		
		newSeqDataLocal = frontParser_newSeqDataAvailable;
		
		if(systick_ticks-now >= 31)
		{
			//timeout
			now = systick_ticks;
			//request step again
			frontPanel_sendByte((stepNr>>7)&0x7f);		//upper nibble 7 bit
			frontPanel_sendByte(stepNr&0x7f);
		}
	}
	
	// we are reusing these members for purposes other than those that were originally intended
	*mainStepData =(uint16_t) ((frontParser_stepData.volume<<8) | frontParser_stepData.prob);
	*length=frontParser_stepData.note;
};

//----------------------------------------------------
static FRESULT preset_writePatternData(uint8_t patternNr)
{
#if 0
#else
		UINT bytesWritten;
		uint8_t length;

		//---------------  write the step data (note, vol, prob, autom.) ---------------
		for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
		{
			preset_writeStepTrack(patternNr,trk,&bytesWritten);

			f_write((FIL*)&SDFile,(const void*)&seq_patternSet.seq_stepTiming[patternNr][trk][0],sizeof(uint8_t)*STEPS_PER_PATTERN,&bytesWritten);
		}

		//--------------- now the main step data ---------------
		for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
		{
			for(uint8_t bar=0;bar<NUM_BARS; bar++)
			{
				const uint16_t mainStepData = seq_patternSet.seq_mainSteps[bar][patternNr][trk];
				f_write((FIL*)&SDFile,(const void*)&mainStepData,sizeof(uint16_t),&bytesWritten);
			}
		}

		//----- shuffle setting ------


		//f_write((FIL*)&SDFile,(const void*)&activeParameters[PAR_SHUFFLE],sizeof(uint8_t),&bytesWritten);
		f_write((FIL*)&SDFile,(const void*)&seq_patternSet.shuffle[patternNr],sizeof(uint8_t),&bytesWritten);

		//----- pattern/track lengths ------
		// we reuse the same call from above (when saving main step data)
		// but we only use the length info retrieved. We want to store it at the end
		// to avoid breaking compatibility with save file


		for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
		{
				length = seq_patternSet.length[patternNr][trk] ;//seq_patternSet.seq_mainSteps[bar][pat][trk];
				f_write((FIL*)&SDFile,(const void*)&length,sizeof(uint8_t),&bytesWritten);
		}

		//write associated kit nr
		f_write((FIL*)&SDFile,&seq_patternSet.kitNr[patternNr],sizeof(uint8_t),&bytesWritten);
		preset_writePatternScale(patternNr);
		preset_writeFlamProbability(patternNr);
		preset_writeTrigConditions(patternNr);
		preset_writeIntSends(patternNr);
        FRESULT lockResult=preset_writeLocks(patternNr);
        if(lockResult==FR_OK)lockResult=preset_writeSlide(patternNr);
        if(lockResult==FR_OK)lockResult=preset_writeAccent(patternNr); // 0.2.93
        return lockResult;

#endif
}

//----------------------------------------------------
/*
void preset_savePatternTemp(uint8_t presetNr)
{

	UINT bytesWritten;
	//lcd_clear();
	//lcd_home();
	//lcd_string(PSTR("Saving pattern"));


	//filename in 8.3  format
	char filename[9];
	//sprintf(filename,"p%03d.pat",presetNr);
	preset_makeFileNameTemp(filename,presetNr,FEXT_PAT);
	//open the file
	f_open((FIL*)&SDFile,filename,FA_CREATE_ALWAYS | FA_WRITE);

	//write preset name to file
	f_write((FIL*)&SDFile,(void*)preset_currentName,8,&bytesWritten);

	preset_writePatternData();

	//close the file
	f_close((FIL*)&SDFile);

	//reset the lcd
	menu_repaintAll();


}
*/
//----------------------------------------------------
#define TRANSFER_V3_KIT_OFFSET (14u + 7u*(64u*7u+64u) + 4u*7u*2u + 1u + 7u)
FRESULT preset_savePatternSD(uint8_t presetNr)
{

	FRESULT res;
	UINT bytesWritten;
	//lcd_clear();
	//lcd_home();
	//lcd_string(PSTR("Saving pattern"));
	
	
	//filename in 8.3  format
	char filename[13];
	//sprintf(filename,"p%03d.pat",presetNr);
	preset_makeFileNameSave(filename,presetNr,FEXT_PAT, savefileNames[presetNr][PATTERN_NAMES]);
	//open the file
	res = f_open((FIL*)&SDFile,filename,FA_CREATE_ALWAYS | FA_WRITE);
	if(res != FR_OK) return res;

	//write preset name to file
	res = f_write((FIL*)&SDFile,(void*)savefileNames[presetNr][PATTERN_NAMES],8,&bytesWritten);
	if(res == FR_OK) res = f_write(&SDFile, "PatV03", 6, &bytesWritten);
	if(res == FR_OK) res = preset_writePatternData(presetNr);
	/* Kit byte, SCL2, FLP1, CND3 (including transform) and ISD1. */
	const FSIZE_t expected = TRANSFER_V3_KIT_OFFSET + 1u + 6u + 4u + 5u
	                       + sizeof(seq_patternSet.flamProbability[presetNr])
	                       + sizeof(seq_patternSet.trigCondition[presetNr])
	                       + 4u + PATTERN_INT_SENDS + preset_lockBytes(presetNr) + preset_slideBytes(presetNr) + preset_accentBytes(presetNr);
	res = preset_finishFile(res, expected);
	menu_repaintAll();
	return res;
}

//----------------------------------------------------
// returns 1 on success
static uint8_t preset_readPatternData(uint8_t patternNr, uint8_t dataVersion)
{
	seq_patternSet.scale[patternNr]=16;
	seq_patternSet.transform[patternNr]=0;
	for(uint8_t track = 0; track < NUM_TRACKS; track++)
		trigTrackClear(&seq_patternSet.trigCondition[patternNr][track]);

#if 0


	// note that the pattern length data is no longer stored in the same way.
	// This means that loading old patterns with non-standard length, the length will be
	// ignored and a standard length used. I think it's acceptable as long as users are aware of this.

	UINT bytesRead;
	uint8_t success=1; // start off succeeding
	//uint16_t i;
	//uint8_t repeat=0;
	uint8_t next=0;

	//lcd_clear();
	//lcd_home();
	//lcd_string(PSTR("Loading pattern"));

	// ---------- Load step data first



	// load step data


	for(uint8_t pat=0; pat<NUM_PATTERN;pat++)
	{
		for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
		{

#if 1

			if( (pat == seq_activePattern) && seq_isRunning() )
			{
				f_read((FIL*)&SDFile,(void*)&seq_tmpPattern.seq_subStepPattern[trk][0],sizeof(Step)*STEPS_PER_PATTERN,&bytesRead);
			} else {
				f_read((FIL*)&SDFile,(void*)&seq_patternSet.seq_subStepPattern[pat][trk][0],sizeof(Step)*STEPS_PER_PATTERN,&bytesRead);
			}



			if(bytesRead!=sizeof(Step)*(STEPS_PER_PATTERN))
			{
				success=0;
				break; // file error, or we ran out of file (eof)
			}
#else
			for(uint8_t stp=0;stp<STEPS_PER_PATTERN; stp++)
			{
				f_read((FIL*)&SDFile,(void*)&frontParser_stepData,sizeof(Step),&bytesRead);
				if(bytesRead==sizeof(Step))
				{
					seq_patternSet.seq_subStepPattern[pat][trk][stp] = frontParser_stepData;
				} else {
					success=0;
					break; // file error, or we ran out of file (eof)
				}
			}
#endif
		}
	}

	// ---------- load the main step data next
	uint16_t mainStepData;

	for(uint8_t pat=0; pat<NUM_PATTERN;pat++)
	{
		for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
		{
			for(uint8_t bar=0;bar<NUM_BARS; bar++)
			{
				f_read((FIL*)&SDFile,(void*)&mainStepData,sizeof(uint16_t),&bytesRead);

				if( bytesRead==sizeof(uint16_t)) {

					if( (pat == seq_activePattern) && seq_isRunning() )
					{
						seq_tmpPattern.seq_mainSteps[bar][trk] = mainStepData;
					} else {
						seq_patternSet.seq_mainSteps[bar][pat][trk] = mainStepData;
					}
				}
				 else {
						success=0;
						break;
					}
			}
		}
	}

	//---------- pattern info (next/repeat)
	/*
	if(success) {
		for(i=0;i<(NUM_PATTERN);i++)
		{
			f_read((FIL*)&preset_File,(void*)&next,sizeof(uint8_t),&bytesRead);
			if(!bytesRead) {
				success=0;
				break;
			}
			f_read((FIL*)&preset_File,(void*)&repeat,sizeof(uint8_t),&bytesRead);
			if(!bytesRead) {
				success=0;
				break;
			}

			if( (i == seq_activePattern) && seq_isRunning() )
			{
				seq_tmpPattern.seq_patternSettings.nextPattern = next;
				seq_tmpPattern.seq_patternSettings.changeBar = repeat;
			} else {
				seq_patternSet.seq_patternSettings[i].nextPattern = next;
				seq_patternSet.seq_patternSettings[i].changeBar = repeat;
			}

		}
	}
	*/

	// ------------ shuffle settings
	if(success) {
		//load the shuffle settings
		f_read((FIL*)&SDFile,(void*)&activeParameters[PAR_SHUFFLE],sizeof(uint8_t),&bytesRead);
		//and update on cortex
		if(bytesRead)
			//frontPanel_sendData(SEQ_CC,SEQ_SHUFFLE,parameter_values[PAR_SHUFFLE]);
			seq_setShuffle(activeParameters[PAR_SHUFFLE]/127.f);
		else {
			success=0;
		}
	}

	// ----------- Pattern/track lengths
	// -- AS this might not exist in the saved data file, we still want success
	if(success) {


		for(uint8_t pat=0; pat<NUM_PATTERN;pat++)
		{
			for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
			{
				f_read((FIL*)&SDFile,(void*)&next,sizeof(uint8_t),&bytesRead);


				if( (pat == seq_activePattern) && seq_isRunning() )
				{
					seq_tmpPattern.length[trk] = next;
				} else {
					seq_patternSet.length[pat][trk] = next;
				}
			}
		}

		// signal new pattern after receiving all the data
		/*
		if( seq_isRunning() ) {
			seq_newPatternAvailable = 1;
		}
		*/

		success=1; // just to document that we don't consider this a failure, we just didn't read the bytes for this
	}

	return success;
#else

	// note that the pattern length data is no longer stored in the same way.
	// This means that loading old patterns with non-standard length, the length will be
	// ignored and a standard length used. I think it's acceptable as long as users are aware of this.

	UINT bytesRead;
	uint8_t success=1; // start off succeeding
	uint8_t next=0;

	// ---------- Load step data first

	// load step data



	for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
	{

		preset_readStepTrack(patternNr,trk,&bytesRead);

		if(bytesRead!=sizeof(Step)*(STEPS_PER_PATTERN))
		{
			success=0;
			break; // file error, or we ran out of file (eof)
		}

		//Pattern V3 and up => flam added
		if(dataVersion > 2)
		{
			f_read((FIL*)&SDFile,(void*)&seq_patternSet.seq_stepTiming[patternNr][trk][0],sizeof(uint8_t)*STEPS_PER_PATTERN,&bytesRead);

			if(bytesRead!=sizeof(uint8_t)*(STEPS_PER_PATTERN))
			{
				success=0;
				break; // file error, or we ran out of file (eof)
			}
		}

	}



	// ---------- load the main step data next
	uint16_t mainStepData;


		for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
		{
			for(uint8_t bar=0;bar<NUM_BARS; bar++)
			{
				f_read((FIL*)&SDFile,(void*)&mainStepData,sizeof(uint16_t),&bytesRead);

				if( bytesRead==sizeof(uint16_t)) {
					seq_patternSet.seq_mainSteps[bar][patternNr][trk] = mainStepData;
				}
				 else {
						success=0;
						break;
					}
			}
		}



	// ------------ shuffle settings
	if(success) {
		//load the shuffle settings
		f_read((FIL*)&SDFile,(void*)&seq_patternSet.shuffle[patternNr],sizeof(uint8_t),&bytesRead);
		//and update on cortex
		if(bytesRead)
		{

			//activeParameters[PAR_SHUFFLE] = seq_patternSet.shuffle[patternNr];
			//frontPanel_sendData(SEQ_CC,SEQ_SHUFFLE,parameter_values[PAR_SHUFFLE]);

			//seq_setShuffle(activeParameters[PAR_SHUFFLE]/127.f);
		}
		else {
			success=0;
		}
	}

	// ----------- Pattern/track lengths
	// -- AS this might not exist in the saved data file, we still want success
	if(success) {

			for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
			{
				f_read((FIL*)&SDFile,(void*)&next,sizeof(uint8_t),&bytesRead);
				seq_patternSet.length[patternNr][trk] = next;
			}

		success=1; // just to document that we don't consider this a failure, we just didn't read the bytes for this
	}

	if(dataVersion > 1)
	{
		f_read((FIL*)&SDFile,(void*)&seq_patternSet.kitNr[patternNr],sizeof(uint8_t),&bytesRead);
		preset_readPatternScale(patternNr);
		preset_readFlamProbability(patternNr);
		preset_readTrigConditions(patternNr);
		preset_readFlamVelocity(patternNr);
        /* 0.2.72: a damaged PLK1 or a full pool keeps the two base locks of every
         * step and loads the pattern anyway; only the extra locks are lost. */
        if(success && !preset_readLocks(patternNr))menu_warnLocksDropped();
        preset_readSlide(patternNr);
        preset_readAccent(patternNr); // 0.2.93
		if(bytesRead == 0) success = 0;

	}

	return success;
#endif

}
//----------------------------------------------------
/*
uint8_t preset_loadPatternTemp(uint8_t presetNr)
{
#if USE_SD_CARD
	//filename in 8.3  format
	char filename[9];
	UINT bytesRead;
	uint8_t success=0;
	//sprintf(filename,"p%03d.pat",presetNr);
	preset_makeFileNameTemp(filename,presetNr,FEXT_PAT);

	//open the file
	FRESULT res = f_open((FIL*)&SDFile,filename,FA_OPEN_EXISTING | FA_READ);

	if(res!=FR_OK)
	{

		return 0; //file open error... maybe the file does not exist?
	}


	//read the preset name
	f_read((FIL*)&SDFile,(void*)preset_currentName,8,&bytesRead);
	if(bytesRead != 8)
		goto closeFile;

	if(!preset_readPatternData())
		goto closeFile;

	success=1;
	//close the file handle
closeFile:
	f_close((FIL*)&SDFile);

	//force complete repaint
	menu_repaintAll();
	// return success or failure
	return success;

#else
frontPanel_sendData(PRESET,PATTERN_LOAD,presetNr);

#endif
}
*/
//----------------------------------------------------
FRESULT preset_loadPatternSD(uint8_t presetNr)
{
#if USE_SD_CARD		
	//filename in 8.3  format
	uint8_t fileVersion = 1;
	char filename[13];
	UINT bytesRead;
	uint8_t success=0;
	//sprintf(filename,"p%03d.pat",presetNr);

	/*
	preset_makeFileNameLoad(filename,presetNr,FEXT_PAT);

	//open the file
	FRESULT res = f_open((FIL*)&SDFile,filename,FA_OPEN_EXISTING | FA_READ);
	*/
	FRESULT res = preset_makeFileNameLoad(filename,presetNr,FEXT_PAT);
	if(res!=FR_OK)
	{
		//try old filename
		preset_makeFileNameOld(filename,presetNr,FEXT_PAT);
		res = f_open((FIL*)&SDFile,filename,FA_OPEN_EXISTING | FA_READ);
		if(res!=FR_OK)
			return res; //file open error... maybe the file does not exist?
	}
	
	//read the preset name
	res = f_read((FIL*)&SDFile,(void*)savefileNames[presetNr][PATTERN_NAMES],8,&bytesRead);
	if(bytesRead != 8)
		goto closeFile;
	
	char buf[7];
	res = f_read((FIL*)&SDFile,buf,6,&bytesRead);
	//zero termination
	buf[6]=0;
	fileVersion = atoi(&buf[4]);
	buf[4] = 0; // PatV\0

	if(strcmp(buf, "PatV") == 0)
	{
		//we have a new version pattern preset >V0 (V0 has no version tag)


	}
	else
	{
		//V1 preset data without version tag -> rewind read pointer
		fileVersion = 1; //re-assign since atoi() broke the 1
		f_lseek((FIL*)&SDFile, f_tell((FIL*)&SDFile) - 6);
	}
	//f_write((FIL*)&SDFile,"PatV02",6,&bytesWritten);

	if(!preset_readPatternData(presetNr, fileVersion))
	{
		goto closeFile;
	}
	
	success=1;
	//close the file handle



closeFile:
	f_close((FIL*)&SDFile);
	
	//force complete repaint
	menu_repaintAll();
	// return success or failure
	if(success) return FR_OK;
	else return FR_INT_ERR;
	
#else
frontPanel_sendData(PRESET,PATTERN_LOAD,presetNr);

#endif
}

//----------------------------------------------------
FRESULT preset_savePatternRAM(uint8_t presetNr)
{

	//check if current slot or new slot
	if(presetNr == seq_activePattern)
	{
		//### Current Slot ###
		//write current (changed) pattern to backup buffer, to make changes permanent
		seq_copyPatternToBackupBuffer(presetNr);
	}
	else
	{
		//### NEW SLOT ###
		//- write current (changed) pattern to new slot
		seq_copyPattern(seq_activePattern, presetNr);
		seq_revertActiveOnSwitch=1;
		//- change active pattern to new slot (writes backup buffer back to current slot, reverting changes being made in current slot)
		seq_setNextPattern(presetNr);
	}

	return FR_OK;
}
//----------------------------------------------------
FRESULT preset_loadPatternRAM(uint8_t presetNr)
{

	//I'm unused since there is no Pattern Load page, it just uses the pattern change/select page instead
	return FR_OK;
}
//----------------------------------------------------
//called periodically to process non blocking morph
void preset_setMorphTarget(uint8_t target)
{
	morph_slewTarget = target;
	morph_slewActive = 1;
}
static void preset_morphSlew(void)
{
	if(!morph_slewActive || systick_ticks - morph_slewLast < MORPH_SLEW_TICKS) return;
	morph_slewLast = systick_ticks;
	uint8_t current = activeParameters[PAR_MORPH];
	const uint8_t target = morph_slewTarget;
	if(current == target)
	{
		morph_slewActive = 0;
		return;
	}
	const uint8_t step = (uint8_t)(((current < target ? target - current : current - target) + 1) / 2);
	current = current < target ? (uint8_t)(current + step) : (uint8_t)(current - step);
	activeParameters[PAR_MORPH] = current;
	preset_morph(current);
}
void preset_morph_tick()
{
	preset_morphSlew();
	if(!morph_state) return;

	// A kit load uses parameterOrder because some settings depend on others.
	// Morph must use the same order and must not send placeholder CC 0.
	const uint8_t paramNr = parameterOrder[morph_index];
	const uint8_t isTargetSelector =
		(paramNr >= PAR_VEL_DEST_1 && paramNr <= PAR_VEL_DEST_6) ||
		(paramNr >= PAR_VOICE_LFO1 && paramNr <= PAR_VOICE_LFO6) ||
		(paramNr >= PAR_TARGET_LFO1 && paramNr <= PAR_TARGET_LFO6);
	if(paramNr != PAR_NONE && paramNr != PAR_BANK_CHANGE &&
	   paramNr != PAR_MORPH_KIT_DEST && !isTargetSelector)
	{
		// Audio routing always comes from the source kit.
		const uint8_t morph = (paramNr >= PAR_AUDIO_OUT1 &&
			paramNr <= PAR_AUDIO_OUT6) ? 0 : activeParameters[PAR_MORPH];
		const uint8_t val = preset_getMorphValue(paramNr, morph);
		MidiMsg msg = {0};
		msg.data2 = val;
		if(paramNr < 128)
		{
			msg.status = MIDI_CC;
			msg.data1 = (uint8_t)(paramNr + 1);
		}
		else
		{
			msg.status = CC_2;
			msg.data1 = (uint8_t)(paramNr - 128);
		}
		midiParser_ccHandler(msg,1,0,0.f);
	}

	if(++morph_index >= END_OF_SOUND_PARAMETERS)
	{
		morph_index = 0;
		morph_state = morph_again;
		morph_again = 0;
	}
}
//----------------------------------------------------
// This will determine an interpolated value between parameters
// and morph parameters and send the data to the back
// if the morph value is 0 it will just send the parameter values
// to the back
uint8_t preset_morphBusy(void)
{
	return morph_state;
}
void preset_morph(uint8_t morph)
{
#if 1
	// A running pass reads the morph value per parameter, so it keeps going and
	// one more full pass follows; restarting at 0 would starve the last
	// parameters while morph keeps changing.
	if(morph_state)
	{
		morph_again = 1;
		return;
	}
	morph_state = 1; //start morph
	morph_index = 0; //reset index
#else
	int i;
	//TODO so far only sound parameters are interpolated, no LFOs etc

	for(i=0;i<END_OF_SOUND_PARAMETERS;i++)
	{


		uint8_t val;
		
		val = interpolate(mainParameters[i],morphParameters[i],morph);

		if(i<128) {
			frontPanel_sendData(MIDI_CC,(uint8_t)i,val);

		} else {
			frontPanel_sendData(CC_2,(uint8_t)(i-128),val);

		}		
		
			
		//to omit front panel button/LED lag we have to process din dout and uart here
		//read next button

		//update LEDs
		dio_process();
		//read uart messages from sequencer
		uart_checkAndParse();
	}		
#endif
}

//----------------------------------------------------
uint8_t preset_getMorphValue(uint16_t index, uint8_t morph)
{
	// PERF sample rate is a live master control for both Morph endpoints.
	// Keep per-voice decimation in the kit interpolation.
	if(index == PAR_VOICE_DECIMATION_ALL || preset_isProjectFx(index))
		return activeParameters[index];
	return interpolate(activeParameters[index],morphParameters[index],morph);
};
//----------------------------------------------------

FRESULT preset_createProject(uint8_t presetNr)
{


	//create default globals

	//clear all patterns

	//clear all kits

	//clear all songs

	//load init kit


	int i;

	preset_loadDefaultGlobals();
	//give active song pointer a proper value
	seq_activeSong = seq_songData[0];

	memset(seq_songData, SONG_END, sizeof(uint8_t) * MAX_SONG_LENGTH * NUM_KIT_SLOTS);
	seq_songData[0][0] = 0;


	//memset(seq_stepIndex,0,NUM_TRACKS);
//	memset(seq_lastMasterStep,0,NUM_TRACKS);


	for(i=0;i<NUM_PATTERN;i++)
	{
		//seq_patternSet.seq_patternSettings[i].changeBar 	= 0;	//default setting: zero repeats (play once then change)
		//seq_patternSet.seq_patternSettings[i].nextPattern 	= i;	//default setting: repeat same pattern
		seq_clearPattern(i); // will clear all tracks in the pattern
		preset_init(i); //set all kits to init sound
	}

	sprintf(savefileNames[presetNr][PROJECT_NAMES], "Init");
	seq_flamResetPresets();
	preset_flamDirty = 0;
	preset_flamShowEdited();

#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	// 0.2.60: keep audio running while the tmp folder is deleted
	const uint8_t timerWasOn = (htim2.Instance->CR1 & TIM_CR1_CEN) && (htim2.Instance->DIER & TIM_IT_UPDATE);
	if(!timerWasOn) HAL_TIM_Base_Start_IT(&htim2);
#endif
	preset_clearTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	if(!timerWasOn) HAL_TIM_Base_Stop_IT(&htim2);
#endif

	return FR_OK;
}
//----------------------------------------------------
// **SAVEALL
// save all settings (global, pattern, kit)
// or save performance settings (pattern, kit)

/* Only directories claimed by this save protocol may be rotated or removed.
 * A user's existing .bak/.new folder must never be recursively erased. */
static FRESULT preset_saveDirTag(const char *dir, uint8_t create)
{
	char path[32];
	FILINFO info;
	snprintf(path, sizeof(path), "%s/LXRSV1.ID", dir);
	FRESULT res = f_stat(path, &info);
	if(res == FR_OK)
		return !info.fsize && !(info.fattrib & AM_DIR) ? FR_OK : FR_EXIST;
	if(res != FR_NO_FILE || !create) return res;
	res = f_open(&SDFile, path, FA_CREATE_NEW | FA_WRITE);
	if(res == FR_OK) res = f_close(&SDFile);
	return res;
}

static FRESULT preset_projectStatus(uint8_t slot, const char *live)
{
	FILINFO info;
	FRESULT res = f_stat(live, &info);
	if(res == FR_NO_FILE) {
		char backup[16];
		snprintf(backup, sizeof(backup), "/proj%02u.bak", (unsigned)slot);
		res = f_stat(backup, &info);
		if(res != FR_OK) return res;
		res = preset_saveDirTag(backup, 0);
		if(res != FR_OK) return res == FR_NO_FILE ? FR_EXIST : res;
		res = f_rename(backup, live);
		if(res != FR_OK) return res;
		res = f_stat(live, &info);
	}
	if(res == FR_OK && !(info.fattrib & AM_DIR)) return FR_DENIED;
	return res;
}

/* FAT can leave two names for the same cluster if power fails inside
 * f_rename. Never recursively clean an alias of the live project. */
static FRESULT preset_removeSaveDir(const char *path, DWORD liveCluster, uint8_t staging)
{
	DIR dir;
	FRESULT res = f_opendir(&dir, path);
	if(res == FR_NO_PATH || res == FR_NO_FILE) return FR_OK;
	if(res != FR_OK) return res;
	const DWORD cluster = dir.obj.sclust;
	res = f_closedir(&dir);
	if(res != FR_OK) return res;
	if(!cluster || cluster == liveCluster) return FR_DENIED;
	res = preset_saveDirTag(path, 0);
	if(res == FR_NO_FILE && staging) {
		/* Power may fail between mkdir and tagging. FatFs only unlinks empty dirs. */
		return f_unlink(path);
	}
	if(res != FR_OK) return res == FR_NO_FILE ? FR_EXIST : res;
	char buffer[256];
	FILINFO entry;
	snprintf(buffer, sizeof(buffer), "%s", path);
	return delete_node(buffer, sizeof(buffer), &entry, 1);
}

FRESULT preset_saveProject(uint8_t presetNr)
{
	char staged[16], backup[16], text[17];
	DWORD liveCluster = 0;
	UINT bytesWritten;
	FRESULT res;
	if(presetNr >= NUM_KIT_SLOTS) return FR_INVALID_PARAMETER;
	snprintf(currentFolder, sizeof(currentFolder), "/proj%02u", (unsigned)presetNr);
	snprintf(staged, sizeof(staged), "/proj%02u.new", (unsigned)presetNr);
	snprintf(backup, sizeof(backup), "/proj%02u.bak", (unsigned)presetNr);

	preset_saveDrumsetRam(menu_selectedPresetNr[SAVE_TYPE_KIT], 0);
	preset_savePatternRAM(seq_activePattern);
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	HAL_TIM_Base_Start_IT(&htim2);
#endif
	lcd_process_display_interrupt = 0;
	while(sendDisplayBuffer() != 0);
	lcd_clear();
	lcd_home();
	lcd_string(PSTR("Saving Project"));

	res = preset_projectStatus(presetNr, currentFolder);
	if(res == FR_OK) {
		DIR dir;
		res = f_opendir(&dir, currentFolder);
		if(res != FR_OK) goto done;
		liveCluster = dir.obj.sclust;
		res = f_closedir(&dir);
		if(res != FR_OK) goto done;
	} else if(res != FR_NO_FILE) goto done;

	res = preset_removeSaveDir(staged, liveCluster, 1);
	if(res != FR_OK) goto done;
	if(liveCluster) {
		res = preset_removeSaveDir(backup, liveCluster, 0);
		if(res != FR_OK) goto done;
	}
	res = f_mkdir(staged);
	if(res != FR_OK) goto done;
	res = preset_saveDirTag(staged, 1);
	if(res != FR_OK) goto done;
	res = f_chdir(staged);
	if(res != FR_OK) goto done;
	res = f_open(&SDFile, "prj.nfo", FA_CREATE_NEW | FA_WRITE);
	if(res != FR_OK) goto done;
	res = f_write(&SDFile, savefileNames[presetNr][PROJECT_NAMES], 8, &bytesWritten);
	if(res == FR_OK && bytesWritten == 8) res = preset_writeFlamPresets();
	res = preset_finishFile(res, 8u + FLAM_FILE_BYTES);
	if(res != FR_OK) goto done;
	res = preset_saveGlobals();
	for(uint8_t i = 0; res == FR_OK && i < NUM_KIT_SLOTS; i++) {
		snprintf(text, sizeof(text), "%u%%", (unsigned)i * 100u / NUM_KIT_SLOTS);
		lcd_setcursor(0,2);
		lcd_string(text);
		res = preset_saveDrumsetSD(i, 0);
		if(res == FR_OK) res = preset_savePatternSD(i);
		if(res == FR_OK) res = preset_saveSongSD(i);
	}
	if(res != FR_OK) goto done;

	res = f_chdir("/");
	if(res != FR_OK) goto done;
	if(liveCluster) {
		res = preset_saveDirTag(currentFolder, 1);
		if(res != FR_OK) goto done;
		res = f_rename(currentFolder, backup);
		if(res != FR_OK) goto done;
	}
	res = f_rename(staged, currentFolder);
	if(res != FR_OK) {
		if(liveCluster) preset_projectStatus(presetNr, currentFolder);
		goto done;
	}
	preset_flamDirty = 0;
	res = preset_clearTmpFolder();
done:
	preset_initTmpFolder();
	lcd_process_display_interrupt = 1;
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	HAL_TIM_Base_Stop_IT(&htim2);
#endif
	return res;
}
//----------------------------------------------------
FRESULT preset_loadSongSD(uint8_t songNr)
{
	FRESULT res;
	char filename[13];
	UINT bytesRead;

	/*
	preset_makeFileNameLoad(filename,songNr,FEXT_SONG);
	//open the file
	res = f_open((FIL*)&SDFile,filename,FA_OPEN_EXISTING | FA_READ);
	*/
	res = preset_makeFileNameLoad(filename,songNr,FEXT_SONG);

	if(res!=FR_OK)
	{
		//try old filename
		preset_makeFileNameOld(filename,songNr,FEXT_SONG);
		res = f_open((FIL*)&SDFile,filename,FA_OPEN_EXISTING | FA_READ);
		if(res!=FR_OK)
			return res; //file open error... maybe the file does not exist?
	}

	//first the song name
	res = f_read((FIL*)&SDFile,(void*)savefileNames[songNr][SONG_NAMES],8,&bytesRead);

	if((!bytesRead) || (res != FR_OK))
		goto closeFile;

	if(preset_isNameEmpty(savefileNames[songNr][SONG_NAMES]))
	{
		sprintf((void*)savefileNames[songNr][SONG_NAMES], "Empty");
	}

	//read song data
	res = f_read((FIL*)&SDFile, seq_songData[songNr], MAX_SONG_LENGTH, &bytesRead);

	closeFile:
		//close the file handle
		f_close((FIL*)&SDFile);
		return res;
}
//----------------------------------------------------
FRESULT preset_saveSongSD(uint8_t songNr)
{
	FRESULT res;
	char filename[13];
	unsigned int bytesWritten;
	preset_makeFileNameSave(filename,songNr,FEXT_SONG, savefileNames[songNr][SONG_NAMES]);
	//open the file
	res = f_open((FIL*)&SDFile,filename,FA_CREATE_ALWAYS | FA_WRITE);
	if(res!=FR_OK)
		return res; //file open error... maybe the file does not exist?
	//write name
	res = f_write((FIL*)&SDFile,(void*)savefileNames[songNr][SONG_NAMES],8,&bytesWritten);
	if (res != FR_OK)
	{
		f_close((FIL*)&SDFile);
		return res;
	}

	//write song data
	res = f_write((FIL*)&SDFile,seq_songData[songNr],MAX_SONG_LENGTH,&bytesWritten);
	if (res != FR_OK)
	{
		f_close((FIL*)&SDFile);
		return res;
	}

	//close the file handle
	return preset_finishFile(res, 8u + MAX_SONG_LENGTH);
}


//----------------------------------------------------
void preset_loadProjectNames(uint8_t projectNr)
{
	FRESULT res;


	//change project folder
	sprintf(currentFolder, "/proj%02d", projectNr);

	res = preset_projectStatus(projectNr, currentFolder);
	if(res != FR_OK || f_chdir(currentFolder) != FR_OK) {
		strcpy(savefileNames[projectNr][PROJECT_NAMES], res == FR_NO_FILE ? "Empty" : "SD Error");
		return;
	}

	//Load Project name

		UINT bytesRead;

		//open the file
		res = f_open((FIL*)&SDFile,"prj.nfo",FA_OPEN_EXISTING | FA_READ);

		//read preset name
		//first the preset name
		res=f_read((FIL*)&SDFile,(void*)savefileNames[projectNr][PROJECT_NAMES],8,&bytesRead);
		if(bytesRead != 8) {
			res=FR_DISK_ERR;
		}
		if(preset_isNameEmpty(savefileNames[projectNr][PROJECT_NAMES]))
		{
			sprintf((void*)savefileNames[projectNr][PROJECT_NAMES], "Empty");
		}

		f_close((FIL*)&SDFile);
		preset_initTmpFolder();

}
//----------------------------------------------------
FRESULT preset_loadProject(uint8_t presetNr, uint8_t clearTmp)
{
	FRESULT res;

	char text[17];

	lcd_process_display_interrupt = 0;
	while(sendDisplayBuffer() != 0);

#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	HAL_TIM_Base_Start_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

	if(clearTmp)
	{
		preset_clearTmpFolder();
	}
	/*
	MX_FATFS_ReInit();
	f_mount(0, (TCHAR const*)SDPath, 0); //un-mount
	memset((FATFS*)&SDFatFS,0,sizeof(FATFS)); //clear FS object to force reinit

	res = f_mount((FATFS*)&SDFatFS, (TCHAR const*)SDPath,1);
	if( res != FR_OK)
	{
		return res;
	}
*/

	lcd_clear();
	lcd_home();
	memcpy(text,"Loading ",8);
	memcpy(text+8,savefileNames[presetNr][PROJECT_NAMES],8);
	text[16]='\0';
	lcd_string(text);
	lcd_setcursor(0,2);
	lcd_string(PSTR("0%"));

	//change project folder
	sprintf(currentFolder, "/proj%02d", presetNr);

	res = preset_projectStatus(presetNr, currentFolder);
	if(res == FR_NO_FILE) res = f_mkdir(currentFolder);
	if(res == FR_OK) res = f_chdir(currentFolder);
	if(res != FR_OK) {
		lcd_process_display_interrupt = 1;
		preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
		HAL_TIM_Base_Stop_IT(&htim2);
#endif
		return res;
	}
	//load data

#if 1

	//Load Project name

	UINT bytesRead;

	//open the file
	seq_flamResetPresets();
	preset_flamDirty = 0;
	res = f_open((FIL*)&SDFile,"prj.nfo",FA_OPEN_EXISTING | FA_READ);
	if (res != FR_OK)
	{
		lcd_process_display_interrupt = 1;
		preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
		return res;
	}
	//read preset name
	//first the preset name
	res = f_read((FIL*)&SDFile,(void*)savefileNames[presetNr][PROJECT_NAMES],8,&bytesRead);
	if (res != FR_OK)
	{
		lcd_process_display_interrupt = 1;
		preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
		f_close((FIL*)&SDFile);
		return res;
	}

	if(bytesRead != 8) {
		sprintf((void*)savefileNames[presetNr][PROJECT_NAMES], "Empty");
		/*
		//res=FR_DISK_ERR;
		lcd_process_display_interrupt = 1;
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
		f_close((FIL*)&SDFile);
		return res;
		*/
	}

	else if(preset_isNameEmpty(savefileNames[presetNr][PROJECT_NAMES]))
	{
		sprintf((void*)savefileNames[presetNr][PROJECT_NAMES], "Empty");
	}
	// 0.2.61: flam presets after the name; older projects keep the factory presets
	if(bytesRead == 8) preset_readFlamPresets();
	preset_flamShowEdited();
	//close the file
	f_close((FIL*)&SDFile);

	//load globals
	// Refresh from the name actually read from this project's prj.nfo.
	memcpy(text,"Loading ",8);
	memcpy(text+8,savefileNames[presetNr][PROJECT_NAMES],8);
	text[16]='\0';
	lcd_home();
	lcd_string(text);
	perf_clearLoop();
	preset_loadGlobals();
	//load all drumkits, patterns and songs
	for(uint8_t i=0;i<NUM_KIT_SLOTS;i++)
	{

		sprintf(text, "%d%%", (uint8_t)(i/(float)NUM_KIT_SLOTS * 100.f));
		lcd_setcursor(0,2);
		lcd_string(text);

		//FR_NO_FILE just means an incomplete project and is no reason to abort!
		res = preset_loadDrumsetSD(i, 0);
		if ((res != FR_OK) && (res != FR_NO_FILE))
		{
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
			f_close((FIL*)&SDFile);
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
			return res;
		}
		res = preset_loadPatternSD(i);
		if ((res != FR_OK) && (res != FR_NO_FILE))
		{
			f_close((FIL*)&SDFile);
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
			return res;
		}
		res = preset_loadSongSD(i);
		if ((res != FR_OK) && (res != FR_NO_FILE))
		{
			f_close((FIL*)&SDFile);
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
			return res;
		}
	}

	res = FR_OK;

	//init morph target to peset 0
	morphParameters = mainParameters[0];
	// 0.2.89: start at the pattern that played when the project was saved, its bank shown
	if(preset_projectPattern < NUM_PATTERN) {
		menu_playedPattern = preset_projectPattern;
		menu_shownPattern = preset_projectPattern;
		seq_activePattern = preset_projectPattern;
		seq_pendingPattern = preset_projectPattern;
		menu_selectedPresetNr[SAVE_TYPE_PATTERN] = preset_projectPattern;
		menu_activePatternBank = (uint8_t)(preset_projectPattern/16u);
		frontPanel_sendData(SEQ_CC,SEQ_SET_SHOWN_PATTERN,preset_projectPattern);
	}
	// The previous project's edit backup must not overwrite a freshly loaded
	// pattern when the pending pattern is activated below.
	seq_copyPatternToBackupBuffer(seq_activePattern);
	if(activeParameters[PAR_LOAD_INT_SEND]) seq_applyIntSends(seq_activePattern);


	//if pattern change mode is 'auto' load corresponding kit
	if(activeParameters[PAR_PATTERN_MODE] >= 1)
	{
		activeParameters[PAR_PATTERN_MODE] = 1; //prevent a value of 2 (skip next autoload) being saved with the project
		preset_loadDrumsetRam(seq_patternSet.kitNr[seq_activePattern], 0, 1);
		menu_selectedPresetNr[SAVE_TYPE_KIT] = seq_patternSet.kitNr[seq_activePattern];
		menu_loadedPresetNr[CURRENT_KIT] = seq_patternSet.kitNr[seq_activePattern];
		//refresh backup buffer with new kit, to prevent corruption when changin patterns with PCM=auto
		seq_copyPatternToBackupBuffer(seq_activePattern);
	}
	else
	{
		//init to preset 1
		//TODO maybe init to current active preset nr???
		preset_loadDrumsetRam(0,0, 1);
		menu_selectedPresetNr[SAVE_TYPE_KIT] = 0;
		menu_loadedPresetNr[CURRENT_KIT] = 0;
		seq_copyPatternToBackupBuffer(seq_activePattern);

	}

	preset_saveLastUsedProjectNrToSD(presetNr);

	//change pattern to pat 1
	seq_setNextPattern(0);

	lcd_process_display_interrupt = 1;
	preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

	return res;
#else
#if USE_SD_CARD
	//filename in 8.3  format
	char filename[GEN_BUF_LEN];
	UINT bytesRead;
	uint16_t remain;
	uint8_t siz;
	uint8_t version=0;
	//sprintf(filename,"p%03d.snd",presetNr);
	if(isAll)
		preset_makeFileName(filename,presetNr,FEXT_ALL);
	else
		preset_makeFileName(filename,presetNr,FEXT_PROJ);

	//open the file
	FRESULT res = f_open((FIL*)&SDFile,filename,FA_OPEN_EXISTING | FA_READ);

	if(res!=FR_OK)
		return; //file open error... maybe the file does not exist?

	//first the preset name
	f_read((FIL*)&SDFile,(void*)savefileNames[KIT_NAMES][presetNr],8,&bytesRead);
	if(!bytesRead)
		goto closeFile;

	// read version number and make sure its valid
	f_read((FIL*)&SDFile,&version,1,&bytesRead);
	if(!bytesRead || version > FILE_VERSION)
		goto closeFile;

	if(isAll){
		// read global data
		if(!preset_readGlobalData())
			goto closeFile;
		// size of padding after globals
		remain=	64- (PAR_CPU_USE - PAR_BEGINNING_OF_GLOBALS);

	} else {
		// read bpm
		f_read((FIL*)&SDFile,&activeParameters[PAR_BPM],1,&bytesRead);
		if(!bytesRead)
			goto closeFile;

		// size of padding after these
		if(version>1) {
			// read pat reset bit
			f_read((FIL*)&SDFile,&activeParameters[PAR_BAR_RESET_MODE],1,&bytesRead);
			if(!bytesRead)
				goto closeFile;
			remain=	64- (1+1);
		} else
			remain=0; // version 1 didn't have padding for performances
	}

	while(remain){
		if(remain < GEN_BUF_LEN)
			siz=(uint8_t)remain;
		else
			siz=GEN_BUF_LEN;
		f_read((FIL*)&SDFile, filename, siz, &bytesRead);
		if(bytesRead !=siz)
			goto closeFile;
		remain -=siz;
	}



	// read kit data
	res=preset_readDrumsetData(presetNr, 0);
	if(res!=FR_OK)
		goto closeFile;

	// read padding
	_Static_assert(END_OF_SOUND_PARAMETERS + SNARE_NOISE_KIT_BYTES + LFO_EXTRA_BYTES + RPS_EXTRA_BYTES + INS_EXTRA_BYTES + GLD_EXTRA_BYTES <= 512, "kit fits the project slot");
	remain = 512 - (END_OF_SOUND_PARAMETERS + SNARE_NOISE_KIT_BYTES + LFO_EXTRA_BYTES + RPS_EXTRA_BYTES + INS_EXTRA_BYTES + GLD_EXTRA_BYTES);
	while(remain){
		if(remain < GEN_BUF_LEN)
			siz=(uint8_t)remain;
		else
			siz=GEN_BUF_LEN;
		f_read((FIL*)&SDFile, filename, siz, &bytesRead);
		if(bytesRead !=siz)
			goto closeFile;
		remain -=siz;
	}


	// read pattern data
	/*//temporary removed
	if(!preset_readPatternData())
		goto closeFile;
		*/



closeFile:
	//close the file handle
	f_close((FIL*)&SDFile);

	// send drumset parameters to back
	preset_sendDrumsetParameters();

	// send global params
	menu_sendAllGlobals();

	//force complete repaint
	menu_repaintAll();

#else
	frontPanel_sendData(PRESET,PRESET_LOAD,presetNr);
#endif
#endif
}
//----------------------------------------------------

static void preset_makeFileNameOld(char *buf, uint8_t num, uint8_t type)
{

	const char *ext;
	buf[0]='p';
	numtostrpu(&buf[1],num,'0');
	switch(type) {
	case FEXT_SOUND:
		ext=PSTR(".snd");
		break;
	case FEXT_PAT:
		ext=PSTR(".pat");
		break;
	case FEXT_ALL:
		ext=PSTR(".all");
		break;
	default:
	case FEXT_PROJ:
		ext=PSTR(".prj");
		break;

	case FEXT_SONG:
		ext=PSTR(".sng");
		break;
	}
	strcpy(&buf[4],ext);

};


//load uses wildcard to find a name of the pattern 00-*.ext
static FRESULT preset_makeFileNameLoad(char *buf, uint8_t num, uint8_t type)
{

	FRESULT fr;     /* Return value */
    DIR dj;         /* Directory object */
    FILINFO fno;    /* File information */
	char selected[13] = {0};

	const char *ext;
	numtostrpu_2Bytes(&buf[0],num,'0');
	buf[2] = '-';
	buf[3] = '*';

	switch(type) {
	case FEXT_SOUND:
		ext=PSTR(".snd");
		break;
	case FEXT_PAT:
		ext=PSTR(".pat");
		break;
	case FEXT_ALL:
		ext=PSTR(".all");
		break;
	default:
	case FEXT_PROJ:
		ext=PSTR(".prj");
		break;

	case FEXT_SONG:
		ext=PSTR(".sng");
		break;
	}
	strcpy(&buf[4],ext);
	buf[8] = 0;


    fr = f_findfirst(&dj, &fno, "", buf);  /* Start to search for preset files */
	while(fr == FR_OK && fno.fname[0])
	{
		// Old cards can contain both "00-.PAT" and "00-NAME.PAT".
		// Prefer the named file; the blank-named copy may contain no notes.
		if(!selected[0] || fno.fname[3] != '.')
		{
			strncpy(selected, fno.fname, sizeof(selected) - 1);
			selected[sizeof(selected) - 1] = 0;
		}
		if(selected[0] && selected[3] != '.')
			break;
		fr = f_findnext(&dj, &fno);
	}
	f_closedir(&dj);
	if(fr != FR_OK)
		return fr;
	if(selected[0])
		return f_open((FIL*)&SDFile,selected,FA_OPEN_EXISTING | FA_READ);

    return FR_NO_FILE;
}

/* Cross-project transfer uses absolute paths. In particular, it must not
 * f_chdir() into the source: currentFolder and the running project stay put. */
static FRESULT preset_findProjectItemPath(uint8_t project,uint8_t slot,uint8_t pattern,char path[32])
{
    if(project>=NUM_KIT_SLOTS || slot>=NUM_KIT_SLOTS || pattern>1)return FR_INVALID_PARAMETER;
    const char *ext=pattern?"pat":"snd";
    char dirName[16],mask[16],selected[13]={0};
    DIR dir;
    FILINFO info;
    sprintf(dirName,"/proj%02u",project);
    sprintf(mask,"%02u-*.%s",slot,ext);
    FRESULT result=f_findfirst(&dir,&info,dirName,mask);
    if(result!=FR_OK)return result;
    while(result==FR_OK && info.fname[0]) {
        if(!selected[0] || info.fname[3]!='.') {
            strncpy(selected,info.fname,sizeof(selected)-1);
            selected[sizeof(selected)-1]=0;
        }
        if(selected[0] && selected[3]!='.')break;
        result=f_findnext(&dir,&info);
    }
    f_closedir(&dir);
    if(result!=FR_OK)return result;
    if(selected[0])sprintf(path,"%s/%s",dirName,selected);
    else sprintf(path,"%s/p%03u.%s",dirName,slot,ext);
    return FR_OK;
}

FRESULT preset_getProjectItemName(uint8_t project,uint8_t slot,uint8_t pattern,char name[9])
{
    char path[32];
    FIL file;
    UINT read=0;
    FRESULT result=preset_findProjectItemPath(project,slot,pattern,path);
    if(result!=FR_OK)return result;
    result=f_open(&file,path,FA_READ|FA_OPEN_EXISTING);
    if(result!=FR_OK)return result;
    result=f_read(&file,name,8,&read);
    f_close(&file);
    if(result!=FR_OK || read!=8)return FR_DISK_ERR;
    name[8]=0;
    for(uint8_t i=0;i<8;i++)if((uint8_t)name[i]<32 || (uint8_t)name[i]==127)name[i]=' ';
    return FR_OK;
}

/* The running project lives in RAM and /tmp; /projNN is only its saved state.
 * Saved slot files in /tmp replace the project's files at boot. */
static void preset_tmpSlotMask(uint8_t slot,uint8_t pattern,char mask[16],char oldPath[20])
{
    const char *ext=pattern?"pat":"snd";
    sprintf(mask,"%02u-*.%s",slot,ext);
    sprintf(oldPath,"/tmp/p%03u.%s",slot,ext);
}
static uint8_t preset_tmpHasItem(uint8_t slot,uint8_t pattern)
{
    char mask[16],oldPath[20];
    DIR dir;
    FILINFO info;
    preset_tmpSlotMask(slot,pattern,mask,oldPath);
    const FRESULT result=f_findfirst(&dir,&info,"/tmp",mask);
    const uint8_t found=(uint8_t)(result==FR_OK && info.fname[0]);
    if(result==FR_OK)f_closedir(&dir);
    return (uint8_t)(found || f_stat(oldPath,&info)==FR_OK);
}
static FRESULT preset_removeTmpItem(uint8_t slot,uint8_t pattern)
{
    char mask[16],oldPath[20],path[24];
    DIR dir;
    FILINFO info;
    preset_tmpSlotMask(slot,pattern,mask,oldPath);
    FRESULT result=FR_OK;
    /* A find handle cannot survive the delete, so restart after each one. */
    while(result==FR_OK) {
        result=f_findfirst(&dir,&info,"/tmp",mask);
        if(result!=FR_OK)break;
        const uint8_t found=(uint8_t)(info.fname[0]!=0);
        if(found)sprintf(path,"/tmp/%s",info.fname);
        f_closedir(&dir);
        if(!found)break;
        result=f_unlink(path);
    }
    if(result==FR_OK) {
        result=f_unlink(oldPath);
        if(result==FR_NO_FILE)result=FR_OK;
    }
    return result;
}
FRESULT preset_loadTransferredItem(uint8_t project,uint8_t slot,uint8_t pattern)
{
    char folder[16];
    sprintf(folder,"/proj%02u",project);
    FRESULT result=f_chdir(folder);
    if(result!=FR_OK)return result;
    result=pattern?preset_loadPatternSD(slot):preset_loadDrumsetSD(slot,0);
    preset_initTmpFolder();
    if(result==FR_OK)result=preset_removeTmpItem(slot,pattern);
    return result;
}
FRESULT preset_transferRefreshActivePattern(void)
{
    /* The edit backup and the tmp.pat autosave would both restore the old pattern. */
    seq_copyPatternToBackupBuffer(seq_activePattern);
    preset_patDirty=0;
    return preset_saveTmpPat();
}

#define TRANSFER_V2_KIT_OFFSET (14u + 7u*64u*7u + 4u*7u*2u + 1u + 7u)
static uint32_t preset_transferKitOffset(const uint8_t header[14])
{
    if(!memcmp(header+8,"PatV03",6))return TRANSFER_V3_KIT_OFFSET;
    if(!memcmp(header+8,"PatV02",6))return TRANSFER_V2_KIT_OFFSET;
    return 0;
}
FRESULT preset_getProjectPatternKit(uint8_t project,uint8_t slot,uint8_t *kitSlot)
{
    char path[32];
    FIL file;
    uint8_t header[14];
    UINT read=0;
    FRESULT result=preset_findProjectItemPath(project,slot,1,path);
    if(result!=FR_OK)return result;
    result=f_open(&file,path,FA_READ|FA_OPEN_EXISTING);
    if(result!=FR_OK)return result;
    result=f_read(&file,header,sizeof(header),&read);
    uint32_t offset=read==sizeof(header)?preset_transferKitOffset(header):0;
    if(result==FR_OK && (!offset || f_size(&file)<=offset))result=FR_INVALID_OBJECT;
    if(result==FR_OK)result=f_lseek(&file,offset);
    if(result==FR_OK)result=f_read(&file,kitSlot,1,&read);
    f_close(&file);
    if(result==FR_OK && (read!=1 || *kitSlot>=NUM_KIT_SLOTS))result=FR_INVALID_OBJECT;
    return result;
}
FRESULT preset_findFreeProjectKit(uint8_t project,uint8_t *kitSlot)
{
    char name[9];
    if(project>=NUM_KIT_SLOTS)return FR_INVALID_PARAMETER;
    for(uint8_t slot=0;slot<NUM_KIT_SLOTS;slot++) {
        FRESULT result=preset_getProjectItemName(project,slot,0,name);
        if(result==FR_NO_FILE || result==FR_NO_PATH) {
            if(project==menu_loadedPresetNr[CURRENT_PROJECT] && preset_tmpHasItem(slot,0))continue;
            *kitSlot=slot;
            return FR_OK;
        }
        if(result!=FR_OK)return result;
    }
    return FR_DENIED;
}

/* sourceFile, when set, replaces the source project and slot lookup. */
static FRESULT preset_copyItem(uint8_t sourceProject, uint8_t sourceSlot, const char *sourceFile,
        uint8_t targetProject, uint8_t targetSlot, uint8_t pattern, uint8_t overwrite,
        uint8_t kitOverride)
{
    if((!sourceFile && (sourceProject>=NUM_KIT_SLOTS || sourceSlot>=NUM_KIT_SLOTS ||
                        sourceProject==targetProject)) ||
       targetProject>=NUM_KIT_SLOTS || targetSlot>=NUM_KIT_SLOTS ||
       pattern>1 || overwrite>1 ||
       (kitOverride<NUM_KIT_SLOTS && !pattern)) return FR_INVALID_PARAMETER;
    const char *ext=pattern?"pat":"snd";
    char targetDir[16],mask[16],sourcePath[32],targetPath[32],tempPath[32],oldTarget[32],backupPath[32];
    char existing[13]={0};
    FILINFO info;
    DIR dir;
    FIL input,output;
    FRESULT result;
    UINT read=0,written=0;
    uint8_t buffer[256];
    uint32_t overrideOffset=0;
    sprintf(targetDir,"/proj%02u",targetProject);
    result=f_stat(targetDir,&info);
    if(result==FR_NO_FILE)result=f_mkdir(targetDir);
    if(result!=FR_OK) return result;
    sprintf(mask,"%02u-*.%s",targetSlot,ext);
    result=f_findfirst(&dir,&info,targetDir,mask);
    if(result!=FR_OK)return result;
    while(result==FR_OK && info.fname[0]) {
        if(existing[0]){f_closedir(&dir);return FR_DENIED;}
        strncpy(existing,info.fname,sizeof(existing)-1);
        existing[sizeof(existing)-1]=0;
        result=f_findnext(&dir,&info);
    }
    f_closedir(&dir);
    if(result!=FR_OK)return result;
    sprintf(oldTarget,"%s/p%03u.%s",targetDir,targetSlot,ext);
    result=f_stat(oldTarget,&info);
    if(result==FR_OK) {
        if(existing[0])return FR_DENIED;
        sprintf(existing,"p%03u.%s",targetSlot,ext);
    } else if(result!=FR_NO_FILE)return result;
    if(existing[0] && !overwrite)return FR_EXIST;
    if(!overwrite && targetProject==menu_loadedPresetNr[CURRENT_PROJECT] &&
       preset_tmpHasItem(targetSlot,pattern))return FR_EXIST;
    if(existing[0])sprintf(targetPath,"%s/%s",targetDir,existing);
    else sprintf(targetPath,"%s/%02u-IMPRT.%s",targetDir,targetSlot,ext);
    sprintf(tempPath,"%s/%02u-TMP.tmp",targetDir,targetSlot);
    sprintf(backupPath,"%s/%02u-BAK.tmp",targetDir,targetSlot);
    result=f_stat(backupPath,&info);
    if(result==FR_OK)return FR_DENIED;
    if(result!=FR_NO_FILE)return result;
    result=f_stat(tempPath,&info);
    if(result==FR_OK)return FR_DENIED;
    if(result!=FR_NO_FILE)return result;
    if(sourceFile)strcpy(sourcePath,sourceFile);
    else {
        result=preset_findProjectItemPath(sourceProject,sourceSlot,pattern,sourcePath);
        if(result!=FR_OK)return result;
    }
    result=f_open(&input,sourcePath,FA_READ|FA_OPEN_EXISTING);
    if(result!=FR_OK)return result;
    if(kitOverride<NUM_KIT_SLOTS) {
        result=f_read(&input,buffer,14,&read);
        overrideOffset=read==14?preset_transferKitOffset(buffer):0;
        if(result==FR_OK && (!overrideOffset || f_size(&input)<=overrideOffset))
            result=FR_INVALID_OBJECT;
        if(result==FR_OK)result=f_lseek(&input,0);
        if(result!=FR_OK){f_close(&input);return result;}
    }
    result=f_open(&output,tempPath,FA_WRITE|FA_CREATE_NEW);
    if(result!=FR_OK){f_close(&input);return result;}
    do {
        result=f_read(&input,buffer,sizeof(buffer),&read);
        if(result!=FR_OK || !read)break;
        result=f_write(&output,buffer,read,&written);
        if(result!=FR_OK || written!=read){result=FR_DISK_ERR;break;}
    } while(1);
    if(result==FR_OK && kitOverride<NUM_KIT_SLOTS) {
        if(f_size(&output)<=overrideOffset)result=FR_INVALID_OBJECT;
        if(result==FR_OK)result=f_lseek(&output,overrideOffset);
        if(result==FR_OK)result=f_write(&output,&kitOverride,1,&written);
        if(result==FR_OK && written!=1)result=FR_DISK_ERR;
    }
    if(result==FR_OK)result=f_sync(&output);
    if(f_close(&output)!=FR_OK && result==FR_OK)result=FR_DISK_ERR;
    f_close(&input);
    if(result==FR_OK && existing[0])result=f_rename(targetPath,backupPath);
    if(result==FR_OK) {
        result=f_rename(tempPath,targetPath);
        if(result!=FR_OK && existing[0])f_rename(backupPath,targetPath);
    }
    if(result!=FR_OK)f_unlink(tempPath);
    else if(existing[0])f_unlink(backupPath);
    return result;
}

FRESULT preset_copyProjectItem(uint8_t sourceProject, uint8_t sourceSlot,
        uint8_t targetProject, uint8_t targetSlot, uint8_t pattern, uint8_t overwrite,
        uint8_t kitOverride)
{
    return preset_copyItem(sourceProject,sourceSlot,NULL,targetProject,targetSlot,pattern,overwrite,kitOverride);
}

/* Converted LXR1 library: /LXR1/Pxxx/LXR2 holds one kit and eight patterns. */
static void preset_performanceKitPath(uint8_t performance,char path[32])
{
    sprintf(path,"/LXR1/P%03u/LXR2/00-LXR1.SND",performance);
}
static void preset_performancePatternPath(uint8_t performance,uint8_t index,char path[32])
{
    sprintf(path,"/LXR1/P%03u/LXR2/%02u-LXR1%u.PAT",performance,index,index+1u);
}
FRESULT preset_getPerformanceName(uint8_t performance,char name[9])
{
    char path[32];
    FIL file;
    UINT read=0;
    if(performance>=LXR1_PERFORMANCES)return FR_INVALID_PARAMETER;
    preset_performanceKitPath(performance,path);
    FRESULT result=f_open(&file,path,FA_READ|FA_OPEN_EXISTING);
    if(result!=FR_OK)return result;
    result=f_read(&file,name,8,&read);
    f_close(&file);
    if(result!=FR_OK || read!=8)return FR_DISK_ERR;
    name[8]=0;
    for(uint8_t i=0;i<8;i++)if((uint8_t)name[i]<32 || (uint8_t)name[i]>=127)name[i]=' ';
    return FR_OK;
}
FRESULT preset_importPerformance(uint8_t performance,uint8_t targetProject,uint8_t firstPattern,
        uint8_t overwrite,uint8_t *targetKit)
{
    char path[32],name[9];
    FILINFO info;
    uint8_t freeKit;
    if(performance>=LXR1_PERFORMANCES || firstPattern%LXR1_PATTERNS ||
       targetProject>=NUM_KIT_SLOTS || firstPattern+LXR1_PATTERNS>NUM_KIT_SLOTS)
        return FR_INVALID_PARAMETER;
    /* Check everything first, so a missing file or an occupied block writes nothing. */
    preset_performanceKitPath(performance,path);
    FRESULT result=f_stat(path,&info);
    if(result!=FR_OK)return result;
    uint8_t occupied=0;
    for(uint8_t i=0;i<LXR1_PATTERNS;i++) {
        preset_performancePatternPath(performance,i,path);
        result=f_stat(path,&info);
        if(result!=FR_OK)return result;
        result=preset_getProjectItemName(targetProject,(uint8_t)(firstPattern+i),1,name);
        if(result==FR_OK)occupied=1;
        else if(result!=FR_NO_FILE && result!=FR_NO_PATH)return result;
        if(targetProject==menu_loadedPresetNr[CURRENT_PROJECT] &&
           preset_tmpHasItem((uint8_t)(firstPattern+i),1))occupied=1;
    }
    if(occupied && !overwrite)return FR_EXIST;
    result=preset_findFreeProjectKit(targetProject,&freeKit);
    if(result!=FR_OK)return result;
    preset_performanceKitPath(performance,path);
    result=preset_copyItem(0,0,path,targetProject,freeKit,0,0,255);
    if(result!=FR_OK)return result;
    for(uint8_t i=0;i<LXR1_PATTERNS;i++) {
        preset_performancePatternPath(performance,i,path);
        result=preset_copyItem(0,0,path,targetProject,(uint8_t)(firstPattern+i),1,overwrite,freeKit);
        if(result!=FR_OK) {
            /* Patterns already copied link to this kit, so it stays unless none exist. */
            if(!i) {
                sprintf(path,"/proj%02u/%02u-IMPRT.snd",targetProject,freeKit);
                f_unlink(path);
            }
            return result;
        }
    }
    *targetKit=freeKit;
    return FR_OK;
}

FRESULT preset_copyProjectPatternWithKit(uint8_t sourceProject,uint8_t sourcePattern,
        uint8_t targetProject,uint8_t targetPattern,uint8_t overwrite,uint8_t *targetKit)
{
    uint8_t sourceKit,freeKit;
    char name[9],kitPath[32];
    FRESULT result=preset_getProjectPatternKit(sourceProject,sourcePattern,&sourceKit);
    if(result!=FR_OK)return result;
    result=preset_getProjectItemName(sourceProject,sourceKit,0,name);
    if(result!=FR_OK)return result;
    result=preset_findFreeProjectKit(targetProject,&freeKit);
    if(result!=FR_OK)return result;
    result=preset_getProjectItemName(targetProject,targetPattern,1,name);
    if(result==FR_OK && !overwrite)return FR_EXIST;
    if(result!=FR_OK && result!=FR_NO_FILE && result!=FR_NO_PATH)return result;
    result=preset_copyProjectItem(sourceProject,sourceKit,targetProject,freeKit,0,0,255);
    if(result!=FR_OK)return result;
    result=preset_copyProjectItem(sourceProject,sourcePattern,targetProject,targetPattern,1,overwrite,freeKit);
    if(result!=FR_OK) {
        /* Only the fresh, uniquely named kit from this call is removed. */
        sprintf(kitPath,"/proj%02u/%02u-IMPRT.snd",targetProject,freeKit);
        f_unlink(kitPath);
        return result;
    }
    *targetKit=freeKit;
    return FR_OK;
}

void clearIllegalCharacters(char *input, char* output, uint8_t sz)
{
	for(uint8_t i=0; i<sz; i++)
	{
		if((input[i] >= 'a') && (input[i] <= 'z')) output[i] = input[i];
		else if((input[i] >= 'A') && (input[i] <= 'Z')) output[i] = input[i];
		else if((input[i] >= '0') && (input[i] <= '9')) output[i] = input[i];
		//! # $ % & ' ( ) - @ ^ _ ` { } ~
		else if(input[i] == ' ')  output[i] = '_';
		else if(input[i] == '!')  output[i] = input[i];
		else if(input[i] == '#')  output[i] = input[i];
		else if(input[i] == '$')  output[i] = input[i];
		else if(input[i] == '%')  output[i] = input[i];
		else if(input[i] == '&')  output[i] = input[i];
		else if(input[i] == '(')  output[i] = input[i];
		else if(input[i] == ')')  output[i] = input[i];
		else if(input[i] == '-')  output[i] = input[i];
		else if(input[i] == '@')  output[i] = input[i];
		else if(input[i] == '^')  output[i] = input[i];
		else if(input[i] == '_')  output[i] = input[i];
		else if(input[i] == '`')  output[i] = input[i];
		else if(input[i] == '{')  output[i] = input[i];
		else if(input[i] == '}')  output[i] = input[i];
		else if(input[i] == '~')  output[i] = input[i];
		else if(input[i] == 0)  output[i] = input[i];
		else output[i] = '_';
	}

}
//save uses the kit name to create a filename eg 00-NAME.ext
static void preset_makeFileNameSave(char *buf, uint8_t num, uint8_t type, char *name)
{

	char clearedName[9];
	clearedName[8] = 0;
	clearIllegalCharacters(name , clearedName, 8);
	//name scheme: 01-NAME.ext
	const char *ext;
	numtostrpu_2Bytes(&buf[0],num,'0');
	buf[2] = '-';

	//copy the first 5 characters of the name to the filename if not empty
	uint8_t i=0;
	for( ; i<5; i++)
	{
		if(clearedName[i] != 0)
		{
			if(clearedName[i] == ' ')
				buf[3+i] = '_';
			else
				buf[3+i] = clearedName[i];
		}
		else
		{
			break;
		}
	}

	switch(type) {
	case FEXT_SOUND:
		ext=PSTR(".snd");
		break;
	case FEXT_PAT:
		ext=PSTR(".pat");
		break;
	case FEXT_ALL:
		ext=PSTR(".all");
		break;
	default:
	case FEXT_PROJ:
		ext=PSTR(".prj");
		break;

	case FEXT_SONG:
		ext=PSTR(".sng");
		break;
	}
	strcpy(&buf[3+i],ext);
}

//----------------------------------------------------
/*
static void preset_makeFileNameTemp(char *buf, uint8_t num, uint8_t type)
{
	const char *ext;
	buf[0]='t';
	numtostrpu(&buf[1],num,'0');
	switch(type) {
	case 0:
		ext=PSTR(".snd");
		break;
	case 1:
		ext=PSTR(".pat");
		break;
	case 2:
		ext=PSTR(".all");
		break;
	default:
	case 3:
		ext=PSTR(".prf");
		break;
	}
	strcpy(&buf[4],ext);
}
*/
