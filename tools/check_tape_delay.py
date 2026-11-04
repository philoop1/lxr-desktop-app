"""The production tape delay on the host, compiled from TapeDelay.c.

--mutate removes the mute of samples older than the last reset; the check
must then fail.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"
HAL = r"""
#pragma once
#define _USE_MATH_DEFINES
#include <stdint.h>
#include <math.h>
#include <string.h>
#define __attribute__(x)
#define __fp16 float
#define inline
static int32_t lxrSat(int32_t v){return v>32767?32767:v<-32768?-32768:v;}
#define __SSAT(v,b) lxrSat((int32_t)(v))
static int32_t __PKHBT(int32_t a,int32_t b,int s){return (a&0xffff)|(b<<s);}
static int32_t __QADD16(int32_t a,int32_t b)
{
 const int32_t lo=lxrSat((int16_t)a+(int16_t)b),hi=lxrSat((int16_t)(a>>16)+(int16_t)(b>>16));
 return (lo&0xffff)|(hi<<16);
}
"""
TESTS = r"""
#include <stdio.h>
#include <stdlib.h>
__fp16 FX_BUFFER[FX_BUFFER_SIZE+1];
static TapeDelay d;
static unsigned checks,failures;
static const char *lastFail;
static void check(int ok,const char *name)
{
 checks++;
 if(!ok){failures++;if(name!=lastFail)printf("FAIL %s\n",name);lastFail=name;}
}
#define LEN 60000
static int16_t outL[LEN],outR[LEN];
/* Runs n samples of a mono input through the delay at 120 BPM. */
static void run(const int16_t *in,unsigned n,float dryWet,unsigned from)
{
 for(unsigned s=0;s<n;s+=16) {
  int16_t fx[32],out[32];
  for(unsigned i=0;i<16;i++)fx[i*2]=fx[i*2+1]=in?in[s+i]:0;
  memset(out,0,sizeof(out));
  TapeDelay_process(&d,fx,out,16,2,dryWet,120);
  for(unsigned i=0;i<16;i++){outL[from+s+i]=out[i*2];outR[from+s+i]=out[i*2+1];}
 }
}
static void setup(float rate,float fb,uint8_t pingPong)
{
 memset(FX_BUFFER,0,sizeof(FX_BUFFER));
 TapeDelay_init(&d);
 TapeDelay_setPingPong(&d,pingPong);
 TapeDelay_setRate(&d,rate);TapeDelay_setFine(&d,64.f/127.f);
 TapeDelay_setTone(&d,1.f);TapeDelay_setFeedback(&d,fb);
 TapeDelay_reset(&d);
}
static unsigned peak(const int16_t *x,unsigned from,unsigned to)
{
 unsigned best=from;
 for(unsigned i=from;i<to;i++) if(abs(x[i])>abs(x[best]))best=i;
 return best;
}
static double near(double a,double b){return fabs(a-b);}
int main(void)
{
 const float fine0=64.f/127.f,eighth=8.5f/16.f;
 /* Divisions at 120 BPM: an eighth is 0.25 s. */
 check(TapeDelay_division(eighth,fine0,120,0)==8,"rate picks the eighth");
 check(near(TapeDelay_targetSamples(eighth,fine0,120,0),0.25*REAL_FS)<1,"eighth length");
 check(TapeDelay_division(0.f,fine0,120,0)==4,"too long falls to the half triplet in mono");
 check(TapeDelay_division(0.f,fine0,120,1)==7,"too long falls to the quarter triplet in ping pong");
 check(TapeDelay_division(1.f,fine0,120,0)==15,"top rate is 1/128");
 for(unsigned r=0;r<=127;r++) for(unsigned bpm=20;bpm<=300;bpm+=7) for(unsigned pp=0;pp<2;pp++) {
  const float t=TapeDelay_targetSamples(r/127.f,1.f,(uint16_t)bpm,(uint8_t)pp);
  check(t>=1.f&&t<=(pp?(FX_BUFFER_SIZE>>1):FX_BUFFER_SIZE)-1,"target fits the line");
 }
 check(near(TapeDelay_targetSamples(eighth,1.f,120,0)/(0.25*REAL_FS),1+63./TAPE_FINE_SPAN)<1e-4,"fine up");
 check(near(TapeDelay_targetSamples(eighth,0.f,120,0)/(0.25*REAL_FS),1-64./TAPE_FINE_SPAN)<1e-4,"fine down");

 /* Mono: the echo comes after one eighth, the next one scaled by feedback. */
 static int16_t in[LEN];
 const unsigned delay=(unsigned)(0.25*REAL_FS);
 setup(eighth,0.5f,0);memset(in,0,sizeof(in));in[0]=16000;
 run(in,LEN,1.f,0);
 unsigned p1=peak(outL,1,delay+200),p2=peak(outL,delay+200,2*delay+200);
 check(p1>=delay-2&&p1<=delay+2,"mono echo time");
 check(abs(outL[p1]-outR[p1])<=1,"mono echo is centred");
 check(abs(abs(outL[p2])-abs(outL[p1])/2)<abs(outL[p1])/20,"feedback halves the next echo");
 check(p2>=2*delay-3&&p2<=2*delay+3,"second echo time");

 /* Ping pong: left first, then right, each one scaled by feedback. */
 setup(eighth,0.5f,1);memset(in,0,sizeof(in));in[0]=16000;
 run(in,LEN,1.f,0);
 p1=peak(outL,1,delay+200);
 const unsigned r1=peak(outR,1,2*delay+200);
 check(p1>=delay-2&&p1<=delay+2,"ping pong left echo");
 check(abs(outR[p1])<abs(outL[p1])/50,"first echo only left");
 check(r1>=2*delay-3&&r1<=2*delay+3,"ping pong right echo");
 check(abs(abs(outR[r1])-abs(outL[p1])/2)<abs(outL[p1])/20,"right echo scaled by feedback");

 /* Stale buffer content from another effect stays silent after a reset. */
 setup(eighth,0.9f,0);
 for(unsigned i=0;i<=FX_BUFFER_SIZE;i++)FX_BUFFER[i]=(float)((i*7919u)%2001u)/1000.f-1.f;
 TapeDelay_reset(&d);
 run(NULL,LEN,1.f,0);
 int quiet=1;for(unsigned i=0;i<LEN;i++)quiet&=outL[i]==0&&outR[i]==0;
 check(quiet,"stale buffer is muted");

 /* Dry passes unchanged at dry/wet 0. */
 setup(eighth,0.5f,0);
 for(unsigned i=0;i<LEN;i++)in[i]=(int16_t)(8000*sin(i*0.01));
 run(in,4096,0.f,0);
 int dry=1;for(unsigned i=0;i<4096;i++)dry&=outL[i]==in[i]&&outR[i]==in[i];
 check(dry,"dry path");

 /* A rate change glides: halfway after about 0.1 s, nearly there after 1 s. */
 setup(eighth,0.f,0);run(NULL,1024,1.f,0);
 const float from=d.delay;
 TapeDelay_setRate(&d,11.5f/16.f);
 const float to=TapeDelay_targetSamples(11.5f/16.f,fine0,120,0);
 run(NULL,16,1.f,0);
 check(near(d.delay,from)<near(from,to)*0.01,"no jump on rate change");
 run(NULL,(unsigned)(0.104*REAL_FS)&~15u,1.f,0);
 check(near(d.delay,(from+to)/2)<near(from,to)*0.05,"glide halfway");
 run(NULL,(unsigned)REAL_FS&~15u,1.f,0);
 check(near(d.delay,to)<near(from,to)*0.002,"glide arrives");

 /* Full feedback and loud input stay finite and in range. */
 for(unsigned pp=0;pp<2;pp++) {
  setup(eighth,1.f,(uint8_t)pp);
  for(unsigned i=0;i<LEN;i++)in[i]=(int16_t)((i&64)?30000:-30000);
  for(unsigned k=0;k<5;k++)run(in,LEN,1.f,0);
  check(isfinite(d.lpL)&&isfinite(d.lpR)&&isfinite(d.delay),"stays finite");
  int bounded=1;for(unsigned i=0;i<=FX_BUFFER_SIZE;i++)bounded&=fabsf(FX_BUFFER[i])<=1.f;
  check(bounded,"buffer stays in range");
 }
 /* Feedback above 1 grows into the saturation and sustains, but stays in range. */
 for(unsigned pp=0;pp<2;pp++) {
  setup(eighth,TAPE_FEEDBACK_MAX,(uint8_t)pp);memset(in,0,sizeof(in));in[0]=3000;
  for(unsigned k=0;k<8;k++)run(k?NULL:in,LEN,1.f,0);
  check(abs(outL[peak(outL,0,LEN)])>16000,"feedback over 1 sustains and grows");
  int bounded=1;for(unsigned i=0;i<=FX_BUFFER_SIZE;i++)bounded&=fabsf(FX_BUFFER[i])<=1.f;
  check(bounded&&isfinite(d.lpL)&&isfinite(d.lpR),"feedback over 1 stays in range");
  /* At unity the repeats do not grow. */
  setup(eighth,1.f,(uint8_t)pp);memset(in,0,sizeof(in));in[0]=3000;
  run(in,LEN,1.f,0);
  const int first=abs(outL[peak(outL,0,LEN)]);
  for(unsigned k=0;k<7;k++)run(NULL,LEN,1.f,0);
  check(first>0&&abs(outL[peak(outL,0,LEN)])<=first,"unity feedback does not grow");
 }
 printf("%s %u assertions\n",failures?"TAPE FAIL":"TAPE PASS",checks);
 return failures!=0;
}
"""


def main() -> None:
    source = (ROOT / 'Core/Src/Soundengine/DSPAudio/FX/TapeDelay.c').read_text()
    if '--mutate' in sys.argv:
        old = '(delay <= (float)valid) ? 1.f : 0.f'
        assert old in source
        source = source.replace(old, '1.f')
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        out = Path(folder)
        (out / 'stm32f7xx_hal.h').write_text(HAL, encoding='utf-8')
        (out / 'stm32f7xx.h').write_text('#include "stm32f7xx_hal.h"\n', encoding='utf-8')
        (out / 'tape.c').write_text('#include "stm32f7xx_hal.h"\n' + source, encoding='utf-8')
        (out / 'tests.c').write_text('#include "stm32f7xx_hal.h"\n'
                                     '#include "Soundengine/DSPAudio/FX/TapeDelay.h"\n' + TESTS,
                                     encoding='utf-8')
        includes = f'/I. /I"{ROOT / "Core/Inc"}"'
        command = (f'call "{VS}" -arch=x64 >nul && cl /nologo /O2 /W1 /TC {includes} '
                   f'/Fe:contract.exe tape.c tests.c && .\\contract.exe')
        subprocess.run(command, shell=True, cwd=out, check=True)


if __name__ == '__main__':
    main()
