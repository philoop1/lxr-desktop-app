"""0.2.102 silent-voice sleep (from the Mutador reference). A voice whose amp EG
is exactly 0 for the block renders zeros, so its work is skipped. What must
still move while it sleeps is derived from the normal path: every oscillator
it renders keeps its phase, every per-sample smoothing filter (calcOnePole)
keeps running, the filter is cleared once, and the voice wakes on the next
block with sound. Source contract; --mutate shows the checks bite."""
from pathlib import Path
import re, sys

ROOT = Path(__file__).resolve().parents[1]
D = 'Core/Src/Soundengine/DSPAudio/'
FILES = {'drum': D + 'DrumVoice.c', 'snare': D + 'Snare.c', 'cym': D + 'CymbalVoice.c',
         'hat': D + 'HiHat.c', 'dist': D + 'distortion.c'}
NOT_OSC = {'filter', 'transGen', 'distortion', 'dither', 'ampFilter'}


def load():
    return {k: (ROOT / v).read_text(encoding='latin-1').replace('\r\n', '\n') for k, v in FILES.items()}


def active(src):
    """config.h sets SMOOTH_MIXER_VOL_PAN_DRIVE 1: drop the #else branches"""
    return re.sub(r'(#if SMOOTH_MIXER_VOL_PAN_DRIVE\n.*?)#else\n.*?(#endif)', r'\1\2', src, flags=re.S)


def body(src, sig):
    src = active(src)
    start = src.index(sig)
    i = src.index('{', start)
    depth = 0
    while True:
        depth += (src[i] == '{') - (src[i] == '}')
        if depth == 0:
            return src[start:i + 1]
        i += 1


def needs(normal, var):
    """oscillators and smoothing filters the normal path keeps moving"""
    oscs = set(re.findall(r'calc\w*Block\w*\(&' + re.escape(var) + r'(\w+)', normal)) - NOT_OSC
    poles = set(re.findall(r'calcOnePole\(\s*&' + re.escape(var) + r'([\w.\[\]0-9]+)', normal))
    return oscs, poles


def voice(p, name, fn, sleep, var, cond, flag, extra_normal=''):
    if cond not in fn:
        p.append(f'{name}: sleep condition missing or changed')
        return
    cut = fn.index(cond)
    wake = fn.find(f'{flag} = 0;')
    if wake < cut:
        p.append(f'{name}: the voice must wake (flag cleared) after the sleep test')
        return
    normal = fn[wake:] + extra_normal
    oscs, poles = needs(normal, var)
    if not oscs:
        p.append(f'{name}: no oscillators found in the normal path')
    for o in sorted(oscs):
        if f'{var}{o}.phase += {var}{o}.phaseInc * size;' not in sleep:
            p.append(f'{name}: {o} does not keep its phase while sleeping')
    for f in sorted(poles):
        if f'calcOnePole(&{var}{f}' not in sleep:
            p.append(f'{name}: smoothing {f} stops while sleeping (volume jump on wake)')
    i = sleep.find(f'if(!{flag})')
    if i < 0 or f'SVF_reset(&{var}filter);' not in sleep[i:i + 120] or f'{flag} = 1;' not in sleep[i:i + 160]:
        p.append(f'{name}: the filter must be cleared once on entry')
    if 'bufferTool_clearBuffer(buf,size);' not in sleep:
        p.append(f'{name}: a sleeping voice must output zeros')


