"""The morph sweep and the MIDI CC morph slew, compiled from presetManager.c.

A dense CC stream must still reach every parameter with the final morph
value, and a CC target must glide in 26 ms half steps.
--mutate restarts the sweep on every morph change again; the check must then
fail.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"


def function(code, name):
    match = re.search(r'^\w[^\n;]*\b' + name + r'\s*\([^)]*\)\s*\{', code, re.M)
    assert match, name
    pos, depth = match.end(), 1
    while depth:
        depth += (code[pos] == '{') - (code[pos] == '}')
        pos += 1
    return code[match.start():pos]


PRELUDE = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "Parameters.h"
#define MIDI_CC 0xB0
#define CC_2 0xd6
typedef struct {uint8_t status,lastNonSysStatus,data1,data2;} MidiMsg;
uint8_t activeParameters[NUM_PARAMS];
uint8_t parameterOrder[END_OF_SOUND_PARAMETERS];
uint32_t systick_ticks;
static uint8_t morph_state,morph_index,morph_again,morph_slewTarget,morph_slewActive;
static uint32_t morph_slewLast;
#define MORPH_SLEW_TICKS 104u
static int sent[NUM_PARAMS];
static unsigned sends;
uint8_t preset_getMorphValue(uint16_t p,uint8_t morph){(void)p;return morph;}
void midiParser_ccHandler(MidiMsg m,int a,int b,float c)
{
 (void)a;(void)b;(void)c;
 const uint16_t p=(m.status==MIDI_CC)?(uint16_t)(m.data1-1):(uint16_t)(m.data1+128);
 sent[p]=m.data2;sends++;
}
void preset_morph(uint8_t morph);
"""

TESTS = r"""
static unsigned checks,failures;
static void check(int ok,const char *name){checks++;if(!ok){failures++;printf("FAIL %s\n",name);}}
static int isSent(uint16_t p)
{
 return p!=PAR_NONE&&p!=PAR_BANK_CHANGE&&p!=PAR_MORPH_KIT_DEST&&
  !(p>=PAR_VEL_DEST_1&&p<=PAR_VEL_DEST_6)&&!(p>=PAR_VOICE_LFO1&&p<=PAR_VOICE_LFO6)&&
  !(p>=PAR_TARGET_LFO1&&p<=PAR_TARGET_LFO6)&&!(p>=PAR_AUDIO_OUT1&&p<=PAR_AUDIO_OUT6);
}
int main(void)
{
 for(unsigned i=0;i<END_OF_SOUND_PARAMETERS;i++)parameterOrder[i]=(uint8_t)i;
 /* A CC every 10 ms (40 ticks) with one sweep step per audio block (3 ticks):
    the old restart reached only the first parameters until the stream stopped. */
 for(unsigned i=0;i<NUM_PARAMS;i++)sent[i]=-1;
 uint8_t value=0;
 for(unsigned t=0;t<4000;t++) {
  systick_ticks=t;
  if(t%40==0){value=(uint8_t)(t*7/40);activeParameters[PAR_MORPH]=value;preset_morph(value);}
  if(t%3==0)preset_morph_tick();
 }
 int reached=1;
 for(uint16_t p=0;p<END_OF_SOUND_PARAMETERS;p++) if(isSent(p)) reached&=sent[p]>=0;
 check(reached,"a dense morph stream reaches every parameter");
 for(unsigned t=4000;t<6000;t++){systick_ticks=t;if(t%3==0)preset_morph_tick();}
 int final=1;
 for(uint16_t p=0;p<END_OF_SOUND_PARAMETERS;p++) if(isSent(p)) final&=sent[p]==value;
 check(final&&!morph_state,"after the stream every parameter has the last morph value");

 /* The CC target glides in half steps every 26 ms. */
 activeParameters[PAR_MORPH]=0;morph_slewLast=systick_ticks=10000;
 preset_setMorphTarget(255);
 uint8_t path[12];unsigned n=0;
 for(unsigned t=10000;t<10000+104*12;t++){
  systick_ticks=t;preset_morph_tick();
  if(t>10000&&(t-10000)%104==0&&n<12)path[n++]=activeParameters[PAR_MORPH];
 }
 check(path[0]==128&&path[1]==192&&path[2]==224,"half steps toward the target");
 check(activeParameters[PAR_MORPH]==255&&!morph_slewActive,"slew arrives and stops");
 /* Faster than 26 ms nothing moves. */
 preset_setMorphTarget(0);systick_ticks=morph_slewLast+50;preset_morph_tick();
 check(activeParameters[PAR_MORPH]==255,"no step before 26 ms");
 systick_ticks=morph_slewLast+104;preset_morph_tick();
 check(activeParameters[PAR_MORPH]==127,"next step after 26 ms");
 /* A new target while gliding takes over from the current value. */
 preset_setMorphTarget(127);systick_ticks+=104;preset_morph_tick();
 check(activeParameters[PAR_MORPH]==127&&!morph_slewActive,"target reached ends the slew");
 printf("%s %u assertions\n",failures?"MORPH FAIL":"MORPH PASS",checks);
 return failures!=0;
}
"""


def main() -> None:
    code = (ROOT / 'Core/Src/Preset/presetManager.c').read_text(encoding='latin1')
    code = re.sub(r'/\*.*?\*/|//[^\n]*', '', code, flags=re.S)
    body = '\n'.join(function(code, n) for n in
                     ('preset_setMorphTarget', 'preset_morphSlew', 'preset_morph_tick', 'preset_morph'))
    if '--mutate' in sys.argv:
        old = 'if(morph_state)\n\t{\n\t\tmorph_again = 1;\n\t\treturn;\n\t}'
        assert old in body, 'mutation anchor'
        body = body.replace(old, '')
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        out = Path(folder)
        (out / 'stm32f7xx_hal.h').write_text('#include <stdint.h>\n', encoding='utf-8')
        (out / 'morph.c').write_text(PRELUDE + body + TESTS, encoding='utf-8')
        command = (f'call "{VS}" -arch=x64 >nul && cl /nologo /O2 /W1 /TC /I. /I"{ROOT / "Core/Inc"}" '
                   f'/Fe:morph.exe morph.c && .\\morph.exe')
        subprocess.run(command, shell=True, cwd=out, check=True)


if __name__ == '__main__':
    main()
