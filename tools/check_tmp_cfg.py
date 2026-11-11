"""0.2.88/0.2.89 autosave of the MUTA.CFG values (master filter and compressor, FX
sends, hm, hpd, project FX): a change is written 2 s later as /tmp/tmp.cfg,
like tmp.snd and tmp.pat, and restored exactly at boot before the kit.
Source contract; --mutate shows the checks bite."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
PM = root / 'Core/Src/Preset/presetManager.c'
MAIN = root / 'Core/Src/main.c'
MENU = root / 'Core/Src/menu/menu.c'


def load():
    return {'pm': PM.read_text(encoding='latin-1').replace('\r\n', '\n'),
            'main': MAIN.read_text(encoding='latin-1').replace('\r\n', '\n'),
            'menu': MENU.read_text(encoding='latin-1').replace('\r\n', '\n')}


def body(src, sig):
    start = src.index(sig)
    i = src.index('{', start)
    depth = 0
    while True:
        depth += (src[i] == '{') - (src[i] == '}')
        if depth == 0:
            return src[start:i + 1]
        i += 1


def contract(s):
    p = []
    pm = s['pm']
    snap = body(pm, 'static void preset_cfgSnapshot(')
    for field in ('PAR_FX_OUTPUT_MODE', 'PAR_HUMANIZE1', 'PAR_HIGH_DAMP', 'PAR_MCOMP_ON', 'PAR_FX_TYPE'):
        if field not in snap:
            p.append(f'snapshot misses {field}')
    timer = body(pm, 'static void preset_processCfgTimer(')
    if 'memcmp(preset_cfgSnap,now,sizeof(now))' not in timer or 'preset_cfgTimer=HAL_GetTick();' not in timer:
        p.append('a change does not restart the save timer')
    if 'HAL_GetTick()-preset_cfgTimer >= PRESET_SAVE_TIME' not in timer:
        p.append('no 2 s delay')
    if 'preset_cfgName="tmp.cfg";' not in timer or 'preset_cfgName="MUTA.CFG";' not in timer:
        p.append('autosave does not write tmp.cfg or leaves the name switched')
    # 0.2.98 the audio keeps running (timer) while tmp.cfg is written
    save = timer[timer.find('preset_cfgName="tmp.cfg";'):timer.find('preset_cfgName="MUTA.CFG";')]
    on, write, off = save.find('if(!timerWasOn) HAL_TIM_Base_Start_IT(&htim2);'), save.find('preset_savePerformanceExtension();'), save.find('if(!timerWasOn) HAL_TIM_Base_Stop_IT(&htim2);')
    if on < 0 or write < 0 or off < 0 or not on < write < off:
        p.append('the tmp.cfg autosave stops the audio while writing (click)')
    if 'preset_processCfgTimer();' not in body(pm, 'void preset_processTimer()'):
        p.append('the timer is not polled')
    boot = body(pm, 'void preset_loadTmpCfg(void)')
    if 'f_stat("tmp.cfg",&fno)==FR_OK' not in boot:
        p.append('a missing tmp.cfg would reset the values to defaults')
    if 'preset_cfgExact=1;' not in boot or 'menu_sendAllGlobals();' not in boot:
        p.append('boot restore is not exact or not applied')
    m = s['main']
    if m.find('preset_loadTmpCfg();') < 0 or m.find('preset_loadTmpCfg();') > m.find('preset_LoadTmpKit();'):
        p.append('tmp.cfg must load before the tmp kit')
    if '!preset_cfgExact && activeParameters[PAR_SHUFFLE_LOAD] == 0' not in pm:
        p.append('exact load still applies the lsh hold')
    # 0.2.89 last played pattern per project, its bank shown at boot and on project load
    proj = body(pm, 'FRESULT preset_loadProject(uint8_t presetNr, uint8_t clearTmp)')
    if 'seq_activePattern = preset_projectPattern;' not in proj or 'menu_activePatternBank = (uint8_t)(preset_projectPattern/16u);' not in proj:
        p.append('project load does not start the saved pattern in its bank')
    if 'data[23+PERFORMANCE_EXTRA_BYTES+PROJECT_FX_COUNT]=menu_playedPattern' not in pm:
        p.append('project save does not store the played pattern')
    i = m.find('preset_LoadTmpPat();')
    j = m.find('menu_activePatternBank = menu_playedPattern < NUM_PATTERN ? (uint8_t)(menu_playedPattern/16u) : 0;')
    if i < 0 or j < i:
        p.append('boot does not show the bank of the autosaved pattern')
    # 0.2.98 the unsaved snd field must not overwrite the loaded project FX type
    glob = body(s['menu'], 'void menu_sendAllGlobals()')
    if 'i!=PAR_SEND_FX' not in glob or 'activeParameters[PAR_SEND_FX]=FxBus_sendIndex(activeParameters[PAR_FX_TYPE]);' not in glob:
        p.append('loading globals resets the saved send FX (Tape) through snd')
    return p


MUTATIONS = {
    'cfg-no-timer': ('pm', '\t\tif(!timerWasOn) HAL_TIM_Base_Start_IT(&htim2);\n#endif\n\t\tconst FRESULT res', '#endif\n\t\tconst FRESULT res'),
    'cfg-timer-early-off': ('pm', '\t\tif(!timerWasOn) HAL_TIM_Base_Stop_IT(&htim2);\n#endif\n\t\tpreset_cfgName="MUTA.CFG";', '#endif\n\t\tpreset_cfgName="MUTA.CFG";'),
    'snd-overwrites': ('menu', 'if(i!=PAR_SEND_FX && i!=PAR_PATTERN_SCALE && ', 'if(i!=PAR_PATTERN_SCALE && '),
    'snd-stale': ('menu', '\tactiveParameters[PAR_SEND_FX]=FxBus_sendIndex(activeParameters[PAR_FX_TYPE]);\n', ''),
    'no-poll': ('pm', '\tpreset_processCfgTimer();\n', '\n'),
    'no-stat': ('pm', 'if(f_stat("tmp.cfg",&fno)==FR_OK) {', 'if(1) {'),
    'no-comp': ('pm', '\tmemcpy(s,&activeParameters[PAR_MCOMP_ON],7);\n', '\n'),
    'late-boot': ('main', 'preset_loadTmpCfg();\n//autosave kit\npreset_LoadTmpKit();\n', '//autosave kit\npreset_LoadTmpKit();\npreset_loadTmpCfg();\n'),
    'no-boot-bank': ('main', 'menu_activePatternBank = menu_playedPattern < NUM_PATTERN ? (uint8_t)(menu_playedPattern/16u) : 0;\n', ''),
    'no-project-bank': ('pm', '\t\tmenu_activePatternBank = (uint8_t)(preset_projectPattern/16u);\n', ''),
    'name-stays': ('pm', '\t\tpreset_cfgName="MUTA.CFG";\n\t\tif(res==FR_OK) preset_cfgDirty=0;', '\t\tif(res==FR_OK) preset_cfgDirty=0;'),
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
print('TMP CFG PASS')
