"""Timing contract for live sct against the production PerformanceScale.c."""

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"
SOURCE = r"""
#include <stdint.h>
#include <stdio.h>
#include "Soundengine/Sequencer/PerformanceScale.h"
static unsigned checks,failures;
static void check(int ok,const char *name,unsigned rate,unsigned mode)
{
 checks++;
 if(!ok){failures++;printf("FAIL %s rate=%u mode=%u\n",name,rate,mode);}
}
static const uint8_t rates[8]={2,4,6,8,12,16,24,32};
static void prepare(unsigned rate,unsigned mode)
{
 perf_scaleSetPattern((uint8_t)rate,0);perf_speedSet(PERF_SPEED_NEUTRAL,0);
 perf_transformSet((uint8_t)mode,0);perf_scaleSlotReset();
}
/* One group is the time of four quaternary or three ternary source steps. */
static void timing(unsigned rate,unsigned mode)
{
 prepare(rate,0);
 const unsigned ternary=perf_scaleIsTernary();
 const unsigned groupTicks=perf_scaleTicks()*(ternary?3u:4u);
 const unsigned groupClocks=perf_scaleMidiClocks()*(ternary?3u:4u);
 check(ternary==(rate%3u==0),"ternary rates",rate,mode);
 prepare(rate,mode);
 const unsigned slots=(mode&&ternary)?4u:(mode?3u:(ternary?3u:4u));
 check(perf_scaleTicks()*slots==groupTicks,"group keeps its ticks",rate,mode);
 check(perf_scaleMidiClocks()*slots==groupClocks,"group keeps its MIDI clocks",rate,mode);
 check(perf_scaleFrames()==perf_scaleTicks()*2u,"frames follow ticks",rate,mode);
 check(perf_scaleTicks()%4u==0,"MIDI clock falls on a tick",rate,mode);
 check(perf_scaleMidiClocks()*4u==perf_scaleTicks(),"step is a whole clock count",rate,mode);
}
/* Played order inside one group, 0 standing for an empty slot. */
static void playback(unsigned rate,unsigned mode,const char *expected)
{
 char text[5]={0};
 prepare(rate,mode);
 if(perf_scaleIsTernary()) {
  unsigned stored=0;
  for(unsigned slot=0;slot<4;slot++)
   text[slot]=perf_scaleSlotIsGap()?'-':(char)('1'+stored++);
  check(stored==3,"three stored steps per group",rate,mode);
 } else {
  unsigned used=0;
  for(unsigned step=0;step<4;step++)
   if(perf_scaleAllowed((uint8_t)step))text[used++]=(char)('1'+step);
  check(used==3,"three steps played",rate,mode);
 }
 for(unsigned i=0;expected[i];i++)check(text[i]==expected[i],expected,rate,mode);
}
/* Dropping a stored step and restoring its slot gives the source rhythm back. */
static void inverse(unsigned mode)
{
 static const uint8_t gapSlot[4]={0,2,1,3};
 prepare(16,mode);
 for(unsigned step=0;step<4;step++)
  check(perf_scaleAllowed((uint8_t)step)==(step!=gapSlot[mode]),"3x drops the 4x gap slot",16,mode);
 prepare(12,mode);
 for(unsigned slot=0;slot<4;slot++)
  check(perf_scaleSlotIsGap()==(slot==gapSlot[mode]),"4x leaves the 3x step empty",12,mode);
}
int main(void)
{
 for(unsigned r=0;r<8;r++)for(unsigned mode=0;mode<4;mode++) {
  timing(rates[r],mode);
  prepare(rates[r],mode);
  if(!perf_scaleIsTernary()&&mode)
   for(unsigned i=0;i<8;i++)check(!perf_scaleSlotIsGap(),"3x never gaps",rates[r],mode);
 }
 for(unsigned r=0;r<8;r++) {
  if(rates[r]%3u) {
   playback(rates[r],1,"124");playback(rates[r],2,"134");playback(rates[r],3,"123");
  } else {
   playback(rates[r],1,"12-3");playback(rates[r],2,"1-23");playback(rates[r],3,"123-");
  }
 }
 for(unsigned mode=1;mode<4;mode++)inverse(mode);
 prepare(12,1);
 check(!perf_scaleAllowed(12),"twelve keeps its page limit",12,1);
 prepare(16,1);
 check(perf_scaleCount(16)==12 && perf_scaleTicks()==32,"sixteen becomes real triplets",16,1);
 prepare(2,1);
 check(perf_scaleTicks()==256,"longest step fits",2,1);

 /* Group edges and pending behaviour. */
 static const uint16_t spans[8]={768,768,384,384,192,192,192,192};
 for(unsigned r=0;r<8;r++) {
  prepare(rates[r],0);
  perf_transformSet(1,1);
  for(unsigned frame=0;frame<768;frame+=48)
   check(perf_transformBoundary((uint16_t)frame)==(frame%spans[r]==0),"group edge",rates[r],1);
  check(perf_transformCommit(),"pending change commits",rates[r],1);
  check(!perf_transformBoundary(0),"nothing left pending",rates[r],1);
 }
 prepare(16,0);
 check(perf_scaleTicks()==24,"unchanged before commit",16,0);
 perf_transformSet(2,1);
 check(perf_scaleTicks()==24 && perf_scaleAllowed(1),"running change waits",16,2);
 perf_transformCommit();
 check(perf_scaleTicks()==32 && !perf_scaleAllowed(1),"change applies at the edge",16,2);
 perf_transformSet(2,1);
 check(!perf_transformCommit(),"same value is no change",16,2);
 prepare(16,1);
 perf_scaleSetPattern(12,0);
 check(perf_scaleIsTernary() && perf_scaleTicks()==24,"sct follows the active rate",12,1);
 prepare(16,0);
 perf_scaleSetPattern(12,0);
 check(perf_scaleIsTernary(),"scl override decides the kind",12,0);
 perf_scaleSetPattern(16,0);
 check(!perf_scaleIsTernary(),"pattern rate decides without override",16,0);
 /* spd scales the stored rate; the kind of pattern never changes. */
 static const uint16_t sixteen[6]={192,96,48,24,12,6},twelve[6]={256,128,64,32,16,8};
 for(unsigned i=0;i<6;i++) {
  perf_transformSet(0,0);perf_speedSet((uint8_t)i,0);
  perf_scaleSetPattern(16,0);check(perf_scaleTicks()==sixteen[i]&&!perf_scaleIsTernary(),"spd on sixteen",16,i);
  perf_scaleSetPattern(12,0);check(perf_scaleTicks()==twelve[i]&&perf_scaleIsTernary(),"spd on twelve",12,i);
  check(!perf_scaleAllowed(12),"spd keeps the slots of twelve",12,i);
 }
 perf_transformSet(0,0);
 perf_speedSet(5,0);perf_scaleSetPattern(32,0);check(perf_scaleTicks()==6,"thirty-two stops at six ticks",32,5);
 perf_scaleSetPattern(24,0);check(perf_scaleTicks()==8,"ternary stops at eight ticks",24,5);
 perf_speedSet(0,0);perf_scaleSetPattern(2,0);check(perf_scaleTicks()==1536,"slowest step fits",2,0);
 perf_transformSet(1,0);check(perf_scaleTicks()==2048&&perf_scaleFrames()==4096,"slowest sct step fits",2,0);
 perf_transformSet(0,0);perf_speedSet(PERF_SPEED_NEUTRAL,0);perf_scaleSetPattern(16,0);
 perf_speedSet(4,1);check(perf_scaleTicks()==24&&perf_scaleHasPending(),"running spd waits for the bar",16,4);
 check(perf_scaleCommit()&&perf_scaleTicks()==12,"spd commits",16,4);
 perf_speedSet(9,0);check(perf_scaleTicks()==24,"invalid spd is neutral",16,9);
 printf("%s %u assertions\n",failures?"SCT FAIL":"SCT PASS",checks);
 return failures!=0;
}
"""


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        out = Path(folder)
        (out / "contract.c").write_text(SOURCE, encoding="utf-8")
        scale = ROOT / "Core/Src/Soundengine/Sequencer/PerformanceScale.c"
        command = (f'call "{VS}" -arch=x64 >nul && cl /nologo /W3 /TC /I"{ROOT / "Core/Inc"}" '
                   f'/Fe:contract.exe contract.c "{scale}" && contract.exe')
        subprocess.run(command, shell=True, cwd=out, check=True)


if __name__ == "__main__":
    main()
