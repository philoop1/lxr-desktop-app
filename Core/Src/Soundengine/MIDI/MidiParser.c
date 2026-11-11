/*
 * MidiParser.c
 *
 *  Created on: 02.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#include <string.h>
#include "freezeDiag.h"
#include <Soundengine/MIDI/CortexParser.h>
#include "Soundengine/MIDI/MidiParser.h"
#include "Soundengine/MIDI/MidiNoteNumbers.h"
#include "Soundengine/DSPAudio/DrumVoice.h"
#include "Soundengine/DSPAudio/FilterEnv.h" // 0.2.93
#include "Soundengine/DSPAudio/Snare.h"
#include "Soundengine/config.h"
#include "Soundengine/DSPAudio/HiHat.h"
#include "Soundengine/DSPAudio/CymbalVoice.h"
#include "Soundengine/MIDI/Uart.h"
#include "Soundengine/Sequencer/sequencer.h"
#include "Soundengine/Sequencer/clockSync.h"
#include "Soundengine/DSPAudio/mixer.h"
#include "Soundengine/MIDI/valueShaper.h"
#include "Soundengine/DSPAudio/modulationNode.h"
#include "Soundengine/USB/usb_manager.h"
#include "menu/menu.h"
#include "menu/CcNr2Text.h"
#include "Soundengine/FxBus.h"
#include "Preset/PresetManager.h"
#include "Soundengine/Sequencer/PerformanceSteps.h"
#include "menu/PerformanceControls.h"
#include "Soundengine/Sequencer/PerformanceDelay.h"
#include "buttonHandler.h"

#include "Soundengine/MIDI/MidiMessages.h"

static uint16_t midiParser_activeNrpnNumber = 0;
static uint32_t midiParser_clockCycles;

uint8_t midiParser_originalCcValues[0x100];

// this will be set to some value if we are ignoring all mtc messages until the next 0 message
static uint8_t midiParser_mtcIgnore=1;
static uint32_t volatile midiParser_lastMtcReceived=0x0;
static uint8_t midiParser_mtcIsRunning=0;

static union {
	uint8_t value;
	struct {
		unsigned usb2midi:1;
		unsigned usb2usb:1;   // not used
		unsigned midi2midi:1;
		unsigned midi2usb:1;
		unsigned :4;
	} route;
} midiParser_routing = {0};



//tx is high nibble
uint8_t midiParser_txRxFilter = 0xFF;

enum State
{
	MIDI_STATUS,  		// waiting for status byte
	MIDI_DATA1,  		// waiting for data byte1
	MIDI_DATA2,  		// waiting for data byte2
	SYSEX_DATA,  		// read sysex data byte
	IGNORE				// set when unknown status byte received, stays in ignore mode until next known status byte
  };

// 2^(1/12) factor for 1 semitone
#define SEMITONE_UP 1.0594630943592952645618252949463f
#define SEMITONE_DOWN 0.94387431268169349664191315666753f

#define NUM_LFO 6
uint8_t midiParser_selectedLfoVoice[NUM_LFO] = {0,0,0,0,0,0};

#if 0
// -- AS for debugging
void midiDebugSend(uint8_t b1, uint8_t b2)
{
	uart_sendMidiByte(0xF2);
	uart_sendMidiByte(b1&0x7F);
	uart_sendMidiByte(b2&0x7F);
}
#endif

//----------------------------------------------------------
#if 0
inline uint16_t calcSlopeEgTime(uint8_t data2)
{
	float val = (data2+1)/128.f;
	return data2>0?val*val*data2*128:1;
}
#endif
//-----------------------------------------------------------
static inline float calcPitchModAmount(uint8_t data2)
{
	const float val = data2/127.f;
	return val*val*PITCH_AMOUNT_FACTOR;
}

//-----------------------------------------------------------
// vars
//-----------------------------------------------------------
uint8_t midi_MidiChannels[8];	// the currently selected midi channel for each voice (element 7 is global channel)
uint8_t midi_ControlChannel = 1; // displayed as Pch 2 by default

// note overrides for each voice
//uint8_t midi_NoteOverride[7];
//uint8_t midi_mode; // not used anymore
MidiMsg midiMsg_tmp;				// buffer message where the incoming data is stored
// these two are used only when building up a midi message
//static uint8_t msgLength;					// number of following data bytes expected for current status
static uint8_t parserState = IGNORE;	// state of the parser state machine. Set to what it's expecting next
										// we set it to ignore initially so that any random data we get before
										// a valid msg header is ignored

//-----------------------------------------------------------
//takes a midi value from 0 to 127 and return +/- 50 cent detune factor
float midiParser_calcDetune(uint8_t value)
{
	//linear interpolation between 1(no change) and semitone up/down)
	float frac = (value/127.f -0.5f);
	float cent = 1;
	if(cent>=0)
	{
		cent += frac*(SEMITONE_UP - 1);
	}
	else
	{
		cent += frac*(SEMITONE_UP - 1);
	}
	return cent;
}
//-----------------------------------------------------------
static void midiParser_nrpnHandler(uint16_t value)
{
	MidiMsg msg2;
	msg2.status = MIDI_CC2;
	msg2.data1 = midiParser_activeNrpnNumber;
	msg2.data2 = value;
	midiParser_ccHandler(msg2,true, 0, 0.f);
}
#define GLOBAL_DECAY_CENTER 63
static uint8_t midiParser_modVelocity[7],midiParser_modVelocityValid;
static uint8_t midiParser_lastHatTrack=5;
static void midiParser_refreshVelocityVoice(uint8_t track);
static void midiParser_refreshVelocityParameter(uint16_t parameter);
static uint8_t midiParser_applyVelocityDepth(uint8_t base, uint8_t amount, uint8_t velocity)
{
	if(amount < GLOBAL_DECAY_CENTER)
	{
		const uint32_t change = (uint32_t)base * (GLOBAL_DECAY_CENTER - amount) * velocity;
		return (uint8_t)(base - ((change + 4000u) / (GLOBAL_DECAY_CENTER * 127u)));
	}
	if(amount > GLOBAL_DECAY_CENTER)
	{
		const uint32_t change = (uint32_t)(127 - base) * (amount - GLOBAL_DECAY_CENTER) * velocity;
		return (uint8_t)(base + ((change + 4064u) / (64u * 127u)));
	}
	return base;
}
static uint8_t midiParser_scalePerformanceVelocityAmount(uint8_t amount)
{
	const int16_t target = (int16_t)amount - GLOBAL_DECAY_CENTER;
	const int16_t level = (int16_t)activeParameters[PAR_PERF_VELO_LEVEL] - GLOBAL_DECAY_CENTER;
	const int16_t divisor = (level < 0) ? GLOBAL_DECAY_CENTER : 64;
	int32_t scaled;

	if(target == 0 || level == 0)
		return GLOBAL_DECAY_CENTER;
	scaled = (int32_t)target * level;
	if(scaled >= 0)
		scaled = (scaled + divisor / 2) / divisor;
	else
		scaled = (scaled - divisor / 2) / divisor;
	if(scaled < -63)
		scaled = -63;
	else if(scaled > 64)
		scaled = 64;
	return (uint8_t)(GLOBAL_DECAY_CENTER + scaled);
}
static uint8_t midiParser_velocityAmount(uint16_t param)
{
	return midiParser_scalePerformanceVelocityAmount(activeParameters[param]);
}
static uint8_t midiParser_velocityForTrack(uint8_t track)
{
	return (midiParser_modVelocityValid & (1u<<track)) ? midiParser_modVelocity[track] : 0;
}
static const uint8_t midiParser_decayParams[7]={VELOD1,VELOD2,VELOD3,VELOD4,VELOD5,VELOD6,VELOD6_OPEN};
static uint8_t midiParser_globalDecay=63;

// Mutador's bipolar depth formula at full modulation velocity (127).
static uint8_t midiParser_decayDepth(uint8_t base,uint8_t amount)
{
	if(amount<63) {
		const uint32_t change=(uint32_t)base*(63-amount)*127u;
		return (uint8_t)(base-((change+4000u)/(63u*127u)));
	}
	if(amount>63) {
		const uint32_t change=(uint32_t)(127-base)*(amount-63)*127u;
		return (uint8_t)(base+((change+4064u)/(64u*127u)));
	}
	return base;
}
static void midiParser_applyGlobalDecayParam(uint8_t param)
{
	uint8_t track=0;
	while(track<7 && midiParser_decayParams[track]!=param) track++;
	if(track>=7)return;
	const uint8_t trackValue=midiParser_applyVelocityDepth(midiParser_originalCcValues[param],
		midiParser_velocityAmount(PAR_PERF_VELO_DECAY),midiParser_velocityForTrack(track));
	const uint8_t value=midiParser_decayDepth(trackValue,midiParser_globalDecay);
	switch(param) {
	case VELOD1: slopeEg2_setDecay(&voiceArray[0].oscVolEg,value,AMP_EG_SYNC); break;
	case VELOD2: slopeEg2_setDecay(&voiceArray[1].oscVolEg,value,AMP_EG_SYNC); break;
	case VELOD3: slopeEg2_setDecay(&voiceArray[2].oscVolEg,value,AMP_EG_SYNC); break;
	case VELOD4: slopeEg2_setDecay(&snareVoice.oscVolEg,value,false); break;
	case VELOD5: slopeEg2_setDecay(&cymbalVoice.oscVolEg,value,false); break;
	case VELOD6: hatVoice.decayClosed=slopeEg2_calcDecay(value); break;
	case VELOD6_OPEN: hatVoice.decayOpen=slopeEg2_calcDecay(value); break;
	default: return;
	}
	modNode_originalValueChanged((uint16_t)(param-1u));
}
void midiParser_setGlobalDecay(uint8_t value)
{
	midiParser_globalDecay=value>127 ? 127 : value;
	activeParameters[PAR_GLOBAL_DECAY]=midiParser_globalDecay;
	for(uint8_t i=0;i<7;i++) midiParser_applyGlobalDecayParam(midiParser_decayParams[i]);
	menu_repaint();
}
void midiParser_setStepPerformance(uint16_t param,uint8_t value)
{
	const uint8_t maximum=param==PAR_PERF_NOTE_REPEAT_CHANCE ? 127 : 100;
	if(param!=PAR_RANDOM_STEP && param!=PAR_PERF_NOTE_REPEAT_CHANCE &&
	   param!=PAR_PERF_SCARCITY && param!=PAR_PERF_PROB && param!=PAR_PERF_NOTE_PROB) return;
	activeParameters[param]=value>maximum ? maximum : value;
	perf_configure(activeParameters[PAR_RANDOM_STEP],activeParameters[PAR_PERF_NOTE_REPEAT_CHANCE],
		activeParameters[PAR_PERF_SCARCITY],activeParameters[PAR_PERF_PROB]);
	perf_setNoteProbability(activeParameters[PAR_PERF_NOTE_PROB]);
	menu_repaint();
}
//-----------------------------------------------------------
static Lfo *midiParser_voiceLfo(uint8_t voice);
/** handle all incoming CCs and invoke action*/
void midiParser_ccHandler(MidiMsg msg, uint8_t updateOriginalValue, uint8_t isFloatModulator, float v)
{
	FREEZE_MARK(lastStatus, msg.status);
	FREEZE_MARK(lastData1, msg.data1);

	struct
	{
		uint8_t itg;
		float flt;
	} value;

	if(isFloatModulator)
	{
		value.itg = v*127;
		value.flt = v;
	}
	else
	{
		value.itg = msg.data2;;
		value.flt = value.itg/127.f;
	}

	if((msg.status &0xF0) == MIDI_CC)
	{

		// Legacy CC0 wraps to parameter 127 (Bank Change). Avoid unsigned
		// underflow: kit loading sends this placeholder along with sound CCs.
		const uint16_t paramNr = (uint16_t)((msg.data1 + 127u) & 0x7fu);
		if(updateOriginalValue && !isFloatModulator) {
			midiParser_originalCcValues[msg.data1] = value.itg;
		}

		switch(msg.data1)
		{

		case CC_MOD_WHEEL:

			break;

		case CC_BANK_CHANGE:
			// bank change (coarse) selects kit (sound)
			/*
			 * already send in parseMidiMessage()
			uart_sendFrontpanelByte(MIDI_CC);
			uart_sendFrontpanelByte(CC_BANK_CHANGE);
			uart_sendFrontpanelByte(value.itg);
			*/
			break;

		case NRPN_DATA_ENTRY_COARSE:
			midiParser_nrpnHandler(value.itg);
			return;
			break;

		case NRPN_FINE:
			midiParser_activeNrpnNumber &= ~(0x7f);	//clear lower 7 bit
			midiParser_activeNrpnNumber |= (value.itg&0x7f);
			break;

		case NRPN_COARSE:
			midiParser_activeNrpnNumber &= 0x7f;	//clear upper 7 bit
			midiParser_activeNrpnNumber |= (value.itg<<7);
			break;

		case VOL_SLOPE1:
			slopeEg2_setSlope(&voiceArray[0].oscVolEg,value.itg);

			break;
		case PITCH_SLOPE1:
			DecayEg_setSlope(&voiceArray[0].oscPitchEg,value.itg);
			break;

		case VOL_SLOPE2:
			slopeEg2_setSlope(&voiceArray[1].oscVolEg,value.itg);
			break;
		case PITCH_SLOPE2:
			DecayEg_setSlope(&voiceArray[1].oscPitchEg,value.itg);
			break;

		case VOL_SLOPE3:
			slopeEg2_setSlope(&voiceArray[2].oscVolEg,value.itg);
			break;
		case PITCH_SLOPE3:
			DecayEg_setSlope(&voiceArray[2].oscPitchEg,value.itg);
			break;

		case PITCH_SLOPE4:
			DecayEg_setSlope(&snareVoice.oscPitchEg,value.itg);
			break;
		case VOL_SLOPE6:
			slopeEg2_setSlope(&hatVoice.oscVolEg,value.itg);
			break;

		case FILTER_FREQ_DRUM1:
		case FILTER_FREQ_DRUM2:
		case FILTER_FREQ_DRUM3:
		{
			const float f = value.flt;//value.itg/127.f;
			//exponential full range freq
			fenv_setBase((uint8_t)(msg.data1-FILTER_FREQ_DRUM1),valueShaperF2F(f,FILTER_SHAPER)); // 0.2.93 base for the filter env
		}
			break;
		case RESO_DRUM1:
		case RESO_DRUM2:
		case RESO_DRUM3:
			SVF_setReso(&voiceArray[msg.data1-RESO_DRUM1].filter, value.flt);
			break;

		case F_OSC1_COARSE:
		{
			//clear upper nibble
			voiceArray[0].osc.midiFreq &= 0x00ff;
			//set upper nibble
			voiceArray[0].osc.midiFreq |= value.itg << 8;
			osc_recalcFreq(&voiceArray[0].osc);
		}
			break;
		case F_OSC2_COARSE:
		{
			//clear upper nibble
			voiceArray[1].osc.midiFreq &= 0x00ff;
			//set upper nibble
			voiceArray[1].osc.midiFreq |= value.itg << 8;
			osc_recalcFreq(&voiceArray[1].osc);
		}
				break;
		case F_OSC3_COARSE:
		{
			//clear upper nibble
			voiceArray[2].osc.midiFreq &= 0x00ff;
			//set upper nibble
			voiceArray[2].osc.midiFreq |= value.itg << 8;
			osc_recalcFreq(&voiceArray[2].osc);
		}
				break;
		case F_OSC4_COARSE:
		{
			//clear upper nibble
			snareVoice.osc.midiFreq &= 0x00ff;
			//set upper nibble
			snareVoice.osc.midiFreq |= value.itg << 8;
			osc_recalcFreq(&snareVoice.osc);
		}
				break;
		case F_OSC5_COARSE:
		{
			//clear upper nibble
			cymbalVoice.osc.midiFreq &= 0x00ff;
			//set upper nibble
			cymbalVoice.osc.midiFreq |= value.itg << 8;
			osc_recalcFreq(&cymbalVoice.osc);
		}
				break;

		case F_OSC1_FINE:
		{
			//clear lower nibble
			voiceArray[0].osc.midiFreq &= 0xff00;
			//set lower nibble
			voiceArray[0].osc.midiFreq |= value.itg;
			osc_recalcFreq(&voiceArray[0].osc);
		}
			break;
		case F_OSC2_FINE:
		{
			//clear lower nibble
			voiceArray[1].osc.midiFreq &= 0xff00;
			//set lower nibble
			voiceArray[1].osc.midiFreq |= value.itg;
			osc_recalcFreq(&voiceArray[1].osc);
		}
				break;
		case F_OSC3_FINE:
		{
			//clear lower nibble
			voiceArray[2].osc.midiFreq &= 0xff00;
			//set lower nibble
			voiceArray[2].osc.midiFreq |= value.itg;
			osc_recalcFreq(&voiceArray[2].osc);
		}
				break;
		case F_OSC4_FINE:
		{
			//clear lower nibble
			snareVoice.osc.midiFreq &= 0xff00;
			//set lower nibble
			snareVoice.osc.midiFreq |= value.itg;
			osc_recalcFreq(&snareVoice.osc);
		}
				break;

		case F_OSC5_FINE:
		{
			//clear lower nibble
			cymbalVoice.osc.midiFreq &= 0xff00;
			//set lower nibble
			cymbalVoice.osc.midiFreq |= value.itg;
			osc_recalcFreq(&cymbalVoice.osc);
		}
				break;

		case F_OSC6_FINE:
		{
			//clear lower nibble
			hatVoice.osc.midiFreq &= 0xff00;
			//set lower nibble
			hatVoice.osc.midiFreq |= value.itg;
			osc_recalcFreq(&hatVoice.osc);
		}
				break;

		case OSC_WAVE_DRUM1:
			if(isFloatModulator)
			{
				uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
				wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
				voiceArray[0].osc.waveform = wave;
			}
			else
			{
				voiceArray[0].osc.waveform = value.itg;
			}
			break;

		case MOD_WAVE_DRUM1:
			if(isFloatModulator)
			{
				uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
				wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
				voiceArray[0].modOsc.waveform = wave;
			}
			else
			{
				voiceArray[0].modOsc.waveform = value.itg;
			}
			break;

		case OSC_WAVE_DRUM2:
			if(isFloatModulator)
			{
				uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
				wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
				voiceArray[1].osc.waveform = wave;
			}
			else
			{
				voiceArray[1].osc.waveform = value.itg;
			}
			break;

		case MOD_WAVE_DRUM2:
			if(isFloatModulator)
			{
				uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
				wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
				voiceArray[1].modOsc.waveform = wave;
			}
			else
			{
				voiceArray[1].modOsc.waveform = value.itg;
			}
			break;

		case OSC_WAVE_DRUM3:
			if(isFloatModulator)
			{
				uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
				wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
				voiceArray[2].osc.waveform = wave;
			}
			else
			{
				voiceArray[2].osc.waveform = value.itg;
			}
			break;

		case MOD_WAVE_DRUM3:
			if(isFloatModulator)
			{
				uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
				wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
				voiceArray[2].modOsc.waveform = wave;
			}
			else
			{
				voiceArray[2].modOsc.waveform = value.itg;
			}
			break;

		case OSC_WAVE_SNARE:
			if(isFloatModulator)
			{
				uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
				wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
				snareVoice.osc.waveform = wave;
			}
			else
			{
				snareVoice.osc.waveform = value.itg;
			}
			break;


		case OSC1_DIST:
#if USE_FILTER_DRIVE
			voiceArray[0].filter.drive = 0.5f + (value.itg/127.f) *6;
#else
			setDistortionShape(&voiceArray[0].distortion,value.flt);
#endif
			break;
		case OSC2_DIST:
#if USE_FILTER_DRIVE
			voiceArray[1].filter.drive = 0.5f + (value.itg/127.f)*6;
#else
			setDistortionShape(&voiceArray[1].distortion,value.flt);
#endif
			break;
		case OSC3_DIST:
#if USE_FILTER_DRIVE
			voiceArray[3].filter.drive = 0.5f + (value.itg/127.f)*6;
#else
			setDistortionShape(&voiceArray[2].distortion,value.flt);
#endif
			break;

		case VELOA1:
			slopeEg2_setAttack(&voiceArray[0].oscVolEg,value.itg,AMP_EG_SYNC);
			break;

		case VELOD1:
		{
			slopeEg2_setDecay(&voiceArray[0].oscVolEg,value.itg,AMP_EG_SYNC);
		}
			break;

		case PITCHD1:
		{
			DecayEg_setDecay(&voiceArray[0].oscPitchEg,value.itg);
		}
			break;

		case MODAMNT1:
			voiceArray[0].egPitchModAmount = calcPitchModAmount(value.itg);
			break;

		case FMAMNT1:
			voiceArray[0].fmModAmount = value.flt;
			break;

		case FMDTN1:
			//clear upper nibble
			voiceArray[0].modOsc.midiFreq &= 0x00ff;
			//set upper nibble
			voiceArray[0].modOsc.midiFreq |= value.itg << 8;
			osc_recalcFreq(&voiceArray[0].modOsc);
			break;

		case VOL1:
			voiceArray[0].vol = value.flt;
			break;

		case PAN1:
			setPan(0,value.itg);
			break;

		case VELOA2:
			slopeEg2_setAttack(&voiceArray[1].oscVolEg,value.itg,AMP_EG_SYNC);
			break;

			case VELOD2:
			slopeEg2_setDecay(&voiceArray[1].oscVolEg,value.itg,AMP_EG_SYNC);
			break;

			case PITCHD2:
			DecayEg_setDecay(&voiceArray[1].oscPitchEg,value.itg);
			break;

			case MODAMNT2:
			voiceArray[1].egPitchModAmount = calcPitchModAmount(value.itg);
			break;

			case FMAMNT2:
			voiceArray[1].fmModAmount = value.flt;
				break;

			case FMDTN2:
				//clear upper nibble
				voiceArray[1].modOsc.midiFreq &= 0x00ff;
				//set upper nibble
				voiceArray[1].modOsc.midiFreq |= value.itg << 8;
				osc_recalcFreq(&voiceArray[1].modOsc);
				break;

			case VOL2:
				voiceArray[1].vol = value.flt;
				break;

			case PAN2:
				setPan(1,value.itg);
				break;


			case VELOA3:
				slopeEg2_setAttack(&voiceArray[2].oscVolEg,value.itg,AMP_EG_SYNC);
				break;

			case VELOD3:
				slopeEg2_setDecay(&voiceArray[2].oscVolEg,value.itg,AMP_EG_SYNC);
				break;

			case PITCHD3:
				DecayEg_setDecay(&voiceArray[2].oscPitchEg,value.itg);
				break;

			case MODAMNT3:
				voiceArray[2].egPitchModAmount = calcPitchModAmount(value.itg);
				break;

			case FMAMNT3:
				voiceArray[2].fmModAmount = value.flt;
				break;

			case FMDTN3:
				//clear upper nibble
				voiceArray[2].modOsc.midiFreq &= 0x00ff;
				//set upper nibble
				voiceArray[2].modOsc.midiFreq |= value.itg << 8;
				osc_recalcFreq(&voiceArray[2].modOsc);
				break;

			case VOL3:
				voiceArray[2].vol = value.flt;
				break;

			case PAN3:
				setPan(2,value.itg);
				break;

			//snare
			case VOL4:
				snareVoice.vol = value.flt;
				break;

			case PAN4:
				Snare_setPan(value.itg);

				break;

			case SNARE_NOISE_F:
				snareVoice.noiseOsc.freq = value.flt*22000;
				//TODO respond to midi note
				break;
			case VELOA4:
				slopeEg2_setAttack(&snareVoice.oscVolEg,value.itg,false);
				break;

			case VELOD4:
				slopeEg2_setDecay(&snareVoice.oscVolEg,value.itg,false);
				break;

			case PITCHD4:
				DecayEg_setDecay(&snareVoice.oscPitchEg,value.itg);
				break;

			case MODAMNT4:
				snareVoice.egPitchModAmount = calcPitchModAmount(value.itg);
				break;
			case SNARE_FILTER_F:
				{
					#if USE_PEAK
						peak_setFreq(&snareVoice.filter, value.itg/127.f*20000.f);
					#else
						const float f = value.flt;
						//exponential full range freq
						fenv_setBase(3,valueShaperF2F(f,FILTER_SHAPER)); // 0.2.93
					#endif
				}
					break;

			case SNARE_RESO:
#if USE_PEAK
				peak_setGain(&snareVoice.filter, value.itg/127.f);
#else
				SVF_setReso(&snareVoice.filter, value.flt);
#endif
				break;

			case SNARE_MIX:
				snareVoice.mix = value.flt;
				break;

			//snare 2
			case VOL5:
				cymbalVoice.vol = value.flt;
				break;

			case PAN5:
				Cymbal_setPan(value.itg);
				break;

			case VELOA5:
				slopeEg2_setAttack(&cymbalVoice.oscVolEg,value.itg,false);
				break;

			case VELOD5:
				slopeEg2_setDecay(&cymbalVoice.oscVolEg,value.itg,false);
				break;

			case CYM_WAVE1:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
					wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
					cymbalVoice.osc.waveform = wave;
				}
				else
				{
					cymbalVoice.osc.waveform = value.itg;
				}
				break;

			case CYM_WAVE2:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
					wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
					cymbalVoice.modOsc.waveform = wave;
				}
				else
				{
					cymbalVoice.modOsc.waveform = value.itg;
				}
				break;

			case CYM_WAVE3:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
					wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
					cymbalVoice.modOsc2.waveform = wave;
				}
				else
				{
					cymbalVoice.modOsc2.waveform = value.itg;
				}
				break;

			case CYM_MOD_OSC_F1:
				//cymbalVoice.modOsc.freq = MidiNoteFrequencies[value.itg];
				//clear upper nibble
				cymbalVoice.modOsc.midiFreq &= 0x00ff;
				//set upper nibble
				cymbalVoice.modOsc.midiFreq |= value.itg << 8;
				osc_recalcFreq(&cymbalVoice.modOsc);
				break;

			case CYM_MOD_OSC_F2:
				//clear upper nibble
				cymbalVoice.modOsc2.midiFreq &= 0x00ff;
				//set upper nibble
				cymbalVoice.modOsc2.midiFreq |= value.itg << 8;
				osc_recalcFreq(&cymbalVoice.modOsc2);
				break;

			case CYM_MOD_OSC_GAIN1:
				cymbalVoice.fmModAmount1 = value.flt;
				break;

			case CYM_MOD_OSC_GAIN2:
				cymbalVoice.fmModAmount2 = value.flt;
				break;

			case CYM_FIL_FREQ:
			{
				const float f = value.flt;
				//exponential full range freq
				fenv_setBase(4,valueShaperF2F(f,FILTER_SHAPER)); // 0.2.93
			}
				break;

			case CYM_RESO:
				SVF_setReso(&cymbalVoice.filter, value.flt);
				break;

			case CYM_REPEAT:
				cymbalVoice.oscVolEg.repeat = value.itg;
				break;
			case CYM_SLOPE:
				slopeEg2_setSlope(&cymbalVoice.oscVolEg,value.itg);
				break;

			// hat
			case WAVE1_HH:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
					wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
					hatVoice.osc.waveform = wave;
				}
				else
				{
					hatVoice.osc.waveform = value.itg;
				}
				break;

			case WAVE2_HH:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
					wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
					hatVoice.modOsc.waveform = wave;
				}
				else
				{
					hatVoice.modOsc.waveform = value.itg;
				}
				break;
			case WAVE3_HH:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_OSC_WAVEFORMS * value.flt;
					wave = wave >= NUM_OSC_WAVEFORMS ? NUM_OSC_WAVEFORMS-1 : wave;
					hatVoice.modOsc2.waveform = wave;
				}
				else
				{
					hatVoice.modOsc2.waveform = value.itg;
				}
				break;

			case VELOD6:
				hatVoice.decayClosed = slopeEg2_calcDecay(value.itg);
				break;

			case VELOD6_OPEN:
				hatVoice.decayOpen = slopeEg2_calcDecay(value.itg);
				break;

			case HAT_FILTER_F:
				{
					const float f = value.flt;
					//exponential full range freq
					fenv_setBase(5,valueShaperF2F(f,FILTER_SHAPER)); // 0.2.93
				}
				break;

			case HAT_RESO:
				SVF_setReso(&hatVoice.filter, value.flt);
				break;

			case VOL6:
				hatVoice.vol = value.flt;
				break;

			case PAN6:
				HiHat_setPan(value.itg);
				break;

			case F_OSC6_COARSE:
				{
					//clear upper nibble
					hatVoice.osc.midiFreq &= 0x00ff;
					//set upper nibble
					hatVoice.osc.midiFreq |= value.itg << 8;
					osc_recalcFreq(&hatVoice.osc);
				}
				break;

			case MOD_OSC_F1:
				//clear upper nibble
				hatVoice.modOsc.midiFreq &= 0x00ff;
				//set upper nibble
				hatVoice.modOsc.midiFreq |= value.itg << 8;
				osc_recalcFreq(&hatVoice.modOsc);
				break;

			case MOD_OSC_F2:
				//clear upper nibble
				hatVoice.modOsc2.midiFreq &= 0x00ff;
				//set upper nibble
				hatVoice.modOsc2.midiFreq |= value.itg << 8;
				osc_recalcFreq(&hatVoice.modOsc2);
				break;

			case MOD_OSC_GAIN1:
				hatVoice.fmModAmount1 = value.flt;
				break;

			case MOD_OSC_GAIN2:
				hatVoice.fmModAmount2 = value.flt;
				break;

			case VELOA6:
				slopeEg2_setAttack(&hatVoice.oscVolEg,value.itg,false);
				break;

			case REPEAT1:
				snareVoice.oscVolEg.repeat = value.itg;
				break;


			case EG_SNARE1_SLOPE:
				slopeEg2_setSlope(&snareVoice.oscVolEg,value.itg);
				break;

			case SNARE_DISTORTION:
				setDistortionShape(&snareVoice.distortion,value.flt);
				break;

			case CYMBAL_DISTORTION:
				setDistortionShape(&cymbalVoice.distortion,value.flt);
				break;

			case HAT_DISTORTION:
				setDistortionShape(&hatVoice.distortion,value.flt);
				break;

			case FREQ_LFO1:
			case FREQ_LFO2:
			case FREQ_LFO3:
				lfo_setFreq(&voiceArray[msg.data1-FREQ_LFO1].lfo,value.flt);
								break;
			case FREQ_LFO4:
				lfo_setFreq(&snareVoice.lfo,value.flt);
								break;
			case FREQ_LFO5:
				lfo_setFreq(&cymbalVoice.lfo,value.flt);
								break;
			case FREQ_LFO6:
				lfo_setFreq(&hatVoice.lfo,value.flt);
				break;

			case AMOUNT_LFO1:
			case AMOUNT_LFO2:
			case AMOUNT_LFO3:
				voiceArray[msg.data1-AMOUNT_LFO1].lfo.modTarget.amount = value.flt;
				break;
			case AMOUNT_LFO4:
				snareVoice.lfo.modTarget.amount = value.flt;
				break;
			case AMOUNT_LFO5:
				cymbalVoice.lfo.modTarget.amount = value.flt;
				break;
			case AMOUNT_LFO6:
				hatVoice.lfo.modTarget.amount = value.flt;
				break;

			case VOICE_DECIMATION1:
			case VOICE_DECIMATION2:
			case VOICE_DECIMATION3:
			case VOICE_DECIMATION4:
			case VOICE_DECIMATION5:
			case VOICE_DECIMATION6:
			case VOICE_DECIMATION_ALL:
				mixer_decimation_rate[msg.data1-VOICE_DECIMATION1] = valueShaperF2F(value.flt,-0.7f); ;//valueShaperI2F(value.itg,-0.7f);
				break;

			default:
				break;
		}
		if(!isFloatModulator)
		{
			if(updateOriginalValue) midiParser_refreshVelocityParameter(msg.data1);
			modNode_originalValueChanged(paramNr);
		}
	} //msg.status == MIDI_CC

	else //MIDI_CC2
	{
		const uint16_t paramNr = msg.data1 + 1 + 127;

		if(updateOriginalValue && !isFloatModulator) {
			midiParser_originalCcValues[paramNr] = value.itg;
		}
		switch(msg.data1)
		{

			case CC2_TRANS1_WAVE:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_TRANSIENTS * value.flt;
					wave = wave >= NUM_TRANSIENTS ? NUM_TRANSIENTS-1 : wave;
					transient_setWaveform(&voiceArray[0].transGen, wave);
				}
				else
				{
					transient_setWaveform(&voiceArray[0].transGen, value.itg);
				}
				break;

			case CC2_TRANS1_VOL:
				voiceArray[0].transGen.volume = value.flt;
				break;

			case CC2_TRANS1_FREQ:
				voiceArray[0].transGen.pitch = 1.f + ((value.itg/33.9f)-0.75f) ;// range about  0.25 to 4 => 1/4 to 1*4
				break;

			case CC2_TRANS2_WAVE:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_TRANSIENTS * value.flt;
					wave = wave >= NUM_TRANSIENTS ? NUM_TRANSIENTS-1 : wave;
					transient_setWaveform(&voiceArray[1].transGen, wave);
				}
				else
				{
					transient_setWaveform(&voiceArray[1].transGen, value.itg);
				}
				break;

			case CC2_TRANS2_VOL:
				voiceArray[1].transGen.volume = value.flt;
				break;

			case CC2_TRANS2_FREQ:
				voiceArray[1].transGen.pitch = 1.f + ((value.itg/33.9f)-0.75f) ;
				break;

			case CC2_TRANS3_WAVE:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_TRANSIENTS * value.flt;
					wave = wave >= NUM_TRANSIENTS ? NUM_TRANSIENTS-1 : wave;
					transient_setWaveform(&voiceArray[2].transGen, wave);
				}
				else
				{
					transient_setWaveform(&voiceArray[2].transGen, value.itg);
				}
				break;

			case CC2_TRANS3_VOL:
				voiceArray[2].transGen.volume = value.flt;
				break;

			case CC2_TRANS3_FREQ:
				voiceArray[2].transGen.pitch = 1.f + ((value.itg/33.9f)-0.75f) ;
				break;

			case CC2_TRANS4_WAVE:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_TRANSIENTS * value.flt;
					wave = wave >= NUM_TRANSIENTS ? NUM_TRANSIENTS-1 : wave;
					transient_setWaveform(&snareVoice.transGen, wave);
				}
				else
				{
					transient_setWaveform(&snareVoice.transGen, value.itg);
				}
				break;

			case CC2_TRANS4_VOL:
				snareVoice.transGen.volume = value.flt;
				break;
			case CC2_TRANS4_FREQ:
				snareVoice.transGen.pitch = 1.f + ((value.itg/33.9f)-0.75f) ;
				break;

			case CC2_TRANS5_WAVE:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_TRANSIENTS * value.flt;
					wave = wave >= NUM_TRANSIENTS ? NUM_TRANSIENTS-1 : wave;
					transient_setWaveform(&cymbalVoice.transGen, wave);
				}
				else
				{
					transient_setWaveform(&cymbalVoice.transGen, value.itg);
				}
				break;

			case CC2_TRANS5_VOL:
				cymbalVoice.transGen.volume = value.flt;
				break;
			case CC2_TRANS5_FREQ:
				cymbalVoice.transGen.pitch = 1.f + ((value.itg/33.9f)-0.75f) ;
				break;

			case CC2_TRANS6_WAVE:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_TRANSIENTS * value.flt;
					wave = wave >= NUM_TRANSIENTS ? NUM_TRANSIENTS-1 : wave;
					transient_setWaveform(&hatVoice.transGen, wave);
				}
				else
				{
					transient_setWaveform(&hatVoice.transGen, value.itg);
				}
				break;

			case CC2_TRANS6_VOL:
				hatVoice.transGen.volume = value.flt;
				break;
			case CC2_TRANS6_FREQ:
				hatVoice.transGen.pitch = 1.f + ((value.itg/33.9f)-0.75f) ;
				break;

			case CC2_FILTER_TYPE_1:
			case CC2_FILTER_TYPE_2:
			case CC2_FILTER_TYPE_3:
				if(isFloatModulator)
				{
					uint8_t type = FILTER_NAIVE_2_POLE * value.flt + 1;
					type = type >= FILTER_OFF ? FILTER_OFF-1 : type;
					voiceArray[msg.data1-CC2_FILTER_TYPE_1].filterType = type;
				}
				else
				{
					voiceArray[msg.data1-CC2_FILTER_TYPE_1].filterType = value.itg+1;
				}
				break;

			case CC2_FILTER_TYPE_4:
				if(isFloatModulator)
				{
					uint8_t type = FILTER_NAIVE_2_POLE * value.flt + 1;
					type = type >= FILTER_OFF ? FILTER_OFF-1 : type;
					snareVoice.filterType = type;
				}
				else
				{
					snareVoice.filterType = value.itg + 1; // +1 because 0 is filter off which results in silence
				}
				break;

			case CC2_FILTER_TYPE_5:
				//cymbal filter
				if(isFloatModulator)
				{
					uint8_t type = FILTER_NAIVE_2_POLE * value.flt + 1;
					type = type >= FILTER_OFF ? FILTER_OFF-1 : type;
					cymbalVoice.filterType = type;
				}
				else
				{
					cymbalVoice.filterType = value.itg+1;
				}
				break;

			case CC2_FILTER_TYPE_6:
				//Hihat filter
				if(isFloatModulator)
				{
					uint8_t type = FILTER_NAIVE_2_POLE * value.flt + 1;
					type = type >= FILTER_OFF ? FILTER_OFF-1 : type;
					hatVoice.filterType = type;
				}
				else
				{
					hatVoice.filterType = value.itg+1;
				}
				//SVF_reset(&hatVoice.filter);
				break;

			case CC2_FILTER_DRIVE_1:
			case CC2_FILTER_DRIVE_2:
			case CC2_FILTER_DRIVE_3:
#if UNIT_GAIN_DRIVE
				voiceArray[msg.data1-CC2_FILTER_DRIVE_1].filter.drive = (value.itg/127.f);
#else
				SVF_setDrive(&voiceArray[msg.data1-CC2_FILTER_DRIVE_1].filter, value.flt);
#endif
				break;
			case CC2_FILTER_DRIVE_4:
#if UNIT_GAIN_DRIVE
				snareVoice.filter.drive = (value.itg/127.f);
#else
				SVF_setDrive(&snareVoice.filter, value.flt);
#endif

				break;
			case CC2_FILTER_DRIVE_5:
#if UNIT_GAIN_DRIVE
				cymbalVoice.filter.drive = (value.itg/127.f);
#else
				SVF_setDrive(&cymbalVoice.filter, value.flt);
#endif

				break;
			case CC2_FILTER_DRIVE_6:
#if UNIT_GAIN_DRIVE
				hatVoice.filter.drive = (value.itg/127.f);
#else
				SVF_setDrive(&hatVoice.filter, value.flt);
#endif

				break;

			case CC2_MIX_MOD_1:
			case CC2_MIX_MOD_2:
			case CC2_MIX_MOD_3:
				voiceArray[msg.data1-CC2_MIX_MOD_1].mixOscs = isFloatModulator ? (uint8_t)(v*4.f+0.5f) : value.itg > 4 ? 4 : value.itg;
				break;

			case PAR_SNARE_NOISE_ATTACK-128:
				Snare_setNoiseAttack(value.itg);
				break;
			case PAR_SNARE_NOISE_DECAY-128:
				Snare_setNoiseDecay(value.itg);
				break;
			case PAR_SNARE_NOISE_SLOPE-128:
				Snare_setNoiseSlope(value.itg);
				break;
			case PAR_SNARE_LAYER_WAVE-128: {
				uint8_t maximum=menu_getWaveformMax();
				uint8_t wave=isFloatModulator ? (uint8_t)(v*maximum+0.5f) : value.itg;
				Snare_setLayerWave(wave>maximum ? maximum : wave); break;
			}
			case PAR_SNARE_LAYER_AMOUNT-128: Snare_setLayerAmount(value.itg); break;
			case PAR_SNARE_LAYER_FREQ-128: Snare_setLayerFreq(value.itg); break;
			case PAR_SNARE_LAYER_MODE-128:
				Snare_setLayerMode(isFloatModulator ? (uint8_t)(v*SNARE_LAYER_MODE_MAX+0.5f) : value.itg); break;

			case CC2_VOLUME_MOD_ON_OFF1:
			case CC2_VOLUME_MOD_ON_OFF2:
			case CC2_VOLUME_MOD_ON_OFF3:
				voiceArray[msg.data1-CC2_VOLUME_MOD_ON_OFF1].volumeMod = value.itg != 0;
				break;
			case CC2_VOLUME_MOD_ON_OFF4:
				snareVoice.volumeMod = value.itg != 0;
				break;
			case CC2_VOLUME_MOD_ON_OFF5:
				cymbalVoice.volumeMod = value.itg != 0;
				break;
			case CC2_VOLUME_MOD_ON_OFF6:
				hatVoice.volumeMod = value.itg != 0;
				break;

            case CC2_VEL_DEST_1: case CC2_VEL_DEST_2: case CC2_VEL_DEST_3:
            case CC2_VEL_DEST_4: case CC2_VEL_DEST_5: case CC2_VEL_DEST_6: {
                uint8_t voice=(uint8_t)(msg.data1-CC2_VEL_DEST_1);
                uint8_t destination=value.itg;
                modNode_setDestination(&velocityModulators[voice],destination);
                activeParameters[PAR_VEL_DEST_1+voice]=modTargetFromParam(destination,voice);	// 0.2.107
                break;
            }
			case CC2_VELO_MOD_AMT_1:
			case CC2_VELO_MOD_AMT_2:
			case CC2_VELO_MOD_AMT_3:
			case CC2_VELO_MOD_AMT_4:
			case CC2_VELO_MOD_AMT_5:
			case CC2_VELO_MOD_AMT_6:
				velocityModulators[msg.data1-CC2_VELO_MOD_AMT_1].amount = value.flt;
				break;

			case CC2_WAVE_LFO1:
			case CC2_WAVE_LFO2:
			case CC2_WAVE_LFO3:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_LFO_WAVEFORMS * value.flt;
					wave = wave >= NUM_LFO_WAVEFORMS ? NUM_LFO_WAVEFORMS-1 : wave;
					lfo_setWaveform(&voiceArray[msg.data1-CC2_WAVE_LFO1].lfo,wave);
				}
				else
				{
					lfo_setWaveform(&voiceArray[msg.data1-CC2_WAVE_LFO1].lfo,value.itg);
				}
				break;

			case CC2_WAVE_LFO4:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_LFO_WAVEFORMS * value.flt;
					wave = wave >= NUM_LFO_WAVEFORMS ? NUM_LFO_WAVEFORMS-1 : wave;
					lfo_setWaveform(&snareVoice.lfo,wave);
				}
				else
				{
					lfo_setWaveform(&snareVoice.lfo,value.itg);
				}
				break;

			case CC2_WAVE_LFO5:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_LFO_WAVEFORMS * value.flt;
					wave = wave >= NUM_LFO_WAVEFORMS ? NUM_LFO_WAVEFORMS-1 : wave;
					lfo_setWaveform(&cymbalVoice.lfo,wave);
				}
				else
				{
					lfo_setWaveform(&cymbalVoice.lfo,value.itg);
				}
				break;

			case CC2_WAVE_LFO6:
				if(isFloatModulator)
				{
					uint8_t wave = NUM_LFO_WAVEFORMS * value.flt;
					wave = wave >= NUM_LFO_WAVEFORMS ? NUM_LFO_WAVEFORMS-1 : wave;
					lfo_setWaveform(&hatVoice.lfo,wave);
				}
				else
				{
					lfo_setWaveform(&hatVoice.lfo,value.itg);
				}
				break;

			case CC2_RETRIGGER_LFO1:
			case CC2_RETRIGGER_LFO2:
			case CC2_RETRIGGER_LFO3:
				if(isFloatModulator)
				{
					uint8_t voice = 7 * value.flt;
					voiceArray[msg.data1-CC2_RETRIGGER_LFO1].lfo.retrigger = voice;
				}
				else
				{
					voiceArray[msg.data1-CC2_RETRIGGER_LFO1].lfo.retrigger = value.itg;
				}
				break;
			case CC2_RETRIGGER_LFO4:
				if(isFloatModulator)
				{
					uint8_t voice = 7 * value.flt;
					snareVoice.lfo.retrigger = voice;
				}
				else
				{
					snareVoice.lfo.retrigger = value.itg;
				}
				break;

			case CC2_RETRIGGER_LFO5:
				if(isFloatModulator)
				{
					uint8_t voice = 7 * value.flt;
					cymbalVoice.lfo.retrigger = voice;
				}
				else
				{
					cymbalVoice.lfo.retrigger = value.itg;
				}
				break;

			case CC2_RETRIGGER_LFO6:
				if(isFloatModulator)
				{
					uint8_t voice = 7 * value.flt;
					hatVoice.lfo.retrigger = voice;
				}
				else
				{
					hatVoice.lfo.retrigger = value.itg;
				}
				break;

			case CC2_SYNC_LFO1:
			case CC2_SYNC_LFO2:
			case CC2_SYNC_LFO3:
				lfo_setSync(&voiceArray[msg.data1-CC2_SYNC_LFO1].lfo, value.itg);
				break;
			case CC2_SYNC_LFO4:
				lfo_setSync(&snareVoice.lfo, value.itg);
				break;
			case CC2_SYNC_LFO5:
				lfo_setSync(&cymbalVoice.lfo, value.itg);
				break;
			case CC2_SYNC_LFO6:
				lfo_setSync(&hatVoice.lfo, value.itg);
				break;

            case CC2_VOICE_LFO1: case CC2_VOICE_LFO2: case CC2_VOICE_LFO3:
            case CC2_VOICE_LFO4: case CC2_VOICE_LFO5: case CC2_VOICE_LFO6: {
                uint8_t voice=(uint8_t)(msg.data1-CC2_VOICE_LFO1);
                uint8_t targetVoice=value.itg<1 ? 1 : value.itg>6 ? 6 : value.itg;
                uint8_t gap=getModTargetGapIndex(activeParameters[PAR_TARGET_LFO1+voice]);
                uint8_t target=getModTargetIdxFromGapIdx((uint8_t)(targetVoice-1),gap);
                activeParameters[PAR_VOICE_LFO1+voice]=targetVoice;
                activeParameters[PAR_TARGET_LFO1+voice]=target;
                modNode_setDestination(&midiParser_voiceLfo(voice)->modTarget,modTargets[target].param);
                break;
            }
            case CC2_TARGET_LFO1: case CC2_TARGET_LFO2: case CC2_TARGET_LFO3:
            case CC2_TARGET_LFO4: case CC2_TARGET_LFO5: case CC2_TARGET_LFO6: {
                uint8_t voice=(uint8_t)(msg.data1-CC2_TARGET_LFO1);
                uint8_t destination=value.itg;
                modNode_setDestination(&midiParser_voiceLfo(voice)->modTarget,destination);
                uint8_t target=modTargetFromParam(destination,(uint8_t)(activeParameters[PAR_VOICE_LFO1+voice]-1));	// 0.2.107
                activeParameters[PAR_TARGET_LFO1+voice]=target;
                uint8_t targetVoice=voiceFromModTargValue(target);
                if(targetVoice)activeParameters[PAR_VOICE_LFO1+voice]=targetVoice;
                break;
            }



			case CC2_OFFSET_LFO1:
			case CC2_OFFSET_LFO2:
			case CC2_OFFSET_LFO3:
				lfo_setPhaseOffset(&voiceArray[msg.data1-CC2_OFFSET_LFO1].lfo,value.itg);
				break;
			case CC2_OFFSET_LFO4:
				lfo_setPhaseOffset(&snareVoice.lfo,value.itg);
				break;
			case CC2_OFFSET_LFO5:
				lfo_setPhaseOffset(&cymbalVoice.lfo,value.itg);
				break;
			case CC2_OFFSET_LFO6:
				lfo_setPhaseOffset(&hatVoice.lfo,value.itg);
				break;

			case CC2_AUDIO_OUT1:
			case CC2_AUDIO_OUT2:
			case CC2_AUDIO_OUT3:
			case CC2_AUDIO_OUT4:
			case CC2_AUDIO_OUT5:
			case CC2_AUDIO_OUT6:
				mixer_audioRouting[msg.data1-CC2_AUDIO_OUT1] = value.itg;
				break;

				/*
			case CC2_MIDI_NOTE1:
			case CC2_MIDI_NOTE2:
			case CC2_MIDI_NOTE3:
			case CC2_MIDI_NOTE4:
			case CC2_MIDI_NOTE5:
			case CC2_MIDI_NOTE6:
			case CC2_MIDI_NOTE7:
				// set the note override for the voice. 0 means use the note value, anything else means
				// that the note will always play with that note
				//midi_NoteOverride[msg.data1-CC2_MIDI_NOTE1] = value.itg;
				break;
				*/

			case CC2_MUTE_1:
			case CC2_MUTE_2:
			case CC2_MUTE_3:
			case CC2_MUTE_4:
			case CC2_MUTE_5:
			case CC2_MUTE_6:
			case CC2_MUTE_7:
			{
				const uint8_t voiceNr = msg.data1 - CC2_MUTE_1;
				if(value.itg == 0)
				{
					seq_setMute(voiceNr,0);
				}
				else
				{
					seq_setMute(voiceNr,1);
				}

			}
				break;

			case CC2_PWM_1:
			case CC2_PWM_2:
			case CC2_PWM_3:
				voiceArray[msg.data1-CC2_PWM_1].pwm = value.flt;
				break;
			case CC2_PWM_4:
				snareVoice.pwm = value.flt;
				break;
			case CC2_PWM_5:
				cymbalVoice.pwm = value.flt;
				break;
			case CC2_PWM_6:
				hatVoice.pwm = value.flt;
				break;

			case CC2_FX_TYPE:
#if 1
				// Clamp types this firmware does not have
				if(value.itg > FX_PHASER) value.itg = FX_OFF;
				if( fxBus.fxType != value.itg) {
					FxBus_prepareFxChange();
#if USE_REVERB
					/* 0.2.71: delay and reverb read FX_BUFFER in different layouts;
					 * clear it when the reverb comes or goes, else the new effect
					 * plays the old one's data as a noise burst (~75 us). */
					if(value.itg == FX_REVERB || fxBus.fxType == FX_REVERB)
						memset((void*)FX_BUFFER, 0, sizeof(FX_BUFFER));
#endif
				}
				fxBus.fxType = value.itg;
				FxBus_updateParameter();
				activeParameters[PAR_SEND_FX] = FxBus_sendIndex(fxBus.fxType); // 0.2.79 snd follows
				//change visible parameters to selected FX type
				if(menu_activePage == FX_MODE_PAGE && !activeParameters[PAR_FX_PAGE])
				{
					/* 0.2.81: only the send page follows; an insert page stays */
					if(menu_getSubPage() != menu_fxPageRow(0))
						menu_switchSubPage(menu_fxPageRow(0), 0 );
				}
#endif
				break;
			case CC2_FX_ROUTING:
				fxBus.audioRouting = value.itg;
				break;
			case CC2_FX_AMOUNT:
				fxBus.dryWet = (isFloatModulator && value.itg>100) ? 1.f : value.itg/100.f;
				break;

			case CC2_FX_DIST_TYPE:
				fxBus.distortion.distortionType = value.itg;
				break;

			case CC2_FX_P1:
				FxBus_setParameter(0, value.flt);
				break;

			case CC2_FX_P2:
				FxBus_setParameter(1, value.flt);
				//fxBus.distortion.p1 = value.itg/127.f;
				break;

			case CC2_FX_P3:
				FxBus_setParameter(2, value.flt);
				//fxBus.distortion.p1 = value.itg/127.f;
				break;

			case CC2_FX_P4:
				FxBus_setParameter(3, value.flt);
				//fxBus.distortion.p1 = value.itg/127.f;
				break;

			case CC2_FX_RATIO:
				Compressor_setRatio(&fxBus.compressor, value.itg);
				break;

			case CC2_FX_WAVE:
				Ringmod_setWave(&fxBus.ringmod, value.itg);
				break;

			case CC2_FX_REVERB_TYPE:
				TapeDelay_setPingPong(&fxBus.tape, value.itg);
				break;

			case CC2_FX_DELAY_TYPE:
				fxBus.delay.delayType = value.itg;
			break;

			default:
				break;
		}
		if(!isFloatModulator)
		{
			if(updateOriginalValue) midiParser_refreshVelocityParameter(paramNr);
			modNode_originalValueChanged(paramNr);
		}
	}
}

