/*
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

//---------------------------------------------------
/*! \file menu.h
    \brief handles the menu structure on the LCD
    
    
*/

// Created:      2012-04-21 (13:47), by Julian Schmidt
// Coypright(c): Julian Schmidt
//---------------------------------------------------

#ifndef __LCD_MENU_MANAGER__
#define __LCD_MENU_MANAGER__

//#include <avr/io.h>
//#include <avr/pgmspace.h>
#include "main.h"
#include "../Parameters.h"
//-----------------------------------------------------------------
//#define NUM_PAGES 12		
#define NUM_SUB_PAGES 8	// a maximum of 8 subpages 
#define MASK_PARAMETER 0x07

#define MASK_PAGE 0xf8
#define PAGE_SHIFT 3
//-----------------------------------------------------------------
  #define PROGMEM
  #define PGM_P const char *
  #define PSTR(s) ((const PROGMEM char *)(s))
  #define pgm_read_byte(x) (*((uint8_t *)(x)))
  #define pgm_read_word(x) (*((uint16_t *)(x)))
  #define pgm_read_dword(x) (*((uint32_t *)(x)))
//-----------------------------------------------------------------
//#define PATTERN_END_MARKER 127
//the currently shown page from the LCD
extern uint8_t menu_activePage;
extern uint8_t menu_activeVoice;
extern uint8_t menu_playedPattern;
extern uint8_t menu_activePatternBank;
extern uint8_t menu_shownPattern;
extern uint8_t menu_muteModeActive;
extern uint8_t menu_activeBar;
extern uint8_t menu_songMenuPosition; //used to show the list in the display and scroll through it

#define NUM_PRESET_LOCATIONS 6 //kit, pattern, morph, Song, project, all
extern uint8_t menu_selectedPresetNr[NUM_PRESET_LOCATIONS];

enum
{
	CURRENT_KIT,
	CURRENT_MORPH,
	CURRENT_SONG,
	CURRENT_PROJECT,
	NUM_CURRENT
};

extern uint8_t menu_loadedPresetNr[NUM_CURRENT];
extern uint32_t sucessTimer;

void menu_setShownPattern(uint8_t patternNr);
uint8_t menu_getViewedPattern();


enum PageNames
{
	VOICE1_PAGE,
	VOICE2_PAGE,
	VOICE3_PAGE,
	VOICE4_PAGE,
	VOICE5_PAGE,
	VOICE6_PAGE,
	VOICE7_PAGE,
	MENU_MIDI_PAGE, // this is the global settings page
	LOAD_PAGE,
	SAVE_PAGE,
	/*
	LFO1_PAGE, //TODO load und savepage verschwenden speicher... nicht gefuellt. ans ende und aus dem array nehmen?
	LFO2_PAGE,
	LFO3_PAGE,
	LFO4_PAGE,
	LFO5_PAGE,
	LFO6_PAGE,
	*/
	
	PERF_PAGE,
	SEQ_PAGE,
	EUKLID_PAGE,
	PATTERN_SETTINGS_PAGE,
	RECORDING_PAGE,
	FX_MODE_PAGE,




	//keep the following 3 grouped together at the end
	//otherwise >=PATTERN LOAD && <= SONG_MODE code will be broken

	PATTERN_LOAD_PAGE,
	PATTERN_SAVE_PAGE,
	PATTERN_SAVE_PAGE_OK,
	MENU_LAST_STEP_PAGE,
	KIT_SAVE_PAGE_OK,
	SONG_MODE_PAGE,
	LFO_EXTRA1_PAGE,LFO_EXTRA2_PAGE,LFO_EXTRA3_PAGE,LFO_EXTRA4_PAGE,LFO_EXTRA5_PAGE,LFO_EXTRA6_PAGE,
	TRANSFER_PAGE,

	//must be last... special case
	//CLEAR_PAGE,




	//The Voice settings -> Midi Channel, Audio Out...
	/*
	VOICE1_SETTINGS_PAGE,
	VOICE2_SETTINGS_PAGE,
	VOICE3_SETTINGS_PAGE,
	VOICE4_SETTINGS_PAGE,
	VOICE5_SETTINGS_PAGE,
	VOICE6_SETTINGS_PAGE,
	*/
	
