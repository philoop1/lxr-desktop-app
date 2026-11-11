"""0.2.98 the CPU value runs from the DMA block request to the ready block, so the
sequencer step and the main loop count; blocks that come too late are counted
and the diagnosis build shows them as a note. Source contract; --mutate shows
the checks bite."""
from pathlib import Path
import re, sys

root = Path(__file__).resolve().parents[1]
FILES = {
    'h': 'Core/Inc/Soundengine/AudioCodecManager.h',
    'acm': 'Core/Src/Soundengine/AudioCodecManager.c',
    'dma': 'Core/Src/Soundengine/cs4344_cs5343.c',
    'menu': 'Core/Src/menu/menu.c',
    'midi': 'Core/Src/Soundengine/MIDI/MidiParser.c',
    'main': 'Core/Src/main.c',
    'se': 'Core/Src/Soundengine/Soundengine.c',
}


def load():
    return {k: (root / v).read_text(encoding='latin-1').replace('\r\n', '\n') for k, v in FILES.items()}


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
    req = body(s['h'], 'static inline void audioCodec_blockRequested(void)')
    if 'bCurrentSampleValid != SAMPLE_VALID && audioCodec_lateBlocks < 0xffffu) audioCodec_lateBlocks++;' not in req:
        p.append('late blocks are not counted')
    if req.find('audioCodec_lateBlocks++') > req.find('audioCodec_blockRequest = DWT->CYCCNT;'):
        p.append('the request time must be taken after the late check')
    cb = body(s['dma'], 'IN_ITCM_RAM void HAL_I2S_TxCpltCallback(I2S_HandleTypeDef *hi2s)')
    i = cb.find('audioCodec_blockRequested();')
    j = cb.find('bCurrentSampleValid = 1-(dmaPtr&0x1);', cb.find('SPI3'))
    if i < 0 or j < 0 or i > j:
        p.append('the DMA request is not marked before the next block is asked for')
    end = body(s['acm'], 'void audioCodec_endCpuMeter(void)')
    if 'now - audioCodec_blockRequest' not in end:
        p.append('the CPU value still leaves out the sequencer step')
    if 'cycles = render;' not in end:
        p.append('no fallback for the first block and the save interrupt mode')
    cpu = body(s['menu'], 'void menu_updateCpuUse(void)')
    if '#if LXR_FREEZE_DIAG' not in cpu or 'menu_showNoteFor(line1, line2, MENU_CPU_NOTE_TICKS);' not in cpu or '(isLate ||' not in cpu:
        p.append('the diagnosis build does not show late blocks')
    # 0.2.99 a vlv/velo change only marks the work; the main loop applies one per pass
    acc = body(s['midi'], 'void midiParser_setAccentParameter(uint16_t param,uint8_t value)')
    if 'midiParser_applyVelocityDestination' in acc or 'midiParser_velocityPending[i]=0x7f;' not in acc:
        p.append('vlv applies all tracks at once (late audio block)')
    tick = body(s['midi'], 'uint8_t midiParser_velocityTick(void)')
    if tick.count('midiParser_applyVelocityDestination(') != 1 or 'return 1;' not in tick:
        p.append('the velo tick must apply exactly one destination per call')
    if 'midiParser_velocityTick();' not in s['main']:
        p.append('the main loop does not apply the pending velo work')
    # 0.2.100 extra block points after buttons and encoder; morph/MIDI stay out
    svc = body(s['se'], 'void soundengine_serviceAudio(void)')
    for bad in ('preset_morph_tick', 'uart_processMidi', 'usb_tick'):
        if bad in svc:
            p.append('serviceAudio must not run ' + bad + ' (morph advances per call)')
    intr = svc[:svc.find('#else')]
    if not (0 <= intr.find('__HAL_TIM_DISABLE_IT(&htim2, TIM_IT_UPDATE);') < intr.find('soundengine_calcNextSampleBlock();')
            and intr.find('seq_tick();') < intr.find('__HAL_TIM_ENABLE_IT(&htim2, TIM_IT_UPDATE);')):
        p.append('serviceAudio must lock TIM2 out while it renders (save mode)')
    # 0.2.106 render first, then the step: its work stays out of request -> ready
    for fn in ('void soundengine_serviceAudio(void)', 'void soundengine_process()'):
        b = re.sub(r'//[^\n]*|/\*.*?\*/', '', body(s['se'], fn), flags=re.S)
        for part in b.split('#else'):
            if 'seq_tick();' in part and not (0 <= part.find('soundengine_calcNextSampleBlock();') < part.find('seq_tick();')):
                p.append(fn + ': the step runs before the block (in the critical path)')
    m = s['main']
    for after in ('buttonHandler_tick();', 'menu_parseEncoder(encode_read4(),encode_readButton());'):
        i = m.find(after)
        nxt = m.find('soundengine_serviceAudio();', i)
        if i < 0 or nxt < 0 or nxt - i > 200:
            p.append('no audio block point right after ' + after)
    d = m.find('\t  dio_process();')
    if d < 0 or m.rfind('soundengine_serviceAudio();', 0, d) < d - 140:
        p.append('no audio block point right before dio_process (blocking SPI)')
    return p