static const uint8_t midiParser_filterParams[6]={FILTER_FREQ_DRUM1,FILTER_FREQ_DRUM2,FILTER_FREQ_DRUM3,SNARE_FILTER_F,CYM_FIL_FREQ,HAT_FILTER_F};
static const uint8_t midiParser_slopeParams[6]={VOL_SLOPE1,VOL_SLOPE2,VOL_SLOPE3,EG_SNARE1_SLOPE,CYM_SLOPE,VOL_SLOPE6};
static uint8_t midiParser_velocityLive(void)
{
	if(activeParameters[PAR_PERF_VELO_LEVEL]==63)return 0;
	for(uint16_t p=PAR_PERF_VELO_DECAY;p<=PAR_PERF_VELO_DRIVE;p++)
		if(activeParameters[p]!=63)return 1;
	return 0;
}
static void midiParser_velocityCc(uint16_t parameter,uint16_t depth,uint8_t velocity)
{
	MidiMsg msg={0};
	msg.data2=midiParser_applyVelocityDepth(midiParser_originalCcValues[parameter],
		midiParser_velocityAmount(depth),velocity);
	if(parameter<128){msg.status=MIDI_CC;msg.data1=(uint8_t)parameter;}
	else {msg.status=MIDI_CC2;msg.data1=(uint8_t)(parameter-128);}
	midiParser_ccHandler(msg,0,0,0.f);
}
static void midiParser_applyVelocityDestination(uint8_t track,uint16_t destination)
{
	if(destination==PAR_PERF_VELO_DECAY) {
		midiParser_applyGlobalDecayParam(midiParser_decayParams[track]);return;
	}
	uint8_t sound=track>5?5:track;
	uint8_t owner=sound==5?midiParser_lastHatTrack:track;
	uint8_t velocity=midiParser_velocityForTrack(owner);
	switch(destination) {
	case PAR_PERF_VELO_SAMPLE_RATE:
		midiParser_velocityCc((uint16_t)(VOICE_DECIMATION1+sound),destination,velocity);break;
	case PAR_PERF_VELO_FILTER:
		midiParser_velocityCc(midiParser_filterParams[sound],destination,velocity);break;
	case PAR_PERF_VELO_SLOPE:
		midiParser_velocityCc(midiParser_slopeParams[sound],destination,velocity);break;
	case PAR_PERF_VELO_DRIVE:
		midiParser_velocityCc((uint16_t)(128+CC2_FILTER_DRIVE_1+sound),destination,velocity);break;
	case PAR_PERF_VELO_MOD_AMOUNT:
		if(sound<4)midiParser_velocityCc((uint16_t)(MODAMNT1+sound),destination,velocity);
		else if(sound==4) {
			midiParser_velocityCc(CYM_MOD_OSC_GAIN1,destination,velocity);
			midiParser_velocityCc(CYM_MOD_OSC_GAIN2,destination,velocity);
		}
		break;
	default: break; // coarse modulation is applied to the next played note
	}
}
static void midiParser_refreshVelocityVoice(uint8_t track)
{
	// Neutral destinations must not overwrite step automation or LFO state.
	for(uint16_t p=PAR_PERF_VELO_DECAY;p<=PAR_PERF_VELO_DRIVE;p++)
		if(midiParser_velocityAmount(p)!=63)midiParser_applyVelocityDestination(track,p);
}
static void midiParser_refreshVelocityParameter(uint16_t parameter)
{
	for(uint8_t track=0;track<7;track++)if(parameter==midiParser_decayParams[track]) {
		if(midiParser_globalDecay!=63 || midiParser_velocityAmount(PAR_PERF_VELO_DECAY)!=63)
			midiParser_applyGlobalDecayParam((uint8_t)parameter);
		return;
	}
	if(!midiParser_velocityLive())return;
	for(uint8_t sound=0;sound<6;sound++) {
		uint16_t destination=PAR_NONE;
		if(parameter==VOICE_DECIMATION1+sound)destination=PAR_PERF_VELO_SAMPLE_RATE;
		if(parameter==midiParser_filterParams[sound])destination=PAR_PERF_VELO_FILTER;
		if(parameter==midiParser_slopeParams[sound])destination=PAR_PERF_VELO_SLOPE;
		if(parameter==128+CC2_FILTER_DRIVE_1+sound)destination=PAR_PERF_VELO_DRIVE;
		if((sound<4 && parameter==MODAMNT1+sound) ||
		   (sound==4 && (parameter==CYM_MOD_OSC_GAIN1 || parameter==CYM_MOD_OSC_GAIN2)))
			destination=PAR_PERF_VELO_MOD_AMOUNT;
		if(destination!=PAR_NONE && midiParser_velocityAmount(destination)!=63) {
			midiParser_applyVelocityDestination(sound==5?midiParser_lastHatTrack:sound,destination);
			return;
		}
	}
}
/* 0.2.99 a vlv/velo change re-applies up to 7 destinations x 7 tracks; done
 * at once it held the main loop past the audio block (click). Each change
 * only marks the tracks, the main loop applies one per pass. */
