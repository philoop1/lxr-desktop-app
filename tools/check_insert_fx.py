"""0.2.79 per-voice inserts: the production InsertFx.c and Phaser.c on the host.
Every type on every voice: silence stays silence, loud noise stays finite and
inside int16, switching the type clears the state, the compressor lowers loud
input more than quiet input, the voices do not share state."""
from pathlib import Path
import os, subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/insert-fx-audit'
OUT.mkdir(parents=True, exist_ok=True)
code = r'''
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Soundengine/DSPAudio/FX/InsertFx.h"
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
static uint32_t rng=7;static int16_t noise(void){rng=rng*1664525u+1013904223u;return (int16_t)(rng>>16);}
#define N 32
static double rms(int16_t*b){double e=0;for(int i=0;i<N;i++)e+=(double)b[i]*b[i];return sqrt(e/N);}
int main(void){
  InsertFx_init();
  for(int t=0;t<INSERT_FX_COUNT;t++)for(int v=0;v<INSERT_FX_VOICES;v++){
    int16_t b[N];
    for(int k=0;k<300;k++){memset(b,0,sizeof b);InsertFx_process((uint8_t)v,(uint8_t)t,b,N);
      for(int i=0;i<N;i++)check(b[i]==0 || t==INSERT_FX_COMP,"silence stays silence");}
    for(int k=0;k<5000;k++){for(int i=0;i<N;i++)b[i]=noise();InsertFx_process((uint8_t)v,(uint8_t)t,b,N);
      check(rms(b)==rms(b),"finite");}
  }
  /* compressor at silence: makeup on zero is still zero */
  {int16_t b[N]={0};InsertFx_process(0,INSERT_FX_COMP,b,N);for(int i=0;i<N;i++)check(b[i]==0,"comp silence");}
  /* compressor: 4:1 above threshold, so +6 dB in (both above) gives about +1.5 dB out */
  {double q=0,l=0;
   for(int k=0;k<4000;k++){int16_t b[N];for(int i=0;i<N;i++)b[i]=(int16_t)(12000*sin((k*N+i)*0.05));InsertFx_process(1,INSERT_FX_COMP,b,N);if(k>3000)q+=rms(b);}
   for(int k=0;k<4000;k++){int16_t b[N];for(int i=0;i<N;i++)b[i]=(int16_t)(24000*sin((k*N+i)*0.05));InsertFx_process(1,INSERT_FX_COMP,b,N);if(k>3000)l+=rms(b);}
   check(l/q<1.4,"compressor reduces the level step");check(l>q,"louder stays louder");}
  /* state per voice: voice 2 with a burst does not change voice 3 */
  {InsertFx_init();int16_t a[N],b[N];
   for(int k=0;k<100;k++){for(int i=0;i<N;i++)a[i]=noise();InsertFx_process(2,INSERT_FX_PHASER,a,N);}
   memset(b,0,sizeof b);InsertFx_process(3,INSERT_FX_PHASER,b,N);for(int i=0;i<N;i++)check(b[i]==0,"voices keep their own state");}
  /* switching the type clears the old state: phaser ring-out does not leak */
  {InsertFx_init();int16_t b[N];
   for(int k=0;k<100;k++){for(int i=0;i<N;i++)b[i]=noise();InsertFx_process(4,INSERT_FX_PHASER,b,N);}
   memset(b,0,sizeof b);InsertFx_process(4,INSERT_FX_DIST,b,N);
   memset(b,0,sizeof b);InsertFx_process(4,INSERT_FX_PHASER,b,N);for(int i=0;i<N;i++)check(b[i]==0,"type change clears state");}
  /* 0.2.83 dst: a -12 dBFS sine leaves about as loud as it came in, at every drive and type,
   * tone open; bias adds no DC; out trims the level; drive 0 soft is nearly clean */
  for(int type=0;type<3;type++)for(int drv=0;drv<128;drv+=21){
   InsertFx_init();InsertFx_setValue(INS_DST_TYPE,(uint8_t)type);InsertFx_setValue(INS_DST_DRIVE,(uint8_t)drv);InsertFx_setValue(INS_DST_TONE,127);
   double e=0,ein=0;for(int k=0;k<400;k++){int16_t b[N];for(int i=0;i<N;i++)b[i]=(int16_t)(8192*sin((k*N+i)*0.01));
     if(k>200)for(int i=0;i<N;i++)ein+=(double)b[i]*b[i];InsertFx_process(5,INSERT_FX_DIST,b,N);if(k>200)for(int i=0;i<N;i++)e+=(double)b[i]*b[i];}
   double db=10*log10(e/ein);check(db>-4.5&&db<3.5,"dst level matched at -12 dBFS");}
  {InsertFx_init();InsertFx_setValue(INS_DST_DRIVE,0);InsertFx_setValue(INS_DST_TONE,127);
   double e=0,ein=0;for(int k=0;k<400;k++){int16_t b[N];for(int i=0;i<N;i++)b[i]=(int16_t)(2000*sin((k*N+i)*0.01));
     if(k>200)for(int i=0;i<N;i++)ein+=(double)b[i]*b[i];InsertFx_process(5,INSERT_FX_DIST,b,N);if(k>200)for(int i=0;i<N;i++)e+=(double)b[i]*b[i];}
   double db=10*log10(e/ein);check(db>-1.&&db<3.,"drive 0 quiet signal close to unity (no +6 dB)");}
  for(int bias=0;bias<128;bias+=127){InsertFx_init();InsertFx_setValue(INS_DST_BIAS,(uint8_t)bias);double dc=0;
   for(int k=0;k<2000;k++){int16_t b[N];for(int i=0;i<N;i++)b[i]=0;InsertFx_process(5,INSERT_FX_DIST,b,N);if(k>1000)for(int i=0;i<N;i++)dc+=b[i];}
   check(fabs(dc/(1000.0*N))<2,"bias adds no DC on silence");}
  {double lv[2];for(int o=0;o<2;o++){InsertFx_init();InsertFx_setValue(INS_DST_OUT,(uint8_t)(o?127:63));double e=0;
     for(int k=0;k<300;k++){int16_t b[N];for(int i=0;i<N;i++)b[i]=(int16_t)(4000*sin((k*N+i)*0.01));InsertFx_process(5,INSERT_FX_DIST,b,N);if(k>200)for(int i=0;i<N;i++)e+=(double)b[i]*b[i];}lv[o]=e;}
   double db=10*log10(lv[1]/lv[0]);check(db>11.&&db<12.5,"out +12 dB");}
  /* fold folds: a full scale sine at high drive crosses zero more often than the input */
  {InsertFx_init();InsertFx_setValue(INS_DST_TYPE,2);InsertFx_setValue(INS_DST_DRIVE,127);InsertFx_setValue(INS_DST_TONE,127);
   int zc=0,zin=0;int16_t lastIn=0,lastOut=0;for(int k=0;k<400;k++){int16_t b[N],c[N];for(int i=0;i<N;i++)c[i]=b[i]=(int16_t)(30000*sin((k*N+i)*0.01));
     InsertFx_process(5,INSERT_FX_DIST,b,N);if(k>100)for(int i=0;i<N;i++){if((c[i]<0)!=(lastIn<0))zin++;if((b[i]<0)!=(lastOut<0))zc++;lastIn=c[i];lastOut=b[i];}}
   check(zc>zin*4,"fold folds");}
  /* 0.2.81 stored values: clamping, defaults = the 0.2.79 measurement settings */
  {InsertFx_init();uint8_t d[INS_VALUE_COUNT];InsertFx_defaultValues(d);
   for(int i=0;i<INS_VALUE_COUNT;i++)check(d[i]<=(i==INS_CMP_RATIO?INS_CMP_RATIO_STEPS-1:i==INS_PH2_STAGES?INS_PH2_STAGE_STEPS-1:i==INS_DST_TYPE?INS_DST_TYPE_STEPS-1:127),"default in range");
   for(int i=0;i<INS_VALUE_COUNT;i++)for(int v=0;v<256;v++){uint8_t r=InsertFx_setValue((uint8_t)i,(uint8_t)v);
     int mx=i==INS_CMP_RATIO?INS_CMP_RATIO_STEPS-1:i==INS_PH2_STAGES?INS_PH2_STAGE_STEPS-1:i==INS_DST_TYPE?INS_DST_TYPE_STEPS-1:127;check(r==(v>mx?mx:v),"setValue clamps");
     const InsertFxParams*p=&insertFx_params;
     check(p->compRatio>=1.f&&p->compRatio<=8.f,"ratio 1..8");check(p->compThreshold>0.f&&p->compThreshold<=1.0001f,"threshold");
     check(p->compAttack>0.f&&p->compAttack<1.f&&p->compRelease>0.f&&p->compRelease<1.f,"comp coefficients");
     check(p->ringFreq>=19.9f&&p->ringFreq<=5200.f,"ring freq");for(int t=0;t<INSERT_FX_COUNT;t++)check(p->mix[t]>=0.f&&p->mix[t]<=1.f,"mix");}
   for(int i=0;i<INS_VALUE_COUNT;i++)InsertFx_setValue((uint8_t)i,d[i]);
   const InsertFxParams*p=&insertFx_params;
   check(fabs(p->ringFreq-440.f)<15.f,"default ring 440 Hz");check(p->compRatio==4.f,"default 4:1");
   check(fabs(20*log10(p->compThreshold)+12.)<0.6,"default -12 dB");check(fabs(20*log10(p->compMakeup)-6.)<0.2,"default +6 dB");
   check(p->mix[INSERT_FX_DIST]==1.f&&p->mix[INSERT_FX_COMP]==1.f,"default mix full");
   /* every value is audible-safe: random settings on noise stay finite */
   for(int k=0;k<3000;k++){InsertFx_setValue((uint8_t)(k%INS_VALUE_COUNT),(uint8_t)(noise()&255));int16_t b[N];
     for(int i=0;i<N;i++)b[i]=noise();InsertFx_process((uint8_t)(k%6),(uint8_t)((k/7)%INSERT_FX_COUNT),b,N);check(rms(b)==rms(b),"random settings finite");}}
  /* 0.2.82 flanger: depth 0, time 127 = 25 ms -> an impulse comes back after 1102.5 samples, mix 1 = half each */
  {InsertFx_init();InsertFx_setValue(INS_FLN_DEPTH,0);InsertFx_setValue(INS_FLN_TIME,127);InsertFx_setValue(INS_FLN_FEEDBACK,63);
   InsertFx_setValue(INS_FLN_MIX,127);
   static int16_t y[2048];memset(y,0,sizeof y);y[0]=20000;
   for(int k=0;k<2048/N;k++)InsertFx_process(0,INSERT_FX_FLANGER,y+k*N,N);
   check(abs(y[0]-10000)<2,"dry half");int peak=0,at=0;for(int i=1;i<2048;i++)if(abs(y[i])>peak){peak=abs(y[i]);at=i;}
   check(at==1102||at==1103,"25 ms delay");check(abs(y[1102])+abs(y[1103])>9000&&abs(y[1102])+abs(y[1103])<10100,"delayed half, interpolated");
   for(int i=1;i<1097;i++)check(y[i]==0,"nothing before the delay");}
  /* time 0 = 0.25 ms = 11 samples */
  {InsertFx_init();InsertFx_setValue(INS_FLN_DEPTH,0);InsertFx_setValue(INS_FLN_TIME,0);InsertFx_setValue(INS_FLN_FEEDBACK,63);
   int16_t y[64]={0};y[0]=20000;InsertFx_process(1,INSERT_FX_FLANGER,y,32);InsertFx_process(1,INSERT_FX_FLANGER,y+32,32);
   int at=0,peak=0;for(int i=1;i<64;i++)if(abs(y[i])>peak){peak=abs(y[i]);at=i;}check(at==11||at==12,"0.25 ms delay");}
  /* flanger feedback: full positive and negative stays finite and bounded, the sweep never reads past 25 ms */
  for(int fb=0;fb<128;fb+=127){InsertFx_init();InsertFx_setValue(INS_FLN_FEEDBACK,(uint8_t)fb);InsertFx_setValue(INS_FLN_RATE,127);
   InsertFx_setValue(INS_FLN_DEPTH,127);InsertFx_setValue(INS_FLN_TIME,127);
   for(int k=0;k<20000;k++){int16_t b[N];for(int i=0;i<N;i++)b[i]=noise();InsertFx_process(2,INSERT_FX_FLANGER,b,N);check(rms(b)==rms(b),"fln finite");}}
  /* ph2: 4, 8, 12 stages give different results; the default is 12 */
  {double r[3];for(int s=0;s<3;s++){InsertFx_init();InsertFx_setValue(INS_PH2_STAGES,(uint8_t)s);InsertFx_setValue(INS_PH2_MIX,127);
     InsertFx_setValue(INS_PH2_FEEDBACK,63);InsertFx_setValue(INS_PH2_RATE,0);
     double e=0;for(int k=0;k<200;k++){int16_t b[N];for(int i=0;i<N;i++)b[i]=(int16_t)(10000*sin((k*N+i)*0.2));InsertFx_process(3,INSERT_FX_PHASER2,b,N);if(k>100)e+=b[5];}r[s]=e;}
   check(fabs(r[0]-r[1])>1&&fabs(r[1]-r[2])>1,"stage count changes the sound");
   InsertFx_init();check(insertFx_params.ph2Stages==12,"default 12 stages");}
  for(int fb=0;fb<128;fb+=127){InsertFx_init();InsertFx_setValue(INS_PH2_FEEDBACK,(uint8_t)fb);InsertFx_setValue(INS_PH2_RATE,127);
   for(int k=0;k<20000;k++){int16_t b[N];for(int i=0;i<N;i++)b[i]=noise();InsertFx_process(4,INSERT_FX_PHASER2,b,N);check(rms(b)==rms(b),"ph2 finite");}}
  printf("INSERT FX PASS %u assertions\n",checks);return 0;}
'''
(OUT / 'contract.c').write_text(code, encoding='latin-1')
inc = ROOT / 'Core/Inc'
srcs = [ROOT / 'Core/Src/Soundengine/DSPAudio/FX/InsertFx.c', ROOT / 'Core/Src/Soundengine/DSPAudio/FX/Phaser.c', ROOT / 'Core/Src/Soundengine/DSPAudio/FX/Flanger.c']
if os.name == 'nt':
    vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    files = ' '.join(f'"{s}"' for s in srcs)
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /I"{inc}" /Fe:contract.exe contract.c {files} && contract.exe',
                   shell=True, cwd=OUT, check=True)
else:
    subprocess.run(['cc', f'-I{inc}', '-o', 'contract', 'contract.c', *map(str, srcs), '-lm'], cwd=OUT, check=True)
    subprocess.run([str(OUT / 'contract')], cwd=OUT, check=True)
