"""0.2.83 performance gater: the production mixer gate functions on the host,
plus the source contract of its wiring (sequencer phase, stop, PERF Step 16
toggle with LED, Pch CC 53). --mutate shows each check catches a broken copy."""
from pathlib import Path
import os, re, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root / 'build/gater-audit'
out.mkdir(parents=True, exist_ok=True)
FILES = {
    'mixer': root / 'Core/Src/Soundengine/DSPAudio/mixer.c',
    'seq': root / 'Core/Src/Soundengine/Sequencer/sequencer.c',
    'button': root / 'Core/Src/buttonHandler.c',
    'led': root / 'Core/Src/ledHandler.c',
    'midi': root / 'Core/Src/Soundengine/MIDI/MidiParser.c',
}
def load():
    return {k: v.read_text(encoding='latin-1').replace('\r\n', '\n') for k, v in FILES.items()}

def function(src, name):
    m = re.search(r'^[^\n]*\b' + name + r'\([^)]*\)\s*\{', src, re.M)
    assert m, name
    pos, depth = m.end(), 1
    while depth:
        depth += (src[pos] == '{') - (src[pos] == '}')
        pos += 1
    return src[m.start():pos]

def body(src, name):
    m = re.search(r'void ' + name + r'\(\)\n\{(.*?)\n\}\n', src, re.S)
    assert m, name
    return m.group(1)

def problems(src):
    p = []
    seq, button, led, midi, mixer = src['seq'], src['button'], src['led'], src['midi'], src['mixer']
    tick = body(seq, 'seq_tick')
    if 'mixer_setPerformanceGatePhase((uint8_t)((uint32_t)seq_prescaleCounter*2u<(uint32_t)perf_scaleTicks()));' not in tick:
        p.append('sequencer does not set the gate phase per half step')
    if 'mixer_setPerformanceGatePhase' in body(seq, 'seq_nextStep'):
        p.append('gate phase still follows whole steps (0.2.83 bug: quarter notes)')
    if 'seq_masterStepCnt = 0;\n\tmixer_setPerformanceGatePhase(1);' not in seq:
        p.append('stop does not open the gate')
    if not re.search(r'seqButtonPressed == 15\) \{.*?mixer_setPerformanceGateEnabled\(!mixer_getPerformanceGateEnabled\(\)\);\s*led_setValue\(mixer_getPerformanceGateEnabled\(\), ledNr\);', button, re.S):
        p.append('PERF Step 16 does not toggle the gater with its LED')
    if 'led_setValue(mixer_getPerformanceGateEnabled(),led_idx2StepLed(15));' not in led:
        p.append('PERF LEDs do not show the gater state')
    if 'case 53: mixer_setPerformanceGateEnabled((uint8_t)(value>=64));return 1;' not in midi or '(cc>=53 && cc<=59)' not in midi:
        p.append('Pch CC 53 does not set the gater')
    if 'mixer_addMasterFxSendAfterFilter(output2,&output[pos],&output[pos+1]);\n\tmixer_applyPerformanceGate(output,output2,OUTPUT_DMA_SIZE);' not in mixer:
        p.append('gate is not applied last on the master')
    return p

MUTATIONS = {
    'no-phase': ('seq', '    mixer_setPerformanceGatePhase((uint8_t)((uint32_t)seq_prescaleCounter*2u<(uint32_t)perf_scaleTicks()));\n', ''),
    'whole-steps': ('seq', '\tseq_masterStepCnt++;\n', '\tseq_masterStepCnt++;\n\tmixer_setPerformanceGatePhase(1);\n'),
    'stop-closed': ('seq', 'seq_masterStepCnt = 0;\n\tmixer_setPerformanceGatePhase(1);', 'seq_masterStepCnt = 0;\n\tmixer_setPerformanceGatePhase(0);'),
    'no-led': ('button', '\t\t\t\tled_setValue(mixer_getPerformanceGateEnabled(), ledNr);\n', ''),
    'no-perf-led': ('led', 'led_setValue(mixer_getPerformanceGateEnabled(),led_idx2StepLed(15));', 'led_setValue(0,led_idx2StepLed(15));'),
    'cc-gone': ('midi', '\tcase 53: mixer_setPerformanceGateEnabled((uint8_t)(value>=64));return 1;', ''),
    'gate-early': ('mixer', '\tmixer_applyPerformanceGate(output,output2,OUTPUT_DMA_SIZE);', ''),
}

