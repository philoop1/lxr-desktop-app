"""Source contract for Mutador 0.2.59 save fixes.

- A real pattern or kit save rewrites the autosave copy (tmp.pat / tmp.snd),
  so an older copy cannot overwrite it when the device starts.
- tmp.pat stores the slot it was written for, not always the played pattern.
- The I2S audio DMA interrupts run above the TIM2 save-time sample interrupt.
- Both pattern save paths show the save timing display.
- 0.2.60: the project save deletes the tmp folder before the save interrupt
  stops, a new project keeps audio running while it is deleted, and a kit load
  from the Load page shows the measurement after all parameters were sent.
- 0.2.62: the transfer (import/export) page keeps the sample interrupt
  running around its SD access, so turning the encoder does not click.
--mutate shows that each check catches a broken version.
"""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
FILES = {
    'menu': root / 'Core/Src/menu/menu.c',
    'button': root / 'Core/Src/buttonHandler.c',
    'preset': root / 'Core/Src/Preset/presetManager.c',
    'main': root / 'Core/Src/main.c',
}


def load():
    return {k: v.read_text(encoding='latin-1').replace('\r\n', '\n') for k, v in FILES.items()}


def problems(src):
    out = []
    menu, button, preset, main = src['menu'], src['button'], src['preset'], src['main']
    m = re.search(r'preset_savePatternSD\(menu_selectedPresetNr\[SAVE_TYPE_PATTERN\]\);(.*?)break;', menu, re.S)
    if not m or 'preset_refreshTmpPat(menu_selectedPresetNr[SAVE_TYPE_PATTERN]);' not in m.group(1):
        out.append('Save page pattern save does not refresh tmp.pat')
    m = re.search(r'preset_saveDrumsetSD\(menu_selectedPresetNr\[SAVE_TYPE_KIT\],0\);(.*?)break;', menu, re.S)
    if not m or 'preset_refreshTmpKit();' not in m.group(1):
        out.append('kit save does not refresh tmp.snd')
    m = re.search(r'preset_savePatternSD\(seqButtonPressed \+ 16 \* menu_activePatternBank\);(.*?)menu_activePage = PATTERN_SAVE_PAGE_OK;', button, re.S)
    if not m or 'preset_refreshTmpPat(menu_selectedPresetNr[SAVE_TYPE_PATTERN]);' not in m.group(1):
        out.append('pattern save page does not refresh tmp.pat')
    if not m or 'menu_showSaveDiag();' not in m.group(1):
        out.append('pattern save page does not show the save timing')
    if 'saveDiag_begin();\n\t\t\t\tseq_patternSet.shuffle[seqButtonPressed' not in button:
        out.append('pattern save page does not start the measurement')
    m = re.search(r'static FRESULT preset_saveTmpPatNr\(uint8_t presetNr\)\n\{(.*?)\n\}', preset, re.S)
    if not m or 'f_write((FIL*)&SDFile,(void*)&presetNr,1,&bytesWritten);' not in m.group(1) \
            or 'menu_playedPattern' in m.group(1):
        out.append('tmp.pat does not store the saved slot')
    m = re.search(r'void preset_refreshTmpPat\(uint8_t presetNr\)\n\{(.*?)\n\}', preset, re.S)
    if not m or 'preset_patDirty = 0;' not in m.group(1) or 'preset_saveTmpPatNr(presetNr);' not in m.group(1):
        out.append('preset_refreshTmpPat does not clear the timer and write the slot')
    m = re.search(r'void preset_refreshTmpKit\(void\)\n\{(.*?)\n\}', preset, re.S)
    if not m or 'preset_kitDirty = 0;' not in m.group(1) or 'preset_saveTmpKit();' not in m.group(1):
        out.append('preset_refreshTmpKit does not clear the timer and write the kit')
    tim2 = int(re.search(r'HAL_NVIC_SetPriority\(TIM2_IRQn, (\d+), 0\)',
                         (root / 'Core/Src/stm32f7xx_hal_msp.c').read_text(encoding='latin-1')).group(1))
    for stream in ('DMA1_Stream4_IRQn', 'DMA1_Stream5_IRQn'):
        p = re.search(r'HAL_NVIC_SetPriority\(' + stream + r', (\d+), 0\)', main)
        if not p or int(p.group(1)) >= tim2:
            out.append(stream + ' is not above the TIM2 sample interrupt')
    m = re.search(r'FRESULT preset_saveProject\(uint8_t presetNr\)\n\{(.*?)\n\}', preset, re.S)
    body = m.group(1) if m else ''
    tail = body[body.rfind('preset_clearTmpFolder();') if 'preset_clearTmpFolder();' in body else 0:]
    if 'preset_clearTmpFolder();' not in body or 'HAL_TIM_Base_Stop_IT(&htim2);' not in tail:
        out.append('project save stops the save interrupt before the tmp folder is deleted')
    m = re.search(r'FRESULT preset_createProject\(uint8_t presetNr\)\n\{(.*?)\n\}', preset, re.S)
    body = m.group(1) if m else ''
    i = body.find('preset_clearTmpFolder();')
    if i < 0 or 'HAL_TIM_Base_Start_IT(&htim2);' not in body[:i] or 'HAL_TIM_Base_Stop_IT(&htim2);' not in body[i:]:
        out.append('new project deletes the tmp folder without the save interrupt')
    m = re.search(r'case SAVE_TYPE_KIT:\n#if 1\n(.*?)break;', menu, re.S)
    body = m.group(1) if m else ''
    if 'saveDiag_begin();' not in body or 'menu_kitLoadDiag = 1;' not in body:
        out.append('kit load does not start the measurement')
    if 'menu_kitLoadDiagTick();' not in main or 'if(menu_kitLoadDiag && !preset_morphBusy())' not in menu:
        out.append('kit load measurement is not shown after the parameters were sent')
    m = re.search(r'static void menu_handleTransfer\(int8_t inc,uint8_t clicked\)\n\{(.*?)\n\}', menu, re.S)
    body = m.group(1) if m else ''
    i, j, k = body.find('menu_transferSdBegin();'), body.find('menu_handleTransferSd(inc,clicked);'), body.find('menu_transferSdEnd(timerWasOn);')
    if not (0 <= i < j < k):
        out.append('transfer page reads the SD card without the sample interrupt')
    m = re.search(r'void menu_transferSelectType\(uint8_t pattern\)\n\{(.*?)\n\}', menu, re.S)
    body = m.group(1) if m else ''
    i, j, k = body.find('menu_transferSdBegin();'), body.find('menu_transferRefreshName(0);'), body.find('menu_transferSdEnd(timerWasOn);')
    if not (0 <= i < j < k):
        out.append('transfer type selection reads the SD card without the sample interrupt')
    m = re.search(r'static uint8_t menu_transferSdBegin\(void\)\n\{(.*?)\n\}', menu, re.S)
    if not m or 'if(!timerWasOn) HAL_TIM_Base_Start_IT(&htim2);' not in m.group(1):
        out.append('transfer SD window does not start the sample interrupt')
    m = re.search(r'static void menu_transferSdEnd\(uint8_t timerWasOn\)\n\{(.*?)\n\}', menu, re.S)
    if not m or 'if(!timerWasOn) HAL_TIM_Base_Stop_IT(&htim2);' not in m.group(1):
        out.append('transfer SD window does not restore the sample interrupt')
    return out