MUTATIONS = {
    'acc-all-now': ('midi', 'if(oldDepth[i]!=newDepth)midiParser_velocityPending[i]=0x7f;', 'if(oldDepth[i]!=newDepth)for(uint8_t t=0;t<7;t++)midiParser_applyVelocityDestination(t,destination);'),
    'no-tick-call': ('main', '\t  midiParser_velocityTick(); // 0.2.99 spread vlv/velo changes over the loop passes\n', ''),
    'svc-after-encoder-gone': ('main', '\t  soundengine_serviceAudio(); // 0.2.100 nor behind the encoder and its repaint\n', ''),
    'svc-after-buttons-gone': ('main', '\t  soundengine_serviceAudio(); // 0.2.100 a due block does not wait behind buttons\n', ''),
    'svc-runs-morph': ('se', '\t__HAL_TIM_SetCounter(&htim2, 1950);\n\t__HAL_TIM_ENABLE_IT', '\t__HAL_TIM_SetCounter(&htim2, 1950);\n\tpreset_morph_tick();\n\t__HAL_TIM_ENABLE_IT'),
    'svc-no-lock': ('se', '\t/* same guard as soundengine_process: during a save TIM2 renders too */\n\t__HAL_TIM_DISABLE_IT(&htim2, TIM_IT_UPDATE);\n', ''),
    'no-count': ('h', 'audioCodec_lateBlocks++;', ';'),
    'no-mark': ('dma', '\t\t\t audioCodec_blockRequested(); // 0.2.98 CPU value and late blocks\n', ''),
    'render-only': ('acm', 'uint32_t cycles = now - audioCodec_blockRequest;', 'uint32_t cycles = now - cpuBlockStart;'),
    'no-note': ('menu', '\t\tmenu_showNoteFor(line1, line2, MENU_CPU_NOTE_TICKS);\n', ''),
    'svc-before-dio-gone': ('main', '\t  soundengine_serviceAudio(); // 0.2.106 a due block does not wait behind the blocking SPI of dio_process\n', ''),
    'step-before-block': ('se', '\tsoundengine_calcNextSampleBlock();\n\t/* 0.2.106 the step after the block: its work runs in the free time, not\n\t * between the DMA request and the ready block (sounds one block later) */\n\t{ CPU_DIAG_SEQ_BEGIN(); // 0.2.104 peak diagnosis (d builds)\n\tseq_tick();\n\tCPU_DIAG_SEQ_END(); }\n\t__HAL_TIM_SetCounter(&htim2, 1950);\n\t__HAL_TIM_ENABLE_IT',
                          '\t{ CPU_DIAG_SEQ_BEGIN();\n\tseq_tick();\n\tCPU_DIAG_SEQ_END(); }\n\tsoundengine_calcNextSampleBlock();\n\t__HAL_TIM_SetCounter(&htim2, 1950);\n\t__HAL_TIM_ENABLE_IT'),
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
print('AUDIO LATE PASS')