src = load()
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        m = dict(src); assert m[key].count(old) == 1, name
        m[key] = m[key].replace(old, new)
        hit = bool(problems(m)); caught += hit
        print(name, 'caught' if hit else 'MISSED')
    print(f'{caught}/{len(MUTATIONS)} mutations caught')
    sys.exit(0 if caught == len(MUTATIONS) else 1)

found = problems(src)
for f in found:
    print('FAIL', f)
if found:
    sys.exit(1)

decl = re.search(r'static uint8_t mixer_gateEnabled;\nstatic float mixer_gateGain = 1.f;\nstatic float mixer_gateTarget = 1.f;\n', src['mixer']).group(0)
code = '#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n' + decl
for n in ('mixer_setPerformanceGateEnabled', 'mixer_getPerformanceGateEnabled', 'mixer_setPerformanceGatePhase', 'mixer_applyPerformanceGate'):
    code += function(src['mixer'], n) + '\n'
code += r'''
static unsigned checks;
static void check(int ok,const char*m){checks++;if(!ok){printf("FAIL %s\n",m);exit(1);}}
#define F 32
static int16_t a[F*2],b[F*2];
static void fill(void){for(int i=0;i<F*2;i++){a[i]=10000;b[i]=-10000;}}
int main(void){
 fill();mixer_setPerformanceGatePhase(0);mixer_applyPerformanceGate(a,b,F);
 for(int i=0;i<F*2;i++)check(a[i]==10000&&b[i]==-10000,"off: closed phase does nothing");
 mixer_setPerformanceGateEnabled(1);check(mixer_getPerformanceGateEnabled()==1,"enabled");
 mixer_setPerformanceGatePhase(0);fill();mixer_applyPerformanceGate(a,b,F);
 check(a[0]<10000&&a[0]>9000,"ramp starts, no hard step");check(a[F*2-2]==0&&b[F*2-1]==0,"closed after 32 samples");
 for(int i=2;i<F*2;i+=2)check(a[i]<=a[i-2],"falls monotonically");
 fill();mixer_applyPerformanceGate(a,b,F);for(int i=0;i<F*2;i++)check(a[i]==0&&b[i]==0,"stays closed");
 mixer_setPerformanceGatePhase(1);fill();mixer_applyPerformanceGate(a,b,F);
 check(a[0]>0&&a[0]<1000,"opens with a ramp");check(a[F*2-2]==10000,"open after 32 samples");
 mixer_setPerformanceGatePhase(0);fill();mixer_applyPerformanceGate(a,b,F/2);
 mixer_setPerformanceGateEnabled(0);fill();mixer_applyPerformanceGate(a,b,F);
 check(a[F*2-2]==10000,"switching off opens again");
 fill();mixer_applyPerformanceGate(a,b,F);for(int i=0;i<F*2;i++)check(a[i]==10000,"off and open: untouched");
 /* sequencer phase: counter 0..ticks-1 inside a step -> open for the first half, at every rate */
 for(unsigned t=2;t<=96;t++){unsigned on=0;for(unsigned c=0;c<t;c++){unsigned open=(unsigned)(c*2u<t);on+=open;
   if(c==0)check(open,"step starts open");}check(on==(t+1)/2,"open half of the step");}
 printf("GATER PASS %u assertions\n",checks);return 0;}
'''
(out / 'contract.c').write_text(code, encoding='latin-1')
if os.name == 'nt':
    vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
    subprocess.run(f'call "{vs}" -arch=x64 >nul && cl /nologo /W3 /TC /Fe:contract.exe contract.c && contract.exe', shell=True, cwd=out, check=True)
else:
    subprocess.run(['cc', '-o', 'contract', 'contract.c'], cwd=out, check=True)
    subprocess.run([str(out / 'contract')], cwd=out, check=True)