	NUM_PAGES
};
//-----------------------------------------------------------------
// These are indices into the valueNames array in menu.c
// PERF subpages used by the direct shortcuts and LED ownership.
#define PERF_DELAY_SUBPAGE 2
#define PERF_ACCENT_SUBPAGE 3
#define PERF_GROOVE_SUBPAGE 4
#define PERF_SEND_SUBPAGE 6
void menu_openPerformanceLayer(uint8_t subPage);
void menu_openLfoExtra(uint8_t secondScreen);
uint8_t menu_cycleVoiceLfo(uint8_t buttonNr);

enum NamesEnum
{
	TEXT_EMPTY = 0,					//0
	TEXT_COARSE,
	TEXT_FINE,
	TEXT_ATTACK,
	TEXT_DECAY,
	TEXT_PITCH_DECAY,
	TEXT_MOD_AMOUNT,
	TEXT_FM_AMOUNT,
	TEXT_FM_FREQ,
	TEXT_DRIVE,
	TEXT_VOLUME,					//10
	TEXT_PAN,
	TEXT_NOISE,
	TEXT_MIX,
	TEXT_REPEAT,
	TEXT_FILTER_F,
	TEXT_FILTER_RESO,
	TEXT_FILTER_TYPE,
	TEXT_MOD_OSC1_FREQ,
	TEXT_MOD_OSC2_FREQ,
	TEXT_MOD_OSC1_GAIN,				//20
	TEXT_MOD_OSC2_GAIN,
	
	TEXT_FREQ_LFO,
	TEXT_MOD_LFO,
	TEXT_WAVE_LFO,
	TEXT_TARGET_LFO,
	TEXT_SYNC_LFO,
	TEXT_RETRIGGER_LFO,
	TEXT_OFFSET_LFO,
	TEXT_TARGET_VOICE_LFO,
	TEXT_EG_SLOPE,					//30
	TEXT_DECAY_CLOSED,
	TEXT_DECAY_OPEN,
	TEXT_WAVEFORM,
	
	TEXT_TRANSIENT_WAVE,
	TEXT_TRANSIENT_VOLUME,
	TEXT_TRANSIENT_FREQ,
	
	TEXT_EQ_GAIN,
	TEXT_EQ_FREQ,
#if USE_CODEC_EQ
	TEXT_CODEC_EQ_ENABLE,
	TEXT_CODEC_EQ_FB,
	TEXT_CODEC_EQ_FT,
	TEXT_CODEC_EQ_GB,
	TEXT_CODEC_EQ_GT,
	
	TEXT_CODEC_LIMIT_ENABLE,
	TEXT_CODEC_LIMIT_ATTACK,
	TEXT_CODEC_LIMIT_RELEASE,
	TEXT_CODEC_LIMIT_MAX,
	TEXT_CODEC_LIMIT_MIN,
#endif
	TEXT_ROLL_SPEED,
	TEXT_X_FADE,					//40
	
	TEXT_STEP_VELOCITY,
	TEXT_NOTE,
	TEXT_PROBABILITY,
	TEXT_ACTIVE_STEP,
	TEXT_PAT_LENGTH,
	TEXT_NUM_STEPS,
	TEXT_ROTATION,
	TEXT_STEP_FLAM,
	TEXT_STEP_SHIFT,
	
	//Global Parameters
	TEXT_BPM,
	TEXT_MIDI_CHANNEL,
	TEXT_AUDIO_OUT,				 	//50
	TEXT_SAMPLE_RATE,
	TEXT_PATTERN_BEAT,
	TEXT_PATTERN_NEXT,
	
	
	//TEXT_OSC_PHASE,
	TEXT_MODE,
	TEXT_OSC_VOLUME,
	TEXT_FILTER_DRIVE,
	
	TEXT_VEL_DEST,
	TEXT_VEL_AMT,
	TEXT_VEL_MOD_VOL,
	TEXT_FETCH,						//60
	TEXT_FOLLOW,
	TEXT_QUANTISATION,
	TEXT_AUTOMATION_TRACK,
	TEXT_PARAM_DEST,	
	TEXT_PARAM_VAL,
	TEXT_SHUFFLE,
	TEXT_SCREENSAVER_ON_OFF,
	
	TEXT_SKIP, //spacer to insert if 1st of 2 pages has only 3 parameters
	
	TEXT_POS_X,
	TEXT_POS_Y,						//70
	TEXT_FLUX,
	TEXT_SOM_FREQ,
	TEXT_MIDI_MODE,	// This is now unused
	TEXT_MIDI_ROUTING,
	TEXT_MIDI_FILT_TX,
	TEXT_MIDI_FILT_RX,
	TEXT_TRIGGER_IN_PPQ,
	TEXT_TRIGGER_OUT1_PPQ,
	TEXT_TRIGGER_OUT2_PPQ,
	TEXT_TRIGGER_GATE_MODE,
	TEXT_BAR_RESET_MODE,
	TEXT_MIDI_CHAN_GLOBAL,
	TEXT_PWM,
	TEXT_FX_TYPE,
	TEXT_FX_ROUTING,
	TEXT_FX_DRY_WET,