def contract(s):
    p = []
    # drum 1-3: the sleep path is its own flash function
    drum = body(s['drum'], 'IN_ITCM_RAM void calcDrumVoiceSyncBlock(')
    slp = body(s['drum'], 'static __attribute__((noinline)) void drum_sleepBlock(')
    if 'IN_ITCM_RAM' in s['drum'][s['drum'].index('static uint8_t drum_voiceSleeping'):s['drum'].index('void drum_sleepBlock(')]:
        p.append('drum: the sleep path must stay out of ITCM')
    if 'drum_sleepBlock(voiceNr, buf, size, faderTarget);\n\t\treturn;' not in drum:
        p.append('drum: the sync block does not hand silent blocks to the sleep path')
    distf = body(s['dist'], 'void calcDistBlockFiltered(').replace('dist->', 'v->distortion.')
    voice(p, 'drum', drum.replace('voiceArray[voiceNr].', 'v->'), slp, 'v->', 'if(v->ampFilterInput == 0.f && v->lastGain == 0.f)',
          'drum_voiceSleeping[voiceNr]', distf if 'calcDistBlockFiltered' in drum else '')
    # snare, cymbal, hihat
    for key, sig, var, cond, flag in (
        ('snare', 'void Snare_calcSyncBlock(', 'snareVoice.',
         'if(snareVoice.egValueOscVol == 0.f &&\n\t\t(!snareVoice.noiseEnvelopeEnabled || snareVoice.noiseEgValue == 0.f))', 'snare_sleeping'),
        ('cym', 'void Cymbal_calcSyncBlock(', 'cymbalVoice.', 'if(cymbalVoice.egValueOscVol == 0.f)', 'cymbal_sleeping'),
        ('hat', 'void HiHat_calcSyncBlock(', 'hatVoice.', 'if(hatVoice.egValueOscVol == 0.f)', 'hat_sleeping')):
        fn = body(s[key], sig)
        if cond not in fn:
            p.append(f'{key}: sleep condition missing or changed')
            continue
        i = fn.index(cond)
        sleep = fn[i:fn.index('return;', i)]
        voice(p, key, fn, sleep, var, cond, flag)
    return p


MUTATIONS = {
    'drum-near-zero': ('drum', 'if(voiceArray[voiceNr].ampFilterInput == 0.f && voiceArray[voiceNr].lastGain == 0.f)',
                       'if(voiceArray[voiceNr].ampFilterInput < 0.001f && voiceArray[voiceNr].lastGain == 0.f)'),
    'drum-no-fader': ('drum', '\t\tv->combinedVolume = mixVol * calcOnePole(&v->FaderVolumeFilter, faderTarget);\n', '\t\tv->combinedVolume = mixVol;\n'),
    'drum-no-drive-smooth': ('drum', '\t\tcalcOnePole(&v->distortion.DriveParamFilter, v->distortion.shape);\n', ''),
    'drum-no-modphase': ('drum', '\tv->modOsc.phase += v->modOsc.phaseInc * size;\n', ''),
    'drum-in-itcm': ('drum', 'static __attribute__((noinline)) void drum_sleepBlock(', 'IN_ITCM_RAM static __attribute__((noinline)) void drum_sleepBlock('),
    'drum-never-wakes': ('drum', '\tdrum_voiceSleeping[voiceNr] = 0;\n', ''),
    'snare-ignores-noise-eg': ('snare', ' &&\n\t\t(!snareVoice.noiseEnvelopeEnabled || snareVoice.noiseEgValue == 0.f))', ')'),
    'snare-no-layer-phase': ('snare', '\t\tsnareVoice.layerOsc.phase += snareVoice.layerOsc.phaseInc * size;\n', ''),
    'snare-no-reset': ('snare', '\t\t\tSVF_reset(&snareVoice.filter);\n', ''),
    'cym-no-fader': ('cym', '\t\tfor(uint8_t i=0;i<size;i++) calcOnePole(&cymbalVoice.FaderVolumeFilter, faderTarget);\n', ''),
    'hat-no-mod2-phase': ('hat', '\t\thatVoice.modOsc2.phase += hatVoice.modOsc2.phaseInc * size;\n', ''),
    'hat-no-clear': ('hat', '\t\tbufferTool_clearBuffer(buf,size);\n\t\treturn;\n\t}\n\that_sleeping = 0;', '\t\treturn;\n\t}\n\that_sleeping = 0;'),
}

src = load()
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        m = dict(src)
        assert m[key].count(old) == 1, name
        m[key] = m[key].replace(old, new)
        hit = bool(contract(m))
        caught += hit
        print(name, 'caught' if hit else 'MISSED')
    print(f'{caught}/{len(MUTATIONS)} mutations caught')
    sys.exit(0 if caught == len(MUTATIONS) else 1)

found = contract(src)
for f in found:
    print('FAIL', f)
if found:
    sys.exit(1)
print('VOICE SLEEP PASS')
