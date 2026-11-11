"""0.2.107 send / insert modulation targets. The old per-voice FX d/w targets
(236..241) are now the voice's internal send (Snd), followed by the shared
insert targets iMix and I1..I4 (242..246); the node's target voice picks the
voice, the menu names I1..I4 after the insert routed on that voice.

Checks: stored target indices 0..235 are unchanged, the Cc2Text helpers on the
host (scroll order, knob fraction, LFO voice change, reverse lookup, clamp),
the production InsertFx.c on the host (an offset moves only its own voice,
mix -1 gives the dry signal), the modulation and menu wiring in the source,
the name tables fit the LCD. --mutate shows the checks bite."""
from pathlib import Path
import re, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
VS = r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat'
FILES = {
    'cc': 'Core/Src/menu/Cc2Text.c',
    'cch': 'Core/Inc/menu/CcNr2Text.h',
    'par': 'Core/Inc/Parameters.h',
    'pa': 'Core/Src/Soundengine/MIDI/ParameterArray.c',
    'mod': 'Core/Src/Soundengine/DSPAudio/modulationNode.c',
    'lfo': 'Core/Src/Soundengine/DSPAudio/lfo.c',
    'mix': 'Core/Src/Soundengine/DSPAudio/mixer.c',
    'ins': 'Core/Src/Soundengine/DSPAudio/FX/InsertFx.c',
    'menu': 'Core/Src/menu/menu.c',
    'step': 'Core/Src/menu/StepSelection.c',
    'fp': 'Core/Src/frontPanelParser.c',
    'midi': 'Core/Src/Soundengine/MIDI/MidiParser.c',
    'btn': 'Core/Src/buttonHandler.c',
}


def load():
    return {k: (ROOT / v).read_text(encoding='latin-1').replace('\r\n', '\n') for k, v in FILES.items()}


def strip(src):
    return re.sub(r'//[^\n]*|/\*.*?\*/', '', src, flags=re.S)


def body(src, sig):
    start = src.index(sig)
    i = src.index('{', start)
    depth = 0
    while True:
        depth += (src[i] == '{') - (src[i] == '}')
        if depth == 0:
            return src[start:i + 1]
        i += 1


def targets(src):
    s = strip(src)
    a = s.index('const ModTarg modTargets')
    return re.findall(r'\{(TEXT_\w+)\s*,\s*(PAR_\w+)\}', s[a:s.index('};', a)])


def head_targets():
    r = subprocess.run(['git', 'show', 'HEAD:' + FILES['cc']], cwd=ROOT, capture_output=True, text=True, errors='replace')
    return targets(r.stdout) if r.returncode == 0 else None


def run_cl(folder, cmd):
    r = subprocess.run(f'call "{VS}" -arch=x64 >nul && {cmd}', shell=True, cwd=folder,
                       capture_output=True, text=True, errors='replace')
    return r.returncode, (r.stdout + r.stderr).strip()


