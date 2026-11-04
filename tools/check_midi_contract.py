"""Compile the actual MIDI dispatch functions with spies instead of hardware.

Run: python tools/check_midi_contract.py
Uses Visual Studio on Windows, or a host C compiler elsewhere. Generated
sources and executable stay in build/midi-audit; no firmware is flashed.
"""
from pathlib import Path
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build' / 'midi-audit'
OUT.mkdir(parents=True, exist_ok=True)
source = (ROOT / 'Core/Src/Soundengine/MIDI/MidiParser.c').read_text()
source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)


def function(name, code=source):
    match = re.search(r'\b(?:void|uint8_t|float)\s+' + name + r'\s*\([^)]*\)\s*\{', code)
    assert match, name
    start = match.start()
    pos, depth = match.end(), 1
    while depth:
        depth += (code[pos] == '{') - (code[pos] == '}')
        pos += 1
    return code[start:pos]


header = (ROOT / 'Core/Inc/Soundengine/MIDI/MidiMessages.h').read_text()
header = header.replace('#include "stm32f7xx_hal.h"', '#include <stdint.h>')
# MSVC makes a one-bit enum field signed (-1 for USB); ARM GCC represents
# this nonnegative enum as unsigned. Test dispatch, not host ABI packing.
header = header.replace('enum MidiSource source:1', 'unsigned source:1')
(OUT / 'MidiMessages.h').write_text(header)
enum = re.search(r'typedef enum\s*\{(.*?)\}\s*ParamEnumsDefinition', header, re.S)[1]
enum = re.sub(r'/\*.*?\*/|//[^\n]*', '', enum, flags=re.S)
names, number = {}, -1
for entry in enum.split(','):
    entry = entry.strip()
    if not entry:
        continue
    pair = entry.split('=')
    number = int(pair[1].strip(), 0) if len(pair) > 1 else number + 1
    names[number] = pair[0].strip()
name_array = ','.join('"' + names[i] + '"' for i in range(128))
routing = re.search(r'static union\s*\{.*?\}\s*midiParser_routing\s*=\s*\{0\};', source, re.S)[0]
prelude = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdbool.h>
#include "MidiMessages.h"
#include "MidiNoteNumbers.h"
#include "Parameters.h"
#include "menu/PerformanceControls.h"
#include "Soundengine/Sequencer/PerformanceSteps.h"
#include "Soundengine/Sequencer/PerformanceDelay.h"
enum { MIDI_FILTER_NOTES=1, MIDI_FILTER_SYSTEM=2, MIDI_FILTER_CC=4, MIDI_FILTER_PROG_C=8 };
#define SEQ_DEFAULT_NOTE 60
#define SEQ_PAGE 1
#define MIDI_NOTE_INPUT_RECORD 1
#define MIDI_NOTE_INPUT_ECHO 2
uint8_t midi_MidiChannels[8], midi_ControlChannel, midiParser_txRxFilter=255;
uint8_t activeParameters[NUM_PARAMS], frontParser_activeTrack, menu_activePage;
static uint32_t midiParser_clockCycles;
struct {uint32_t CYCCNT;} dwtMock;
#define DWT (&dwtMock)
uint8_t midiParser_originalCcValues[255];
#define AMP_EG_SYNC 1
#define GLOBAL_DECAY_CENTER 63
static const uint8_t midiParser_decayParams[7]={VELOD1,VELOD2,VELOD3,VELOD4,VELOD5,VELOD6,VELOD6_OPEN};
static uint8_t midiParser_globalDecay=63;
static uint8_t midiParser_modVelocity[7],midiParser_modVelocityValid,midiParser_lastHatTrack=5;
static const uint8_t midiParser_filterParams[6]={FILTER_FREQ_DRUM1,FILTER_FREQ_DRUM2,FILTER_FREQ_DRUM3,SNARE_FILTER_F,CYM_FIL_FREQ,HAT_FILTER_F};
static const uint8_t midiParser_slopeParams[6]={VOL_SLOPE1,VOL_SLOPE2,VOL_SLOPE3,EG_SNARE1_SLOPE,CYM_SLOPE,VOL_SLOPE6};
static void midiParser_refreshVelocityVoice(uint8_t track);
uint8_t midiParser_applyPerformanceVelocity(uint8_t voice,uint8_t velocity,uint8_t note);
static PerfGroove seq_groove;
static float seq_shuffle;
void trigger_setGrooveClock(uint8_t enabled){(void)enabled;}

static uint8_t vcaValues[7],sendValues[7],fxMode,fxOutput,filterSwitch,filterCut,filterRes,filterDrive;
uint8_t mixer_handleVcaCc(uint8_t cc,uint8_t value){if(cc<20||cc>26)return 0;vcaValues[cc-20]=value;return 1;}
uint8_t mixer_handleFxSendCc(uint8_t cc,uint8_t value){if(cc<30||cc>36)return 0;sendValues[cc-30]=value;return 1;}
void mixer_setFxSendMode(uint8_t value){fxMode=value;}
void mixer_setFxOutputMode(uint8_t value){fxOutput=value;for(int i=0;i<7;i++)sendValues[i]=value?64:0;}
uint8_t mixer_getFxOutputMode(void){return fxOutput;}
void mixer_setMasterFilterEnabled(uint8_t value){filterSwitch=value;}
void mixer_setMasterFilter(uint8_t value){filterCut=value;}
void mixer_setMasterFilterResonance(uint8_t value){filterRes=value>105?105:value;}
void mixer_setMasterFilterDrive(uint8_t value){filterDrive=value;}

