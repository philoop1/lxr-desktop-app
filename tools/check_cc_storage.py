"""Regression for production CC bookkeeping used by immediate kit loading.

Hardware switch bodies are replaced by no-ops; surrounding production index,
storage and modulation notification code is retained verbatim. An enlarged
sentinel buffer catches the original CC0 write at offset 65536 safely.
"""
from pathlib import Path
import os, re, subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/cc-storage-audit';OUT.mkdir(parents=True,exist_ok=True)
src=(ROOT/'Core/Src/Soundengine/MIDI/MidiParser.c').read_text()
start=src.index('void midiParser_ccHandler(')
brace=src.index('{',start);pos=brace+1;depth=1
while depth:
    depth+=(src[pos]=='{')-(src[pos]=='}');pos+=1
body=src[start:pos]
while 'switch(msg.data1)' in body:
    begin=body.index('switch(msg.data1)');brace=body.index('{',begin)
    pos=brace+1;depth=1
    while depth:
        depth+=(body[pos]=='{')-(body[pos]=='}');pos+=1
    body=body[:begin]+body[pos:]
code=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MIDI_CC 0xb0
typedef struct {uint8_t status,data1,data2;} MidiMsg;
uint8_t midiParser_originalCcValues[65537];
unsigned notified,refreshes,checks;
void modNode_originalValueChanged(uint16_t p){notified=p;}
void midiParser_refreshVelocityParameter(uint16_t p){(void)p;refreshes++;}
void check(int ok,const char *msg){checks++;if(!ok){puts(msg);exit(1);}}
'''+body+r'''
int main(void){
 for(unsigned bank=0;bank<2;bank++)for(unsigned cc=0;cc<128;cc++)
 for(unsigned value=0;value<128;value++){
  memset(midiParser_originalCcValues,0xa5,sizeof(midiParser_originalCcValues));
  notified=999;refreshes=0;
  MidiMsg m={(uint8_t)(bank?0xc0:MIDI_CC),(uint8_t)cc,(uint8_t)value};
  midiParser_ccHandler(m,1,0,0);
  unsigned stored=bank?128+cc:cc;
  unsigned parameter=bank?128+cc:(cc+127)%128;
  check(midiParser_originalCcValues[stored]==value,"CC base value stored at correct index");
  check(midiParser_originalCcValues[65536]==0xa5,"CC0 must not write 64 KiB beyond cache");
  check(notified==parameter,"modulation notified with wrapped legacy parameter ID");
  for(unsigned i=0;i<256;i++)if(i!=stored)
   check(midiParser_originalCcValues[i]==0xa5,"unrelated CC base values preserved");
  midiParser_originalCcValues[stored]=0xa5;
  midiParser_ccHandler(m,0,0,0);
  check(midiParser_originalCcValues[stored]==0xa5,"modulation does not overwrite original");
 }
 printf("CC STORAGE PASS %u assertions\n",checks);return 0;
}
'''
(OUT/'contract.c').write_text(code)
if os.name=='nt':
    vs=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /Fe:contract.exe contract.c && contract.exe',shell=True,cwd=OUT,check=True)
else:
    subprocess.run(['cc','-o','contract','contract.c'],cwd=OUT,check=True)
    subprocess.run([str(OUT/'contract')],cwd=OUT,check=True)
