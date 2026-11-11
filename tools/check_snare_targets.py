"""0.2.85 mod target list: the snare's appended noise/layer targets and the
pitch EG slopes carry their own names, and every target selection (LFO,
velocity, random per step, encoder and knob) steps through a voice's targets
in display order. Stored target indices do not change. Runs the production
tables and step function on the host; --mutate shows the checks bite."""
from pathlib import Path
import os, re, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root / 'build/snare-targets'
out.mkdir(parents=True, exist_ok=True)
CC2 = root / 'Core/Src/menu/Cc2Text.c'
MENU = root / 'Core/Src/menu/menu.c'

def load():
    return {'cc2': CC2.read_text(encoding='latin-1').replace('\r\n', '\n'),
            'menu': MENU.read_text(encoding='latin-1').replace('\r\n', '\n')}

def contract(src):
    p = []
    m = src['menu']
    if m.count('modTargetStepVoice(') < 5:
        p.append('not every target selection steps in display order')
    if '*paramValue=modTargetClampVoice(voiceNr,*paramValue,inc);' in m:
        p.append('encoder still clamps the incremented index')
    if 'TODO not implemented yet: limit the velocity/LFO target' in m:
        p.append('knob path still steps raw indices')
    return p

def harness(src):
    cc2 = src['cc2']
    start = cc2.index('const ModTarg modTargets[]')
    end = cc2.index('\nuint8_t modTargetFromFraction(')
    names = re.search(r'const Name valueNames\[NUM_NAMES\] =\n\{.*?\n\};\n', src['menu'], re.S).group(0)
    return r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "menu/menu.h"
#include "menu/MenuText.h"
#include "menu/CcNr2Text.h"
uint8_t getNumModTargets(void);
uint8_t voiceFromModTargValue(uint8_t val);
uint8_t modTargetClampVoice(uint8_t voice,uint8_t target,int8_t direction);
uint8_t modTargetStepVoice(uint8_t voice,uint8_t target,int8_t inc);
''' + names + cc2[start:end] + r'''
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
static const char *shortOf(uint8_t t){return shortNames[valueNames[modTargets[t].nameIdx].shortName];}
static const char *catOf(uint8_t t){return catNames[valueNames[modTargets[t].nameIdx].category];}
int main(void){
 check(getNumModTargets()==247,"247 targets (0.2.107 + imix, i1..i4), indices unchanged");
 /* stored indices still mean the same parameters */
 check(modTargets[116].param==PAR_COARSE4&&modTargets[120].param==PAR_OSC_WAVE_SNARE&&modTargets[152].param==PAR_FX_P4,"snare block");
 check(modTargets[229].param==PAR_SNARE_NOISE_ATTACK&&modTargets[235].param==PAR_SNARE_LAYER_MODE&&modTargets[239].param==PAR_MODX_SND,"appended block");
 /* own names */
 static const char *want[7]={"nat","ndc","nsl","lwv","lmx","lfq","wmd"};
 for(int i=0;i<7;i++)check(!strcmp(shortOf((uint8_t)(229+i)),want[i]),"snare extra short name");
 check(!strcmp(catOf(229),"Noise")&&!strcmp(catOf(232),"Oscilltr"),"snare extra categories");
 const uint16_t ps[4]={PAR_PITCH_SLOPE1,PAR_PITCH_SLOPE2,PAR_PITCH_SLOPE3,PAR_PITCH_SLOPE4};
 for(int i=0;i<4;i++){int found=0;for(int t=1;t<242;t++)if(modTargets[t].param==ps[i]){found=1;
   check(!strcmp(shortOf((uint8_t)t),"psl"),"pitch slope short");check(!strcmp(catOf((uint8_t)t),"Mod EG"),"pitch slope category");}
   check(found,"pitch slope is a target");}
 for(int t=1;t<242;t++)if(modTargets[t].param==PAR_VOL_SLOPE4)check(!strcmp(shortOf((uint8_t)t),"slp"),"amp slope keeps slp");
 /* the short display shows voice + two letters: the snare's must all differ */
 {uint8_t seen[256]={0},n=0,list[64];uint8_t t=0;
  do{t=modTargetStepVoice(3,t,1);if(seen[t])break;seen[t]=1;list[n++]=t;}while(n<64);
  check(n==50,"snare list has 37+7+snd+imix+i1..i4 entries");
  for(int i=0;i<45;i++)check(voiceFromModTargValue(list[i])==4,"every snare entry belongs to voice 4");
  for(int i=45;i<50;i++)check(list[i]==MOD_TARGET_INSERT+i-45,"insert targets after snd");
  static const uint8_t head[13]={116,117,120,121,232,233,234,235,118,119,229,230,231};
  for(int i=0;i<13;i++)check(list[i]==head[i],"snare display order");
  check(list[44]==239,"d/w last");
  for(int i=13;i<44;i++)check(list[i]==122+i-13,"rest in stored order");
  for(int a=0;a<n;a++)for(int b=a+1;b<n;b++){const char*x=shortOf(list[a]),*y=shortOf(list[b]);
    int fx=modTargets[list[a]].param>=PAR_FX_P1&&modTargets[list[a]].param<=PAR_FX_P4;(void)fx;
    if(list[a]>=229&&list[a]<=235)check(strncmp(x,y,2)!=0,"new snare targets readable in the short display");}
  /* walking back reaches off through the same order */
  uint8_t back=239;for(int i=43;i>=0;i--){back=modTargetStepVoice(3,back,-1);check(back==list[i],"reverse order");}
  check(modTargetStepVoice(3,back,-1)==0,"then off");check(modTargetStepVoice(3,0,-1)==0,"off stays off");
  check(modTargetStepVoice(3,239,1)==MOD_TARGET_INSERT&&modTargetStepVoice(3,MOD_TARGET_INSERT+4,1)==MOD_TARGET_INSERT+4,"i4 is the end");
  check(modTargetStepVoice(3,121,3)==234,"fast turn skips along the order");
 }
 /* other voices: identical to the old clamp for single steps */
 for(uint8_t v=0;v<6;v++){if(v==3)continue;
  uint8_t s=modTargetVoiceOffsets[v].start,e=modTargetVoiceOffsets[v].end,dw=(uint8_t)(236+v);
  for(int t=0;t<242;t++){if(t && !(t>=s&&t<=e) && t!=dw)continue;
   for(int inc=-1;inc<=1;inc+=2){int raw=t+inc;if(raw<0)raw=0;
    check(modTargetStepVoice(v,(uint8_t)t,(int8_t)inc)==modTargetClampVoice(v,(uint8_t)raw,(int8_t)inc),"other voices unchanged");}}}
 check(modTargetStepVoice(6,5,1)==0,"invalid voice is off");
 /* a target of another voice falls back to the clamp */
 check(modTargetStepVoice(3,5,1)==modTargetClampVoice(3,6,1),"foreign target uses the clamp");
 printf("SNARE TARGETS PASS %u assertions\n",checks);return 0;}