unsigned voiceDisplayRefresh;
void buttonHandler_refreshVoiceDisplay(void){voiceDisplayRefresh++;}
unsigned macroWrites;
uint8_t applied[255];
unsigned modUpdates;
void modNode_originalValueChanged(uint16_t x){(void)x;modUpdates++;}
uint8_t midiParser_mtcIgnore, midiParser_mtcIsRunning;
unsigned midiParser_lastMtcReceived, systick_ticks;
static unsigned handled, morphed, recorded, front, din, usb, notes[7], cases;
static uint8_t frontBytes[16], extSync, runState;
static unsigned added[7], echoes, noteOffs, muted, repaints;
void menu_repaintAll(void){repaints++;}
void midiParser_setPitchBendRange(uint8_t value);
uint8_t midiParser_isValidChannel(uint8_t chan);
static uint16_t parsedParameter;
void menu_parseGlobalParam(uint16_t parameter,uint8_t value){parsedParameter=parameter;(void)value;}
static uint8_t played[7], recordedNote[7], active_voices;
typedef struct { uint16_t midiFreq; uint8_t baseNote; float freq,pitchBend; } OscInfo;
typedef struct { OscInfo osc,modOsc,modOsc2; uint8_t oscVolEg; float decayClosed,decayOpen; } TestVoice;
TestVoice voiceArray[3],snareVoice,cymbalVoice,hatVoice;
void slopeEg2_setDecay(uint8_t *eg,uint8_t value,uint8_t sync){(void)sync;*eg=value;}
float slopeEg2_calcDecay(uint8_t value){return (float)value;}
static int8_t osc_notePitchOffset,osc_globalPitchOffset;
static float osc_globalPitchBend;
static const float OSC_SEMITONE_UP=1.0594630943592953f;
static int16_t midiParser_pitchBendValue;
static uint8_t midiParser_pitchBendRange=12;
float midiParser_calcDetune(uint8_t x) { (void)x; return 1.f; }
struct { struct { uint8_t note; } seq_subStepPattern[1][7][64]; } seq_patternSet;
uint8_t menu_getActiveVoice(void) { return frontParser_activeTrack; }
uint8_t menu_getViewedPattern(void) { return 0; }
void menu_repaint(void) { repaints++; }
int seq_isTrackMuted(uint8_t v) { return (muted & (1u<<v)) != 0; }
void seq_addNote(uint8_t v,uint8_t vel,uint8_t n) { (void)vel; added[v]++; recordedNote[v]=n; }
void seq_sendMidiNoteOn(uint8_t c,uint8_t n,uint8_t v) { (void)c;(void)n;(void)v; echoes++; }
void seq_midiNoteOff(uint8_t c) { (void)c; noteOffs++; }
void Drum_trigger(uint8_t v,uint8_t vel,uint8_t n) { (void)vel; notes[v]++; played[v]=n; }
void Snare_trigger(uint8_t vel,uint8_t n) { Drum_trigger(3,vel,n); }
void Cymbal_trigger(uint8_t vel,uint8_t n) { Drum_trigger(4,vel,n); }
void HiHat_trigger(uint8_t vel,uint8_t open,uint8_t n) { Drum_trigger(5+open,vel,n); }
static uint8_t lastMorph;
static int pattern=-1;
void uart_sendMidi(MidiMsg m) { (void)m; din++; }
void usb_sendMidi(MidiMsg m) { (void)m; usb++; }
void uart_sendFrontpanelByte(uint8_t x) { if(front<sizeof(frontBytes))frontBytes[front]=x;front++; }
uint8_t menu_getWaveformMax(void){return 5;}
uint8_t menu_limitSoundParameter(uint16_t p,uint8_t v){
 if(p==PAR_SNARE_LAYER_WAVE&&v>5)return 5;
 if(p==PAR_SNARE_LAYER_MODE&&v>2)return 2;
 return v;
}
void preset_morph(uint8_t x) { (void)x; }
void preset_setMorphTarget(uint8_t x) { morphed++; lastMorph=x; }
void midiParser_ccHandler(MidiMsg m,int a,int b,float c) {
    (void)b;(void)c;
    uint16_t index=(m.status&0xf0)==MIDI_CC?m.data1:(uint16_t)(128+m.data1);
    if(a) {handled++;midiParser_originalCcValues[index]=m.data2;}
    else {macroWrites++;applied[index]=m.data2;}
}
uint8_t recordedTrack,recordedTarget,recordedValue;
void seq_recordAutomation(uint8_t t,uint8_t c,uint8_t v) {recordedTrack=t;recordedTarget=c;recordedValue=v;recorded++;}
void seq_setNextPattern(uint8_t p) { if(p<64) pattern=p; }
int seq_getExtSync(void) { return extSync; }
uint8_t seq_isRunning(void) { return runState; }
void seq_sync(void) {}
void sync_tickAtCycles(uint32_t cycles) {(void)cycles;}
void sync_midiResetPosition(void) {}
void sync_midiStartStop(int r) { runState=(uint8_t)r; }
void sync_setClockOffset(uint8_t coarse,uint8_t fine) {(void)coarse;(void)fine;}
uint8_t seq_applyPendingScale(void){return 0;}
void seq_setRunning(int r) { runState=(uint8_t)r; }
'''
tests = r'''
static void reset_parameters(void) {
    memset(activeParameters,0,sizeof(activeParameters));
    activeParameters[PAR_PERF_VELO_LEVEL]=63;
    for(uint16_t p=PAR_PERF_VELO_DECAY;p<=PAR_PERF_VELO_DRIVE;p++)activeParameters[p]=63;
    activeParameters[PAR_PERF_NOTE_PROB]=100;
    midiParser_globalDecay=63;
}
static void reset_spies(void) {
    handled=morphed=recorded=front=din=usb=0;
    memset(frontBytes,0,sizeof(frontBytes));
    memset(notes,0,sizeof(notes)); memset(added,0,sizeof(added));
    echoes=noteOffs=repaints=macroWrites=voiceDisplayRefresh=0; pattern=-1;
}
static void check(int ok,const char *label,int a,int b,int c) {
    cases++;
    if(!ok) { fprintf(stderr,"FAIL %s: %d %d %d\n",label,a,b,c); exit(1); }
}
static MidiMsg message(int source,int channel,int status,int cc,int value) {
    MidiMsg m={0}; m.status=(uint8_t)(status|channel); m.data1=(uint8_t)cc;
    m.data2=(uint8_t)value; m.bits.source=source; return m;
}
int main(void) {
    int source,overlap,rx,channel,cc,v,routing;
    /* Distinct channels expose the legacy one-based target / zero-based array bug. */
    const int representative[6]={2,3,4,5,7,8};
    for(v=0;v<8;v++) midi_MidiChannels[v]=(uint8_t)v;
    midi_ControlChannel=15; reset_parameters();
    for(v=0;v<6;v++) {
        reset_spies(); midiParser_parseMidiMessage(message(0,v,MIDI_CC,representative[v],64));
        check(handled==1,"voice CC must use its own channel",v,representative[v],handled);
    }
    for(source=0;source<2;source++) for(overlap=-1;overlap<8;overlap++) {
        midi_ControlChannel=(uint8_t)(overlap<0?15:overlap);
        for(rx=0;rx<2;rx++) for(channel=0;channel<16;channel++) for(cc=0;cc<128;cc++) {
            int target=midiParser_cc2voiceNr((uint8_t)cc);
            int wantMorph=rx && overlap<0 && channel==15 && cc==2;
            int wantPitch=rx && channel==midi_ControlChannel && cc==27;
            int wantExtra=rx && channel==midi_ControlChannel &&
                (cc==5||cc==6||cc==7||cc==8||cc==9||cc==28||(cc>=10&&cc<=16)||cc==126||
                 (cc>=20&&cc<=26)||(cc>=30&&cc<=44)||((cc>=79&&cc<=84)||(cc>=88&&cc<=91))||(cc>=46&&cc<=52)||(cc>=60&&cc<=66)||
                 (overlap<0&&((cc>=54&&cc<=59)||(cc>=67&&cc<=75)||(cc>=92&&cc<=97)||(cc>=102&&cc<=119))));
            int wantPwm=rx && overlap<0 && channel==midi_ControlChannel && ((cc>=92&&cc<=97)||(cc>=70&&cc<=75));
            MidiMsg mapped=message(source,channel,MIDI_CC,cc,127);
            int wantVoice=rx && channel<7 && channel!=midi_ControlChannel && midiParser_mapVoiceCc((uint8_t)channel,(uint8_t)cc,&mapped);
            int wantSnare=wantVoice && channel==3 && cc>=112 && cc<=118;
            int wantLegacy=!wantVoice && !wantExtra && !wantPitch && rx && (target==0 || target==7 ? channel<8 :
                channel==target-1 || channel==7);
            reset_parameters(); reset_spies(); midiParser_setFilter(0,rx?15:11);
            midiParser_parseMidiMessage(message(source,channel,MIDI_CC,cc,127));
            check(morphed==(unsigned)wantMorph && handled==(unsigned)(wantLegacy||wantVoice||wantPwm),
                "CC route",overlap,channel,cc);
            check(recorded==(unsigned)(wantLegacy||wantVoice) && front==(unsigned)(3*wantLegacy),
                "legacy automation/front feedback",overlap,channel,cc);
            if(wantVoice)check(repaints==1,"voice alias repaints",channel,cc,0);
            if(wantSnare){
                const uint16_t ids[]={PAR_SNARE_LAYER_WAVE,PAR_SNARE_LAYER_AMOUNT,PAR_SNARE_LAYER_FREQ,PAR_SNARE_LAYER_MODE,PAR_SNARE_NOISE_ATTACK,PAR_SNARE_NOISE_DECAY,PAR_SNARE_NOISE_SLOPE};
                const uint8_t expected=cc==112?5:cc==115?2:127;
                check(activeParameters[ids[cc-112]]==expected&&midiParser_originalCcValues[ids[cc-112]]==expected&&repaints==1,"snare CC state and base value",channel,cc,0);
            }
            if(wantMorph) check(lastMorph==255,"Morph endpoint",overlap,channel,cc);
            if(wantPitch) check(activeParameters[PAR_GLOBAL_PITCH]==127 && repaints==1,
                "Pch CC27 master pitch",overlap,channel,cc);
            if(wantExtra && (cc==5||cc==6||cc==7||cc==28)){
                uint16_t p=cc==5?PAR_RANDOM_STEP:cc==6?PAR_PERF_NOTE_REPEAT_CHANCE:
                    cc==7?PAR_PERF_PROB:PAR_GLOBAL_DECAY;
                check(activeParameters[p]==(cc==5||cc==7?100:127)&&repaints==1,
                    "imported performance CC",overlap,channel,cc);
            }
            else if(wantExtra)check(repaints==1,"delay/accent CC consumed",overlap,channel,cc);
        }
    }
    midi_ControlChannel=15; midiParser_setFilter(0,15);
    for(source=0;source<2;source++)for(cc=112;cc<=118;cc++)for(v=0;v<128;v++){
        const uint16_t ids[]={PAR_SNARE_LAYER_WAVE,PAR_SNARE_LAYER_AMOUNT,PAR_SNARE_LAYER_FREQ,PAR_SNARE_LAYER_MODE,PAR_SNARE_NOISE_ATTACK,PAR_SNARE_NOISE_DECAY,PAR_SNARE_NOISE_SLOPE};
        uint8_t expected=cc==112&&v>5?5:cc==115&&v>2?2:v;
        reset_parameters();reset_spies();
        midiParser_parseMidiMessage(message(source,3,MIDI_CC,cc,v));
        check(handled==1&&recorded==1&&front==0&&repaints==1,"snare CC single dispatch",source,cc,v);
        check(recordedTrack==3&&recordedTarget==ids[cc-112]&&recordedValue==expected,"snare automation uses internal target",source,cc,v);
        check(activeParameters[ids[cc-112]]==expected&&midiParser_originalCcValues[ids[cc-112]]==expected,"snare CC exact values",source,cc,v);
    }

    for(v=0;v<128;v++)for(cc=40;cc<=43;cc++) {
        reset_spies();midiParser_parseMidiMessage(message(0,15,MIDI_CC,(uint8_t)cc,(uint8_t)v));
        uint16_t p=cc==40?PAR_SHUFFLE:(uint16_t)(PAR_GROOVE_SH2+cc-41);
        check(activeParameters[p]==(cc>40&&v==64?63:v)&&repaints==1,
            "groove CC values and bipolar deadband",cc,v,activeParameters[p]);
    }
    for(v=0;v<128;v++) {
        reset_spies(); midiParser_parseMidiMessage(message(0,15,MIDI_CC,2,v));
        check(morphed==1 && lastMorph==(v==127?255:2*v),"Morph scaling",v,lastMorph,0);
    }
    for(source=0;source<2;source++) for(routing=0;routing<6;routing++) {
        /* Routing is intentionally before local RX filters and channel rejection. */
        reset_spies(); midiParser_setFilter(0,0); midiParser_setRouting((uint8_t)routing);
        midiParser_parseMidiMessage(message(source,15,MIDI_CC,2,127));
        check(!handled && !morphed,"RX off",source,routing,0);
        check(din==(unsigned)(source==1?(routing==1||routing==3):
            (routing==2||routing==3||routing==5)),"DIN forwarding",source,routing,din);
        check(usb==(unsigned)(source==0&&(routing==4||routing==5)),"USB forwarding",source,routing,usb);
    }
    midiParser_setRouting(0); midiParser_setFilter(0,15);
    /* All nte/note pairs, both ports, Global and dedicated Voice routes. */
    frontParser_activeTrack=2;
    for(source=0;source<2;source++) for(rx=0;rx<2;rx++)
      for(cc=0;cc<128;cc++) for(v=0;v<128;v++) {
        int want=rx || cc==0 || cc==v;
        int playedNote=(!rx && cc!=0)?SEQ_DEFAULT_NOTE:v;
        activeParameters[PAR_MIDI_NOTE1+2]=(uint8_t)cc;
        reset_spies(); midiParser_parseMidiMessage(message(source,rx?2:7,NOTE_ON,v,100));
        check(notes[2]==(unsigned)want && added[2]==(unsigned)want,
            "note map/record",rx,cc,v);
        check(echoes==(unsigned)(!rx&&want) && noteOffs==echoes,"note echo",rx,cc,v);
        if(want) check(played[2]==playedNote && recordedNote[2]==playedNote,
            "note pitch",rx,cc,v);
      }
    reset_parameters();
    frontParser_activeTrack=0;
    activeParameters[PAR_MIDI_NOTE1+1]=38; activeParameters[PAR_MIDI_NOTE1+2]=38;
    midi_MidiChannels[1]=7;
    reset_spies(); midiParser_parseMidiMessage(message(0,7,NOTE_ON,38,100));
    check(notes[1]==1 && notes[2]==1 && !notes[0] && echoes==2,"duplicate map beats ANY",0,0,0);
    reset_spies(); midiParser_parseMidiMessage(message(0,7,NOTE_ON,39,100));
    check(notes[0]==1 && !notes[1] && echoes==1,"unmapped ANY fallback",0,0,0);
    activeParameters[PAR_MIDI_NOTE1]=40;
    reset_spies(); midiParser_parseMidiMessage(message(0,7,NOTE_ON,39,100));
    check(!notes[0]&&!notes[1]&&!notes[2],"fixed selection has no ANY fallback",0,0,0);
    reset_spies(); midiParser_parseMidiMessage(message(0,7,NOTE_ON,40,100));
    check(notes[0]==1 && !notes[1],"Global wins over shared Voice channel",0,0,0);
    reset_spies(); midiParser_parseMidiMessage(message(0,7,NOTE_ON,60,0));
    check(!notes[0]&&!notes[1]&&!echoes,"zero velocity ignored",0,0,0);
    reset_spies(); midiParser_parseMidiMessage(message(0,0,NOTE_OFF,40,100));
    check(!notes[0]&&!echoes,"Note Off unchanged",0,0,0);
    muted=1; reset_spies(); midiParser_parseMidiMessage(message(0,0,NOTE_ON,60,100));
    check(!notes[0]&&!added[0]&&!echoes,"muted voice",0,0,0); muted=0;
    midiParser_setFilter(0,14); reset_spies();
    midiParser_parseMidiMessage(message(0,0,NOTE_ON,60,100));
    check(!notes[0]&&!added[0],"RX N off",0,0,0); midiParser_setFilter(0,15);
    midi_MidiChannels[1]=0;
    reset_spies(); midiParser_parseMidiMessage(message(0,0,NOTE_ON,70,100));
    check(notes[0]==1 && notes[1]==1 && added[0]==1 && added[1]==1 && !echoes,
        "shared Voice channel chromatic no echo",0,0,0);
    midi_ControlChannel=0;
    for(v=0;v<128;v++) {
        reset_spies(); midiParser_parseMidiMessage(message(0,0,NOTE_ON,v,100));
        check(osc_notePitchOffset==(v>124?64:v-60) && !notes[0] && !notes[1] && !echoes,
            "Pch note wins over Voice and clamps",v,osc_notePitchOffset,0);
    }
    midi_ControlChannel=7;
    reset_spies(); midiParser_parseMidiMessage(message(0,7,NOTE_ON,40,100));
    check(notes[0]==1 && echoes==1,"Global wins over shared Pch",0,0,0);
    midi_ControlChannel=15;
    reset_spies(); midiParser_parseMidiMessage(message(0,15,NOTE_ON,60,100));
    check(osc_notePitchOffset==0 && !notes[0]&&!notes[1],"Pch middle C neutral",0,0,0);
    menu_activePage=SEQ_PAGE; activeParameters[PAR_ACTIVE_STEP]=3;
    reset_spies(); midiParser_parseMidiMessage(message(0,0,NOTE_ON,72,100));
    check(seq_patternSet.seq_subStepPattern[0][0][3].note==72 && repaints==1 &&
        !notes[0] && notes[1]==1 && !echoes,"step entry stays on edited voice",0,0,0);
    menu_activePage=0;
    reset_spies(); voiceControl_noteOn(0,60,100);
    check(notes[0]==1 && echoes==1,"normal sequencer trigger retains MIDI output",0,0,0);
    { OscInfo o={60u<<8,60,0};
      osc_setGlobalPitchOffset(63); osc_setGlobalPitchBend(0,12);
      osc_setNotePitchOffset(12); osc_setBaseNote(&o,60);
      check(fabsf(o.freq-MidiNoteFrequencies[72])<0.001f,"transpose at trigger",0,0,0);
      osc_setNotePitchOffset(-12); osc_recalcFreq(&o);
      check(fabsf(o.freq-MidiNoteFrequencies[48])<0.001f,"transpose sounding voice",0,0,0);
      osc_setNotePitchOffset(64); osc_setBaseNote(&o,127);
      check(o.freq>MidiNoteFrequencies[127],"frequency above MIDI127",0,0,0);
      osc_setNotePitchOffset(-63); o.midiFreq=0; osc_setBaseNote(&o,0);
      check(o.freq>0.f && o.freq<MidiNoteFrequencies[0],"frequency below MIDI0",0,0,0);
    }
    /* Compare oscillator composition with the unmodified mutador source. */
    for(v=0;v<128;v++) for(cc=0;cc<128;cc+=7) for(rx=-8192;rx<=8191;rx+=2047) {
        OscInfo a={0},b={0}; a.midiFreq=b.midiFreq=(uint16_t)(cc<<8);
        osc_setGlobalPitchOffset((uint8_t)cc); ref_osc_setGlobalPitchOffset((uint8_t)cc);
        osc_setNotePitchOffset((int8_t)(v>124?64:v-60));
        ref_osc_setNotePitchOffset((int8_t)(v>124?64:v-60));
        osc_setGlobalPitchBend((int16_t)rx,48); ref_osc_setGlobalPitchBend((int16_t)rx,48);
        osc_setPitchBend(&a,(int16_t)-rx,12); ref_osc_setPitchBend(&b,(int16_t)-rx,12);
        osc_setBaseNote(&a,(uint8_t)v); ref_osc_setBaseNote(&b,(uint8_t)v);
        check(fabsf(a.freq-b.freq)<=fabsf(b.freq)*0.000001f,"Mutador pitch parity",v,cc,rx);
    }
    osc_setNotePitchOffset(0); midiParser_setGlobalPitch(63); midiParser_setPitchBendRange(12);
    midi_ControlChannel=15; midi_MidiChannels[0]=0; midi_MidiChannels[1]=0;
    for(v=0;v<3;v++) voiceArray[v].osc.midiFreq=voiceArray[v].modOsc.midiFreq=60u<<8;
    reset_spies(); midiParser_parseMidiMessage(message(0,15,MIDI_PITCH_WHEEL,0,64));
    check(osc_globalPitchBend==0,"bend center",0,0,0);
    reset_spies(); midiParser_parseMidiMessage(message(0,15,MIDI_PITCH_WHEEL,0,0));
    check(osc_globalPitchBend==-12.f,"Pch global bend",0,0,0);
    reset_spies(); midiParser_parseMidiMessage(message(0,7,MIDI_PITCH_WHEEL,127,127));
    check(osc_globalPitchBend>11.99f && osc_globalPitchBend<12.f,"Global positive bend",0,0,0);
    reset_spies(); midiParser_parseMidiMessage(message(0,0,MIDI_PITCH_WHEEL,0,0));
    check(voiceArray[0].osc.pitchBend==-12.f && voiceArray[0].modOsc.pitchBend==-12.f &&
        voiceArray[1].osc.pitchBend==0.f,"first matching Voice bend",0,0,0);
    midiParser_setPitchBendRange(100);
    check(activeParameters[PAR_PITCH_BEND_RANGE]==48 && osc_globalPitchBend>47.99f,
        "range clamps and reapplies global bend",0,0,0);
    midiParser_setFilter(0,0); midiParser_setRouting(5);
    reset_spies(); midiParser_parseMidiMessage(message(0,15,NOTE_ON,72,100));
    check(osc_notePitchOffset==12 && !din && !usb,
        "Mutador Pch pitch before RX and Thru",0,0,0);
    for(v=61;v<=66;v++) check(midiParser_scaleGlobalPitchCc((uint8_t)v)==63,
        "CC27 neutral dead band",v,0,0);
    for(v=0;v<128;v++)for(cc=0;cc<128;cc++)
        check(midiParser_decayDepth((uint8_t)v,(uint8_t)cc)==
            ref_midiParser_applyVelocityDepth((uint8_t)v,(uint8_t)cc,127),
            "Mutador GDC depth parity",v,cc,0);
    for(v=0;v<7;v++)midiParser_originalCcValues[midiParser_decayParams[v]]=(uint8_t)(10+v*13);
    midiParser_setGlobalDecay(0);
    check(voiceArray[0].oscVolEg==0&&hatVoice.decayClosed==0&&hatVoice.decayOpen==0,
        "GDC minimum affects all envelope types",0,0,0);
    midiParser_setGlobalDecay(127);
    check(voiceArray[0].oscVolEg==127&&snareVoice.oscVolEg==127&&cymbalVoice.oscVolEg==127&&
        hatVoice.decayClosed==127&&hatVoice.decayOpen==127,"GDC maximum",0,0,0);
    midiParser_setGlobalDecay(63);
    check(voiceArray[0].oscVolEg==10&&snareVoice.oscVolEg==49&&hatVoice.decayClosed==75&&
        hatVoice.decayOpen==88,"GDC neutral restores independent raw decay values",0,0,0);
    for(v=0;v<7;v++)check(midiParser_originalCcValues[midiParser_decayParams[v]]==10+v*13,
        "GDC preserves source kit/morph cache",v,0,0);
    // Actual accent functions, with the MIDI parameter sink spied above.
    reset_parameters();
    for(v=0;v<255;v++)midiParser_originalCcValues[v]=60;
    for(v=0;v<3;v++)voiceArray[v].oscVolEg=60;
    snareVoice.oscVolEg=cymbalVoice.oscVolEg=60;hatVoice.decayClosed=hatVoice.decayOpen=60;
    for(v=0;v<7;v++)midiParser_applyPerformanceVelocity((uint8_t)v,127,60);
    midiParser_setAccentParameter(PAR_PERF_VELO_DECAY,127);
    check(voiceArray[0].oscVolEg==60,"VLV neutral disables destinations",0,0,0);
    midiParser_setAccentParameter(PAR_PERF_VELO_LEVEL,127);
    check(voiceArray[0].oscVolEg==127&&hatVoice.decayOpen==127,"VDC full positive",0,0,0);
    applied[FILTER_FREQ_DRUM1]=77; midiParser_applyPerformanceVelocity(0,127,60);
    check(applied[FILTER_FREQ_DRUM1]==77,"neutral accent target preserves step automation",0,0,0);
    midiParser_setGlobalDecay(0);
    check(voiceArray[0].oscVolEg==0,"GDC follows velocity decay layer",0,0,0);
    midiParser_setGlobalDecay(63);
    for(uint16_t p=PAR_PERF_VELO_SAMPLE_RATE;p<=PAR_PERF_VELO_DRIVE;p++)
        midiParser_setAccentParameter(p,127);
    check(applied[VOICE_DECIMATION1]==127&&applied[FILTER_FREQ_DRUM1]==127&&
        applied[VOL_SLOPE1]==127&&applied[MODAMNT1]==127&&applied[128+CC2_FILTER_DRIVE_1]==127,
        "all accent destinations enabled",0,0,0);
    check(midiParser_applyPerformanceVelocity(0,127,60)==127,"VCO note offset clamp",0,0,0);
    midiParser_setAccentParameter(PAR_PERF_VELO_LEVEL,0);
    check(applied[VOICE_DECIMATION1]==0&&voiceArray[0].oscVolEg==0,
        "negative VLV inverts destination depth",0,0,0);
    midiParser_setAccentParameter(PAR_PERF_VELO_LEVEL,63);
    check(applied[VOICE_DECIMATION1]==60&&applied[FILTER_FREQ_DRUM1]==60&&
        applied[128+CC2_FILTER_DRIVE_1]==60&&voiceArray[0].oscVolEg==60,
        "turning VLV off restores raw kit values",0,0,0);
    for(v=0;v<255;v++)check(midiParser_originalCcValues[v]==60,
        "accent preserves all source cache values",v,0,0);
    // The last triggered hat owns shared tone controls; amp decays stay separate.
    midiParser_setAccentParameter(PAR_PERF_VELO_DECAY,127);
    midiParser_setAccentParameter(PAR_PERF_VELO_SAMPLE_RATE,127);
    midiParser_setAccentParameter(PAR_PERF_VELO_LEVEL,127);
    midiParser_applyPerformanceVelocity(5,0,60);midiParser_applyPerformanceVelocity(6,127,60);
    check(hatVoice.decayClosed==60&&hatVoice.decayOpen==127&&applied[VOICE_DECIMATION6]==127,
        "independent hat decay/shared last-trigger rate",0,0,0);
    midiParser_applyPerformanceVelocity(5,0,60);
    check(applied[VOICE_DECIMATION6]==60,"closed hat regains shared control",0,0,0);
    midiParser_setFilter(0,15); midiParser_setRouting(0);
    reset_spies(); midiParser_parseMidiMessage(message(0,15,PROG_CHANGE,5,0));
    check(pattern==-1,"Pch is not Program Change channel",0,0,0);
    reset_spies(); midiParser_parseMidiMessage(message(0,7,PROG_CHANGE,63,0));
    check(pattern==63,"Global Program Change",0,0,0);
    extSync=2;midiParser_txRxFilter=255;
    reset_spies();midiParser_parseMidiMessage(message(0,0,MIDI_START,0,0));
    check(runState==1&&front==3&&frontBytes[0]==FRONT_SEQ_CC&&
      frontBytes[1]==FRONT_SEQ_RUN_STOP&&frontBytes[2]==1,
      "MIDI START updates front-panel PLAY state",0,0,0);
    reset_spies();midiParser_parseMidiMessage(message(0,0,MIDI_STOP,0,0));
    check(runState==0&&front==3&&frontBytes[0]==FRONT_SEQ_CC&&
      frontBytes[1]==FRONT_SEQ_RUN_STOP&&frontBytes[2]==0,
      "MIDI STOP updates front-panel PLAY state",0,0,0);
    reset_spies();midiParser_parseMidiMessage(message(0,0,MIDI_CONTINUE,0,0));
    check(runState==1&&front==3&&frontBytes[2]==1,
      "MIDI CONTINUE updates front-panel PLAY state",0,0,0);
    { /* Pch controls added in 0.2.22 reach the same state as the menu. */
      static const struct {uint8_t cc;uint16_t parameter;uint8_t top;} pch[]={
        {54,PAR_PERF_SCARCITY,100},{55,PAR_PERF_AVL,200},{56,PAR_PERF_FILL,1},
        {57,PAR_MASTER_FILTER_ENABLE,1},{58,PAR_PITCH_BEND_RANGE,48},
        {59,PAR_FX_SEND_MODE,3},{67,PAR_FX_OUTPUT_MODE,1},{68,PAR_CLOCK_OFFSET,80}};
      midi_ControlChannel=15; midiParser_setFilter(0,15);
      for(unsigned i=0;i<sizeof(pch)/sizeof(pch[0]);i++) {
        reset_parameters(); reset_spies();
        midiParser_parseMidiMessage(message(0,15,MIDI_CC,pch[i].cc,127));
        check(activeParameters[pch[i].parameter]==pch[i].top&&repaints>=1,"Pch control reaches its top",pch[i].cc,127,activeParameters[pch[i].parameter]);
      }
      reset_parameters(); activeParameters[PAR_CLOCK_OFFSET]=50;
      midiParser_parseMidiMessage(message(0,15,MIDI_CC,69,127));
      check(activeParameters[PAR_CLOCK_OFFSET_FINE]==9,"Pch fine clock offset",69,127,0);
      for(unsigned v=0;v<3;v++) {
        static const uint16_t amounts[3]={PAR_FMAMNT1,PAR_FMAMNT2,PAR_FMAMNT3};
        for(unsigned value=0;value<128;value++) {
          reset_parameters(); reset_spies();
          midiParser_parseMidiMessage(message(0,15,MIDI_CC,70+v,value));
          check(activeParameters[PAR_MIX_MOD_1+v]==(value*4u+63u)/127u&&handled==1,"Pch Drum mode spans five modes",v,value,0);
          midiParser_parseMidiMessage(message(0,15,MIDI_CC,73+v,value));
          check(activeParameters[amounts[v]]==value&&handled==2,"Pch Drum FM amount",v,value,0);
        }
        reset_parameters();midiParser_parseMidiMessage(message(0,15,MIDI_CC,70+v,127));
        check(activeParameters[PAR_MIX_MOD_1+v]==4,"Pch Drum mode top is pd",v,127,0);
      }
      for(unsigned v=0;v<6;v++) {
        reset_parameters(); reset_spies(); parsedParameter=0;
        midiParser_parseMidiMessage(message(0,15,MIDI_CC,92+v,100));
        check(activeParameters[PAR_PWM_1+v]==100&&handled==1,"Pch PWM",v,100,0);
        midiParser_parseMidiMessage(message(0,15,MIDI_CC,102+v,100));
        check(activeParameters[PAR_LFO_SLEW1+v]==100&&parsedParameter==PAR_LFO_SLEW1+v,"Pch LFO slew",v,100,0);
        midiParser_parseMidiMessage(message(0,15,MIDI_CC,108+v,127));
        check(activeParameters[PAR_LFO_POL1+v]==2&&parsedParameter==PAR_LFO_POL1+v,"Pch LFO polarity",v,127,0);
        midiParser_parseMidiMessage(message(0,15,MIDI_CC,114+v,100));
        check(activeParameters[PAR_RPS_AMT1+v]==100&&parsedParameter==PAR_RPS_AMT1+v,"Pch random step depth",v,100,0);
      }
    }
    printf("PASS %u assertions against extracted firmware dispatch functions\n",cases);
    { FILE *f=fopen("cc-map.csv","w"); if(!f) return 2;
      fprintf(f,"cc,legacy_symbol,legacy_target_group,dedicated_Pch_now\n");
      for(cc=0;cc<128;cc++) fprintf(f,"%d,%s,%d,%s\n",cc,cc_names[cc],
        midiParser_cc2voiceNr((uint8_t)cc),cc==2?"Morph":cc==27?"Global pitch":
          cc==28?"Global decay":cc==5?"Random step":cc==6?"Previous step repeat":
          cc==7?"Global probability":cc==8?"Step chance scale":cc==9?"Random velocity":
          cc==10?"Delay chance":cc==11?"Delay clock":cc==12?"Delay count":
          cc==13?"Delay bounce":cc==14?"Delay exponent":
          cc==15?"Delay pitch":cc==16?"Delay mode":cc==126?"Delay velocity target":
          (cc>=20&&cc<=26)?"Voice/master VCA":(cc>=30&&cc<=36)?"External FX send":
          cc==37?"Master filter cutoff":cc==38?"Master filter resonance":cc==39?"Master filter drive":
          (cc>=79&&cc<=84)?"spd":(cc>=88&&cc<=91)?"sct":
          cc==54?"Scarcity":cc==55?"All velocity":cc==56?"Fill":cc==57?"Master filter enable":
          cc==58?"Pitch bend range":cc==59?"FX send mode":cc==67?"FX output mode":
          cc==68?"Clock offset":cc==69?"Clock offset fine":(cc>=70&&cc<=72)?"Drum mode":(cc>=73&&cc<=75)?"Drum FM amount":(cc>=92&&cc<=97)?"Voice PWM":
          (cc>=102&&cc<=107)?"LFO slew":(cc>=108&&cc<=113)?"LFO polarity":
          (cc>=114&&cc<=119)?"Random step LFO depth":
          cc==40?"Shuffle master":cc==41?"Groove SH2":cc==42?"Groove SH3":cc==43?"Groove SH4":cc==44?"Accent master":cc==46?"Accent decay":cc==47?"Accent sample rate":
          cc==48?"Accent filter":cc==49?"Accent coarse pitch":
          cc==50?"Accent slope":cc==51?"Accent mod amount":
          cc==52?"Accent drive":(cc>=60&&cc<=66)?"Delay input toggle":"Ignored");
      fclose(f);
    }
    return 0;
}
'''
def stripped(path):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', (ROOT / path).read_text(), flags=re.S)

voice_source = stripped('Core/Src/Soundengine/MIDI/MidiVoiceControl.c')
osc_source = stripped('Core/Src/Soundengine/DSPAudio/Oscillator.c')
(OUT / 'Soundengine/Sequencer').mkdir(parents=True, exist_ok=True)
(OUT / 'Soundengine/Sequencer/PerformanceSteps.h').write_text(
    (ROOT/'Core/Inc/Soundengine/Sequencer/PerformanceSteps.h').read_text())
(OUT / 'Soundengine/Sequencer/PerformanceDelay.h').write_text(
    (ROOT/'Core/Inc/Soundengine/Sequencer/PerformanceDelay.h').read_text())
(OUT/'Soundengine/Sequencer/PerformanceGroove.h').write_text((ROOT/'Core/Inc/Soundengine/Sequencer/PerformanceGroove.h').read_text())
for relative in ('menu/PerformanceControls.h','Soundengine/Sequencer/PerformanceScale.h','Soundengine/DSPAudio/mixer.h','Soundengine/DSPAudio/PerformanceMasterFilter.h'):
    target=OUT/relative;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text((ROOT/'Core/Inc'/relative).read_text())
(OUT/'Parameters.h').write_text((ROOT/'Core/Inc/Parameters.h').read_text())
(OUT/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
(OUT/'Soundengine/Sequencer/clockSync.h').write_text('void sync_setClockOffset(uint8_t,uint8_t);\n')
(OUT / 'MidiNoteNumbers.h').write_text((ROOT / 'Core/Inc/Soundengine/MIDI/MidiNoteNumbers.h').read_text())
functions = '\n'.join(function(n, osc_source) for n in (
    'osc_calcMidiNoteFrequency', 'osc_setNotePitchOffset', 'osc_setBaseNote', 'osc_recalcFreq',
    'osc_setGlobalPitchOffset', 'osc_setGlobalPitchBend', 'osc_setPitchBend'))
reference_path = ROOT.parent / 'mutador/mainboard/LxrStm32/src/DSPAudio/Oscillator.c'
reference = re.sub(r'/\*.*?\*/|//[^\n]*', '', reference_path.read_text(), flags=re.S)
ref_names = ['osc_calcMidiNoteFrequency','osc_recalcFreq','osc_setBaseNote',
             'osc_setGlobalPitchOffset','osc_setNotePitchOffset','osc_setGlobalPitchBend','osc_setPitchBend']
ref_code = '\n'.join(function(n, reference) for n in ref_names)
for name in ref_names + ['osc_globalPitchOffset','osc_notePitchOffset','osc_globalPitchBend','OSC_SEMITONE_UP']:
    ref_code = re.sub(r'\b'+name+r'\b', 'ref_'+name, ref_code)
functions += '\nstatic int8_t ref_osc_globalPitchOffset,ref_osc_notePitchOffset;\n'
functions += 'static float ref_osc_globalPitchBend;\nstatic const float ref_OSC_SEMITONE_UP=1.0594630943592953f;\n'
functions += 'void ref_osc_recalcFreq(OscInfo* osc);\n'+ref_code
ref_parser=re.sub(r'/\*.*?\*/|//[^\n]*', '',
    (ROOT.parent/'mutador/mainboard/LxrStm32/src/MIDI/MidiParser.c').read_text(),flags=re.S)
functions += '\n'+function('midiParser_applyVelocityDepth',ref_parser).replace(
    'midiParser_applyVelocityDepth','ref_midiParser_applyVelocityDepth')
functions += '\n'+(ROOT/'Core/Src/Soundengine/Sequencer/PerformanceSteps.c').read_text()
functions += '\n'+(ROOT/'Core/Src/Soundengine/Sequencer/PerformanceScale.c').read_text()
functions += '\n'+(ROOT/'Core/Src/menu/PerformanceControls.c').read_text()
functions += '\n'+(ROOT/'Core/Src/Soundengine/Sequencer/PerformanceGroove.c').read_text()
functions += '\n'+(ROOT/'Core/Src/Soundengine/Sequencer/PerformanceDelay.c').read_text()
seq_source=stripped('Core/Src/Soundengine/Sequencer/sequencer.c')
functions += '\n'+function('seq_setShuffle',seq_source)+'\n'+function('seq_setGrooveStep',seq_source)
functions += '\n' + '\n'.join(function(n, voice_source) for n in (
    'voiceControl_trigger', 'voiceControl_noteOn', 'voiceControl_noteOnNoEcho'))
functions += '\n' + '\n'.join(function(n) for n in (
    'midiParser_noteOn', 'midiParser_scaleGlobalPitchNote', 'midiParser_scaleGlobalPitchCc',
    'midiParser_applyVelocityDepth','midiParser_scalePerformanceVelocityAmount',
    'midiParser_velocityAmount','midiParser_velocityForTrack',
    'midiParser_decayDepth', 'midiParser_applyGlobalDecayParam', 'midiParser_setGlobalDecay',
    'midiParser_setStepPerformance',
    'midiParser_velocityLive','midiParser_velocityCc','midiParser_applyVelocityDestination','midiParser_refreshVelocityVoice',
    'midiParser_refreshVelocityParameter','midiParser_setAccentParameter',
    'midiParser_applyPerformanceVelocity','midiParser_setDelayParameter','midiParser_needsOwnPch','midiParser_scaleCc','midiParser_menuCc','midiParser_extendedPerformanceCc',
    'midiParser_recalcGlobalPitch', 'midiParser_setGlobalPitch', 'midiParser_setPitchBendRange',
    'midiParser_setControlNotePitch', 'midiParser_applyVoicePitchBend',
    'midiParser_isValidChannel', 'midiParser_mapVoiceCc', 'midiParser_handleVoiceChannelCc', 'midiParser_cc2voiceNr',
    'midiParser_setFilter', 'midiParser_setRouting', 'midiParser_parseMidiMessage'))
# Compare every supported voice CC/value to Mutador's actual source mapper.
ref_map_source=(ROOT.parent/'mutador/mainboard/LxrStm32/src/MIDI/MidiParser.c').read_text()
ref_map=function('midiParser_mapVoiceCc',ref_map_source)
ref_map=ref_map.replace('midiParser_mapVoiceCc','reference_mapVoiceCc')
ref_map=ref_map.replace('midiParser_centerBipolarCc(out->data2)','(out->data2==64 ? 63 : out->data2)')
for suffix in ['LAYER_WAVE','LAYER_AMOUNT','LAYER_FREQ','LAYER_MODE','NOISE_ATTACK','NOISE_DECAY','NOISE_SLOPE']:
    ref_map=ref_map.replace('CC2_EXT_SNARE_'+suffix,'(PAR_SNARE_'+suffix+'-128)')
# Membrane is intentionally excluded by the user.
x=ref_map.index('case 111:'); y=ref_map.index('case 112:',x)
ref_map=ref_map[:x]+ref_map[y:]
functions+='\n'+ref_map
needle='    /* Distinct channels expose'
new=r"""    for(int voice=0;voice<7;voice++)for(int cc=0;cc<128;cc++)for(int value=0;value<128;value++){
        MidiMsg mapped=message(0,voice,MIDI_CC,cc,value), ref=mapped;
        int got=midiParser_mapVoiceCc(voice,cc,&mapped),want=reference_mapVoiceCc(voice,cc,&ref);
        check(got==want,"voice CC supported set matches Mutador",voice,cc,value);
        if(got)check(mapped.status==ref.status&&mapped.data1==ref.data1&&mapped.data2==ref.data2,
            "voice CC translation matches Mutador",voice,cc,value);
    }
    /* Distinct channels expose"""
assert needle in tests;tests=tests.replace(needle,new,1)
(OUT / 'midi_contract.c').write_text(prelude + '\n' + routing + '\n' + functions +
    '\nstatic const char *cc_names[128]={' + name_array + '};\n' + tests)
if os.name == 'nt':
    vsdev = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / (
        'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat')
    subprocess.run(f'call "{vsdev}" -arch=x64 >nul && cl /nologo /W3 /wd4305 /TC '
                   '/Fe:midi_contract.exe midi_contract.c && midi_contract.exe',
                   shell=True, cwd=OUT, check=True)
else:
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-o', 'midi_contract',
                    'midi_contract.c'], cwd=OUT, check=True)
    subprocess.run([str(OUT / 'midi_contract')], cwd=OUT, check=True)
print('Generated numeric map:', OUT / 'cc-map.csv')