static uint8_t midiParser_velocityPending[7];
uint8_t midiParser_velocityTick(void)
{
	for(uint8_t i=0;i<7;i++) {
		const uint8_t mask=midiParser_velocityPending[i];
		if(!mask)continue;
		uint8_t track=0;
		while(!(mask&(1u<<track)))track++;
		midiParser_velocityPending[i]=(uint8_t)(mask&~(1u<<track));
		midiParser_applyVelocityDestination(track,(uint16_t)(PAR_PERF_VELO_DECAY+i));
		return 1;
	}
	return 0;
}
void midiParser_setAccentParameter(uint16_t param,uint8_t value)
{
	if(param!=PAR_PERF_VELO_LEVEL && (param<PAR_PERF_VELO_DECAY || param>PAR_PERF_VELO_DRIVE))return;
	uint8_t oldDepth[7];
	for(uint8_t i=0;i<7;i++)oldDepth[i]=midiParser_velocityAmount((uint16_t)(PAR_PERF_VELO_DECAY+i));
	activeParameters[param]=value>127?127:value;
	for(uint8_t i=0;i<7;i++) {
		uint16_t destination=(uint16_t)(PAR_PERF_VELO_DECAY+i);
		uint8_t newDepth=midiParser_velocityAmount(destination);
		(void)destination;
		if(oldDepth[i]!=newDepth)midiParser_velocityPending[i]=0x7f; // 0.2.99 applied by midiParser_velocityTick
	}
	menu_repaint();
}
uint8_t midiParser_applyPerformanceVelocity(uint8_t voice,uint8_t velocity,uint8_t note)
{
	if(voice>6)return note;
	midiParser_modVelocity[voice]=velocity;
	midiParser_modVelocityValid |= (uint8_t)(1u<<voice);
	if(voice>=5)midiParser_lastHatTrack=voice;
	if(!midiParser_velocityLive())return note;
	midiParser_refreshVelocityVoice(voice);
	uint8_t sound=voice>5?5:voice;
	uint8_t coarse=(uint8_t)(F_OSC1_COARSE+sound*2u);
	uint8_t base=midiParser_originalCcValues[coarse];
	uint8_t value=midiParser_applyVelocityDepth(base,midiParser_velocityAmount(PAR_PERF_VELO_COARSE),velocity);
	int16_t shifted=(int16_t)note+value-base;
	if(shifted<0)shifted=0;
	if(shifted>127)shifted=127;
	return (uint8_t)shifted;
}
void midiParser_setDelayParameter(uint16_t param,uint8_t value)
{
	if(param<PAR_PERF_DELAY_CHANCE || param>PAR_PERF_DELAY_INPUT_MASK)return;
	uint8_t maximum=127;
	if(param==PAR_PERF_DELAY_CHANCE)maximum=100;
	if(param==PAR_PERF_DELAY_SYNC)maximum=15;
	if(param==PAR_PERF_DELAY_COUNT)maximum=32;
	if(param==PAR_PERF_DELAY_TARGET)maximum=10;
	if(param==PAR_PERF_DELAY_MODE)maximum=1;
	activeParameters[param]=value>maximum?maximum:value;
	PerfDelayConfig cfg={activeParameters[PAR_PERF_DELAY_CHANCE],activeParameters[PAR_PERF_DELAY_SYNC],
		activeParameters[PAR_PERF_DELAY_COUNT],activeParameters[PAR_PERF_DELAY_BOUNCE],
		activeParameters[PAR_PERF_DELAY_TARGET],activeParameters[PAR_PERF_DELAY_MODE],
		activeParameters[PAR_PERF_DELAY_EXP],activeParameters[PAR_PERF_DELAY_INPUT_MASK],
		(int8_t)(((uint16_t)activeParameters[PAR_PERF_DELAY_PITCH]*24u+63u)/127u-12)};
	perf_delayConfigure(cfg);
	if(param==PAR_PERF_DELAY_INPUT_MASK)buttonHandler_refreshVoiceDisplay();
	menu_repaint();
}
uint8_t midiParser_isValidChannel(uint8_t chan);
/* Numbers with a legacy meaning: like Morph CC2 they need a Pch of their own. */
static uint8_t midiParser_needsOwnPch(uint8_t cc)
{
	return (cc>=53 && cc<=59) || (cc>=67 && cc<=75) || (cc>=92 && cc<=97) || (cc>=102 && cc<=119);
}
static uint8_t midiParser_scaleCc(uint8_t value,uint8_t maximum)
{
	return (uint8_t)(((uint16_t)value*maximum+63u)/127u);
}
static uint8_t midiParser_menuCc(uint16_t parameter,uint8_t value)
{
	activeParameters[parameter]=value;
	menu_parseGlobalParam(parameter,value);
	menu_repaintAll();
	return 1;
}
static uint8_t midiParser_extendedPerformanceCc(uint8_t cc,uint8_t value)
{
	uint16_t parameter=PAR_NONE;
	if(midiParser_needsOwnPch(cc) && midiParser_isValidChannel(midi_ControlChannel))return 0;
	switch(cc) {
    case 9:
        performance_set(PAR_PERF_RANDOM_VELO,(uint8_t)(((uint16_t)value*100u+63u)/127u));
        menu_repaintAll();return 1;
	case 20:case 21:case 22:case 23:case 24:case 25:case 26:
		performance_set((uint16_t)(PAR_VCA1+cc-20),value);menu_repaintAll();return 1;
	case 30:case 31:case 32:case 33:case 34:case 35:case 36:
		performance_set((uint16_t)(PAR_FX_SEND1+cc-30),value);menu_repaintAll();return 1;
	case 37:performance_set(PAR_MASTER_FILTER,value==64?63:value);menu_repaintAll();return 1;
	case 38:performance_set(PAR_MASTER_FILTER_RESO,value);menu_repaintAll();return 1;
	case 39:performance_set(PAR_MASTER_FILTER_DRIVE,value);menu_repaintAll();return 1;
	case 79:case 80:case 81:case 82:case 83:case 84:
		if(!value||value>=64) {performance_set(PAR_GLOBAL_SCALE,(uint8_t)(cc-79));menu_repaintAll();}
		return 1;
	case 88:case 89:case 90:case 91:
		if(!value||value>=64) {performance_set(PAR_SCALE_TRANSFORM,(uint8_t)(cc-88));menu_repaintAll();}
		return 1;
	case 40: seq_setShuffle(value/127.f);menu_repaintAll();return 1;
	case 41:
	case 42:
	case 43: seq_setGrooveStep((uint8_t)(cc-40),value==64?63:value);menu_repaintAll();return 1;
	case 8: midiParser_setStepPerformance(PAR_PERF_NOTE_PROB,(uint8_t)(((uint16_t)value*100u+63u)/127u));return 1;
	case 10: parameter=PAR_PERF_DELAY_CHANCE;value=(uint8_t)(((uint16_t)value*100u+63u)/127u);break;
	case 11: parameter=PAR_PERF_DELAY_SYNC;value=(uint8_t)(((uint16_t)value*15u+63u)/127u);break;
	case 12: parameter=PAR_PERF_DELAY_COUNT;value=(uint8_t)(((uint16_t)value*32u+63u)/127u);break;
	case 13: parameter=PAR_PERF_DELAY_BOUNCE;if(value==64)value=63;break;
	case 14: parameter=PAR_PERF_DELAY_EXP;break;
	case 15: parameter=PAR_PERF_DELAY_PITCH;break;
	case 16: parameter=PAR_PERF_DELAY_MODE;value=(uint8_t)(value>=64);break;
	case 126: parameter=PAR_PERF_DELAY_TARGET;value=(uint8_t)(((uint16_t)value*10u+63u)/127u);break;
	case 44: midiParser_setAccentParameter(PAR_PERF_VELO_LEVEL,value==64?63:value);return 1;
	case 53: mixer_setPerformanceGateEnabled((uint8_t)(value>=64));return 1;	// 0.2.83 gater, as on the LXR1
	case 54: midiParser_setStepPerformance(PAR_PERF_SCARCITY,midiParser_scaleCc(value,100));return 1;
	case 55: performance_set(PAR_PERF_AVL,midiParser_scaleCc(value,200));menu_repaintAll();return 1;
	case 56: return midiParser_menuCc(PAR_PERF_FILL,(uint8_t)(value>=64));
	case 57: performance_set(PAR_MASTER_FILTER_ENABLE,(uint8_t)(value>=64));menu_repaintAll();return 1;
	case 58: midiParser_setPitchBendRange(value);menu_repaintAll();return 1;
	case 59: performance_set(PAR_FX_SEND_MODE,midiParser_scaleCc(value,3));menu_repaintAll();return 1;
	case 67: performance_set(PAR_FX_OUTPUT_MODE,(uint8_t)(value>=64));menu_repaintAll();return 1;
	case 68: performance_set(PAR_CLOCK_OFFSET,midiParser_scaleCc(value,80));menu_repaintAll();return 1;
	case 69: performance_set(PAR_CLOCK_OFFSET_FINE,midiParser_scaleCc(value,9));menu_repaintAll();return 1;
	default:
		if(cc>=46 && cc<=52) {
			midiParser_setAccentParameter((uint16_t)(PAR_PERF_VELO_DECAY+cc-46),value==64?63:value);return 1;
		}
		if(cc>=60 && cc<=66) {
			if(value>=64)midiParser_setDelayParameter(PAR_PERF_DELAY_INPUT_MASK,
				activeParameters[PAR_PERF_DELAY_INPUT_MASK]^(uint8_t)(1u<<(cc-60)));
			return 1;
		}
		if(cc>=70 && cc<=72) {
			MidiMsg msg={0};
			msg.status=MIDI_CC2;
			msg.data1=(uint8_t)(CC2_MIX_MOD_1+cc-70);
			msg.data2=midiParser_scaleCc(value,4);
			activeParameters[PAR_MIX_MOD_1+cc-70]=msg.data2;
			midiParser_ccHandler(msg,1,0,0.f);
			menu_repaintAll();
			return 1;
		}
		if(cc>=73 && cc<=75) {
			static const uint8_t fmAmounts[3]={FMAMNT1,FMAMNT2,FMAMNT3};
			static const uint8_t fmParameters[3]={PAR_FMAMNT1,PAR_FMAMNT2,PAR_FMAMNT3};
			MidiMsg msg={0};
			msg.status=MIDI_CC;
			msg.data1=fmAmounts[cc-73];
			msg.data2=value;
			activeParameters[fmParameters[cc-73]]=value;
			midiParser_ccHandler(msg,1,0,0.f);
			menu_repaintAll();
			return 1;
		}
		if(cc>=92 && cc<=97) {
			MidiMsg msg={0};
			msg.status=MIDI_CC2;
			msg.data1=(uint8_t)(CC2_PWM_1+cc-92);
			msg.data2=value;
			activeParameters[PAR_PWM_1+cc-92]=value;
			midiParser_ccHandler(msg,1,0,0.f);
			menu_repaintAll();
			return 1;
		}
		if(cc>=102 && cc<=107)return midiParser_menuCc((uint16_t)(PAR_LFO_SLEW1+cc-102),value);
		if(cc>=108 && cc<=113)return midiParser_menuCc((uint16_t)(PAR_LFO_POL1+cc-108),midiParser_scaleCc(value,2));
		if(cc>=114 && cc<=119)return midiParser_menuCc((uint16_t)(PAR_RPS_AMT1+cc-114),value);
		return 0;
	}
	midiParser_setDelayParameter(parameter,value);return 1;
}
//-----------------------------------------------------------
// this will check whether mtc is running, and if so will
// check to see whether we need to stop the sequencer due to
// lack of recent mtc activity. It will also reset our running indicator
// if the sequencer has stopped for some other reason
void midiParser_checkMtc()
{
	if(!midiParser_mtcIsRunning)
		return;

	if(!seq_isRunning()) {
		// inform mtc that his services are no longer needed
		midiParser_mtcIsRunning=0;
		return;
	}

	// at a 24fps framerate (the lowest) we should receive a completed message (we receive one every 2 frames)
	// every 83 ms. our tick counter is .25 ms resolution
	if(systick_ticks-midiParser_lastMtcReceived > 100 * 4) { // overestimate, just in case something untoward should happen
		// too much time has elapsed since our last message. mtc has gone away.
		midiParser_mtcIsRunning=0;

		uart_sendFrontpanelByte(FRONT_SEQ_CC);
		uart_sendFrontpanelByte(FRONT_SEQ_RUN_STOP);
		uart_sendFrontpanelByte(0);
		// stop the sequencer
		seq_setRunning(0);
	}
}

