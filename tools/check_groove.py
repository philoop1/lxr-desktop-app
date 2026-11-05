"""Compare the new rational-grid groove core with actual Mutador source."""
from pathlib import Path
import os
import subprocess

root=Path(__file__).resolve().parents[1]
out=root/'build/groove-audit'
out.mkdir(parents=True,exist_ok=True)
reference=(root.parent/'mutador/mainboard/LxrStm32/src/Sequencer/sequencer.c').read_text()
def extract(name,code=reference):
    import re
    match=re.search(r'(?:static )?(?:int8_t|void) '+name+r'\([^;]*?\)\s*\{',code)
    start=match.start()
    brace=code.index('{',match.start())
    depth=0
    for end in range(brace,len(code)):
        depth+=(code[end]=='{')-(code[end]=='}')
        if depth==0:return code[start:end+1]

import re
trigger=re.sub(r'/\*.*?\*/|//[^\n]*','',(root/'Core/Src/Soundengine/TriggerOut.c').read_text(),flags=re.S)
clock=r'''
enum { PRE_2_PPQ_OUT,PRE_4_PPQ_OUT,PRE_8_PPQ_OUT,PRE_16_PPQ_OUT,PRE_24_PPQ_OUT,PRE_48_PPQ_OUT,PRE_16SH_OUT };
#define CLOCK_1 0
static uint8_t trigger_nextPulseOut1,trigger_dividerClockOut1,trigger_grooveClock,pinState;
static unsigned pinWrites;
void trigger_setPin(uint8_t index,uint8_t on){(void)index;pinState=on;pinWrites++;}
'''
clock+='\n'.join(extract(n,trigger) for n in ('trigger_setGrooveClock','trigger_clockGrooveTick','trigger_clockTick'))