MUTATIONS = {
    'menu-no-tmp-pat': ('menu', '\t\t\t\t\t\t\tpreset_refreshTmpPat(menu_selectedPresetNr[SAVE_TYPE_PATTERN]);\n', ''),
    'kit-no-tmp': ('menu', '\t\t\t\t\t\t\tpreset_refreshTmpKit();\n', ''),
    'page-no-tmp-pat': ('button', '\t\t\t\tpreset_refreshTmpPat(menu_selectedPresetNr[SAVE_TYPE_PATTERN]);\n', ''),
    'page-no-diag': ('button', '\t\t\t\tpreset_refreshTmpPat(menu_selectedPresetNr[SAVE_TYPE_PATTERN]);\n\t\t\t\tmenu_showSaveDiag();\n', '\t\t\t\tpreset_refreshTmpPat(menu_selectedPresetNr[SAVE_TYPE_PATTERN]);\n'),
    'tmp-played-pattern': ('preset', 'f_write((FIL*)&SDFile,(void*)&presetNr,1,&bytesWritten);', 'f_write((FIL*)&SDFile,(void*)&menu_playedPattern,1,&bytesWritten);'),
    'refresh-keeps-timer': ('preset', '\tpreset_patDirty = 0;\n\tpreset_saveTmpPatNr(presetNr);', '\tpreset_saveTmpPatNr(presetNr);'),
    'stop-before-clear': ('preset', '\tpreset_clearTmpFolder();\n#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ\n\t\t\tHAL_TIM_Base_Stop_IT(&htim2);\t//calc sample interrupt - prio 1\n#else\n\n#endif\n\n\treturn FR_OK;',
                          '#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ\n\t\t\tHAL_TIM_Base_Stop_IT(&htim2);\t//calc sample interrupt - prio 1\n#else\n\n#endif\n\tpreset_clearTmpFolder();\n\n\treturn FR_OK;'),
    'new-project-unwrapped': ('preset', '\tif(!timerWasOn) HAL_TIM_Base_Start_IT(&htim2);\n', ''),
    'kit-load-no-diag': ('menu', '\t\t\t\t\tmenu_kitLoadDiag = 1;\n', ''),
    'kit-diag-too-early': ('menu', 'if(menu_kitLoadDiag && !preset_morphBusy())', 'if(menu_kitLoadDiag)'),
    'transfer-unwrapped': ('menu', '    const uint8_t timerWasOn=menu_transferSdBegin();\n    menu_handleTransferSd(inc,clicked);\n', '    const uint8_t timerWasOn=1;\n    menu_handleTransferSd(inc,clicked);\n'),
    'select-type-unwrapped': ('menu', '    menu_transfer.stage=2;\n    const uint8_t timerWasOn=menu_transferSdBegin();\n', '    menu_transfer.stage=2;\n    const uint8_t timerWasOn=1;\n'),
    'window-no-start': ('menu', '\tif(!timerWasOn) HAL_TIM_Base_Start_IT(&htim2);\n\treturn timerWasOn;', '\treturn timerWasOn;'),
    'window-stays-on': ('menu', '\t/* an inner save (tmp.pat) may already have stopped it */\n\tif(!timerWasOn) HAL_TIM_Base_Stop_IT(&htim2);\n', ''),
    'dma-old-prio': ('main', 'HAL_NVIC_SetPriority(DMA1_Stream4_IRQn, 3, 0);', 'HAL_NVIC_SetPriority(DMA1_Stream4_IRQn, 5, 0);'),
}

src = load()
if '--mutate' in sys.argv:
    caught = 0
    for name, (key, old, new) in MUTATIONS.items():
        mutated = dict(src)
        assert mutated[key].count(old) == 1, name
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
    print('SAVE TMP REFRESH PASS')
sys.exit(1 if found else 0)