//------------------------------------------------------
#define MIDI_NOTE_INPUT_RECORD 0x01u
#define MIDI_NOTE_INPUT_ECHO   0x02u

// Input routing has already matched the note; recording and echo are independent.
static void midiParser_noteOn(uint8_t voice, uint8_t note, uint8_t vel, uint8_t inputFlags)
{
	// Preserve desktop step-note entry for the voice being edited.
	if(menu_activePage == SEQ_PAGE && voice == menu_getActiveVoice())
	{
		const uint8_t step = activeParameters[PAR_ACTIVE_STEP];
		const uint8_t patternNr = menu_getViewedPattern();
		seq_patternSet.seq_subStepPattern[patternNr][voice][step].note = note;
		activeParameters[PAR_STEP_NOTE] = note;
		menu_repaint();
		return;
	}
	if(seq_isTrackMuted(voice)) return;
	// Normal voiceControl_noteOn also sends MIDI: avoid that hidden echo.
	voiceControl_noteOnNoEcho(voice, note, vel);
	if(inputFlags & MIDI_NOTE_INPUT_RECORD)
		seq_addNote(voice, vel, note);
	if(inputFlags & MIDI_NOTE_INPUT_ECHO)
	{
		const uint8_t chan = midi_MidiChannels[voice];
		seq_midiNoteOff(chan);
		seq_sendMidiNoteOn(chan, note, vel);
	}
}

static inline uint8_t midiParser_scaleGlobalPitchNote(uint8_t note)
{
	int16_t offset = (int16_t)note - 60; // C4 is neutral.

	if(offset < -63)
		offset = -63;
	if(offset > 64)
		offset = 64;

	return (uint8_t)(63 + offset);
}

static inline uint8_t midiParser_scaleGlobalPitchCc(uint8_t data2)
{
	uint8_t dist;
	uint8_t amount;

	if(data2 >= 61 && data2 <= 66)
		return 63;

	if(data2 < 61)
	{
		dist = 61 - data2;
		if(dist <= 36)
			amount = (uint8_t)(((uint16_t)dist * 12 + 35) / 36);
		else
			amount = (uint8_t)(12 + (((uint16_t)(dist - 36) * 51 + 12) / 25));
		return (uint8_t)(63 - amount);
	}

	dist = data2 - 66;
	if(dist <= 36)
		amount = (uint8_t)(((uint16_t)dist * 12 + 35) / 36);
	else
		amount = (uint8_t)(12 + (((uint16_t)(dist - 36) * 52 + 12) / 25));

	return (uint8_t)(63 + amount);
}

static int16_t midiParser_pitchBendValue = 0;
static uint8_t midiParser_pitchBendRange = 12;

static void midiParser_recalcGlobalPitch(void)
{
	for(uint8_t i=0; i<3; ++i)
	{
		osc_recalcFreq(&voiceArray[i].osc);
		osc_recalcFreq(&voiceArray[i].modOsc);
	}
	osc_recalcFreq(&snareVoice.osc);
	osc_recalcFreq(&cymbalVoice.osc);
	osc_recalcFreq(&cymbalVoice.modOsc);
	osc_recalcFreq(&cymbalVoice.modOsc2);
	osc_recalcFreq(&hatVoice.osc);
	osc_recalcFreq(&hatVoice.modOsc);
	osc_recalcFreq(&hatVoice.modOsc2);
}

void midiParser_setGlobalPitch(uint8_t value)
{
	if(value > 127) value = 127;
	activeParameters[PAR_GLOBAL_PITCH] = value;
	osc_setGlobalPitchOffset(value);
	midiParser_recalcGlobalPitch();
	menu_repaint();
}

void midiParser_setPitchBendRange(uint8_t value)
{
	midiParser_pitchBendRange = value > 48 ? 48 : value;
	activeParameters[PAR_PITCH_BEND_RANGE] = midiParser_pitchBendRange;
	osc_setGlobalPitchBend(midiParser_pitchBendValue, midiParser_pitchBendRange);
	midiParser_recalcGlobalPitch();
}

static void midiParser_setControlNotePitch(uint8_t note)
{
	const uint8_t value = midiParser_scaleGlobalPitchNote(note);
	osc_setNotePitchOffset((int8_t)((int16_t)value - 63));
	midiParser_recalcGlobalPitch();
	menu_repaint();
}

static void midiParser_applyVoicePitchBend(uint8_t voice, int16_t bend)
{
	if(voice < 3)
	{
		osc_setPitchBend(&voiceArray[voice].osc,bend,midiParser_pitchBendRange);
		osc_setPitchBend(&voiceArray[voice].modOsc,bend,midiParser_pitchBendRange);
	}
	else if(voice == 3)
	{
		osc_setPitchBend(&snareVoice.osc,bend,midiParser_pitchBendRange);
	}
	else if(voice == 4)
	{
		osc_setPitchBend(&cymbalVoice.osc,bend,midiParser_pitchBendRange);
		osc_setPitchBend(&cymbalVoice.modOsc,bend,midiParser_pitchBendRange);
		osc_setPitchBend(&cymbalVoice.modOsc2,bend,midiParser_pitchBendRange);
	}
	else
	{
		// Closed and open hi-hat share one sound engine.
		osc_setPitchBend(&hatVoice.osc,bend,midiParser_pitchBendRange);
		osc_setPitchBend(&hatVoice.modOsc,bend,midiParser_pitchBendRange);
		osc_setPitchBend(&hatVoice.modOsc2,bend,midiParser_pitchBendRange);
	}
}
//------------------------------------------------------
//static void midiParser_noteOff(uint8_t voice, uint8_t note, uint8_t vel)
//{
	// in case we ever need it
//}


//check if midi channel is selected for a voice or as global channel
uint8_t midiParser_isValidChannel(uint8_t chan)
{
	for(int i=0;i<8;i++)
	{
		if(chan == midi_MidiChannels[i]) return 1;
	}

	return 0;
}