# ---------------------------------------------------------------- Cc2Text on the host
CC_MAIN = r'''
static unsigned checks, fails;
#define CHECK(c, m) do { checks++; if(!(c)) { fails++; printf("FAIL %s\n", m); } } while(0)
int main(void)
{
	paramToModTargetInit();
	CHECK(getNumModTargets() == 247, "247 targets");
	for(uint8_t v = 0; v < 6; v++) {
		uint8_t seen[256] = {0}, list[64]; int n = 0; uint8_t t = 0;
		for(int k = 0; k < 80; k++) { uint8_t nt = modTargetStepVoice(v, t, 1); if(nt == t) break; t = nt; list[n++] = t; }
		CHECK(n >= 6 && list[n-6] == MOD_TARGET_SND + v, "scroll: snd of the voice after its targets");
		for(int k = 0; k < 5; k++) CHECK(n >= 6 && list[n-5+k] == MOD_TARGET_INSERT + k, "scroll: imix, i1..i4 at the end");
		for(int k = 0; k < n; k++) { CHECK(!seen[list[k]], "scroll visits a target once"); seen[list[k]] = 1;
			CHECK(list[k] < MOD_TARGET_SND || list[k] == MOD_TARGET_SND + v || list[k] >= MOD_TARGET_INSERT, "scroll: no other voice's snd"); }
		for(int k = n - 1; k > 0; k--) { t = modTargetStepVoice(v, t, -1); CHECK(t == list[k-1], "scroll back the same way"); }
		CHECK(modTargetStepVoice(v, list[0], -1) == 0, "scroll back to off");
		uint8_t hit[256] = {0};
		for(int k = 0; k <= 1000; k++) { uint8_t f = modTargetFromFraction(v, k / 1000.f); hit[f] = 1;
			CHECK(!f || seen[f], "knob only gives the voice's targets"); }
		CHECK(modTargetFromFraction(v, 0.f) == 0 && modTargetFromFraction(v, 1.f) == MOD_TARGET_INSERT + 4, "knob ends: off .. i4");
		CHECK(hit[MOD_TARGET_SND + v], "knob reaches snd");
		for(int k = 0; k < n; k++) CHECK(hit[list[k]], "knob reaches every target of the voice");
		for(int k = 0; k < 5; k++) CHECK(hit[MOD_TARGET_INSERT + k], "knob reaches every insert target");
		CHECK(voiceFromModTargValue(MOD_TARGET_SND + v) == v + 1, "snd carries its voice");
		CHECK(modTargetFromParam(PAR_MODX_SND, v) == MOD_TARGET_SND + v, "reverse: snd by the node's voice");
		for(int d = -1; d <= 1; d++) CHECK(modTargetClampVoice(v, (uint8_t)(MOD_TARGET_SND + v), (int8_t)d) == MOD_TARGET_SND + v, "clamp keeps the voice's snd");
		if(v < 5) {	// voice 6: snd + 1 is already the first insert target
			CHECK(modTargetClampVoice(v, (uint8_t)(MOD_TARGET_SND + v + 1), 1) == MOD_TARGET_INSERT, "clamp: forward from snd to the insert targets");
			CHECK(modTargetClampVoice(v, (uint8_t)(MOD_TARGET_SND + v + 1), -1) == MOD_TARGET_SND + v, "clamp: back past snd stays on snd");
		}
		if(v > 0) CHECK(modTargetClampVoice(v, (uint8_t)(MOD_TARGET_SND + v - 1), -1) == (v == 3 ? 235 : modTargetVoiceOffsets[v].end), "clamp: another voice's snd backwards = end of the list (as before)");
		for(uint8_t w = 0; w < 6; w++) {
			CHECK(getModTargetIdxFromGapIdx(w, getModTargetGapIndex(MOD_TARGET_SND + v)) == MOD_TARGET_SND + w, "lfo voice change keeps snd");
			for(int k = 0; k < 5; k++)
				CHECK(getModTargetIdxFromGapIdx(w, getModTargetGapIndex(MOD_TARGET_INSERT + k)) == MOD_TARGET_INSERT + k, "lfo voice change keeps the insert target");
		}
		const uint8_t mid = (uint8_t)(modTargetVoiceOffsets[v].start + 3);
		CHECK(getModTargetIdxFromGapIdx(v, getModTargetGapIndex(mid)) == mid, "normal targets keep their gap mapping");
	}
	for(int k = 0; k < 5; k++) {
		CHECK(voiceFromModTargValue(MOD_TARGET_INSERT + k) == 0, "insert targets are shared");
		CHECK(modTargetFromParam((uint8_t)(PAR_MODX_IMIX + k), 0xff) == MOD_TARGET_INSERT + k, "reverse: insert targets");
		for(uint8_t v = 0; v < 6; v++) CHECK(modTargetClampVoice(v, (uint8_t)(MOD_TARGET_INSERT + k), 0) == MOD_TARGET_INSERT + k, "clamp keeps insert targets");
	}
	CHECK(modTargetFromParam(PAR_MODX_SND, 0xff) == 0, "reverse: snd without a voice is off");
	CHECK(modTargetFromParam(FAKE_PAR(50), 2) == 50, "reverse: normal params unchanged");
	CHECK(modTargetClampVoice(0, 250, 0) == MOD_TARGET_INSERT + 4, "clamp past the end");
	printf("%s %u assertions\n", fails ? "CC TARGETS FAIL" : "CC TARGETS PASS", checks);
	return fails != 0;
}
'''


