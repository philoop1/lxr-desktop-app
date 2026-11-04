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
    f_write((FIL*)&SDFile,"CND2",4,&written);
    f_write((FIL*)&SDFile,&seq_patternSet.transform[pattern],1,&written);
    f_write((FIL*)&SDFile,seq_patternSet.trigCondition[pattern],
            NUM_TRACKS*NUM_STEPS,&written);
}
static void preset_readTrigConditions(uint8_t pattern)
{
    UINT read=0;
    uint8_t magic[4]={0};
    memset(seq_patternSet.trigCondition[pattern],TRIG_COND_ALWAYS,NUM_TRACKS*NUM_STEPS);
    seq_patternSet.transform[pattern]=0;
    if(f_read((FIL*)&SDFile,magic,4,&read)!=FR_OK || read!=4)return;
    if(!memcmp(magic,"CND2",4)) {
        if(f_read((FIL*)&SDFile,&seq_patternSet.transform[pattern],1,&read)!=FR_OK || read!=1)return;
        if(seq_patternSet.transform[pattern]>3)seq_patternSet.transform[pattern]=0;
    } else if(memcmp(magic,"CND1",4))return;
    if(f_read((FIL*)&SDFile,seq_patternSet.trigCondition[pattern],NUM_TRACKS*NUM_STEPS,&read)!=FR_OK ||
       read!=NUM_TRACKS*NUM_STEPS) {
        memset(seq_patternSet.trigCondition[pattern],TRIG_COND_ALWAYS,NUM_TRACKS*NUM_STEPS);
        return;
    }
    for(uint8_t track=0;track<NUM_TRACKS;track++)
        for(uint8_t step=0;step<NUM_STEPS;step++)
            if(seq_patternSet.trigCondition[pattern][track][step]>=TRIG_COND_COUNT)
                seq_patternSet.trigCondition[pattern][track][step]=TRIG_COND_ALWAYS;
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

			f_read((FIL*)&SDFile,(void*)&seq_patternSet.seq_subStepPattern[patternNr][trk][0],sizeof(Step)*STEPS_PER_PATTERN,&bytesRead);

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

FRESULT preset_saveTmpPat()
{

	//don't save invalid pattern
	if(menu_playedPattern >= NUM_PATTERN) return FR_INVALID_PARAMETER;
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	HAL_TIM_Base_Start_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

	FRESULT res;
	UINT bytesWritten;
	uint8_t presetNr = menu_playedPattern;
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
	res = f_write((FIL*)&SDFile,(void*)&menu_playedPattern,1,&bytesWritten);
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
			f_write((FIL*)&SDFile,(const void*)&seq_patternSet.seq_subStepPattern[presetNr][trk][0],sizeof(Step)*STEPS_PER_PATTERN,&bytesWritten);

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

#endif

	//close the file
	f_close((FIL*)&SDFile);

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


FRESULT delete_node (
    TCHAR* path,    /* Path name buffer with the sub-directory to delete */
    UINT sz_buff,   /* Size of path name buffer (items) */
    FILINFO* fno    /* Name read buffer */
)
{
    UINT i, j;
    FRESULT fr;
    DIR dir;


    fr = f_opendir(&dir, path); /* Open the sub-directory to make it empty */
    if (fr != FR_OK) return fr;

    for (i = 0; path[i]; i++) ; /* Get current path length */
    path[i++] = _T('/');

    for (;;) {
        fr = f_readdir(&dir, fno);  /* Get a directory item */
        if (fr != FR_OK || !fno->fname[0]) break;   /* End of directory? */
        j = 0;
        do {    /* Make a path name */
            if (i + j >= sz_buff) { /* Buffer over flow? */
                fr = 100; break;    /* Fails with 100 when buffer overflow */
            }
            path[i + j] = fno->fname[j];
        } while (fno->fname[j++]);
        if (fno->fattrib & AM_DIR) {    /* Item is a sub-directory */
            fr = delete_node(path, sz_buff, fno);
        } else {                        /* Item is a file */
            fr = f_unlink(path);
        }
        if (fr != FR_OK) break;
    }

    path[--i] = 0;  /* Restore the path name */
    f_closedir(&dir);

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

	fr = delete_node(buff, sizeof buff / sizeof buff[0], &fno);

	preset_initTmpFolder();

	return fr;
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
}


/*------------------------------------------------------------/
/ Remove all contents of a directory
/ This function works regardless of FF_FS_RPATH.
/------------------------------------------------------------*/




FRESULT empty_directory (
    char* path      /* Working buffer filled with start directory */
)
{
	FILINFO fno;
    UINT i, j;
    FRESULT fr;
    DIR dir;

    fr = f_opendir(&dir, path);
    if (fr == FR_OK) {
        for (i = 0; path[i]; i++) ;
        path[i++] = '/';
        for (;;) {
            fr = f_readdir(&dir, &fno);
            if (fr != FR_OK || !fno.fname[0]) break;
            if (_FS_RPATH && fno.fname[0] == '.') continue;
            j = 0;
            do
                path[i+j] = fno.fname[j];
            while (fno.fname[j++]);
            if (fno.fattrib & AM_DIR) {
                fr = empty_directory(path);
                if (fr != FR_OK) break;
            }
            fr = f_unlink(path);
            if (fr != FR_OK) break;
        }
        path[--i] = '\0';
        f_closedir(&dir);
    }

    return fr;
}
//----------------------------------

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

	for(int i=8;i<END_OF_SOUND_PARAMETERS; i++)
	{
		para[i-8] = i<INIT_KIT_SIZE ? initKit[i] : 0;
	}
	preset_defaultSnareNoise(para);
	preset_defaultLfoExtras(mainLfoExtras[presetNr]);
	preset_defaultRpsExtras(mainRpsExtras[presetNr]);

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

	//copy parameters to edit buffer
	memcpy(activeParameters, mainParameters[presetNr], sizeof(uint8_t) * END_OF_SOUND_PARAMETERS);
	preset_applyLfoExtras(mainLfoExtras[presetNr]);
	preset_applyRpsExtras(mainRpsExtras[presetNr]);
	preset_sendDrumsetParameters();
	//frontPanel_sendData(PRESET,PRESET_LOAD,presetNr);

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
			uint8_t value;
			//Mod targets are not morphed!!!
			if( (i >= PAR_VEL_DEST_1) && (i <= PAR_VEL_DEST_6) )
			{
				value = activeParameters[i];
			} else if( (i >= PAR_TARGET_LFO1) && (i <= PAR_TARGET_LFO6) )
			{
				value = activeParameters[i];
			} else if( (i >= PAR_VOICE_LFO1) && (i <= PAR_VOICE_LFO6) )
			{
				value = activeParameters[i];
			} 
			else 
			{
				value = preset_getMorphValue(i,activeParameters[PAR_MORPH]);
			}					
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
}

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
		memcpy(activeParameters, mainParameters[presetNr], sizeof(uint8_t) * END_OF_SOUND_PARAMETERS);
		preset_applyLfoExtras(mainLfoExtras[presetNr]);
	preset_applyRpsExtras(mainRpsExtras[presetNr]);
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
			uint8_t value;
			//Mod targets are not morphed!!!
			if( (i >= PAR_VEL_DEST_1) && (i <= PAR_VEL_DEST_6) )
			{
				value = activeParameters[i];
			} else if( (i >= PAR_TARGET_LFO1) && (i <= PAR_TARGET_LFO6) )
			{
				value = activeParameters[i];
			} else if( (i >= PAR_VOICE_LFO1) && (i <= PAR_VOICE_LFO6) )
			{
				value = activeParameters[i];
			}
			else
			{
				value = preset_getMorphValue(i,activeParameters[PAR_MORPH]);
			}
			//f_write((FIL*)&SDFile,&value,1,&bytesWritten);
			mainParameters[presetNr][i] = value;
		}
	}
	else
	{
		//copy edit buffer to parameter array
		memcpy(mainParameters[presetNr], activeParameters, sizeof(uint8_t) * END_OF_SOUND_PARAMETERS);
		preset_captureLfoExtras(mainLfoExtras[presetNr]);
	preset_captureRpsExtras(mainRpsExtras[presetNr]);
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
	if(res != FR_OK) return res;
	//write the preset data
	preset_writeDrumsetData(presetNr, isMorph);
	
	//close the file
	f_close((FIL*)&SDFile);

	return FR_OK;
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
    uint8_t modernScale=0;
    uint8_t data[8+PERFORMANCE_EXTRA_BYTES+2+1]={0};
    UINT bytes=0;
    performance_resetExtended();
    if(f_open((FIL*)&SDFile,"MUTA.CFG",FA_OPEN_EXISTING|FA_READ)==FR_OK) {
        FRESULT result=f_read((FIL*)&SDFile,data,sizeof(data),&bytes);
        f_close((FIL*)&SDFile);
        if(result==FR_OK) {
            uint8_t count=0;
            if(bytes==sizeof(data)&&!memcmp(data,magicV4,8))count=PERFORMANCE_EXTRA_BYTES+2;
            else if(bytes==8+PERFORMANCE_EXTRA_BYTES+1&&(!memcmp(data,magicV2,8)||!memcmp(data,magicV3,8)))count=PERFORMANCE_EXTRA_BYTES;
            else if(bytes==8+18+1&&!memcmp(data,magicV1,8))count=18;
            if(count) {
                uint8_t checksum=0;
                for(uint8_t i=8;i<8+count;i++)checksum=(uint8_t)(checksum+data[i]);
                if(checksum==data[8+count]) {
                    modernScale=(uint8_t)(!memcmp(data,magicV3,8)||!memcmp(data,magicV4,8));
                    memcpy(&activeParameters[PAR_FX_OUTPUT_MODE],&data[8],count>PERFORMANCE_EXTRA_BYTES ? PERFORMANCE_EXTRA_BYTES : count);
                    if(count==PERFORMANCE_EXTRA_BYTES+2) {
                        activeParameters[PAR_PERF_RANDOM_VELO]=data[8+PERFORMANCE_EXTRA_BYTES];
                        activeParameters[PAR_PERF_AVL]=data[9+PERFORMANCE_EXTRA_BYTES];
                    }
                    performance_validateExtended();
                }
            }
        }
    }
    (void)modernScale;
    activeParameters[PAR_GLOBAL_SCALE]=PERF_SPEED_NEUTRAL; // spd is live only
    performance_prepareLoaded();
}
static FRESULT preset_savePerformanceExtension(void)
{
    uint8_t data[8+PERFORMANCE_EXTRA_BYTES+2+1]={'M','U','T','A','0','0','0','4'};
    UINT bytes=0;
    memcpy(&data[8],&activeParameters[PAR_FX_OUTPUT_MODE],PERFORMANCE_EXTRA_BYTES);
    data[8+PERFORMANCE_EXTRA_BYTES]=activeParameters[PAR_PERF_RANDOM_VELO];
    data[9+PERFORMANCE_EXTRA_BYTES]=activeParameters[PAR_PERF_AVL];
    uint8_t checksum=0;
    for(uint8_t i=8;i<sizeof(data)-1;i++)checksum=(uint8_t)(checksum+data[i]);
    data[sizeof(data)-1]=checksum;
    FRESULT result=f_open((FIL*)&SDFile,"MUTA.CFG",FA_CREATE_ALWAYS|FA_WRITE);
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

	//close the file
	f_close((FIL*)&SDFile);

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
	if(activeParameters[PAR_GLOBAL_PITCH] > 127)
		activeParameters[PAR_GLOBAL_PITCH] = 63;
	if(activeParameters[PAR_PITCH_BEND_RANGE] > 48)
		activeParameters[PAR_PITCH_BEND_RANGE] = 12;
	if(activeParameters[PAR_GLOBAL_DECAY] > 127)
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
		para=mainParameters[presetNr];

	FRESULT res=f_read((FIL*)&SDFile, para,END_OF_SOUND_PARAMETERS, &bytesRead);
	if(res==FR_OK) {
		// set to 0 for any that were not read from the file
		if(END_OF_SOUND_PARAMETERS-bytesRead)
			memset(para+bytesRead,0,END_OF_SOUND_PARAMETERS-bytesRead);
		uint8_t magic[SNARE_NOISE_KIT_BYTES]={0};
		UINT magicBytes=0;
		FRESULT magicResult=f_read((FIL*)&SDFile,magic,sizeof(magic),&magicBytes);
		preset_validateSnareExtension(para,bytesRead,magic,magicResult==FR_OK?magicBytes:0);
		if(!isMorph){preset_readLfoExtras(mainLfoExtras[presetNr]);preset_readRpsExtras(mainRpsExtras[presetNr]);}
		
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
static void preset_writePatternData(uint8_t patternNr)
{
#if 0
#else
		UINT bytesWritten;
		uint8_t length;

		//---------------  write the step data (note, vol, prob, autom.) ---------------
		for(uint8_t trk=0; trk<NUM_TRACKS;trk++)
		{
			f_write((FIL*)&SDFile,(const void*)&seq_patternSet.seq_subStepPattern[patternNr][trk][0],sizeof(Step)*STEPS_PER_PATTERN,&bytesWritten);

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
	if(res != FR_OK) return res;
	//write version tag
	res = f_write((FIL*)&SDFile,"PatV03",6,&bytesWritten);
	if(res != FR_OK) return res;

	//write pattern data
	preset_writePatternData(presetNr);

	//close the file
	f_close((FIL*)&SDFile);
	
	//reset the lcd
	menu_repaintAll();
	
	return FR_OK;
}

//----------------------------------------------------
// returns 1 on success
static uint8_t preset_readPatternData(uint8_t patternNr, uint8_t dataVersion)
{
	seq_patternSet.scale[patternNr]=16;
	seq_patternSet.transform[patternNr]=0;
	memset(seq_patternSet.trigCondition[patternNr],TRIG_COND_ALWAYS,NUM_TRACKS*NUM_STEPS);

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

		f_read((FIL*)&SDFile,(void*)&seq_patternSet.seq_subStepPattern[patternNr][trk][0],sizeof(Step)*STEPS_PER_PATTERN,&bytesRead);

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
	if(index == PAR_VOICE_DECIMATION_ALL)
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

	preset_clearTmpFolder();

	return FR_OK;
}
//----------------------------------------------------
// **SAVEALL
// save all settings (global, pattern, kit)
// or save performance settings (pattern, kit)

FRESULT preset_saveProject(uint8_t presetNr)
{
	FRESULT res;
	FILINFO fno;

	preset_saveDrumsetRam(menu_selectedPresetNr[SAVE_TYPE_KIT], 0);
	preset_savePatternRAM(seq_activePattern);

#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	HAL_TIM_Base_Start_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

	lcd_process_display_interrupt = 0;
	while(sendDisplayBuffer() != 0);

	lcd_clear();
	lcd_home();
	lcd_string(PSTR("Saving Project"));
	lcd_setcursor(0,2);
	lcd_string(PSTR("0%"));
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
	//change project folder
	sprintf(currentFolder, "/proj%02d", presetNr);

	res = f_stat(currentFolder, &fno);
	if(res == FR_NO_FILE)
	{
		res = f_mkdir(currentFolder);
		if(res == FR_OK)
		{
			f_chdir(currentFolder);
		}
		else
		{
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif


			return res;
		}
	}
	else
	{
		res = empty_directory(currentFolder);
		if(res != FR_OK)
		{
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

			return res;
		}

		res = f_chdir(currentFolder);
		if(res != FR_OK)
		{
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

			return res;
		};
	}
	//save data

#if 1



	char text[17];

	//Save Project name
	//open the file
	res = f_open((FIL*)&SDFile,"prj.nfo",FA_CREATE_ALWAYS | FA_WRITE);
	if(res != FR_OK) {
		lcd_process_display_interrupt = 1;
		preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

		return res;
	}
	unsigned int bytesWritten;
	//write preset name to file
	res = f_write((FIL*)&SDFile,(void*)savefileNames[presetNr][PROJECT_NAMES],8,&bytesWritten);
	if(res != FR_OK) {
		lcd_process_display_interrupt = 1;
		preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

		return res;
	}
	//close the file
	f_close((FIL*)&SDFile);

//	soundengine_process();
	//save globals
	preset_saveGlobals();
	//save all drumkits, patterns and songs
	for(uint8_t i=0;i<NUM_KIT_SLOTS;i++)
	{
		sprintf(text, "%d%%", (uint8_t)(i/(float)NUM_KIT_SLOTS * 100.f));
		lcd_setcursor(0,2);
		lcd_string(text);
	//	soundengine_process();
		res = preset_saveDrumsetSD(i, 0);
		if(res != FR_OK) {
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

			return res;
		}
	//	soundengine_process();
		res = preset_savePatternSD(i);
		if(res != FR_OK) {
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
			return res;
		}
	//	soundengine_process();
		res = preset_saveSongSD(i);
		if(res != FR_OK) {
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
			return res;
		}
	}

	lcd_process_display_interrupt = 1;
	preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif

			preset_clearTmpFolder();

	return FR_OK;

#else
#if USE_SD_CARD
	uint16_t remain;
	uint8_t siz;
	//filename in 8.3  format
	char filename[GEN_BUF_LEN];
	if(isAll)
		preset_makeFileName(filename,presetNr,FEXT_ALL);
	else
		preset_makeFileName(filename,presetNr,FEXT_PROJ);
	//open the file
	f_open((FIL*)&SDFile,filename,FA_CREATE_ALWAYS | FA_WRITE);


	unsigned int bytesWritten;
	//write preset name to file
	f_write((FIL*)&SDFile,(void*)savefileNames[KIT_NAMES][presetNr],8,&bytesWritten);

	//write the version
	filename[0]=FILE_VERSION;
	f_write((FIL*)&SDFile, filename, 1, &bytesWritten);

	memset(filename,0xFF,GEN_BUF_LEN); // reuse this as our buffer for padding

	if(isAll) {
		// write global settings
		preset_writeGlobalData();

		// write some padding (we'll allocate 64 bytes for globals, right now we have +/- 18) so that
		// we don't need to change the file format later
		remain=	64- (PAR_CPU_USE - PAR_BEGINNING_OF_GLOBALS);

	} else {
		// write the bpm
		f_write((FIL*)&SDFile, &activeParameters[PAR_BPM], 1, &bytesWritten);
		// bar reset mode
		f_write((FIL*)&SDFile, &activeParameters[PAR_BAR_RESET_MODE], 1, &bytesWritten);

		remain=	64 - (1+1);
	}

	// write padding after globals/perf data
	while(remain){
		if(remain < GEN_BUF_LEN)
			siz=(uint8_t)remain;
		else
			siz=GEN_BUF_LEN;
		f_write((FIL*)&SDFile, filename, siz, &bytesWritten);
		remain -=siz;
	}

	// save kit
	preset_writeDrumsetData(0);

	// write some more padding (we'll allocate 512 bytes for kit data. This should be more than
	// we'll ever need. Right now we use about 228 bytes).
	remain = 512 - (END_OF_SOUND_PARAMETERS + SNARE_NOISE_KIT_BYTES + LFO_EXTRA_BYTES + RPS_EXTRA_BYTES);
	while(remain){
		if(remain < GEN_BUF_LEN)
			siz=(uint8_t)remain;
		else
			siz=GEN_BUF_LEN;
		f_write((FIL*)&SDFile, filename, siz, &bytesWritten);
		remain -=siz;
	}

	// write pattern data
	preset_writePatternData(0);

	//close the file
	f_close((FIL*)&SDFile);
#else
#endif
#endif
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
	res = f_close((FIL*)&SDFile);
	return res;
}


//----------------------------------------------------
void preset_loadProjectNames(uint8_t projectNr)
{
	FRESULT res;
	FILINFO fno;

	//change project folder
	sprintf(currentFolder, "/proj%02d", projectNr);

	res = f_stat(currentFolder, &fno);
	if(res == FR_NO_FILE)
	{
		sprintf((void*)savefileNames[projectNr][PROJECT_NAMES], "Empty");
		return;
	}
	else
	{
		f_chdir(currentFolder);
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
	FILINFO fno;
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

	res = f_stat(currentFolder, &fno);
	if(res == FR_NO_FILE)
	{
		res = f_mkdir(currentFolder);
		if(res == FR_OK)
		{
			f_chdir(currentFolder);
		}
		else
		{
			lcd_process_display_interrupt = 1;
			preset_initTmpFolder();
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
			HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#else

#endif
			return res;
		}
	}
	else
	{
		res = f_chdir(currentFolder);
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
	}
	//load data

#if 1

	//Load Project name

	UINT bytesRead;

	//open the file
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
	// The previous project's edit backup must not overwrite a freshly loaded
	// pattern when the pending pattern is activated below.
	seq_copyPatternToBackupBuffer(seq_activePattern);


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
	remain = 512 - (END_OF_SOUND_PARAMETERS + SNARE_NOISE_KIT_BYTES + LFO_EXTRA_BYTES + RPS_EXTRA_BYTES);
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

#define TRANSFER_V3_KIT_OFFSET (14u + 7u*(64u*7u+64u) + 4u*7u*2u + 1u + 7u)
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
