"""Source contract for the Mutador 0.2.61 flam presets.

- The project's 15 flam presets are stored in prj.nfo after the name, and as
  /tmp/flam.cfg two seconds after an edit; the device loads the tmp copy before
  the tmp patterns, so old patterns convert against the edited presets.
- Loading or creating a project starts from the factory presets.
- Pattern files no longer carry the per-step flam velocity (FLV1).
- The third Step page edits the preset; its values are not sent as globals and
  are not applied to the selected steps.
- 0.2.63: presets carry stp (FLM2, FLM1 still loads with stp 1), the page
  shows stp instead of fla, stop and pattern change end a running long flam,
  and the encoder on the Step page steps over empty places.
--mutate shows that each check catches a broken version.
"""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
FILES = {
    'preset': root / 'Core/Src/Preset/presetManager.c',
    'menu': root / 'Core/Src/menu/menu.c',
    'pages': root / 'Core/Inc/menu/menuPages.h',
    'steps': root / 'Core/Src/menu/StepSelection.c',
    'seq': root / 'Core/Src/Soundengine/Sequencer/sequencer.c',
    'front': root / 'Core/Src/frontPanelParser.c',
}


def load():
    return {k: v.read_text(encoding='latin-1').replace('\r\n', '\n') for k, v in FILES.items()}


def body(src, head):
    m = re.search(re.escape(head) + r'\n?\{(.*?)\n\}', src, re.S)
    return m.group(1) if m else ''


def problems(src):
    out = []
    preset, menu, pages, steps, seq, front = (src[k] for k in ('preset', 'menu', 'pages', 'steps', 'seq', 'front'))
    save = body(preset, 'FRESULT preset_saveProject(uint8_t presetNr)')
    i = save.find('res = f_write(&SDFile, savefileNames[presetNr][PROJECT_NAMES], 8, &bytesWritten);')
    j = save.find('preset_writeFlamPresets();')
    k = save.find('preset_finishFile(res, 8u + FLAM_FILE_BYTES)')
    if i < 0 or not (i < j < k):
        out.append('project save does not write the flam presets after the name in prj.nfo')
    load_ = body(preset, 'FRESULT preset_loadProject(uint8_t presetNr, uint8_t clearTmp)')
    r = load_.find('seq_flamResetPresets();')
    o = load_.find('res = f_open((FIL*)&SDFile,"prj.nfo"')
    n = load_.find('if(bytesRead == 8) preset_readFlamPresets();')
    p = load_.find('preset_loadDrumsetSD(i, 0);')
    if not (0 <= r < o < n < p):
        out.append('project load does not reset and then read the flam presets before the patterns')
    if 'seq_flamResetPresets();' not in body(preset, 'FRESULT preset_createProject(uint8_t presetNr)'):
        out.append('new project keeps the flam presets of the old project')
    tmp = body(preset, 'FRESULT loadTmpFolderFiles()')
    if not (0 <= tmp.find('preset_loadTmpFlam();') < tmp.find('preset_loadPatternSD(i);')):
        out.append('tmp flam presets are not loaded before the tmp patterns')
    timer = body(preset, 'void preset_processTimer()')
    if 'if(preset_saveTmpFlam() == FR_OK)' not in timer or \
            'if(preset_flamDirty && HAL_GetTick()-preset_flamTimer >= PRESET_SAVE_TIME)' not in timer:
        out.append('edited flam presets are not written to tmp after the save time')
    if 'preset_writeFlamVelocity' in preset:
        out.append('pattern files still write the per-step flam velocity')
    rd = body(preset, 'static uint8_t preset_readFlamPresets(void)')
    if 'checksum!=data[bytes-1u]' not in rd or 'seq_flamPresetsChanged();' not in rd:
        out.append('flam preset file is read without checksum or without preparing the masks')
    m = re.search(r'// 0\.2\.61 flam preset page.*?\n(.*?)\n(.*?)\n', pages)
    if not m or 'PAR_FLAM_STEPS' not in m.group(2) or 'PAR_STEP_FLAM_VELO' not in m.group(2) or 'PAR_FLAM_ACCEL' not in m.group(2):
        out.append('third Step page does not edit the flam preset')
    if m and 'PAR_FLAM_SLOT' in m.group(2):
        out.append('third Step page still shows the preset choice')
    wr = body(preset, 'static FRESULT preset_writeFlamPresets(void)')
    if "{'F','L','M','2'}" not in wr or 'd[6]=p->steps;' not in wr:
        out.append('flam presets are written without the steps')
    if '!memcmp(data,"FLM1",4)' not in rd or 'p->steps=width>FLAM_FILE_V1_WIDTH ? d[6] : 1;' not in rd:
        out.append('flam presets of 0.2.61/0.2.62 are no longer read')
    if 'seq_longFlamCancel();' not in body(seq, 'void seq_setRunning(uint8_t isRunning)'):
        out.append('stop keeps a long flam running')
    if 'seq_activePattern = seq_pendingPattern;\n\t\tseq_longFlamCancel();' not in seq:
        out.append('pattern change keeps a long flam running')
    move = body(menu, 'static void menu_moveToMenuItem(int8_t inc)')
    if 'if(menu_activePage==SEQ_PAGE && allowedEmpty--)\n\t\t\tgoto checkvalid;' not in move:
        out.append('encoder stops at empty places of the Step page')
    if 'PAR_STEP_FLAM_VELO' in steps:
        out.append('flam velocity is applied to the selected steps')
    if '(i<PAR_FLAM_SLOT || i>PAR_FLAM_STEPS)' not in menu:
        out.append('flam preset values are sent as globals at start')
    edit = body(menu, 'static uint8_t menu_flamEditParam(uint16_t paramNr,uint8_t value)')
    if 'preset_touchFlamTimer();' not in edit or 'seq_flamPresetsChanged();' not in edit:
        out.append('flam preset edit is not stored or not applied')
    glob = body(menu, 'void menu_parseGlobalParam(uint16_t paramNr, uint8_t value)')
    a = glob.find('if(menu_flamEditParam(paramNr,value))return;')
    b = glob.find('stepEdit_apply(')
    if a < 0 or a > b:
        out.append('flam preset edit is not handled before the step selection')
    if 'menu_flamEditSelect(frontParser_midiMsg.data2);' not in front:
        out.append('selecting a step does not show its flam preset')
    if 'seq_flamResetPresets();' not in body(seq, 'void seq_init()'):
        out.append('sequencer starts without flam presets')
    return out