def cc_harness(s):
    cc = s['cc']
    a = cc.index('const ModTargetVoiceOffset modTargetVoiceOffsets')
    b = cc.index('uint8_t modTargetFromFraction')
    helpers = cc[a:cc.index('\n}\n', b) + 3].replace('_Static_assert(', 'STATIC_ASSERT(')
    entries = targets(cc)
    pars = s['par'][s['par'].index('#define PAR_MODX_SND'):]
    pars = pars[:pars.index('#define PAR_MODX_LAST')] + '#define PAR_MODX_LAST\tPAR_MODX_I4\n'
    consts = '\n'.join(re.findall(r'#define MOD_TARGET_\w+\s+\d+', s['cch']))
    table = []
    for i, (_, par) in enumerate(entries):
        table.append('{0,%s}' % (par if par.startswith('PAR_MODX') else 'FAKE_PAR(%d)' % i))
    pre = '\n'.join([
        '#include <stdint.h>', '#include <stdio.h>',
        '#define pgm_read_byte(p) (*(p))', '#define pgm_read_word(p) (*(p))', '#define PROGMEM',
        '#define STATIC_ASSERT(c, m) typedef char static_assert_[(c) ? 1 : -1]',
        '#define END_OF_SOUND_PARAMETERS 256',
        '#define PAR_UNUSED_1 222', '#define PAR_UNUSED_2 223', '#define PAR_UNUSED_3 224',
        '#define PAR_UNUSED_4 225', '#define PAR_UNUSED_5 226', '#define PAR_UNUSED_6 227',
        '#define FAKE_PAR(i) ((i) < 222 ? (i) : (i) + 6)	// unique, clear of the PAR_MODX numbers',
        pars, consts,
        'typedef struct { uint8_t nameIdx; uint16_t param; } ModTarg;',
        'typedef struct { uint8_t start; uint8_t end; } ModTargetVoiceOffset;',
        'const ModTarg modTargets[] = {' + ','.join(table) + '};',
        'uint8_t getNumModTargets(); uint8_t voiceFromModTargValue(uint8_t val);',
        'uint8_t modTargetClampVoice(uint8_t voice,uint8_t target,int8_t direction);',
        'void paramToModTargetInit(); uint8_t modTargetFromParam(uint8_t param,uint8_t voice);',
    ])
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        (Path(folder) / 'cc.c').write_text(pre + '\n' + helpers + '\n' + CC_MAIN, encoding='latin-1')
        rc, out = run_cl(folder, 'cl /nologo /W3 /TC cc.c >nul && cc.exe')
    return [] if rc == 0 and 'PASS' in out else ['cc harness: ' + out[-600:]]


