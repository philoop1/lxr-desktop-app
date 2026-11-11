"""0.2.71 master compressor: production Compressor.c on the host.

Bypass is bit exact, on/off and mix fade without jumps, loud input is reduced
by the ratio, quiet input below the threshold passes, and the gain stays finite.
"""
from pathlib import Path
import os, subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/master-comp-audit'
OUT.mkdir(parents=True, exist_ok=True)
src = (ROOT / 'Core/Src/Soundengine/DSPAudio/FX/Compressor.c').read_text(encoding='latin-1')
src = src.replace('#include "Soundengine/DSPAudio/FX/Compressor.h"', '#include "Compressor.h"')
src = src.replace('__attribute__((noinline)) ', '')
src = src.replace('int16_t left[size];', 'int16_t left[256];').replace('int16_t right[size];', 'int16_t right[256];')  # MSVC has no VLA
(OUT / 'Compressor.c').write_text(src, encoding='latin-1')
hdr = (ROOT / 'Core/Inc/Soundengine/DSPAudio/FX/Compressor.h').read_text(encoding='latin-1')
hdr = hdr.replace('#include "Soundengine/globals.h"', '').replace('#include "Soundengine/config.h"', '#include "config.h"')
(OUT / 'Compressor.h').write_text(hdr, encoding='latin-1')
(OUT / 'config.h').write_text('#include <stdint.h>\n#define REAL_FS (float)44140.f\n')
(OUT / 'main.h').write_text(
    '#include <stdint.h>\n'
    'static inline int32_t __SSAT(int32_t v,int b){(void)b;return v>32767?32767:(v<-32768?-32768:v);}\n'
    'static inline int32_t __QADD16(int32_t a,int32_t b){return a+b;}\n'
    'static inline int32_t __PKHBT(int32_t a,int32_t b,int s){return (a&0xffff)|(b<<s);}\n')
(OUT / 'contract.c').write_text(r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "Compressor.h"
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
#define N 32
static int16_t buf[2*N];
static void fill(int16_t v){for(int i=0;i<N;i++){buf[2*i]=v;buf[2*i+1]=(int16_t)-v;}}
static void run(int16_t v,int blocks){for(int b=0;b<blocks;b++){fill(v);masterComp_process(buf,N);}}
static void settings(uint8_t on,uint8_t ratio,uint8_t att,uint8_t rel,uint8_t thr,uint8_t gain,uint8_t mix){
 const uint8_t v[7]={on,ratio,att,rel,thr,gain,mix};for(uint8_t i=0;i<7;i++)masterComp_set(i,v[i]);}
int main(void){
 /* before init and while off: untouched */
 fill(12345);masterComp_process(buf,N);check(buf[0]==12345&&buf[1]==-12345,"no init passes");
 settings(0,3,10,40,90,0,100);run(20000,20);check(buf[0]==20000&&buf[1]==-20000,"off is bit exact");
 /* on, 4:1: loud signal is reduced, both channels alike */
 settings(1,3,0,40,90,0,100);run(20000,400);
 check(buf[2*N-2]<20000&&buf[2*N-2]>1000&&buf[2*N-1]==-buf[2*N-2],"loud signal reduced, stereo linked");
 const int16_t c4=buf[2*N-2];
 /* 8:1 squeezes harder than 4:1 */
 masterComp_set(1,5);run(20000,400);check(buf[2*N-2]<c4,"8:1 below 4:1");
 /* 1:1 does nothing */
 masterComp_set(1,0);run(20000,400);check(abs(buf[2*N-2]-20000)<=1,"1:1 is neutral");
 /* below the threshold nothing happens */
 masterComp_set(1,3);masterComp_set(4,127);run(300,3000);check(abs(buf[2*N-2]-300)<=1,"below threshold passes");
 /* mix 0 equals dry, mix 50 lies between */
 masterComp_set(4,90);masterComp_set(6,0);run(20000,400);check(abs(buf[2*N-2]-20000)<=1,"mix 0 is dry");
 masterComp_set(6,50);run(20000,400);const int16_t half=buf[2*N-2];
 masterComp_set(6,100);run(20000,400);check(half>buf[2*N-2]&&half<20000,"mix 50 between dry and wet");
 /* switching off fades: no jump larger than one fade step from the compressed level */
 run(20000,50);const int16_t before=buf[2*N-2];masterComp_set(0,0);fill(20000);masterComp_process(buf,N);
 check(abs(buf[0]-before)<400,"off fades in, no click");
 run(20000,40);check(buf[2*N-2]==20000,"after the fade off is exact again");
 /* make-up gain saturates instead of wrapping */
 settings(1,3,0,40,127,127,100);run(30000,100);check(buf[2*N-2]>0&&buf[2*N-2]<=32767,"saturates, no wrap");
 /* silence: finite gain, no NaN */
 run(0,100);check(buf[0]==0,"silence stays silent");run(20000,10);check(buf[2*N-2]>0,"recovers after silence");
 printf("MASTER COMP PASS %u assertions\n",checks);return 0;}
''')
if os.name == 'nt':
    vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /I. /Fe:contract.exe contract.c Compressor.c && contract.exe',
                   shell=True, cwd=OUT, check=True)
else:
    subprocess.run(['cc', '-I.', '-o', 'contract', 'contract.c', 'Compressor.c', '-lm'], cwd=OUT, check=True)
    subprocess.run([str(OUT / 'contract')], cwd=OUT, check=True)