	TEXT_FX_DIST_DRIVE,
	TEXT_FX_COLOR,
	TEXT_FX_RATIO,
	TEXT_FX_COMP_ATTACK,
	TEXT_FX_COMP_DECAY,
	TEXT_FX_COMP_THRESHOLD,
	TEXT_FX_FREQ,
	TEXT_FX_WAVE,
	TEXT_FX_VOLUME,
	TEXT_FX_TONE,
	TEXT_FX_GAIN,
	TEXT_FX_FEEDBACK,
	TEXT_FX_RANGE,
	TEXT_FX_TIME,
	TEXT_FX_PREDELAY,
	TEXT_FX_REFLECTION,
	TEXT_FX_P1,
	TEXT_FX_P2,
	TEXT_FX_P3,
	TEXT_FX_P4,
	TEXT_PATTERN_MODE,
	TEXT_MIDI_CHAN_PC,
	TEXT_CPU_USE,
	TEXT_SHUFFLE_LOAD,
	TEXT_LOAD_MORPH,
	TEXT_LOAD_SAMPLE_RATE,
	TEXT_GLOBAL_PITCH,
	TEXT_PITCH_BEND_RANGE,
	TEXT_GLOBAL_DECAY,
	TEXT_RANDOM_STEP,
	TEXT_PERF_NOTE_REPEAT_CHANCE,
	TEXT_PERF_SCARCITY,
	TEXT_PERF_PROB,
	TEXT_PERF_NOTE_PROB,
	TEXT_PERF_DELAY_CHANCE,
	TEXT_PERF_DELAY_SYNC,
	TEXT_PERF_DELAY_COUNT,
	TEXT_PERF_DELAY_BOUNCE,
	TEXT_PERF_DELAY_TARGET,
	TEXT_PERF_DELAY_MODE,
	TEXT_PERF_DELAY_EXP,
	TEXT_PERF_DELAY_PITCH,
	TEXT_PERF_DELAY_INPUT_MASK,
	TEXT_PERF_VELO_DECAY,
	TEXT_PERF_VELO_SAMPLE_RATE,
	TEXT_PERF_VELO_FILTER,
	TEXT_PERF_VELO_COARSE,
	TEXT_PERF_VELO_SLOPE,
	TEXT_PERF_VELO_MOD_AMOUNT,
	TEXT_PERF_VELO_DRIVE,
	TEXT_PERF_VELO_LEVEL,
	TEXT_GROOVE_SH2,
	TEXT_GROOVE_SH3,
	TEXT_GROOVE_SH4,
	TEXT_MASTER_FILTER_ENABLE,
	TEXT_GLOBAL_SCALE,
	TEXT_FX_SEND_MODE,
	TEXT_FX_OUTPUT_MODE,
	TEXT_MASTER_FILTER,
	TEXT_MASTER_FILTER_RESO,
	TEXT_MASTER_FILTER_DRIVE,
	TEXT_FX_SEND1,
	TEXT_FX_SEND2,
	TEXT_FX_SEND3,
	TEXT_FX_SEND4,
	TEXT_FX_SEND5,
	TEXT_FX_SEND6,
	TEXT_FX_SEND7,
	TEXT_VCA1,
	TEXT_VCA2,
	TEXT_VCA3,
	TEXT_VCA4,
	TEXT_VCA5,
	TEXT_VCA6,
	TEXT_VCA7,
	TEXT_SNARE_NOISE_ATTACK,
	TEXT_SNARE_NOISE_DECAY,
	TEXT_SNARE_NOISE_SLOPE,
	TEXT_CLOCK_OFFSET,
	TEXT_CLOCK_OFFSET_FINE,
	TEXT_SNARE_LAYER_WAVE,
	TEXT_SNARE_LAYER_AMOUNT,
	TEXT_SNARE_LAYER_FREQ,
	TEXT_SNARE_LAYER_MODE,
	TEXT_PATTERN_SCALE,
	TEXT_PERF_RANDOM_VELO,
	TEXT_PERF_AVL,
	TEXT_STEP_FLAM_PROB,
	TEXT_LFO_SLEW,TEXT_LFO_POL,
	TEXT_STEP_CONDITION,TEXT_PERF_FILL,
	TEXT_SCALE_TRANSFORM,




