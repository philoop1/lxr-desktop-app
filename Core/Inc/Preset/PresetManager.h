/*
 * PresetManager.h
 *
 * Created: 09.05.2012 14:11:49
 *  Author: Julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */ 


#ifndef PRESETMANAGER_H_
#define PRESETMANAGER_H_

#include "main.h"
#include "string.h"
#include "fatfs.h"
#include "Parameters.h"
#include "InitKit.h"

//#define f_unmount(path) f_mount(0, path, 0)

enum
{
	KIT_NAMES,
	PATTERN_NAMES,
	SONG_NAMES,
	PROJECT_NAMES,
	NUM_SAVEFILE_NAMES,
	UNUSED_NAMES
};

extern char savefileNames[NUM_KIT_SLOTS][NUM_SAVEFILE_NAMES][8];
extern char currentFolder[13];
//extern char presetNameBuffer[8];
//extern uint8_t activePresetNr; //currently loaded kit

void preset_init(uint8_t presetNr);

#define SKIP_NEXT_KIT_AUTOLOAD 2

//-----------------------------------------------------------------
// autosave timer
// after a kit/pat is changed, wait a while, then autosave
typedef enum
{
	PRESET_KIT_TIMER,
	PRESET_PAT_TIMER,
	PRESET_STOP_PAT_TIMER
} PresetTimer;


FRESULT preset_LoadTmpKit();
void preset_loadTmpCfg(void); // 0.2.88 autosaved MUTA.CFG values
FRESULT preset_LoadTmpPat();
void preset_initTmpFolder();
void preset_touchTimer(PresetTimer type);
void preset_processTimer();
FRESULT preset_clearTmpFolder();
void preset_resetAllSaveTimers();
void preset_refreshTmpPat(uint8_t presetNr);
void preset_refreshTmpKit(void);
//load all manually saved kits and patterns found in the tmp folder
FRESULT loadTmpFolderFiles();



FRESULT preset_savePatternSD(uint8_t presetNr);
FRESULT preset_loadPatternSD(uint8_t presetNr);
/* Copy a saved LXR2 kit (0) or pattern (1) between project folders.
 * Existing targets require overwrite=1; the active project is never changed. */
FRESULT preset_copyProjectItem(uint8_t sourceProject, uint8_t sourceSlot,
        uint8_t targetProject, uint8_t targetSlot, uint8_t pattern, uint8_t overwrite,
        uint8_t kitOverride);
FRESULT preset_getProjectItemName(uint8_t project, uint8_t slot, uint8_t pattern, char name[9]);
FRESULT preset_getProjectPatternKit(uint8_t project,uint8_t slot,uint8_t *kitSlot);
FRESULT preset_findFreeProjectKit(uint8_t project,uint8_t *kitSlot);
FRESULT preset_copyProjectPatternWithKit(uint8_t sourceProject,uint8_t sourcePattern,
        uint8_t targetProject,uint8_t targetPattern,uint8_t overwrite,uint8_t *targetKit);
/* After an import: load the copied file from the project folder into RAM and
 * drop any older /tmp copy of that slot, so it survives Save Project and reboot. */
FRESULT preset_loadTransferredItem(uint8_t project,uint8_t slot,uint8_t pattern);
FRESULT preset_transferRefreshActivePattern(void);
#define LXR1_PERFORMANCES 61
#define LXR1_PATTERNS 8
/* Import a converted LXR1 performance: its kit goes to the lowest free slot and
 * its eight patterns to an eight-slot block starting at firstPattern. */
FRESULT preset_getPerformanceName(uint8_t performance,char name[9]);
FRESULT preset_importPerformance(uint8_t performance,uint8_t targetProject,uint8_t firstPattern,
        uint8_t overwrite,uint8_t *targetKit);

/** save the parameters of all 6 voices + LFO settings to a file on the SD card 
if isMorph==1 the sound will be loaded into the morph buffer
*/

//load/save drumset from/to SD card
FRESULT preset_saveDrumsetSD(uint8_t presetNr, uint8_t isMorph);
FRESULT preset_loadDrumsetSD(uint8_t presetNr, uint8_t isMorph);
//copy drumset to/from edit buffer
extern uint8_t preset_activeKitNr;
void preset_loadDrumsetRam(uint8_t presetNr, uint8_t isMorph, uint8_t sendImmediate);
void preset_saveDrumsetRam(uint8_t presetNr, uint8_t isMorph);


FRESULT preset_saveGlobals();
uint8_t preset_loadGlobals();
void preset_createGlobals();

FRESULT preset_loadLastUsedProjectNrFromSD(uint8_t* projNr);
FRESULT preset_saveLastUsedProjectNrToSD(uint8_t projNr);

void preset_loadDefaultGlobals();

FRESULT preset_saveProject(uint8_t presetNr);
FRESULT preset_loadProject(uint8_t presetNr, uint8_t clearTmp);
FRESULT preset_createProject(uint8_t presetNr);
void preset_loadProjectNames(uint8_t projectNr);

FRESULT preset_loadSongSD(uint8_t songNr);
FRESULT preset_saveSongSD(uint8_t songNr);

//char* preset_loadName(uint8_t presetNr, uint8_t nameBufferIdx, uint8_t what);

/** save a pattern set to the sd card */


FRESULT preset_savePatternRAM(uint8_t presetNr);
FRESULT preset_loadPatternRAM(uint8_t presetNr);


//uint8_t preset_loadPatternTemp(uint8_t presetNr);
//void preset_savePatternTemp(uint8_t presetNr);
/** morph pattern linear to �pattern buffer 2*/
void preset_morph(uint8_t morph);
// MIDI CC morph: glides to the target in 26 ms half steps
void preset_setMorphTarget(uint8_t target);
void preset_morph_tick(); //handler for non blocking morph
uint8_t preset_getMorphValue(uint16_t index, uint8_t morph);
uint8_t preset_morphBusy(void);
void preset_touchFlamTimer(void);
void preset_sendDrumsetParameters();
void preset_sendDrumsetParametersImmediate();

uint8_t preset_isNameEmpty(char* name);

#endif /* PRESETMANAGER_H_ */