// Dedicated voice channels use Mutador's common voice map; gch/Pch retain priority.
static uint8_t midiParser_mapVoiceCc(uint8_t voice, uint8_t cc, MidiMsg* out)
{
	const uint8_t soundVoice = (voice > 5) ? 5 : voice;

	out->status = MIDI_CC;
	out->data1 = cc;

	switch(cc)
	{
	case 7:
		out->data1 = VOL1 + soundVoice;
		return 1;
	case 9:
		if(soundVoice < 3) out->data1 = OSC_WAVE_DRUM1 + soundVoice;
		else if(soundVoice == 3) out->data1 = OSC_WAVE_SNARE;
		else if(soundVoice == 4) out->data1 = CYM_WAVE1;
		else out->data1 = WAVE1_HH;
		return 1;
	case 10:
		out->data1 = (soundVoice < 3) ? (PAN1 + soundVoice) : (PAN4 + (soundVoice - 3));
		out->data2 = (out->data2==64 ? 63 : out->data2);
		return 1;
	case 12:
		out->data1 = VOICE_DECIMATION1 + soundVoice;
		return 1;
	case 13:
		if(soundVoice < 3) out->data1 = OSC1_DIST + soundVoice;
		else if(soundVoice == 3) out->data1 = SNARE_DISTORTION;
		else if(soundVoice == 4) out->data1 = CYMBAL_DISTORTION;
		else out->data1 = HAT_DISTORTION;
		return 1;
	case 14:
		out->data1 = F_OSC1_COARSE + (soundVoice * 2);
		return 1;
	case 16:
		if(soundVoice < 3) out->data1 = FILTER_FREQ_DRUM1 + soundVoice;
		else if(soundVoice == 3) out->data1 = SNARE_FILTER_F;
		else if(soundVoice == 4) out->data1 = CYM_FIL_FREQ;
		else out->data1 = HAT_FILTER_F;
		return 1;
	case 17:
		if(soundVoice < 3) out->data1 = RESO_DRUM1 + soundVoice;
		else if(soundVoice == 3) out->data1 = SNARE_RESO;
		else if(soundVoice == 4) out->data1 = CYM_RESO;
		else out->data1 = HAT_RESO;
		return 1;
	case 18:
		out->status = MIDI_CC2;
		out->data1 = CC2_FILTER_DRIVE_1 + soundVoice;
		return 1;
	case 19:
		out->status = MIDI_CC2;
		out->data1 = CC2_FILTER_TYPE_1 + soundVoice;
		return 1;
	case 20:
		if(soundVoice == 3) { out->data1 = SNARE_MIX; return 1; }
		break;
	case 21:
		if(soundVoice == 3) { out->data1 = SNARE_NOISE_F; return 1; }
		break;
	case 22:
		if(soundVoice < 3) {
			out->status = MIDI_CC2;
			out->data1 = CC2_MIX_MOD_1 + soundVoice;
			return 1;
		}
		break;
	case 23:
		out->status = MIDI_CC2;
		out->data1 = CC2_VOLUME_MOD_ON_OFF1 + soundVoice;
		return 1;
	case 24:
		out->status = MIDI_CC2;
		out->data1 = CC2_VELO_MOD_AMT_1 + soundVoice;
		return 1;
	case 25:
		out->status = MIDI_CC2;
		out->data1 = CC2_VEL_DEST_1 + soundVoice;
		return 1;
	case 26:
		out->status = MIDI_CC2;
		out->data1 = CC2_TRANS1_VOL + soundVoice;
		return 1;
	case 27:
		out->status = MIDI_CC2;
		out->data1 = CC2_TRANS1_WAVE + soundVoice;
		return 1;
	case 28:
		out->status = MIDI_CC2;
		out->data1 = CC2_TRANS1_FREQ + soundVoice;
		return 1;
	case 46:
		out->data1 = F_OSC1_FINE + (soundVoice * 2);
		out->data2 = (out->data2==64 ? 63 : out->data2);
		return 1;
	case 70:
		if(soundVoice == 3) { out->data1 = REPEAT1; return 1; }
		if(soundVoice == 4) { out->data1 = CYM_REPEAT; return 1; }
		break;
	case 72:
		if(soundVoice == 5) { out->data1 = VELOD6_OPEN; return 1; }
		break;
	case 73:
		out->data1 = VELOA1 + (soundVoice * 2);
		return 1;
	case 74:
		if(soundVoice < 3) out->data1 = VOL_SLOPE1 + soundVoice;
		else if(soundVoice == 3) out->data1 = EG_SNARE1_SLOPE;
		else if(soundVoice == 4) out->data1 = CYM_SLOPE;
		else out->data1 = VOL_SLOPE6;
		return 1;
	case 75:
		out->data1 = VELOD1 + (soundVoice * 2);
		return 1;
	case 76:
		out->data1 = FREQ_LFO1 + soundVoice;
		return 1;
	case 77:
		out->data1 = AMOUNT_LFO1 + soundVoice;
		return 1;
	case 78:
		out->status = MIDI_CC2;
		out->data1 = CC2_OFFSET_LFO1 + soundVoice;
		return 1;
	case 79:
		out->status = MIDI_CC2;
		out->data1 = CC2_WAVE_LFO1 + soundVoice;
		return 1;
	case 80:
		out->status = MIDI_CC2;
		out->data1 = CC2_VOICE_LFO1 + soundVoice;
		return 1;
	case 81:
		out->status = MIDI_CC2;
		out->data1 = CC2_TARGET_LFO1 + soundVoice;
		return 1;
	case 82:
		out->status = MIDI_CC2;
		out->data1 = CC2_RETRIGGER_LFO1 + soundVoice;
		return 1;
	case 83:
		out->status = MIDI_CC2;
		out->data1 = CC2_SYNC_LFO1 + soundVoice;
		return 1;
	case 84:
		if(soundVoice < 3) out->data1 = PITCHD1 + soundVoice;
		else if(soundVoice == 3) out->data1 = PITCHD4;
		else break;
		return 1;
	case 85:
		if(soundVoice < 3) out->data1 = MODAMNT1 + soundVoice;
		else if(soundVoice == 3) out->data1 = MODAMNT4;
		else break;
		return 1;
	case 86:
		if(soundVoice < 3) out->data1 = PITCH_SLOPE1 + soundVoice;
		else if(soundVoice == 3) out->data1 = PITCH_SLOPE4;
		else break;
		return 1;
	case 89:
		out->status = MIDI_CC2;
		out->data1 = CC2_AUDIO_OUT1 + soundVoice;
		return 1;
	case 102:
		if(soundVoice < 3) { out->data1 = MOD_WAVE_DRUM1 + soundVoice; return 1; }
		break;
	case 103:
		if(soundVoice < 3) { out->data1 = FMDTN1 + (soundVoice * 2); return 1; }
		break;
	case 104:
		if(soundVoice < 3) { out->data1 = FMAMNT1 + (soundVoice * 2); return 1; }
		break;
	case 105:
		if(soundVoice == 4) out->data1 = CYM_WAVE2;
		else if(soundVoice == 5) out->data1 = WAVE2_HH;
		else break;
		return 1;
	case 106:
		if(soundVoice == 4) out->data1 = CYM_MOD_OSC_GAIN1;
		else if(soundVoice == 5) out->data1 = MOD_OSC_GAIN1;
		else break;
		return 1;
	case 107:
		if(soundVoice == 4) out->data1 = CYM_MOD_OSC_F1;
		else if(soundVoice == 5) out->data1 = MOD_OSC_F1;
		else break;
		return 1;
	case 108:
		if(soundVoice == 4) out->data1 = CYM_WAVE3;
		else if(soundVoice == 5) out->data1 = WAVE3_HH;
		else break;
		return 1;
	case 109:
		if(soundVoice == 4) out->data1 = CYM_MOD_OSC_GAIN2;
		else if(soundVoice == 5) out->data1 = MOD_OSC_GAIN2;
		else break;
		return 1;
	case 110:
		if(soundVoice == 4) out->data1 = CYM_MOD_OSC_F2;
		else if(soundVoice == 5) out->data1 = MOD_OSC_F2;
		else break;
		return 1;
	case 112:
		if(soundVoice == 3) { out->status = MIDI_CC2; out->data1 = (PAR_SNARE_LAYER_WAVE-128); return 1; }
		break;
	case 113:
		if(soundVoice == 3) { out->status = MIDI_CC2; out->data1 = (PAR_SNARE_LAYER_AMOUNT-128); return 1; }
		break;
	case 114:
		if(soundVoice == 3) { out->status = MIDI_CC2; out->data1 = (PAR_SNARE_LAYER_FREQ-128); return 1; }
		break;
	case 115:
		if(soundVoice == 3) { out->status = MIDI_CC2; out->data1 = (PAR_SNARE_LAYER_MODE-128); return 1; }
		break;
	case 116:
		if(soundVoice == 3) { out->status = MIDI_CC2; out->data1 = (PAR_SNARE_NOISE_ATTACK-128); return 1; }
		break;
	case 117:
		if(soundVoice == 3) { out->status = MIDI_CC2; out->data1 = (PAR_SNARE_NOISE_DECAY-128); return 1; }
		break;
	case 118:
		if(soundVoice == 3) { out->status = MIDI_CC2; out->data1 = (PAR_SNARE_NOISE_SLOPE-128); return 1; }
		break;
	default:
		break;
	}

	return 0;
}
static Lfo *midiParser_voiceLfo(uint8_t voice)
{
    if(voice<3)return &voiceArray[voice].lfo;
    if(voice==3)return &snareVoice.lfo;
    if(voice==4)return &cymbalVoice.lfo;
    return &hatVoice.lfo;
}
static uint8_t midiParser_handleVoiceChannelCc(uint8_t channel,MidiMsg msg)
{
    if(channel==midi_MidiChannels[7] || channel==midi_ControlChannel)return 0;
    for(uint8_t voice=0;voice<7;voice++) {
        MidiMsg mapped=msg;
        if(channel!=midi_MidiChannels[voice] || !midiParser_mapVoiceCc(voice,msg.data1,&mapped))continue;
        uint16_t parameter=(mapped.status==MIDI_CC2) ? (uint16_t)(mapped.data1+128) : (uint16_t)(mapped.data1-1);
        if(parameter>=END_OF_SOUND_PARAMETERS)return 0;
        uint8_t value=mapped.data2;
        if(msg.data1!=25 && msg.data1!=81) {
            if(msg.data1==80)value=(uint8_t)((value>5 ? 5 : value)+1);
            value=menu_limitSoundParameter(parameter,value);
            activeParameters[parameter]=value;
        }
        mapped.data2=value;
        midiParser_ccHandler(mapped,1,0,0.f);
        // Low-half automation destinations use wire CC numbering (+1).
        uint8_t automDestination=(uint8_t)(parameter+(parameter<128 ? 1 : 0));
        seq_recordAutomation(voice,automDestination,value);
        menu_repaintAll();
        return 1; // As in Mutador, the first matching voice wins on shared channels.
    }
    return 0;
}

uint8_t midiParser_cc2voiceNr(uint8_t cc)
{
	switch(cc)
	{

	//No voice
	default:
		case 0:
		case 1:
		case 6:
		case 98:
		case 99:
			return 0;

	//voice 1
		case 2:
		case 9:
		case 10:
		case 21:
		case 38:
		case 44:
		case 50:
		case 51:
		case 63:
		case 71:
		case 75:
		case 79:
		case 83:
		case 84:
		case 89:
		case 95:
		case 103:
		case 109:
		case 116:
		case 122:
			return 1;

	//voice 2
		case 3:
		case 11:
		case 12:
		case 22:
		case 39:
		case 45:
		case 52:
		case 53:
		case 64:
		case 72:
		case 76:
		case 80:
		case 85:
		case 86:
		case 90:
		case 96:
		case 104:
		case 110:
		case 117:
		case 123:
			return 2;

	//voice 3
		case 4:
		case 13:
		case 14:
		case 23:
		case 40:
		case 46:
		case 54:
		case 55:
		case 65:
		case 73:
		case 77:
		case 81:
		case 87:
		case 88:
		case 91:
		case 97:
		case 105:
		case 111:
		case 118:
		case 124:
			return 3;

	//voice 4
		case 5:
		case 15:
		case 16:
		case 28:
		case 29:
		case 41:
		case 47:
		case 56:
		case 57:
		case 66:
		case 69:
		case 74:
		case 78:
		case 82:
		case 92:
		case 100:
		case 106:
		case 112:
		case 119:
		case 125:
			return 4;

	//voice 5
		case 7:
		case 17:
		case 18:
		case 24:
		case 25:
		case 30:
		case 31:
		case 32:
		case 33:
		case 42:
		case 48:
		case 58:
		case 59:
		case 67:
		case 70:
		case 93:
		case 101:
		case 107:
		case 113:
		case 120:
		case 126:
			return 5;

	//voice 6
		case 8:
		case 19:
		case 20:
		case 26:
		case 27:
		case 34:
		case 35:
		case 36:
		case 37:
		case 43:
		case 49:
		case 60:
		case 61:
		case 62:
		case 68:
		case 94:
		case 102:
		case 108:
		case 114:
		case 121:
		case 127:
			return 6;

	//all voices
		case 115:
			return 7;

	}
}

//-----------------------------------------------------------
/** Parse incoming midi messages and invoke corresponding action
 */