	NUM_NAMES
};
//-----------------------------------------------------------------
enum WaveformNamesEnum
{
	WAVEFORM_SINE,
	WAVEFORM_TRI,
	WAVEFORM_SAW,
	WAVEFORM_REC,
	WAVEFORM_NOISE,
	WAVEFORM_PWM,
};	
//-----------------------------------------------------------------
enum shortNamesEnum
{ // these must correspond with shortNames
	SHORT_EMPTY,
	SHORT_COARSE,
	SHORT_FINE,
	SHORT_ATTACK,
	SHORT_DECAY,
	SHORT_EG2,
	SHORT_MOD,
	SHORT_AMNT,
	SHORT_FREQ,
	SHORT_DRIVE,
	SHORT_VOL,
	SHORT_PAN,
	SHORT_NOISE,
	SHORT_REPEAT,
	SHORT_MIX,
	SHORT_FIL_RESO,
	SHORT_TYPE,
	SHORT_MOD_OSC1_FREQ,
	SHORT_MOD_OSC2_FREQ,
	SHORT_MOD_OSC1_GAIN,
	SHORT_MOD_OSC2_GAIN,
	SHORT_WAVE,
	SHORT_DEST,
	SHORT_SYNC,
	SHORT_RETRIGGER,
	SHORT_OFFSET,
	SHORT_VOICE,
	SHORT_SLOPE,
	SHORT_DECAY1,
	SHORT_DECAY2,
	SHORT_EQ_GAIN,
	SHORT_EQ_FREQ,
#if USE_CODEC_EQ	
	SHORT_EQ,
	SHORT_LIMITER,
	SHORT_RELEASE,
	SHORT_MAX,
	SHORT_MIN,
#endif	
	SHORT_ROLL,
	SHORT_MORPH,
	SHORT_NOTE,
	SHORT_PROBABILITY,
	SHORT_STEP,
	SHORT_LENGTH,
	SHORT_ROTATION,
	
	SHORT_BPM,
	SHORT_CHANNEL,
	SHORT_OUT,
	SHORT_SR,
	
	SHORT_NXT,