'''

def run(code):
    (out / 'targets.c').write_text(code, encoding='latin-1')
    # menu.h includes "main.h" (HAL); the tables only need the integer types
    pp = out / 'stub'
    pp.mkdir(parents=True, exist_ok=True)
    (pp / 'main.h').write_text('#include <stdint.h>\n')
    (pp / 'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
    (out / 'main.h').write_text('#include <stdint.h>\n')
    if os.name == 'nt':
        vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
        r = subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /wd4305 /wd4244 /TC /I"{pp}" /I"{root / "Core/Inc"}" /Fe:targets.exe targets.c && targets.exe',
                           shell=True, cwd=out, capture_output=True, text=True, errors="replace")
    else:
        r = subprocess.run(f'cc -I"{pp}" -I"{root / "Core/Inc"}" -o targets targets.c && ./targets', shell=True, cwd=out, capture_output=True, text=True, errors="replace")
    return r.returncode, r.stdout + r.stderr

MUTATIONS = {
    'old-names': ('cc2', '{TEXT_SNARE_NOISE_ATTACK,PAR_SNARE_NOISE_ATTACK},', '{TEXT_ATTACK,PAR_SNARE_NOISE_ATTACK},'),
    'pitch-slope-name': ('cc2', '{TEXT_PITCH_SLOPE,PAR_PITCH_SLOPE4},', '{TEXT_EG_SLOPE,PAR_PITCH_SLOPE4},'),
    'raw-order': ('cc2', '{116,117,120,121,232,233,234,235,118,119,229,230,231,', '{116,117,118,119,120,121,229,230,231,232,233,234,235,'),
    'no-dw': ('cc2', ',MOD_TARGET_SND+3,\n', ',\n'),
    'other-voice-order': ('cc2', 'if(pos<=n)return (uint8_t)(modTargetVoiceOffsets[voice].start+pos-1);', 'if(pos<n)return (uint8_t)(modTargetVoiceOffsets[voice].start+pos-1);'),
    'encoder-clamp': ('menu', '\t\t*paramValue=modTargetStepVoice(voiceNr,oldParamValue,inc);\n\n\t\t// determine the parameter id', '\t\t*paramValue=modTargetClampVoice(voiceNr,*paramValue,inc);\n\n\t\t// determine the parameter id'),
    'knob-raw': ('menu', '\t\tnewValue=modTargetStepVoice(voiceNr,originalValue,diff);\n', ''),
}

src = load()
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        m = dict(src); assert m[key].count(old) == 1, name
        m[key] = m[key].replace(old, new)
        hit = bool(contract(m)) or run(harness(m))[0] != 0
        caught += hit
        print(name, 'caught' if hit else 'MISSED')
    print(f'{caught}/{len(MUTATIONS)} mutations caught')
    sys.exit(0 if caught == len(MUTATIONS) else 1)

found = contract(src)
for f in found:
    print('FAIL', f)
if found:
    sys.exit(1)
code, text = run(harness(src))
print(text.strip().splitlines()[-1] if text.strip() else text)
if code:
    print(text)
    sys.exit(1)
