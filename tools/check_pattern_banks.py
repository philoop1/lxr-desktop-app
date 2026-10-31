"""Exercise production pattern-bank LED code across every bank and pattern."""
from pathlib import Path
import os, re, subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/pattern-bank-audit'
OUT.mkdir(parents=True, exist_ok=True)

def function(src, name):
    match = re.search(r'[^\n]*\b' + name + r'\([^{};]*\)\s*\{', src)
    assert match, name
    pos, depth = match.end(), 1
    while depth:
        depth += (src[pos] == '{') - (src[pos] == '}')
        pos += 1
    return src[match.start():pos]

src = (ROOT / 'Core/Src/ledHandler.c').read_text()
header = (ROOT / 'Core/Inc/ledHandler.h').read_text()
code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define NUM_OF_BLINKABLE_LEDS 4
uint8_t dout_outputData[5],led_originalLedState[5];
uint8_t led_blinkLedNumber[4],led_blinkingLeds;
uint8_t menu_playedPattern,menu_activePatternBank,viewed,loopOn,lo,hi;
struct { uint32_t ODR; } gpio;
#define LED_43_GPIO_Port (&gpio)
#define LED_43_Pin 1u
uint8_t menu_getViewedPattern(void){return viewed;}
uint8_t perf_getLoop(uint8_t *a,uint8_t *b){*a=lo;*b=hi;return loopOn;}
'''
code += re.search(r'enum LedNumbers\s*\{.*?\};', header, re.S)[0] + '\n'
for name in ['led_setValue', 'led_reset', 'led_toggleTemp', 'led_idx2StepLed',
             'led_clearAllBlinkLeds', 'led_setBlinkLed', 'led_clearSequencerLeds',
             'led_initPatternSelectLeds']:
    code += function(src, name) + '\n'
code += r'''
int main(void){
 unsigned calls=0;
 for(unsigned loop=0;loop<2;loop++)for(unsigned played=0;played<64;played++)
 for(unsigned shown=0;shown<64;shown++)for(unsigned bank=0;bank<4;bank++){
  memset(dout_outputData,0,sizeof(dout_outputData));
  memset(led_originalLedState,0,sizeof(led_originalLedState));
  memset(led_blinkLedNumber,0,sizeof(led_blinkLedNumber));led_blinkingLeds=0;
  loopOn=loop;lo=5;hi=52;menu_playedPattern=played;viewed=shown;
  menu_activePatternBank=bank;
  for(unsigned repeat=0;repeat<8;repeat++){
   led_initPatternSelectLeds();calls++;
   for(unsigned slot=0;slot<4;slot++)
    if(led_blinkLedNumber[slot]>=40){puts("Invalid blink LED");return 1;}
  }
 }
 printf("PATTERN BANK PASS: %u production LED refreshes\n",calls);
 return 0;
}
'''
(OUT / 'contract.c').write_text(code)
if os.name == 'nt':
    vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /Od /RTC1 /W3 /TC /Fe:contract.exe contract.c && contract.exe', shell=True, cwd=OUT, check=True)
else:
    subprocess.run(['cc', '-fsanitize=address,undefined', '-o', 'contract', 'contract.c'], cwd=OUT, check=True)
    subprocess.run([str(OUT / 'contract')], cwd=OUT, check=True)