	SHORT_MODE,
	SHORT_VELOCITY,
	SHORT_FETCH,
	SHORT_FOLLOW,
	SHORT_QUANT,
	SHORT_TRACK,
	SHORT_VALUE,
	SHORT_SHUFFLE,
	SHORT_SCREEN_SAVER,
	SHORT_X,
	SHORT_Y,
	SHORT_FLUX,
	SHORT_MIDI,
	SHORT_MIDI_ROUTING,
	SHORT_MIDI_FILT_TX,
	SHORT_MIDI_FILT_RX,
	SHORT_TRIGGER_IN,
	SHORT_TRIGGER_OUT1,
	SHORT_TRIGGER_OUT2,
	SHORT_BAR_RESET_MODE,
	SHORT_PWM,
	SHORT_COLOR,
	SHORT_DRY_WET,
	SHORT_RATIO,
	SHORT_THRESH,
	SHORT_TONE,
	SHORT_GAIN,
	SHORT_FEEDBACK,
	SHORT_RANGE,
	SHORT_TIME,
	SHORT_PRE,
	SHORT_REF,
	SHORT_P1,
	SHORT_P2,
	SHORT_P3,
	SHORT_P4,
	SHORT_KCM,
	SHORT_FLAM,
	SHORT_SHIFT,
	SHORT_PCH,
	SHORT_CPU_USE,
	SHORT_SHUFFLE_LOAD,
	SHORT_LOAD_MORPH,
	SHORT_LOAD_SAMPLE_RATE,
	SHORT_GLOBAL_PITCH,
	SHORT_PITCH_BEND_RANGE,
	SHORT_GLOBAL_DECAY,
	SHORT_RANDOM_STEP,
	SHORT_PERF_NOTE_REPEAT_CHANCE,
	SHORT_PERF_SCARCITY,
	SHORT_PERF_PROB,
	SHORT_PERF_NOTE_PROB,
	SHORT_PERF_DELAY_CHANCE,
	SHORT_PERF_DELAY_SYNC,
	SHORT_PERF_DELAY_COUNT,
	SHORT_PERF_DELAY_BOUNCE,
	SHORT_PERF_DELAY_TARGET,
	SHORT_PERF_DELAY_MODE,
	SHORT_PERF_DELAY_EXP,
	SHORT_PERF_DELAY_PITCH,
	SHORT_PERF_DELAY_INPUT_MASK,
	SHORT_PERF_VELO_DECAY,
	SHORT_PERF_VELO_SAMPLE_RATE,
	SHORT_PERF_VELO_FILTER,
	SHORT_PERF_VELO_COARSE,
	SHORT_PERF_VELO_SLOPE,
	SHORT_PERF_VELO_MOD_AMOUNT,
	SHORT_PERF_VELO_DRIVE,
	SHORT_PERF_VELO_LEVEL,
	SHORT_GROOVE_SH2,
	SHORT_GROOVE_SH3,
	SHORT_GROOVE_SH4,
	SHORT_MASTER_FILTER_ENABLE,
	SHORT_GLOBAL_SCALE,
	SHORT_FX_SEND_MODE,
	SHORT_FX_OUTPUT_MODE,
	SHORT_MASTER_FILTER,
	SHORT_MASTER_FILTER_RESO,
	SHORT_MASTER_FILTER_DRIVE,
	SHORT_FX_SEND1,
	SHORT_FX_SEND2,
	SHORT_FX_SEND3,
	SHORT_FX_SEND4,
	SHORT_FX_SEND5,
	SHORT_FX_SEND6,
	SHORT_FX_SEND7,
	SHORT_VCA1,
	SHORT_VCA2,
	SHORT_VCA3,
	SHORT_VCA4,
	SHORT_VCA5,
	SHORT_VCA6,
	SHORT_VCA7,
	SHORT_SNARE_NOISE_ATTACK,
	SHORT_SNARE_NOISE_DECAY,
	SHORT_SNARE_NOISE_SLOPE
	,SHORT_CLOCK_OFFSET
	,SHORT_CLOCK_OFFSET_FINE
	,SHORT_SNARE_LAYER_WAVE
	,SHORT_SNARE_LAYER_AMOUNT
	,SHORT_SNARE_LAYER_FREQ
	,SHORT_SNARE_LAYER_MODE, SHORT_PATTERN_SCALE, SHORT_PERF_RANDOM_VELO, SHORT_PERF_AVL, SHORT_STEP_FLAM_PROB, SHORT_LFO_SLEW, SHORT_LFO_POL
	,SHORT_STEP_CONDITION,SHORT_PERF_FILL
	,SHORT_SCALE_TRANSFORM

	
};
//-----------------------------------------------------------------
// These correspond with catNames in MenuText.h
enum catNamesEnum
{
	CAT_EMPTY,
	CAT_OSC,
	CAT_VELO_EG,
	CAT_PITCH_EG,
	CAT_PITCH_MOD,
	CAT_FM,
	CAT_VOICE,
	CAT_NOISE,
	CAT_NOISE_OSC,
	CAT_FILTER,
	CAT_MOD_OSC,
	CAT_LFO,
	CAT_TRANS,
	CAT_EQ,
#if USE_CODEC_EQ	
	CAT_LIMIT,
#endif
	CAT_PATTERN,
	CAT_SOUND,
	CAT_STEP,
	CAT_EUKLID,
	CAT_GLOBAL,
	CAT_VELOCITY,
	CAT_PARAMETER,
	CAT_SEQUENCER,
	CAT_GENERATOR,
	CAT_MIDI,
	CAT_CLOCK,
	CAT_FX
};
//-----------------------------------------------------------------
// these must correspond with longNames in MenuText.h
enum longNamesEnum
{
	LONG_EMPTY,
	LONG_COARSE,
	LONG_FINE,
	LONG_ATTACK,
	LONG_DECAY,
	LONG_AMOUNT,
	LONG_FREQ,
	LONG_DRIVE,
	LONG_VOL,
	LONG_PAN,
	LONG_MIX,
	LONG_REPEAT_CNT,
	LONG_RESONANCE,
	LONG_TYPE,
	LONG_GAIN,
	LONG_WAVE,
	LONG_DEST_PARAM,
	LONG_CLOCKSYNC,
	LONG_RETRIGGER,
	LONG_OFFSET,
	LONG_DEST_VOICE,
	LONG_SLOPE,
	LONG_DECAY_CLOSED,
	LONG_DECAY_OPEN,
#if USE_CODEC_EQ	
	LONG_ENABLE,
	LONG_RELEASE,
	LONG_THRESH_MAX,
	LONG_THRESH_MIN,
#endif
	LONG_ROLLRATE,
	LONG_MORPH,
	LONG_NOTE,
	LONG_PROBABILITY,
	LONG_NUMBER,
	LONG_LENGTH,
	LONG_STEPS,
	LONG_ROTATION,
	LONG_TEMPO,
	LONG_AUDIO_OUT,
	LONG_MIDI_CHANNEL,
	LONG_SAMPLE_RATE,
	LONG_NEXT_PAT,
	LONG_PHASE,
	LONG_MODE,
	LONG_VOLUME_MOD,
	LONG_FETCH,
	LONG_FOLLOW,
	LONG_QUANTISATION,
	LONG_AUTOMATION_TRACK,
	LONG_AUTOMATION_DEST,
	LONG_AUTOMATION_VAL,
	LONG_SHUFFLE,
	LONG_SCREENSAVER,
	LONG_X,
	LONG_Y,
	LONG_FLUX,
	LONG_VELOCITY,
	LONG_FREQ1,
	LONG_FREQ2,
	LONG_GAIN1,
	LONG_GAIN2,
	LONG_MIDI_ROUTING,
	LONG_MIDI_FILT_TX,
	LONG_MIDI_FILT_RX,
	LONG_CLOCK_IN,
	LONG_CLOCK_OUT1,
	LONG_TRIGGER_OUT2,
	LONG_TRIGGER_GATE_MODE,
	LONG_BAR_RESET_MODE,
	LONG_PWM,
	LONG_COLOR,
	LONG_DRY_WET,
	LONG_RATIO,
	LONG_THRESH,
	LONG_TONE,
	LONG_FEEDBACK,
	LONG_RANGE,
	LONG_TIME,
	LONG_PREDELAY,
	LONG_REFLECTION,
	LONG_P1,
	LONG_P2,
	LONG_P3,
	LONG_P4,
	LONG_PATTERN_MODE,
	LONG_FLAM,
	LONG_SHIFT,
	LONG_CONTROL_CHANNEL,
	LONG_CPU_USE,
	LONG_SHUFFLE_LOAD,
	LONG_LOAD_MORPH,
	LONG_LOAD_SAMPLE_RATE,
	LONG_GLOBAL_PITCH,
	LONG_PITCH_BEND_RANGE,
	LONG_GLOBAL_DECAY,
	LONG_RANDOM_STEP,
	LONG_PERF_NOTE_REPEAT_CHANCE,
	LONG_PERF_SCARCITY,
	LONG_PERF_PROB,
	LONG_PERF_NOTE_PROB,
	LONG_PERF_DELAY_CHANCE,
	LONG_PERF_DELAY_SYNC,
	LONG_PERF_DELAY_COUNT,
	LONG_PERF_DELAY_BOUNCE,
	LONG_PERF_DELAY_TARGET,
	LONG_PERF_DELAY_MODE,
	LONG_PERF_DELAY_EXP,
	LONG_PERF_DELAY_PITCH,
	LONG_PERF_DELAY_INPUT_MASK,
	LONG_PERF_VELO_DECAY,
	LONG_PERF_VELO_SAMPLE_RATE,
	LONG_PERF_VELO_FILTER,
	LONG_PERF_VELO_COARSE,
	LONG_PERF_VELO_SLOPE,
	LONG_PERF_VELO_MOD_AMOUNT,
	LONG_PERF_VELO_DRIVE,
	LONG_PERF_VELO_LEVEL,
	LONG_GROOVE_SH2,
	LONG_GROOVE_SH3,
	LONG_GROOVE_SH4,
	LONG_MASTER_FILTER_ENABLE,
	LONG_GLOBAL_SCALE,
	LONG_FX_SEND_MODE,
	LONG_FX_OUTPUT_MODE,
	LONG_MASTER_FILTER,
	LONG_MASTER_FILTER_RESO,
	LONG_MASTER_FILTER_DRIVE,
	LONG_FX_SEND1,
	LONG_FX_SEND2,
	LONG_FX_SEND3,
	LONG_FX_SEND4,
	LONG_FX_SEND5,
	LONG_FX_SEND6,
	LONG_FX_SEND7,
	LONG_VCA1,
	LONG_VCA2,
	LONG_VCA3,
	LONG_VCA4,
	LONG_VCA5,
	LONG_VCA6,
	LONG_VCA7,
	LONG_SNARE_NOISE_ATTACK,
	LONG_SNARE_NOISE_DECAY,
	LONG_SNARE_NOISE_SLOPE
	,LONG_CLOCK_OFFSET
	,LONG_CLOCK_OFFSET_FINE
	,LONG_SNARE_LAYER_WAVE
	,LONG_SNARE_LAYER_AMOUNT
	,LONG_SNARE_LAYER_FREQ
	,LONG_SNARE_LAYER_MODE, LONG_PATTERN_SCALE, LONG_PERF_RANDOM_VELO, LONG_PERF_AVL, LONG_STEP_FLAM_PROB, LONG_LFO_SLEW, LONG_LFO_POL
	,LONG_STEP_CONDITION,LONG_PERF_FILL
	,LONG_SCALE_TRANSFORM
	
};