# ---------------------------------------------------------------- InsertFx on the host
INS_MAIN = r'''
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "Soundengine/DSPAudio/FX/InsertFx.h"
static unsigned checks, fails;
#define CHECK(c, m) do { checks++; if(!(c)) { fails++; printf("FAIL %s\n", m); } } while(0)
#define N 32
static void sine(int16_t *b, int k, double a) { for(int i = 0; i < N; i++) b[i] = (int16_t)(a * sin((k * N + i) * 0.07)); }
/* two voices with the same insert; offset on voice 0 only (slot, value) */
static void run(uint8_t type, int slot, float off, int16_t out0[200][N], int16_t out1[200][N])
{
	InsertFx_init();
	for(int k = 0; k < 200; k++) {
		InsertFx_clearMod();
		if(slot >= 0) InsertFx_addMod(0, (uint8_t)slot, off);
		sine(out0[k], k, 9000); sine(out1[k], k, 9000);
		InsertFx_process(0, type, out0[k], N);
		InsertFx_process(1, type, out1[k], N);
	}
}
static int16_t a0[200][N], a1[200][N], b0[200][N], b1[200][N];
int main(void)
{
	for(uint8_t t = 0; t < INSERT_FX_COUNT; t++)
		for(int slot = INS_MOD_MIX; slot < INS_MOD_SLOTS; slot++) {
			if(InsertFx_slotValue(t, (uint8_t)(slot - INS_MOD_MIX)) == INS_SLOT_NONE) continue;
			run(t, -1, 0.f, a0, a1);
			run(t, slot, slot == INS_MOD_MIX ? -0.5f : 0.4f, b0, b1);
			CHECK(!memcmp(a1, b1, sizeof a1), "an offset on voice 1 leaves voice 2 alone");
			CHECK(memcmp(a0, b0, sizeof a0) != 0, "the offset changes its own voice");
		}
	/* mix -1: the insert is bypassed exactly */
	for(uint8_t t = 0; t < INSERT_FX_COUNT; t++) {
		InsertFx_init(); int ok = 1;
		for(int k = 0; k < 50; k++) { int16_t x[N], y[N]; sine(x, k, 12000); memcpy(y, x, sizeof y);
			InsertFx_clearMod(); InsertFx_addMod(2, INS_MOD_MIX, -1.f); InsertFx_process(2, t, y, N);
			if(t != INSERT_FX_FLANGER && t != INSERT_FX_PHASER && memcmp(x, y, sizeof x)) ok = 0; }
		CHECK(ok, "mix offset -1 gives the dry signal");
	}
	/* the offsets are per block: cleared, the next block runs on the stored settings again */
	run(INSERT_FX_DIST, -1, 0.f, a0, a1);
	InsertFx_init();
	for(int k = 0; k < 200; k++) {
		InsertFx_clearMod();
		if(k < 0) InsertFx_addMod(0, INS_MOD_I1, 1.f);
		sine(b0[k], k, 9000); InsertFx_process(0, INSERT_FX_DIST, b0[k], N);
	}
	CHECK(!memcmp(a0, b0, sizeof a0), "no offset: same as before 0.2.107");
	CHECK(InsertFx_slotValue(INSERT_FX_COUNT, 0) == INS_SLOT_NONE && InsertFx_slotValue(0, INS_MOD_INSERT_SLOTS) == INS_SLOT_NONE, "slot range");
	printf("%s %u assertions\n", fails ? "INS TARGETS FAIL" : "INS TARGETS PASS", checks);
	return fails != 0;
}
'''


def ins_harness(s):
    inc = ROOT / 'Core/Inc'
    fx = ROOT / 'Core/Src/Soundengine/DSPAudio/FX'
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        (Path(folder) / 'InsertFx.c').write_text(s['ins'], encoding='latin-1')
        (Path(folder) / 'h.c').write_text(INS_MAIN, encoding='latin-1')
        rc, out = run_cl(folder, f'cl /nologo /W3 /TC /I"{inc}" /Fe:h.exe h.c InsertFx.c "{fx / "Phaser.c"}" "{fx / "Flanger.c"}" >nul && h.exe')
    return [] if rc == 0 and 'PASS' in out else ['insert harness: ' + out[-600:]]


