"""0.2.78 phaser (FX type pha): the production Phaser.c on the host.
Checks: coefficients stay inside (-1, 1) over the whole parameter range; the
wet chain is an allpass (energy kept, feedback 0); full feedback with loud noise
stays bounded and decays to silence; d/w 0.5 makes a notch at the sweep
frequency; mono writes only the left slot; silence stays silence."""
from pathlib import Path
import os, subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/phaser-audit'
OUT.mkdir(parents=True, exist_ok=True)
code = r'''
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Soundengine/DSPAudio/FX/Phaser.h"
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
static uint32_t rng=1;static int16_t noise(void){rng=rng*1664525u+1013904223u;return (int16_t)(rng>>16);}
#define N 32
int main(void){
  Phaser p;
  /* coefficients for every knob position and sweep position */
  for(int c=0;c<=127;c++)for(int d=0;d<=127;d+=7)for(int l=-10;l<=10;l++){
    Phaser_init(&p);Phaser_setCentre(&p,c/127.f);Phaser_setDepth(&p,d/127.f);
    float a=Phaser_coefficient(&p,l/10.f);check(a>-1.f&&a<1.f&&a==a,"coefficient inside (-1,1)");}
  /* silence in, silence out */
  {Phaser_init(&p);int16_t in[2*N]={0},out[2*N]={0};
   for(int b=0;b<500;b++){Phaser_process(&p,in,out,N,2,1.f);for(int i=0;i<2*N;i++)check(out[i]==0,"silence stays silence");}}
  /* allpass: wet only, feedback 0, energy of a long noise burst is kept */
  {Phaser_init(&p);Phaser_setFeedback(&p,0.f);Phaser_setRate(&p,0.f);Phaser_setDepth(&p,0.f);
   double ein=0,eout=0;
   for(int b=0;b<4000;b++){int16_t in[2*N],out[2*N]={0};
     for(int i=0;i<2*N;i++){in[i]=b<3000?(int16_t)(noise()/4):0;ein+=(double)in[i]*in[i];}
     Phaser_process(&p,in,out,N,2,1.f);for(int i=0;i<2*N;i++)eout+=(double)out[i]*out[i];}
   check(fabs(eout/ein-1.0)<0.02,"wet chain keeps energy (allpass)");}
  /* full feedback, loud noise: bounded, then decays */
  for(int r=0;r<=127;r+=31){Phaser_init(&p);Phaser_setFeedback(&p,1.f);Phaser_setDepth(&p,1.f);Phaser_setRate(&p,r/127.f);
   double tail=0;
   for(int b=0;b<20000;b++){int16_t in[2*N],out[2*N]={0};
     for(int i=0;i<2*N;i++)in[i]=b<10000?noise():0;
     Phaser_process(&p,in,out,N,2,0.5f);
     for(int i=0;i<2*N;i++){check(p.last[i&1]==p.last[i&1]&&fabsf(p.last[i&1])<40.f,"feedback bounded");if(b>19000)tail+=fabs(out[i]);}}
   check(tail==0.0,"feedback decays to silence");}
  /* notch: stage frequency where 6 stages give 540 degrees, i.e. the sum
     cancels; find the minimum of the d/w 0.5 response over frequency */
  {double best=1e9,worst=0;
   for(int k=0;k<60;k++){double f=60.0*pow(2.0,k/8.0);if(f>16000)break;
     Phaser_init(&p);Phaser_setFeedback(&p,0.f);Phaser_setRate(&p,0.f);Phaser_setDepth(&p,0.f);Phaser_setCentre(&p,0.4f);
     double ph=0,e=0,ein=0;
     for(int b=0;b<600;b++){int16_t in[2*N],out[2*N]={0};
       for(int i=0;i<N;i++){int16_t s=(int16_t)(12000*sin(ph));ph+=2*3.14159265358979*f/44100.0;in[2*i]=in[2*i+1]=s;}
       Phaser_process(&p,in,out,N,2,0.5f);
       if(b>=300)for(int i=0;i<2*N;i++){e+=(double)out[i]*out[i];ein+=(double)in[i]*in[i];}}
     double g=sqrt(e/ein);if(g<best)best=g;if(g>worst)worst=g;}
   check(best<0.15,"d/w 0.5 has a notch");check(worst>0.9,"d/w 0.5 passes away from the notch");}
  /* mono: only the left slot of each pair is written */
  {Phaser_init(&p);int16_t in[2*N],out[2*N];
   for(int b=0;b<200;b++){for(int i=0;i<2*N;i++){in[i]=noise();out[i]=(int16_t)(i&1?1234:0);}
     Phaser_process(&p,in,out,N,1,0.7f);for(int i=1;i<2*N;i+=2)check(out[i]==1234,"mono leaves the right slot");}}
  printf("PHASER PASS %u assertions\n",checks);return 0;}
'''
(OUT / 'contract.c').write_text(code, encoding='latin-1')
inc = ROOT / 'Core/Inc'
src = ROOT / 'Core/Src/Soundengine/DSPAudio/FX/Phaser.c'
if os.name == 'nt':
    vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /I"{inc}" /Fe:contract.exe contract.c "{src}" && contract.exe',
                   shell=True, cwd=OUT, check=True)
else:
    subprocess.run(['cc', f'-I{inc}', '-o', 'contract', 'contract.c', str(src), '-lm'], cwd=OUT, check=True)
    subprocess.run([str(OUT / 'contract')], cwd=OUT, check=True)