//enum for the save category parameter
enum loadSaveEnum
{
	SAVE_TYPE_KIT = 0,
	SAVE_TYPE_PATTERN,
	SAVE_TYPE_SONG,
	SAVE_TYPE_MORPH,

	SAVE_TYPE_PROJECT,	// kit data, pattern data and BPM
	SAVE_TYPE_ALL,			// all global settings, kit data and pattern data
	SAVE_TYPE_GLO,
	//SAVE_TYPE_SAMPLES,
	NUM_SAVE_TYPES
};

//-----------------------------------------------------------------

//-----------------------------------------------------------------
/** struct describing a display page.
top values are from the 'NamesEnum' selecting a text to display.
bottom values are from the 'ParamEnums' selecting the parameter value to show*/
typedef struct PageStruct
{
	uint8_t top1;
	uint8_t top2;
	uint8_t top3;
	uint8_t top4;
	
	uint8_t top5;
	uint8_t top6;
	uint8_t top7;
	uint8_t top8;
	
	uint16_t bot1;
	uint16_t bot2;
	uint16_t bot3;
	uint16_t bot4;
		
	uint16_t bot5;
	uint16_t bot6;
	uint16_t bot7;
	uint16_t bot8;
}Page;

//-----------------------------------------------------------------
// for storing valueNames which is defined in menu.c
typedef struct NameStruct
{
	const uint8_t shortName; /**< 3 letter short name id*/
	const uint8_t category; /**< category name id e.g. Filter, Noise, Velocity etc...*/
	const uint8_t longName; /**< full name id of the parameter*/
}Name;