void midiParser_parseMidiMessage(MidiMsg msg)
{
	// Match Mutador: Pch note pitch is consumed before Thru and RX filtering.
	if(!msg.bits.sysxbyte && (msg.status & 0xF0) == NOTE_ON && msg.data2 &&
	   (msg.status & 0x0F) == midi_ControlChannel &&
	   midi_ControlChannel != midi_MidiChannels[7])
	{
		midiParser_setControlNotePitch(msg.data1);
		return;
	}
	// route message if needed
	if(midiParser_routing.value) {
		if(msg.bits.source==midiSourceUSB) {
			if(midiParser_routing.route.usb2midi){
				// route to midi out port
				uart_sendMidi(msg);
			}
		} else if(msg.bits.source==midiSourceMIDI) {
			if(midiParser_routing.route.midi2midi) {
				// route to midi out port
				uart_sendMidi(msg);
			}
			if(midiParser_routing.route.midi2usb) {
				// route to usb out port
				usb_sendMidi(msg);
			}
		}
	}

	if(msg.bits.sysxbyte)
		return; // no further action needed. we don't interpret sysex data right now

	// FILT filter messages here. Filter inline below to be more optimal
	// we are interested in the low nibble since we are Rx here


	if((msg.status & 0xF0) == 0xF0)
  {
		// non-channel specific messages (system messages)
		switch(msg.status)
    {
      case MIDI_CLOCK:
        if((midiParser_txRxFilter & MIDI_FILTER_SYSTEM) && seq_getExtSync())
          if(seq_getExtSync()==2)
            sync_tickAtCycles(msg.bits.source==midiSourceMIDI ?
                midiParser_clockCycles : DWT->CYCCNT);
        break;
      case MIDI_START:
        if((midiParser_txRxFilter & MIDI_FILTER_SYSTEM) && seq_getExtSync())
        {
          sync_midiResetPosition();
          sync_midiStartStop(1);
          uart_sendFrontpanelByte(FRONT_SEQ_CC);
          uart_sendFrontpanelByte(FRONT_SEQ_RUN_STOP);
          uart_sendFrontpanelByte(1);
        }
        break;
      case MIDI_CONTINUE:
        if((midiParser_txRxFilter & MIDI_FILTER_SYSTEM) && seq_getExtSync())
        {
          sync_midiStartStop(1);
          uart_sendFrontpanelByte(FRONT_SEQ_CC);
          uart_sendFrontpanelByte(FRONT_SEQ_RUN_STOP);
          uart_sendFrontpanelByte(1);
        }
        break;
      case MIDI_STOP:
        if((midiParser_txRxFilter & MIDI_FILTER_SYSTEM) && seq_getExtSync())
        {
          sync_midiStartStop(0);
          uart_sendFrontpanelByte(FRONT_SEQ_CC);
          uart_sendFrontpanelByte(FRONT_SEQ_RUN_STOP);
          uart_sendFrontpanelByte(0);
        }
        break;
      case MIDI_SONG_POSITION_POINTER:
        {
          /* Two data bytes follow the status. Just like with the Pitch Wheel,
          * these two bytes are combined into a 14-bit value. (See Pitch Wheel).
          * This 14-bit value is the MIDI Beat upon which to start the song.
          * Songs are always assumed to start on a MIDI Beat of 0. Each MIDI
          * Beat spans 6 MIDI Clocks. In other words, each MIDI Beat is a 16th
          * note (since there are 24 MIDI Clocks in a quarter note).
          *
          */
          // TODO song position pointer is not implemented yet:
          // position = msg.data1 | (msg.data2<<7)  (in MIDI beats = 16th notes)
        }
        break;
      case MIDI_MTC_QFRAME:
        /* Strategy:
        * If we get through all 8 of the mtc messages with a value of 0, it means that
        * the song has just started playing. That is the only time we will start the
        * sequencer. so we will not start it if they start the tape recorder playing half way
        * through the song. Also, if the sequencer is running, or we are in external sync mode
        * we will ignore mtc messages as well
        */
        if ((midiParser_txRxFilter & MIDI_FILTER_SYSTEM) == 0)
          break; // ignore filtered

        // keep track of when we got the last mtc. only do this for the 0 msg to save time
        if((msg.data1 & 0x70)==0) {
          midiParser_lastMtcReceived=systick_ticks;
        }

        if(seq_isRunning()) {
          break; //already running, so we don't care to figure out where we are
        }
        if(seq_getExtSync())
          break; // bypass the lot. we are using external midi clock sync

        // figure out whether we are at 0:0:0:0
        if((msg.data1 & 0x7F)==0) { // this is the first mtc message of the set AND it's value is 0
          midiParser_mtcIgnore=0; // reset our level of ignorance
        } else if(midiParser_mtcIgnore) { // not the first msg and we are ignoring
          break; // get out of here fast
        } else if((msg.data1 & 0x70)!=0x70) { // messages 0 to 6 and we are not ignoring yet
          if((msg.data1 & 0x0F) !=0) {
            midiParser_mtcIgnore=1;
            break; // get out fast
          }
        } else { // message 7 and we are not ignoring yet
          if((msg.data1 & 0x01)==0) { // hour high nibble is 0
            // well, we got all the way thru all 8 messages with 0, so the song has just begun
            // tell the front that we've started running on our own
            uart_sendFrontpanelByte(FRONT_SEQ_CC);
            uart_sendFrontpanelByte(FRONT_SEQ_RUN_STOP);
            uart_sendFrontpanelByte(1);
            midiParser_mtcIgnore=1; // in case we happen to miss a 0 message. probably wouldn't happen, but...
            midiParser_mtcIsRunning=1;
            midiParser_lastMtcReceived=systick_ticks; // also might not be needed, but...
            // start the sequencer
            seq_setRunning(1);
          }
        }
        break;

      default:
        break;
		}
    // msg.status = msg.lastNonSysStatus;
	}
  else
  { // channel specific message
		const uint8_t msgonly = msg.status & 0xF0;
		const uint8_t chanonly= msg.status & 0x0F;
		// First performance control: morph on CC 2. Keep the existing global/voice
		// CC map unchanged when Pch overlaps a legacy channel.
		if(msgonly == MIDI_CC && chanonly == midi_ControlChannel &&
		   !midiParser_isValidChannel(chanonly) && msg.data1 == 2 &&
		   (midiParser_txRxFilter & MIDI_FILTER_CC)) {
			preset_setMorphTarget(msg.data2 == 127 ? 255 : (uint8_t)(msg.data2 * 2u));
			return;
		}

    msg.lastNonSysStatus = msg.status;

		if((msgonly & 0xE0) == 0x80) {
			// note on or note off message (one of these two only)
			if(midiParser_txRxFilter & MIDI_FILTER_NOTES) {
				if(msgonly == NOTE_ON && msg.data2)
				{
					if(chanonly == midi_MidiChannels[7])
					{
						uint8_t mapped = 0;
						for(uint8_t v=0; v<7; ++v)
						{
							if(activeParameters[PAR_MIDI_NOTE1+v] != 0 &&
							   activeParameters[PAR_MIDI_NOTE1+v] == msg.data1)
							{
								midiParser_noteOn(v, SEQ_DEFAULT_NOTE, msg.data2,
									MIDI_NOTE_INPUT_RECORD | MIDI_NOTE_INPUT_ECHO);
								mapped = 1;
							}
						}
						if(!mapped && activeParameters[PAR_MIDI_NOTE1+frontParser_activeTrack] == 0)
							midiParser_noteOn(frontParser_activeTrack, msg.data1, msg.data2,
								MIDI_NOTE_INPUT_RECORD | MIDI_NOTE_INPUT_ECHO);
					}
					else
					{
						for(uint8_t v=0; v<7; ++v)
							if(midi_MidiChannels[v] == chanonly)
								midiParser_noteOn(v, msg.data1, msg.data2, MIDI_NOTE_INPUT_RECORD);
					}
				}
			} // check midi filter

		} else if(msgonly==PROG_CHANGE) {
			// respond to prog change and change patterns. This responds only when global channel matches the PC message's channel.
			if((midiParser_txRxFilter & MIDI_FILTER_PROG_C) && (chanonly == midi_MidiChannels[7]))
				seq_setNextPattern(msg.data1);

		} else if(msgonly==MIDI_CC){
			if((midiParser_txRxFilter & MIDI_FILTER_CC) && midiParser_handleVoiceChannelCc(chanonly,msg))return;
			if(chanonly == midi_ControlChannel && msg.data1 == 27 &&
			   (midiParser_txRxFilter & MIDI_FILTER_CC))
			{
				midiParser_setGlobalPitch(midiParser_scaleGlobalPitchCc(msg.data2));
				return;
			}

			if(chanonly == midi_ControlChannel && (midiParser_txRxFilter & MIDI_FILTER_CC))
			{
				uint16_t parameter=PAR_NONE;
				uint8_t value=msg.data2;
				if(msg.data1==28) {
					midiParser_setGlobalDecay(midiParser_scaleGlobalPitchCc(value));
					return;
				}
				if(msg.data1==5) parameter=PAR_RANDOM_STEP;
				if(msg.data1==6) parameter=PAR_PERF_NOTE_REPEAT_CHANCE;
				if(msg.data1==7) parameter=PAR_PERF_PROB;
				if(parameter!=PAR_NONE) {
					if(parameter!=PAR_PERF_NOTE_REPEAT_CHANCE)
						value=(uint8_t)(((uint16_t)value*100u+63u)/127u);
					midiParser_setStepPerformance(parameter,value);
					return;
				}
			}
			if(chanonly==midi_ControlChannel && (midiParser_txRxFilter & MIDI_FILTER_CC) &&
			   midiParser_extendedPerformanceCc(msg.data1,msg.data2)) return;
			uint8_t voiceNr = midiParser_cc2voiceNr(msg.data1);

			if(voiceNr==0 || voiceNr >= 7) //any set midi channel
			{
				if((midiParser_txRxFilter & MIDI_FILTER_CC) && (midiParser_isValidChannel(chanonly) ))
				{
					//record automation if record is turned on
					seq_recordAutomation(frontParser_activeTrack, msg.data1, msg.data2);

					//handle midi data
					midiParser_ccHandler(msg,1, 0, 0.f);
					//we received a midi cc message forward it to the front panel
					uart_sendFrontpanelByte(msg.status);
					uart_sendFrontpanelByte(msg.data1);
					uart_sendFrontpanelByte(msg.data2);
				}
			}
			else
			{

				// respond to CC message. This responds only when global channel or voice channel matches the cc message's channel
				if((midiParser_txRxFilter & MIDI_FILTER_CC) && ((chanonly == midi_MidiChannels[voiceNr - 1u]) || (chanonly == midi_MidiChannels[7]) )) {
					//record automation if record is turned on
					seq_recordAutomation(frontParser_activeTrack, msg.data1, msg.data2);

					//handle midi data
					midiParser_ccHandler(msg,1, 0, 0.f);
					//we received a midi cc message forward it to the front panel
					uart_sendFrontpanelByte(msg.status);
					uart_sendFrontpanelByte(msg.data1);
					uart_sendFrontpanelByte(msg.data2);
				}
			}
		} else if(msgonly == MIDI_PITCH_WHEEL) {
			const int16_t bend = (int16_t)((msg.data1 | (msg.data2 << 7)) - 8192);
			if(chanonly == midi_MidiChannels[7] || chanonly == midi_ControlChannel)
			{
				midiParser_pitchBendValue = bend;
				osc_setGlobalPitchBend(bend, midiParser_pitchBendRange);
				midiParser_recalcGlobalPitch();
			}
			else
				for(uint8_t v=0; v<7; ++v)
					if(midi_MidiChannels[v] == chanonly)
					{
						midiParser_applyVoicePitchBend(v, bend);
						break;
					}
		}
	} // channel specific vs non channel specific

}

//-----------------------------------------------------------

void midiParser_handleStatusByte(unsigned char data)
{
	// we received a channel voice/mode byte. set the status as appropriate
	switch(data&0xF0)
  {
    // 2 databyte messages
    case NOTE_OFF:
    case NOTE_ON:
    case MIDI_CC:
    case MIDI_PITCH_WHEEL:
    case MIDI_AT:
      midiMsg_tmp.status = data;	// store the new status byte
      parserState = MIDI_DATA1;	//status received, next should be data byte 1
      midiMsg_tmp.bits.length = 2;// status is followed by 2 data bytes
      break;

    // 1 databyte messages
    case PROG_CHANGE:
    case CHANNEL_PRESSURE:
      midiMsg_tmp.status = data;	// store the new status byte
      parserState = MIDI_DATA1;	//status received, next should be data byte 1
      midiMsg_tmp.bits.length = 1;// status is followed by 1 data bytes
      break;

    // messages we don't care about right now, and don't know how to handle or passthru (Are there any?).
    default:
      parserState = IGNORE;	// throw away any data bytes until next message
      midiMsg_tmp.bits.length = 0;
      break;
	}

  midiMsg_tmp.lastNonSysStatus = data;
}
//-----------------------------------------------------------
// This will build up the midi message and hand it off to
// parseMidiMessage when it's complete
volatile static uint8_t checkMIDIprocPAR_t = 0;
volatile static int8_t checkMIDIprocPAR = 0;

void midiParser_parseUartData(unsigned char data)
{
  checkMIDIprocPAR_t = ((checkMIDIprocPAR_t^1) & 0x01);
  checkMIDIprocPAR = (int8_t)checkMIDIprocPAR_t - 6;

  uint8_t parseMsg = 0;

  // if (data == 0xF8)
  // {
  //   return;
  // }

	if(data & 0x80)
  {
  /*  High bit is set -  its either a status or a system message.
      regardless of current state, we blindly start a new message without questioning it */
		midiMsg_tmp.bits.sysxbyte = 0;

		if((data&0xf0) == 0xF0) /* System message */
    {
			midiMsg_tmp.status = data;
			switch(data)
      {
        case MIDI_CLOCK:
          parseMsg = 1;
          break;  
			  case SYSEX_START: /*  Get into sysex receive mode. any more bytes received until this status changes are considered
							                to be sysex data. we still need to parse this sysex start, in case we are routing it */
          parserState = SYSEX_DATA;
          midiMsg_tmp.bits.length = 0;
          parseMsg = 1; /* we will still parse it in case we are doing a passthru */
          break;
        case SYSEX_END:	  /* Get out of sysex mode */
          if(parserState == SYSEX_DATA)
          {
            parserState = MIDI_STATUS;
            midiMsg_tmp.bits.length = 0;
            parseMsg = 1; // We will still parse it in case we are doing a passthru
            break;
          }
          else
          {
            // spurious sysex end msg received. ignore it
          }
          break;
        /* 1 byte payload messages */
        case MIDI_SONG_SEL:		  // passthru only
          parseMsg = 1;
          break; 
        case MIDI_MTC_QFRAME: 	// mtc chunk
          parserState = MIDI_DATA1; 	  // we expect the nugget of mtc frame info
          midiMsg_tmp.bits.length = 1;  // we expect 1 data byte
          break;
        case MIDI_SONG_POSITION_POINTER:
          parserState = MIDI_DATA1; 	// we expect 14-bit value for song position
          midiMsg_tmp.bits.length = 2;// we expect 1 data byte
          break;
        default: /* 0 byte payload messages (we will assume that any system message
                    other than those above has 0 byte payload) */
          // midiMsg_tmp.bits.length = 0;
          parseMsg = 1;
          break;
			}
		}
    else
    { /* Status byte (channel specific message containing a channel number) */
			midiParser_handleStatusByte(data);
		}
	}
  else
  { /* High bit is not set - it's a data byte */
		switch(parserState)
    {
      case MIDI_STATUS: /* We are expecting status msg, but got data, so running status may be in effect */
        midiMsg_tmp.status = midiMsg_tmp.lastNonSysStatus;
        if(midiMsg_tmp.bits.length)
        {
          midiMsg_tmp.data1 = data;
          if(midiMsg_tmp.bits.length == 2)
          {
            parserState = MIDI_DATA2;
          }
          else
          {
            midiMsg_tmp.data2 = 0;
            parseMsg = 1;
            break;
          }
        }
        else
        {
          break; // last msg had 0 payload, so wtf is this? just ignore it
        }
        break;
      case MIDI_DATA1:
        midiMsg_tmp.data1 = data;
        if(midiMsg_tmp.bits.length == 2)
        {
          parserState = MIDI_DATA2; /* We need another byte before we can do anything meaningful */
        }
        else /* It must be 1 */
        {
          parseMsg = 1;
          break;
        }
        break;
      case MIDI_DATA2:
        midiMsg_tmp.data2 = data;
        parseMsg = 1; /* Message complete */
        break;
      case SYSEX_DATA: /* We are in sysex mode */
        midiMsg_tmp.bits.sysxbyte = 1;
        midiMsg_tmp.status = data; // Status will contain the sysex byte
        midiMsg_tmp.bits.length = 0;
        parseMsg = 1;
        break;
      default: /* We are expecting no data byte, but we got one */
			  break;
		}
	}

  if (parseMsg == 1)
  {
    /* We get here if we have proudly received a message that we want to do something with */
    if(parserState != SYSEX_DATA) // we are still in sysex receive mode
      parserState = MIDI_STATUS;  // next byte should be a new message, or we don't care about it
    midiMsg_tmp.bits.source = midiSourceMIDI;
    if(midiMsg_tmp.status==MIDI_CLOCK)
      midiParser_clockCycles=uart_takeMidiClockCycles();
    midiParser_parseMidiMessage(midiMsg_tmp);
    parseMsg = 0;
  }

	return;
}

// 0 - Off - nothing to nothing
// 1 - U2M - usb in to midi out
// 2 - M2M - midi in to midi out
// 3 - A2M - usb in and midi in to midi out
// 4 - M2U - midi in to usb out
// 5 - M2A - midi in to usb out and midi out

void midiParser_setRouting(uint8_t value)
{
	midiParser_routing.value=0;

	switch(value) {
	case 1:
		midiParser_routing.route.usb2midi=1;
		break;
	case 2:
		midiParser_routing.route.midi2midi=1;
		break;
	case 3:
		midiParser_routing.route.usb2midi=1;
		midiParser_routing.route.midi2midi=1;
		break;
	case 4:
		midiParser_routing.route.midi2usb=1;
		break;
	case 5:
		midiParser_routing.route.midi2midi=1;
		midiParser_routing.route.midi2usb=1;
		break;
	default:
	case 0:

		break;
	}

}

void midiParser_setFilter(uint8_t is_tx, uint8_t value)
{

	if(is_tx) // set the high nibble to value
		midiParser_txRxFilter = (value << 4) | (midiParser_txRxFilter & 0x0F);
	else // set the low nibble to value
		midiParser_txRxFilter = (value & 0x0F) | (midiParser_txRxFilter & 0xF0);

}