# ---------------------------------------------------------------- source contract
def contract(s):
    p = []
    now, old = targets(s['cc']), head_targets()
    if len(now) != 247:
        p.append(f'modTargets has {len(now)} entries, expected 247')
    if old is not None and [x[1] for x in now[:236]] != [x[1] for x in old[:236]]:
        p.append('stored target indices 0..235 changed (old kits)')	# names may differ, the params may not
    if now[236:242] != [('TEXT_FX_SEND1', 'PAR_MODX_SND')] * 6:
        p.append('236..241 are not the voice send targets')
    if [x[1] for x in now[242:247]] != ['PAR_MODX_IMIX', 'PAR_MODX_I1', 'PAR_MODX_I2', 'PAR_MODX_I3', 'PAR_MODX_I4']:
        p.append('242..246 are not imix, i1..i4')
    par = s['par']
    for k, name in enumerate(['SND', 'IMIX', 'I1', 'I2', 'I3', 'I4']):
        if not re.search(rf'#define PAR_MODX_{name}\s+PAR_UNUSED_{k + 1}\b', par):
            p.append(f'PAR_MODX_{name} is not PAR_UNUSED_{k + 1} (same order as the insert mod slots)')
    if re.search(r'parameterArray\[PAR_(UNUSED_[1-6]|MODX_\w+)\]\.ptr', s['pa']):
        p.append('a modulation-only target got a parameter pointer')
    upd = strip(body(s['mod'], 'void modNode_updateValue(ModulationNode* vm, float val)'))
    i, j = upd.find('if(destination >= PAR_MODX_FIRST && destination <= PAR_MODX_LAST) {'), upd.find('if(!p->ptr)')
    if i < 0 or j < 0 or i > j or 'InsertFx_addMod(voice, (uint8_t)(destination - PAR_MODX_FIRST)' not in upd:
        p.append('send/insert targets are not caught before the pointer check')
    rst = strip(body(s['mod'], 'void modNode_resetTargets()'))
    if 'InsertFx_clearMod();' not in rst:
        p.append('the offsets are not cleared every block')
    tv = strip(body(s['mod'], 'static uint8_t modNode_targetVoice(const ModulationNode* vm)'))
    if 'PAR_VOICE_LFO1 + i' not in tv or 'lfo_randomStepTargetVoice(vm)' not in tv or 'vm - &velocityModulators[0]' not in tv:
        p.append('the node target voice misses velocity, LFO or random step')
    if 'activeParameters[PAR_RPS_VOI1+i]' not in strip(body(s['lfo'], 'uint8_t lfo_randomStepTargetVoice(const ModulationNode *node)')):
        p.append('random step target voice not from its voice setting')
    if 'insertFx_mod[voiceNr][INS_MOD_SND]' not in strip(s['mix']):
        p.append('the voice send ignores the snd offset')
    m = strip(s['menu'])
    if 'const uint8_t nmt=MOD_TARGET_SND;' not in m or m.count('(MOD_TARGET_SND-1)') != 3:
        p.append('automation can pick send/insert targets')
    if 'value>=MOD_TARGET_SND' not in strip(s['step']):
        p.append('step selection automation can pick send/insert targets')
    for key, need in (('fp', 2), ('midi', 2)):
        if strip(s[key]).count('modTargetFromParam(') != need:
            p.append(f'{FILES[key]}: reverse lookup without the voice')
    btn = strip(body(s['btn'], 'uint8_t buttonHandler_lockParameter(uint16_t parameter,uint8_t value,uint8_t remove)'))
    if 'parameter==PAR_FX_DRY_WET)supported=1' not in btn:
        p.append('FX d/w is no longer lockable')
    init = strip(body(s['cc'], 'void paramToModTargetInit()'))
    if 'continue' not in init:
        p.append('paramToModTarget maps snd to one voice')
    for fn in ('static void menu_displayModTargetFull(uint8_t curParmVal, uint8_t voice)',
               'static void menu_displayModTargetShort(uint8_t curParmVal, char *valueAsText, char inclVoice, uint8_t voice)'):
        if 'menu_modTargetXNames(curParmVal,voice' not in strip(body(s['menu'], fn)):
            p.append(fn.split('(')[0] + ': no dynamic insert names')
    if 'mixer_audioRouting[voice]' not in strip(body(s['menu'], 'static uint8_t menu_insTypeOfVoice(uint8_t voice)')):
        p.append('insert names not from the voice routing')
    if m.count('menu_modTargetVoice(parNr)') < 5:
        p.append('a target display does not pass the voice')
    # name tables: the LCD fields and the slot table
    def table(name):
        t = re.search(name + r'\[[^=]*=\{(.*?)\};', s['menu'], re.S)
        return re.findall(r'"([^"]*)"', t.group(1)) if t else []
    shorts, longs = table('menu_insShortName'), table('menu_insLongName')
    types, nshort, nlong = table('menu_insTypeName'), table('menu_insNoneShort'), table('menu_insNoneLong')
    if len(shorts) != 30 or len(longs) != 30 or len(types) != 6 or len(nshort) != 5 or len(nlong) != 5:
        p.append('insert name tables incomplete')
    else:
        if any(len(x) != 3 for x in shorts + nshort):
            p.append('a short insert name is not 3 letters')
        if any(len(x) > 8 for x in longs + nlong) or any(len(x) > 7 for x in types):
            p.append('an insert name does not fit the LCD field')
        slots = re.findall(r'\[INSERT_FX_\w+\]\s*=\s*\{([^}]*)\}', s['ins'])
        for t, row in enumerate(slots):
            for k, v in enumerate(x.strip() for x in row.split(',')):
                if (v == 'INS_SLOT_NONE') != shorts[t * 5 + k].endswith('-'):
                    p.append(f'insert name {shorts[t * 5 + k]} does not match the slot table')
    return p