//-----------------------------------------------------------------
// **AUTOM declare ModTarg struct
typedef struct ModTargStruct {
	const uint8_t nameIdx; 	// index into NameStruct (valueNames)
	const uint16_t param;	// equivalent param number
} ModTarg;

//**AUTOM declare ModTargetVoiceOffset struct
// see cc2text.c for the array of these
typedef struct ModTargetVoiceOffsetStruct {
	uint8_t start;
	uint8_t end;
}  ModTargetVoiceOffset;



// need array corresponding to parameters with indices into above array
// later will need an array of 6 or 7 for indices into above to target indiv voices

//-----------------------------------------------------------------
enum Datatypes
{
	DTYPE_0B255,	//0:255
	DTYPE_0B127,	//0-127
	DTYPE_PM100,	//-100:100
	DTYPE_MENU,		//text type outputs 
	DTYPE_PM63,		//-63 <-> 63
	DTYPE_1B16,		//1-16
	DTYPE_ON_OFF,	//0-1
//	DTYPE_MIX_FM,	//0-1
	DTYPE_TARGET_SELECTION_LFO,
	DTYPE_TARGET_SELECTION_VELO,	
	DTYPE_VOICE_LFO,
	DTYPE_AUTOM_TARGET,
	DTYPE_0b1,
	DTYPE_NOTE_NAME, // eg C#0, D 1 for note name
	DTYPE_0B15,		//0-15
	DTYPE_1B64,		//1-64
	DTYPE_0B100,	// 0-100
	//mÃƒÂ¶ÃƒÂ¶p - only 8 bit available, the others are used for menu :-/
	//DTYPE_BPM,		// 0=EXT then 1 to 255

    Internal_ForceMyEnumIntSize = 0xffff //to make enum 16 bit
};

//-----------------------------------------------------------------
extern const enum Datatypes parameter_dtypes[NUM_PARAMS];
extern uint8_t mainParameters[NUM_KIT_SLOTS][END_OF_SOUND_PARAMETERS];		// keeps all kits from sd card in memory
extern uint8_t activeParameters[NUM_PARAMS];					// keeps the currently used kit in memory -> editBuffer
//extern uint8_t morphParameters[END_OF_SOUND_PARAMETERS];
extern uint8_t *morphParameters;
//extern uint8_t abs_pot_Parameter_position[NUM_PARAMS];