program='''#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "Soundengine/Sequencer/PerformanceGroove.h"
#define GROOVE_FINE_MAX_OFFSET 12
static uint8_t seq_shuffleAmount;
static int8_t seq_grooveShape[3],seq_grooveOffset[4];
'''+extract('seq_centerGrooveValue')+'\n'+extract('seq_recalcGrooveOffsets')+clock+'''
int main(void) {
  PerfGroove g;
  unsigned checks=0;
  for(unsigned amount=0;amount<128;amount++)
    for(unsigned shape=0;shape<128;shape++) {
      seq_shuffleAmount=(uint8_t)amount;
      for(unsigned lane=0;lane<3;lane++) seq_grooveShape[lane]=seq_centerGrooveValue((uint8_t)shape);
      seq_recalcGrooveOffsets();
      perf_grooveConfigure(&g,(uint8_t)amount,(uint8_t)shape,(uint8_t)shape,(uint8_t)shape);
      for(unsigned lane=0;lane<4;lane++) {
        if(g.offset[lane]!=seq_grooveOffset[lane]*3) return 1;
        if(perf_grooveEvent(&g,0,(uint8_t)lane)!=g.offset[lane]) return 2;
        checks+=2;
      }
      uint8_t lane=0;
      int32_t sum=0;
      for(unsigned i=0;i<4;i++) sum+=(int32_t)perf_grooveRepeat(&g,96,&lane);
      if(sum!=768) return 3;
      checks++;
    }
  const uint8_t shapes[4][3]={{0,127,0},{127,0,127},{68,58,64},{63,63,63}};
  for(unsigned configuration=0;configuration<4;configuration++) {
    seq_shuffleAmount=127;
    for(unsigned lane=0;lane<3;lane++) seq_grooveShape[lane]=seq_centerGrooveValue(shapes[configuration][lane]);
    seq_recalcGrooveOffsets();
    perf_grooveConfigure(&g,127,shapes[configuration][0],shapes[configuration][1],shapes[configuration][2]);
    for(unsigned lane=0;lane<4;lane++) for(unsigned period=1;period<=128;period++) {
      uint8_t target=(uint8_t)lane;
      int fine=(int)period*2;
      if(period>=8) {
        target=(uint8_t)((lane+(period+4)/8)&3);
        fine+=seq_grooveOffset[target]-seq_grooveOffset[lane];
      }
      if(fine<1)fine=1;
      uint8_t actualLane=(uint8_t)lane;
      if(perf_grooveRepeat(&g,(uint16_t)(period*3),&actualLane)!=(unsigned)(fine*3)||actualLane!=target) return 4;
      checks++;
    }
    for(unsigned lane=0;lane<4;lane++) for(int shift=-7;shift<=7;shift++)
      for(unsigned pulse=0;pulse<24;pulse++) for(int neighbor=-2;neighbor<=2;neighbor++)
        for(unsigned frame=0;frame<48;frame++) {
          int expected=neighbor*48+(int)pulse*2+shift*6+seq_grooveOffset[lane]*3;
          if(perf_grooveDue(&g,1u<<(23-pulse),(int8_t)shift,(uint8_t)lane,
                             (int8_t)neighbor,(uint8_t)frame,0)!=(frame==(unsigned)expected)) return 5;
          checks++;
        }
  }
  {
    /* 0.2.55 humanize: per-hit offset, even, within +-12 frames, fixed per eventId */
    PerfGroove h;memset(&h,0,sizeof(h));
    if(perf_grooveActive(&h)) return 20;
    h.human[2]=127;
    if(!perf_grooveActive(&h)) return 21;
    if(perf_grooveHuman(&h,0,77)||perf_grooveHuman(&h,1,77)||perf_grooveHuman(&h,2,0)) return 22;
    unsigned seen[13]={0};
    for(uint32_t id=1;id<=4000;id++) {
      int16_t v=perf_grooveHuman(&h,2,id);
      if(v<-HUMANIZE_MAX_FRAMES||v>HUMANIZE_MAX_FRAMES||(v&1)) return 23;
      if(v!=perf_grooveHuman(&h,6,id)) return 24; /* lane&3, same id -> same roll */
      seen[(v+12)/2]++;checks++;
    }
    for(unsigned i=0;i<13;i++) if(seen[i]<200) return 25; /* every offset occurs */
    unsigned differ=0;for(uint32_t id=1;id<=100;id++) differ+=perf_grooveHuman(&h,2,id)!=perf_grooveHuman(&h,2,id+1);
    if(differ<70) return 26; /* neighbouring hits (other voices) roll their own */
    h.human[2]=10;for(uint32_t id=1;id<=500;id++){int16_t v=perf_grooveHuman(&h,2,id);if(v<-0||v>0){if(v<-2||v>2)return 27;}}
    h.human[2]=127;
    for(unsigned frame=0;frame<48;frame++) {
      const uint8_t due=perf_grooveDue(&h,1u<<23,0,2,0,(uint8_t)frame,8);
      if(due!=(frame==8u)) return 28;
      const uint8_t early=perf_grooveDue(&h,1u<<23,0,2,1,(uint8_t)frame,-8);
      if(early!=(frame==40u)) return 29;
      checks+=2;
    }
  }
  for(unsigned divider=0;divider<=6;divider++) {
    trigger_dividerClockOut1=(uint8_t)divider;
    trigger_nextPulseOut1=0;trigger_setGrooveClock(0);pinWrites=0;
    for(unsigned frame=0;frame<96;frame++) trigger_clockTick(0,(uint8_t)(frame%24));
    if(pinWrites!=96) return 6;
    trigger_setGrooveClock(1);pinWrites=0;
    trigger_clockTick(0,0);
    if((divider==6&&pinWrites)||(divider!=6&&pinWrites!=1))return 7;
    pinWrites=0;trigger_clockGrooveTick(1,0);
    if(divider==6&&(pinState||pinWrites!=1))return 8;
    if(divider!=6&&pinWrites)return 9;
    pinWrites=0;trigger_clockGrooveTick(0,1);
    if(divider==6&&(!pinState||pinWrites!=1))return 10;
    if(divider!=6&&pinWrites)return 11;
    checks+=4;
  }
  perf_grooveConfigure(&g,127,127,63,127);
  for(unsigned shuffled=0;shuffled<2;shuffled++) {
    trigger_dividerClockOut1=shuffled?PRE_16SH_OUT:PRE_4_PPQ_OUT;
    trigger_setGrooveClock(1);trigger_nextPulseOut1=0;pinState=0;
    unsigned edges=0;uint8_t previous=0;
    const unsigned straight[4]={0,48,96,144},swing[4]={0,84,96,180};
    for(unsigned frame=0;frame<192;frame++) {
      if(!(frame&1))trigger_clockTick(0,(uint8_t)((frame/2)%24));
      uint8_t on4=0;
      for(int n=-1;n<=1;n++) {
        uint8_t lane=(uint8_t)(((int)(frame/48)+n+4)%4);
        on4|=perf_groovePulse(&g,lane,(int8_t)n,(uint8_t)(frame%48));
      }
      trigger_clockGrooveTick(0,on4);
      if(pinState&&!previous) {
        if(edges>=4||frame!=(shuffled?swing[edges]:straight[edges]))return 12;
        edges++;checks++;
      }
      previous=pinState;
    }
    if(edges!=4)return 13;
    checks++;
  }
  printf("GROOVE PASS: %u assertions against original Mutador functions and real clock output code\\n",checks);
  return 0;
}
'''
(out/'groove.c').write_text(program)
source=root/'Core/Src/Soundengine/Sequencer/PerformanceGroove.c'
include=root/'Core/Inc'
if os.name=='nt':
    vsdev=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vsdev}" -arch=x64 >nul && cl /nologo /W3 /TC /I"{include}" /Fe:groove.exe groove.c "{source}" && groove.exe',shell=True,cwd=out,check=True)
else:
    subprocess.run(['cc','-std=c11','-I'+str(include),'groove.c',str(source),'-o','groove'],cwd=out,check=True)
    subprocess.run([str(out/'groove')],cwd=out,check=True)