def run(s):
    return contract(s) + cc_harness(s) + ins_harness(s)


MUTATIONS = {
    'kit-index-moved': ('cc', '{TEXT_SNARE_LAYER_MODE,PAR_SNARE_LAYER_MODE},      //235\n', ''),
    'intercept-after-ptr': ('mod', '\tif(destination >= PAR_MODX_FIRST && destination <= PAR_MODX_LAST) {', '\tif(!p->ptr && destination >= PAR_MODX_FIRST && destination <= PAR_MODX_LAST) {'),
    'no-clear': ('mod', '\tInsertFx_clearMod();\t// 0.2.107', '\t// 0.2.107'),
    'lfo-own-voice': ('mod', 'const uint8_t v = activeParameters[PAR_VOICE_LFO1 + i];', 'const uint8_t v = (uint8_t)(i + 1);'),
    'snd-not-modulated': ('mix', ' + insertFx_mod[voiceNr][INS_MOD_SND]', ''),
    'autom-all': ('menu', 'const uint8_t nmt=MOD_TARGET_SND;', 'const uint8_t nmt=getNumModTargets();'),
    'midi-reverse-plain': ('midi', 'modTargetFromParam(destination,voice)', 'paramToModTarget[destination]'),
    'dw-not-lockable': ('btn', '    if(parameter==PAR_FX_DRY_WET)supported=1;\n', ''),
    'init-maps-snd': ('cc', '\t\tif(par>=PAR_MODX_FIRST && par<=PAR_MODX_LAST)continue;', ''),
    'static-names': ('menu', '\tif(menu_modTargetXNames(curParmVal,voice,&cat,&lng,&shrt)) {\t// 0.2.107 3 letters', '\tif(0) {\t// 0.2.107 3 letters'),
    'long-name': ('menu', '"Thresh"', '"Threshold"'),
    'ring-name': ('menu', '{"iMx","iFq","i2-","i3-","i4-"}', '{"iMx","iFq","iX-","i3-","iXX"}'),
    'snare-order-no-insert': ('cc', 'MOD_TARGET_SND+3,\n\tMOD_TARGET_INSERT,MOD_TARGET_INSERT+1,MOD_TARGET_INSERT+2,MOD_TARGET_INSERT+3,MOD_TARGET_INSERT+4};', 'MOD_TARGET_SND+3};'),
    'fraction-no-insert': ('cc', '+1+MOD_TARGET_INSERT_SLOTS);\n\tunsigned ordinal', '+1);\n\tunsigned ordinal'),
    'gap-insert-off': ('cc', '\t\treturn (uint8_t)(MOD_TARGET_INSERT+gapidx-(NUM_TOT_TARGETS+8));', '\t\treturn 0;'),
    'insert-voice': ('cc', '\tif(val>=MOD_TARGET_INSERT)return 0;', '\tif(val>=MOD_TARGET_INSERT)return 1;'),
    'clamp-insert': ('cc', '\tif(target>=MOD_TARGET_INSERT)return target<', '\tif(target>=MOD_TARGET_INSERT+9)return target<'),
    'reverse-snd-voice6': ('cc', 'return voice<6 ? (uint8_t)(MOD_TARGET_SND+voice) : 0;\n\tif(param>PAR_MODX_SND', 'return (uint8_t)(MOD_TARGET_SND+5);\n\tif(param>PAR_MODX_SND'),
    'ins-mod-shared': ('ins', 'const float *m = &insertFx_mod[voice][INS_MOD_MIX];', 'const float *m = &insertFx_mod[0][INS_MOD_MIX];'),
    'ins-mod-ignored': ('ins', 'float value = (float)ins_values[index] + m[k] * max;', 'float value = (float)ins_values[index];'),
}

src = load()
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        m = dict(src)
        assert m[key].count(old) == 1, name
        m[key] = m[key].replace(old, new)
        hit = bool(run(m))
        caught += hit
        print(name, 'caught' if hit else 'MISSED')
    print(f'{caught}/{len(MUTATIONS)} mutations caught')
    sys.exit(0 if caught == len(MUTATIONS) else 1)

found = run(src)
for f in found:
    print('FAIL', f)
if found:
    sys.exit(1)
print('INSERT TARGETS PASS')