extern const Page menuPages[NUM_PAGES][NUM_SUB_PAGES];


// **AUTOM declare modTargets array
// this is used for better organizing modulation targets. An index into this
// array is stored in PAR_P*_DEST in front. this table is used to display values
// as well as translate the value to a parameter. Param value in "Front" represents an index
// into this array, but is translated to a real param number when going back to "cortex"
// also, translated the other way when coming back
// we have a separate array of indices into this array called modTargetVoiceOffsets that determines
// where a voice starts and ends in modTargets array.
extern const ModTarg modTargets[];
extern const ModTargetVoiceOffset modTargetVoiceOffsets[6];

// **AUTOM declare paramToModTarget array
// this is an array of indices into modTargets which is defined in cc2text.c
// It is calculated at runtime TODO move this to progmem sometime
extern uint8_t paramToModTarget[END_OF_SOUND_PARAMETERS];


void menu_showSdError(uint8_t res);

/** returns the current menu index (page and parameter, see MASK_PAGE / MASK_PARAMETER) */
uint8_t getMenuIndx(void);

//-----------------------------------------------------------------
/** forces a complete repaint of the display*/
void menu_repaintAll();
//-----------------------------------------------------------------
//repaint the screen. show all changes*/
void menu_repaint();
//-----------------------------------------------------------------
//For nonblocking display refreshs
void menu_tick();
void menu_updateCpuUse(void);
//-----------------------------------------------------------------
//blocking display refresh
//void menu_fastRefreshDisplay();
//-----------------------------------------------------------------
//number of user samples in flash
void menu_setNumSamples(uint8_t num);
//-----------------------------------------------------------------
/**set all save state parameters to 0*/
void menu_resetSaveParameters();
//-----------------------------------------------------------------
void menu_setLoadSaveCategory(uint8_t cat);
uint8_t menu_isProjectLoadSavePage(uint8_t exportMode);
void menu_openTransfer(uint8_t exportMode);
uint8_t menu_isTransferActive(void);
void menu_transferSelectType(uint8_t pattern);
void menu_transferSelectProject(void);
//-----------------------------------------------------------------
void menu_init();
//-----------------------------------------------------------------
/** takes the values received from the encoder and translates it to menu changes*/
void menu_parseEncoder(int8_t inc, uint8_t button);
//-----------------------------------------------------------------
void menu_switchPage(uint8_t pageNr);
//-----------------------------------------------------------------
void menu_switchSubPage(uint8_t subPageNr, uint8_t toggle);
//-----------------------------------------------------------------
void menu_resetActiveParameter();
//-----------------------------------------------------------------
uint8_t menu_getSubPage();
//-----------------------------------------------------------------
uint8_t menu_getDisplayParameterType(uint8_t pos);
//-----------------------------------------------------------------
uint8_t menu_parseKnobValue(uint8_t potNr, int16_t diff);
//-----------------------------------------------------------------
void menu_parseGlobalParam(uint16_t paramNr, uint8_t value);
//-----------------------------------------------------------------
/** all parameters are send to the cortex soundchip. called after loading a preset into the avr ram*/
void menu_sendAllParameters();
//-----------------------------------------------------------------
/** get the currently active page nr*/
uint8_t menu_getActivePage();
//-----------------------------------------------------------------
uint8_t menu_areMuteLedsShown();
//-----------------------------------------------------------------
/** get the currently active voice nr*/
uint8_t menu_getActiveVoice();
void menu_openPatternScale(void);
uint8_t menu_getWaveformMax(void);
uint8_t menu_limitSoundParameter(uint16_t parameter,uint8_t value);
//-----------------------------------------------------------------
void menu_setActiveVoice(uint8_t voiceNr);
//-----------------------------------------------------------------
/** used to upodate all global parameters that need processing after a preset is loaded*/
void menu_sendAllGlobals();
//-----------------------------------------------------------------
uint8_t sendDisplayBuffer();
//-----------------------------------------------------------------
void numtostrpu_2Bytes(char *buf, uint8_t num, char pad);
/* fill up to 3 bytes of a buffer with string representation of a number */
// left padded with specified char unsigned
void numtostrpu(char *buf, uint8_t num, char pad);
// space padded signed
void numtostrps(char *buf, int8_t num);
// non space padded unsigned
void numtostru(char *buf, uint8_t num);
// non space padded signed
//void numtostrs(char *buf, int8_t num);

#endif