MUTATIONS = {
    'no-prj-write': ('preset', 'res = preset_writeFlamPresets();', 'res = FR_OK;'),
    'no-prj-read': ('preset', '\tif(bytesRead == 8) preset_readFlamPresets();\n', ''),
    'load-keeps-old': ('preset', '\tseq_flamResetPresets();\n\tpreset_flamDirty = 0;\n\tres = f_open((FIL*)&SDFile,"prj.nfo"', '\tpreset_flamDirty = 0;\n\tres = f_open((FIL*)&SDFile,"prj.nfo"'),
    'create-keeps-old': ('preset', '\tseq_flamResetPresets();\n\tpreset_flamDirty = 0;\n\tpreset_flamShowEdited();\n', '\tpreset_flamDirty = 0;\n\tpreset_flamShowEdited();\n'),
    'no-tmp-load': ('preset', '\tpreset_loadTmpFlam();\n', ''),
    'no-tmp-save': ('preset', 'if(preset_saveTmpFlam() == FR_OK)', 'if(1)'),
    'no-checksum': ('preset', '    if(checksum!=data[bytes-1u])return 0;\n', ''),
    'no-page': ('pages', 'PAR_FLAM_STEPS,\t\tPAR_NONE', 'PAR_NONE,\t\tPAR_NONE'),
    'slot-on-page': ('pages', '\t\t\t\tPAR_FLAM_REPEATS,\tPAR_FLAM_GRID', '\t\t\t\tPAR_FLAM_SLOT,\tPAR_FLAM_GRID'),
    'no-steps-written': ('preset', '        d[6]=p->steps;\n', ''),
    'flm1-unread': ('preset', 'else if(!memcmp(data,"FLM1",4)', 'else if(0'),
    'stop-keeps-flam': ('seq', '\tseq_longFlamCancel();\n\tseq_running = isRunning;', '\tseq_running = isRunning;'),
    'switch-keeps-flam': ('seq', '\t\tseq_activePattern = seq_pendingPattern;\n\t\tseq_longFlamCancel();\n', '\t\tseq_activePattern = seq_pendingPattern;\n'),
    'encoder-stops': ('menu', '\t\tif(menu_activePage==SEQ_PAGE && allowedEmpty--)\n\t\t\tgoto checkvalid;\n', ''),
    'globals-send': ('menu', ' &&\n\t\t   (i<PAR_FLAM_SLOT || i>PAR_FLAM_STEPS))', ')'),
    'edit-not-stored': ('menu', '\tpreset_touchFlamTimer();\n\treturn 1;', '\treturn 1;'),
    'edit-after-steps': ('menu', '\tif(menu_flamEditParam(paramNr,value))return;\n', ''),
    'no-step-select': ('front', '\t\t\t\t\t\t\tmenu_flamEditSelect(frontParser_midiMsg.data2);\n', ''),
    'no-init': ('seq', '\tseq_flamResetPresets();\n', ''),
}

src = load()
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        mutated = dict(src)
        assert mutated[key].count(old) == 1, (name, mutated[key].count(old))
        mutated[key] = mutated[key].replace(old, new)
        hit = bool(problems(mutated))
        print(name, 'caught' if hit else 'MISSED')
        caught += hit
    print(f'{caught}/{len(MUTATIONS)} mutations caught')
    sys.exit(0 if caught == len(MUTATIONS) else 1)

found = problems(src)
for f in found:
    print('FAIL', f)
if not found:
    print('FLAM PRESETS PASS')
sys.exit(1 if found else 0)
