"""User samples (Mutador 0.2.51) on the host.

Python: make_samples.py reads 8/16/24 bit and float WAVs, mixes to mono, keeps
the rate, fades the tail and writes the header the firmware expects; the LXR1
Mutador set has 16 samples and the crash. import_lxr1_patterns.SampleMap moves
the LXR1 waveform numbers to 38+n (crash 5 to the crash) and shifts coarse and
fine so a sample plays at its LXR1 speed (1024*f(note) frames per second).

C (MSVC): the real SampleBank.c with flash and card stubs (install behind the
wavetables, unchanged file, bad CRC, 1 MB chip, wavetables that grow, a cut
write) and the sample oscillator from Oscillator.c (root-note pitch, linear
interpolation, one shot that stays silent at the end, FM offset).
--mutate runs each mutation and expects the check to fail.
"""
from pathlib import Path
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import make_samples as ms  # noqa: E402
import import_lxr1_patterns as conv  # noqa: E402

VS = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat'
MUTADOR = ROOT.parent / 'mutador'

MUTATIONS = {
    'no-crc': ('SampleBank.c', 'if(crc != h.crc || f_lseek', 'if(f_lseek'),
    'header-first': ('SampleBank.c', '\taddr = base + SAMPLEBANK_HEADER_BYTES;\n', '\taddr = base;\n'),
    'ignore-base': ('SampleBank.c', 'sampleBank_samples && sampleBank_address == base && !memcmp', 'sampleBank_samples && !memcmp'),
    'sector-7': ('SampleBank.c', 'return sector < SAMPLEBANK_FIRST_SECTOR ? SAMPLEBANK_FIRST_SECTOR : sector;', 'return sector;'),
    'no-space-check': ('SampleBank.c', '\tif(available < SAMPLEBANK_HEADER_BYTES || h.dataBytes > available - SAMPLEBANK_HEADER_BYTES)\n\t{\n\t\tresult = SAMPLEBANK_NO_SPACE;', '\tif(0)\n\t{\n\t\tresult = SAMPLEBANK_NO_SPACE;'),
    'no-end-stop': ('Oscillator.c', 'return (next < phase || next > end) ? end : next;', 'return next;'),
    'no-rate': ('Oscillator.c', '*rate/(REAL_FS*MidiNoteFrequencies[SAMPLEBANK_ROOT_NOTE])', '/MidiNoteFrequencies[SAMPLEBANK_ROOT_NOTE]'),
    'no-interpolation': ('Oscillator.c', 'return (int16_t)(a + (((b - a) * (int32_t)(index & OSC_SAMPLE_FRAC)) >> SAMPLEBANK_PHASE_BITS));', 'return (int16_t)a;'),
    'fm-ignored': ('Oscillator.c', '+ ((int64_t)(int32_t)(modBuffer[i]*osc->fmMod) << OSC_SAMPLE_FM_SHIFT)', ''),
    'menu-no-jump': ('menu.c', 'return (dir > 0 && sampleBank_count()) ? (uint8_t)SAMPLEBANK_FIRST_WAVE : (uint8_t)(free - 1u);', 'return value;'),
    'converter-no-fine': ('py', 'target = detune(fine) * 2 ** ((shift - steps) / 12)', 'target = detune(fine)'),
    'converter-crash-pwm': ('py', 'return SAMPLE_FIRST_WAVE + self.crash, self.rates[self.crash]', 'return LXR1_CRASH, None'),
}
if '--mutate' in sys.argv:
    missed = []
    for name in MUTATIONS:
        r = subprocess.run([sys.executable, __file__, '--mutation=' + name], capture_output=True, text=True)
        bad = 'BAD MUTATION' in r.stdout
        print(('MISSED ' if bad or not r.returncode else 'caught ') + name + (' (anchor)' if bad else ''))
        if bad or not r.returncode:
            missed.append(name)
    sys.exit(1 if missed else 0)
mutation = None
for arg in sys.argv[1:]:
    if arg.startswith('--mutation='):
        mutation = MUTATIONS[arg.split('=', 1)[1]]


def mutate(where, text):
    if mutation and mutation[0] == where:
        if text.count(mutation[1]) != 1:
            print('BAD MUTATION', mutation[1])
            sys.exit(0)
        return text.replace(mutation[1], mutation[2])
    return text


if mutation and mutation[0] == 'py':
    for module in (conv,):
        source = Path(module.__file__).read_text(encoding='utf-8')
        if source.count(mutation[1]) != 1:
            print('BAD MUTATION', mutation[1])
            sys.exit(0)
        exec(compile(source.replace(mutation[1], mutation[2]), module.__file__, 'exec'), module.__dict__)

checks = failures = 0


def check(ok, what):
    global checks, failures
    checks += 1
    if not ok:
        failures += 1
        print('FAIL', what)


def wav(path, frames, rate=44100, channels=1, bits=16, kind=1):
    if kind == 3:
        data = struct.pack(f'<{len(frames)}f', *frames)
    elif bits == 8:
        data = bytes(v + 128 for v in frames)
    elif bits == 16:
        data = struct.pack(f'<{len(frames)}h', *frames)
    else:
        data = b''.join(int(v).to_bytes(3, 'little', signed=True) for v in frames)
    fmt = struct.pack('<HHIIHH', kind, channels, rate, rate * channels * bits // 8, channels * bits // 8, bits)
    body = b'WAVE' + b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'LIST' + struct.pack('<I', 3) + b'abc\0'
    body += b'data' + struct.pack('<I', len(data)) + data + (b'\0' if len(data) & 1 else b'')
    path.write_bytes(b'RIFF' + struct.pack('<I', len(body)) + body)


def parse(blob):
    magic, count, reserved, data_bytes, crc, reserved2 = ms.HEAD.unpack_from(blob, 0)
    entries = [ms.ENTRY.unpack_from(blob, 24 + 16 * i) for i in range(ms.MAX_SAMPLES)]
    return magic, count, reserved, data_bytes, crc, reserved2, entries


def frames_of(blob, entry):
    _, offset, frames, _ = entry
    return list(struct.unpack_from(f'<{frames}h', blob, ms.HEADER_BYTES + offset))


def check_tool(folder):
    src = folder / 'src'
    src.mkdir()
    ramp = [i * 100 - 20000 for i in range(400)]
    wav(src / 'a ramp.wav', ramp)
    wav(src / 'b stereo.wav', [v for i in range(300) for v in (1000, 3000)], rate=48000, channels=2)
    wav(src / 'c24.wav', [i * 256 * 10 for i in range(200)], rate=22050, bits=24)
    wav(src / 'd8.wav', [64] * 100, rate=11025, bits=8)
    wav(src / 'e float.wav', [0.5] * 100, rate=96000, kind=3, bits=32)
    class A: pass
    args = A()
    args.mutador = None; args.list = None; args.crash = True; args.sources = [src]
    samples = ms.collect(args)
    blob = ms.build(samples)
    magic, count, reserved, data_bytes, crc, reserved2, entries = parse(blob)
    check(magic == b'LXRSM001' and count == 6 and not reserved and not reserved2, 'header')
    check(len(blob) == 1024 + data_bytes and data_bytes % 4 == 0, 'sizes')
    check(crc == zlib.crc32(blob[24:24 + 16 * ms.MAX_SAMPLES] + blob[1024:]) & 0xFFFFFFFF, 'CRC of entries and data')
    names = [e[0][:3].decode() for e in entries[:count]]
    check(names == ['ara', 'bst', 'c24', 'd8x', 'efl', 'crs'], f'names {names}')
    check(all(e[0][3] == 0 for e in entries[:count]) and all(e == (bytes(4), 0, 0, 0) for e in entries[count:]), 'entry padding')
    check([e[3] for e in entries[:count]] == [44100, 48000, 22050, 11025, 96000, 32000], 'rates kept')
    check(all(e[1] % 4 == 0 for e in entries[:count]) and entries[1][1] == 800, 'offsets aligned')
    a = frames_of(blob, entries[0])
    check(a[:336] == ramp[:336] and a[-1] == 0 and abs(a[-2]) < abs(ramp[-2]) and len(a) == 400, 'tail fades to 0')
    b = frames_of(blob, entries[1])
    check(len(b) == 300 and b[0] == 2000, 'stereo mixed to mono')
    c = frames_of(blob, entries[2])
    check(c[10] == 100, '24 bit scaled to 16 bit')
    check(frames_of(blob, entries[3])[0] == 64 * 256 and frames_of(blob, entries[4])[0] == 16384, '8 bit and float')
    crash = frames_of(blob, entries[5])
    check(len(crash) == 32768 and crash[0] == 256, 'crash from Samples.c')
    check(abs(ms.lxr1_shift(44100) - 31.2346) < 1e-3 and abs(ms.lxr1_shift(32000) - 36.787) < 1e-3, 'LXR1 shift')
    used = {'abc'}
    check(ms.default_name('abc', used) == 'ab1', 'name collision')
    try:
        ms.build([('x', 'x', [0] * 600000, 44100)])
        check(False, 'too big refused')
    except ValueError:
        check(True, 'too big refused')
    if MUTADOR.exists():
        args.mutador = MUTADOR; args.sources = []; args.crash = False
        blob = ms.build(ms.collect(args))
        _, count, _, _, _, _, entries = parse(blob)
        check(count == 17 and entries[16][0][:3] == b'crs' and entries[16][3] == 32000 and
              entries[0][0][:3] == b'cfl' and entries[15][0][:3] == b'rid' and entries[15][2] == 34839, 'Mutador set')
        (folder / 'mutador.bin').write_bytes(blob)
    return blob


def check_converter():
    enum = conv.enum_values(ROOT / 'Core/Inc/Parameters.h')
    rates, crash = conv.sample_bank(None)
    check(len(rates) == 17 and crash == 16, 'default Mutador bank')

    def lxr1_speed(c, f):
        return 1024 * 440 * 2 ** ((c - 69) / 12) * conv.detune(f)

    def new_speed(c, f, rate):
        return rate * 2 ** ((c - 60) / 12) * conv.detune(f)
    worst = 0
    for rate in (44100, 32000, 48000):
        for c in range(0, 90, 7):
            for f in (0, 30, 63, 64, 100, 127):
                nc, nf, clamped = conv.shift_pitch(c, f, conv.lxr1_pitch_shift(rate))
                if clamped:
                    continue
                cents = 1200 * math.log2(new_speed(nc, nf, rate) / lxr1_speed(c, f))
                worst = max(worst, abs(cents))
    check(worst < 1.0, f'coarse and fine keep the LXR1 speed ({worst:.2f} cents)')
    nc, nf, clamped = conv.shift_pitch(126, None, 31.23)
    check(nc == 127 and nf is None and clamped, 'coarse only, clamped')
    check(conv.shift_pitch(40, None, 31.23)[0] == 71, 'coarse only rounds')
    m = conv.SampleMap(enum, rates, crash)
    check(m.map_wave(3)[0] == 3 and m.map_wave(5) == (54, 32000) and m.map_wave(6) == (38, 44100) and
          m.map_wave(21) == (53, 44100), 'waveform numbers')
    check(m.map_wave(22, 'x')[0] == 0 and m.notes, 'missing LXR1 sample becomes sine')
    kit = bytearray(enum['PAR_SNARE_LAYER_WAVE'] + 1)
    kit[enum['PAR_WAVE1_HH']] = 7
    kit[enum['PAR_COARSE6']] = 40
    kit[enum['PAR_FINE6']] = 93
    kit[enum['PAR_OSC_WAVE_DRUM1']] = 2
    kit[enum['PAR_COARSE1']] = 50
    kit[enum['PAR_OSC_WAVE_SNARE']] = 5
    kit[enum['PAR_COARSE4']] = 32
    kit[enum['PAR_FINE4']] = 127
    kit[enum['PAR_WAVE2_HH']] = 8
    kit[enum['PAR_MOD_OSC_F1']] = 60
    m = conv.SampleMap(enum, rates, crash)
    m.apply(kit)
    check(kit[enum['PAR_WAVE1_HH']] == 39 and kit[enum['PAR_COARSE6']] == 71 and kit[enum['PAR_FINE6']] == 123, 'hihat sample')
    check(kit[enum['PAR_OSC_WAVE_DRUM1']] == 2 and kit[enum['PAR_COARSE1']] == 50, 'oscillator untouched')
    check(kit[enum['PAR_OSC_WAVE_SNARE']] == 54 and kit[enum['PAR_COARSE4']] == 69, 'crash on the snare')
    check(kit[enum['PAR_WAVE2_HH']] == 40 and kit[enum['PAR_MOD_OSC_F1']] == 91, 'hihat modulator coarse only')
    check(m.remap(enum['PAR_COARSE6'], 40) == 71 and m.remap(enum['PAR_COARSE1'], 40) == 40 and
          m.remap(enum['PAR_OSC_WAVE_DRUM2'], 9) == 41 and m.remap(enum['PAR_VOL1'], 9) == 9, 'automation')


STUB_HAL = r"""
#include <stdint.h>
#include <stddef.h>
typedef enum {HAL_OK, HAL_ERROR} HAL_StatusTypeDef;
typedef struct {uint32_t TypeErase, Banks, Sector, NbSectors, VoltageRange;} FLASH_EraseInitTypeDef;
#define FLASH_TYPEERASE_SECTORS 0
#define FLASH_VOLTAGE_RANGE_3 2
#define FLASH_TYPEPROGRAM_WORD 2
HAL_StatusTypeDef HAL_FLASH_Unlock(void);
HAL_StatusTypeDef HAL_FLASH_Lock(void);
HAL_StatusTypeDef HAL_FLASHEx_Erase(FLASH_EraseInitTypeDef *e, uint32_t *sectorError);
HAL_StatusTypeDef HAL_FLASH_Program(uint32_t type, uintptr_t address, uint64_t data);
void SCB_InvalidateDCache_by_Addr(uint32_t *addr, int32_t size);
"""
STUB_FATFS = r"""
#include <stdint.h>
typedef unsigned int UINT;
typedef uint32_t FSIZE_t;
typedef enum {FR_OK, FR_DISK_ERR, FR_NO_FILE = 4} FRESULT;
typedef struct {FSIZE_t pos;} FIL;
#define FA_READ 1
#define FA_OPEN_EXISTING 0
extern FIL SDFile;
FRESULT f_open(FIL *f, const char *path, uint8_t mode);
FRESULT f_read(FIL *f, void *buf, UINT n, UINT *got);
FRESULT f_lseek(FIL *f, FSIZE_t pos);
FRESULT f_close(FIL *f);
FSIZE_t f_size(FIL *f);
"""

TEST = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "stm32f7xx_hal.h"
#include "fatfs.h"
#include "Soundengine/DSPAudio/SampleBank.h"
#include "Soundengine/DSPAudio/WaveBank.h"

uint8_t flashMem[WAVEBANK_FLASH_BYTES];
uint32_t deviceBytes = 2048u*1024u, waveBytes = 0;
FIL SDFile;
static uint8_t *card; static uint32_t cardSize; static int open, locked = 1;
static unsigned erases, programs, erasedMask, firstProgram = 0xFFFFFFFFu; static long cutAfter = -1;
static unsigned checks, failures;
static void check(int ok, const char *what){checks++; if(!ok){failures++; printf("FAIL %s\n", what);}}

uint32_t waveBank_flashBytes(void){return waveBytes;}
HAL_StatusTypeDef HAL_FLASH_Unlock(void){locked = 0; return HAL_OK;}
HAL_StatusTypeDef HAL_FLASH_Lock(void){locked = 1; return HAL_OK;}
HAL_StatusTypeDef HAL_FLASHEx_Erase(FLASH_EraseInitTypeDef *e, uint32_t *sectorError)
{
	const uint32_t last = deviceBytes >= 2048u*1024u ? 11u : 7u;
	if(locked || e->Sector < 7 || e->Sector > last || e->NbSectors != 1){*sectorError = e->Sector; return HAL_ERROR;}
	memset(flashMem + (e->Sector - 7u)*0x40000u, 0xFF, 0x40000u); erases++; erasedMask |= 1u << e->Sector;
	*sectorError = 0xFFFFFFFFu; return HAL_OK;
}
HAL_StatusTypeDef HAL_FLASH_Program(uint32_t type, uintptr_t address, uint64_t data)
{
	const uintptr_t base = (uintptr_t)flashMem;
	if(locked || type != FLASH_TYPEPROGRAM_WORD || address < base || address + 4 > base + sizeof(flashMem) || (address & 3))
		return HAL_ERROR;
	if(cutAfter >= 0 && (long)programs >= cutAfter) return HAL_ERROR;
	if(firstProgram == 0xFFFFFFFFu) firstProgram = (unsigned)(address - base);
	programs++;
	uint32_t old; memcpy(&old, (void*)address, 4);
	old &= (uint32_t)data; memcpy((void*)address, &old, 4);
	return HAL_OK;
}
void SCB_InvalidateDCache_by_Addr(uint32_t *addr, int32_t size){(void)addr; (void)size;}
FRESULT f_open(FIL *f, const char *path, uint8_t mode)
{
	(void)mode;
	if(!card || strcmp(path, "/SAMPLES/SAMPLES.BIN")) return FR_NO_FILE;
	f->pos = 0; open = 1; return FR_OK;
}
FRESULT f_read(FIL *f, void *buf, UINT n, UINT *got)
{
	if(!open) return FR_DISK_ERR;
	*got = f->pos + n <= cardSize ? n : cardSize - f->pos;
	memcpy(buf, card + f->pos, *got); f->pos += *got; return FR_OK;
}
FRESULT f_lseek(FIL *f, FSIZE_t pos){f->pos = pos; return FR_OK;}
FRESULT f_close(FIL *f){(void)f; open = 0; return FR_OK;}
FSIZE_t f_size(FIL *f){(void)f; return cardSize;}

static uint8_t *readFile(const char *path, uint32_t *size)
{
	FILE *f = fopen(path, "rb"); if(!f) return 0;
	fseek(f, 0, SEEK_END); *size = (uint32_t)ftell(f); fseek(f, 0, SEEK_SET);
	uint8_t *b = malloc(*size); fread(b, 1, *size, f); fclose(f); return b;
}
static int bankAt(uint32_t offset, const uint8_t *file, uint32_t size){return !memcmp(flashMem + offset, file, size);}
static void reset(void){erases = programs = erasedMask = 0; firstProgram = 0xFFFFFFFFu;}

/* --- the sample oscillator from Oscillator.c --- */
typedef struct {int16_t output; uint32_t phaseInc, phase; float freq; uint8_t waveform; float pitchMod, fmMod, modNodeValue;} OscInfo;
#define REAL_FS 44140.f
#define NUM_OSC_WAVEFORMS 6
static float MidiNoteFrequencies[128];
OSC_CODE

static float noteFreq(int n){return 440.f*powf(2.f,(n-69)/12.f);}

/* --- the waveform menu skip from menu.c --- */
static const char waveformNames[][4] = {{6}};
static uint8_t waveTables;
uint8_t waveBank_count(void){return waveTables;}
MENU_CODE

int main(int argc, char **argv)
{
	uint32_t sizeA, sizeB;
	uint8_t *a = readFile(argv[1], &sizeA), *b = readFile(argv[2], &sizeB);
	if(!a || !b){puts("no test files"); return 1;}
	for(int n=0;n<128;n++) MidiNoteFrequencies[n] = noteFreq(n);
	const SampleBankHeader *ha = (const SampleBankHeader*)a;
	check(sizeof(SampleBankHeader) == 1024 && sizeof(SampleBankEntry) == 16, "header layout");
	check(sampleBank_headerValid(ha), "tool header is valid");

	memset(flashMem, 0xFF, sizeof(flashMem));
	sampleBank_init(); check(sampleBank_count() == 0 && !strcmp(sampleBank_name(0), "---") && !sampleBank_data(0), "empty flash");
	check(sampleBank_installFromSd(0) == SAMPLEBANK_NO_FILE, "no file");

	card = a; cardSize = sizeA; reset();
	check(sampleBank_installFromSd(0) == SAMPLEBANK_WRITTEN, "written");
	check(sampleBank_count() == ha->count && bankAt(0x40000u, a, sizeA), "bank in sector 8 without wavetables");
	check(!(erasedMask & 0x80u) && (erasedMask & 0x100u), "sector 7 stays for the wavetables");
	check(firstProgram == 0x40000u + SAMPLEBANK_HEADER_BYTES, "data before the header");
	check(sampleBank_data(0) == (const int16_t*)(flashMem + 0x40000u + 1024u + ha->entries[0].offset) &&
	      sampleBank_frames(1) == ha->entries[1].frames && sampleBank_rate(1) == ha->entries[1].rate &&
	      !strcmp(sampleBank_name(0), ha->entries[0].name), "entries");
	reset();
	check(sampleBank_installFromSd(0) == SAMPLEBANK_UNCHANGED && !erases && !programs, "same file is skipped");
	sampleBank_init(); check(sampleBank_count() == ha->count, "boot finds the bank");

	/* the wavetables grow into sector 8: the bank moves behind them */
	waveBytes = 0x40000u + 4u; memset(flashMem + 0x40000u, 0xFF, 0x40000u); reset();
	sampleBank_init(); check(sampleBank_count() == 0, "erased header: no samples");
	check(sampleBank_installFromSd(0) == SAMPLEBANK_WRITTEN && bankAt(0x80000u, a, sizeA) && (erasedMask & 0x200u) &&
	      !(erasedMask & 0x180u), "bank written behind wavetables in sector 9");
	waveBytes = 0x10000u; sampleBank_init();
	check(sampleBank_count() == 0, "smaller wavetables: the bank belongs in sector 8 again");
	check(sampleBank_installFromSd(0) == SAMPLEBANK_WRITTEN && bankAt(0x40000u, a, sizeA), "rewritten in sector 8");
	waveBytes = 0x40000u + 4u; reset();
	check(sampleBank_installFromSd(0) == SAMPLEBANK_WRITTEN && (erasedMask & 0x200u), "a bank in the old place is not taken as unchanged");
	waveBytes = 0; sampleBank_init(); reset();
	check(sampleBank_count() == 0 && sampleBank_installFromSd(0) == SAMPLEBANK_WRITTEN && bankAt(0x40000u, a, sizeA), "back in sector 8: the copy in sector 9 overwrote its data, so it is written again");

	/* too little space */
	waveBytes = 4u*0x40000u; reset();
	check(sizeA > 0x40000u, "file A needs more than one sector");
	check(sampleBank_installFromSd(0) == SAMPLEBANK_NO_SPACE && !erases, "too big for sector 11 alone");
	waveBytes = 0; deviceBytes = 1024u*1024u; sampleBank_init();
	check(sampleBank_count() == 0, "a 1 MB chip has no sample sectors");
	check(sampleBank_installFromSd(0) == SAMPLEBANK_NO_SPACE && !erases, "a 1 MB chip refuses the bank");
	deviceBytes = 2048u*1024u; sampleBank_init(); check(sampleBank_count() == ha->count, "2 MB again");

	/* bad files keep the flash */
	uint8_t *bad = malloc(sizeA); memcpy(bad, a, sizeA); card = bad;
	bad[sizeA-1] ^= 1; reset();
	check(sampleBank_installFromSd(0) == SAMPLEBANK_UNCHANGED && !erases, "the header decides: same header, no copy");
	((SampleBankHeader*)bad)->crc ^= 1; reset();
	check(sampleBank_installFromSd(0) == SAMPLEBANK_BAD_FILE && !erases && sampleBank_count() == ha->count, "bad CRC");
	memcpy(bad, a, sizeA); ((SampleBankHeader*)bad)->entries[0].rate = 4000; reset();
	check(sampleBank_installFromSd(0) == SAMPLEBANK_BAD_FILE && !erases, "bad rate");
	memcpy(bad, a, sizeA); ((SampleBankHeader*)bad)->entries[0].offset = 2; reset();
	check(sampleBank_installFromSd(0) == SAMPLEBANK_BAD_FILE && !erases, "unaligned offset");
	memcpy(bad, a, sizeA); ((SampleBankHeader*)bad)->entries[ha->count-1].frames += 0x100000u; reset();
	check(sampleBank_installFromSd(0) == SAMPLEBANK_BAD_FILE && !erases, "frames past the data");
	cardSize = sizeA - 4; card = a; reset();
	check(sampleBank_installFromSd(0) == SAMPLEBANK_BAD_FILE && !erases, "short file");

	/* a cut write leaves no samples; the next boot writes the new file */
	card = b; cardSize = sizeB; cutAfter = 10; reset();
	check(sampleBank_installFromSd(0) == SAMPLEBANK_FLASH_ERROR && sampleBank_count() == 0 && locked, "cut write");
	cutAfter = -1; reset();
	check(sampleBank_installFromSd(0) == SAMPLEBANK_WRITTEN && sampleBank_count() == ((const SampleBankHeader*)b)->count, "next boot writes it");

	/* oscillator: bank B sample 0 is a ramp 0, 100, 200 ... */
	OscInfo o; memset(&o, 0, sizeof(o));
	o.waveform = SAMPLEBANK_FIRST_WAVE; o.pitchMod = o.modNodeValue = 1.f; o.freq = noteFreq(60);
	osc_calcSampleBankFreq(&o);
	const float rate = (float)sampleBank_rate(0);
	check(fabsf(o.phaseInc - rate/REAL_FS*4096.f) < 1.f, "root note plays at the sample rate");
	o.freq = noteFreq(72); osc_calcSampleBankFreq(&o);
	check(fabsf(o.phaseInc - 2.f*rate/REAL_FS*4096.f) < 1.f, "an octave up doubles the speed");
	o.freq = noteFreq(61); o.pitchMod = 2.f; osc_calcSampleBankFreq(&o);
	check(fabsf(o.phaseInc/(2.f*rate/REAL_FS*4096.f) - 1.0594631f) < 1e-3f, "semitone and pitch modulation");
	o.phaseInc = 2048; o.phase = 0;
	int16_t buf[16]; calcSampleBankBlock(&o, buf, 16, 1.f);
	int ok = 1; for(int i=0;i<16;i++) ok &= buf[i] == i*50;
	check(ok, "half speed interpolates between frames");
	const uint32_t frames = sampleBank_frames(0), end = (frames-1u) << 12;
	o.phaseInc = 4096u*3u; o.phase = end - 4096u*5u;
	int16_t tail[16]; calcSampleBankBlock(&o, tail, 16, 1.f);
	check(o.phase == end && tail[0] != 0 && tail[15] == 0 && tail[3] == 0, "the one shot ends silent at the last frame");
	calcSampleBankBlock(&o, tail, 16, 1.f); check(o.phase == end && tail[0] == 0 && o.output == 0, "and stays there");
	o.phaseInc = 0xF0000000u; o.phase = 4096u; calcSampleBankBlock(&o, tail, 1, 1.f);
	check(o.phase == end, "no wrap past the end");
	int16_t mod[4] = {0, 800, -800, 0}; o.waveform = SAMPLEBANK_FIRST_WAVE; o.phaseInc = 0; o.phase = 100u << 12; o.fmMod = 0.01f;
	calcSampleBankFmBlock(&o, mod, buf, 4, 1.f);
	check(buf[0] == 10000 && buf[1] == 10100 && buf[2] == 9900 && buf[3] == 10000, "the modulator moves the read point (8 -> one frame)");
	int16_t low[2] = {-32768, 32767}; o.phase = 0; o.fmMod = 1.f;
	calcSampleBankFmBlock(&o, low, buf, 2, 1.f);
	check(buf[0] == 0 && buf[1] >= 0 && buf[1] < 100, "the read point stays inside the sample (last frame is 0)");
	o.waveform = (uint8_t)(SAMPLEBANK_FIRST_WAVE + sampleBank_count()); o.phase = 0; o.phaseInc = 4096;
	buf[0] = 1; calcSampleBankBlock(&o, buf, 4, 1.f); check(!buf[0] && !buf[3] && !o.output, "a missing sample is silent");
	/* menu: 3 wavetables (6..8), samples from 38 */
	waveTables = 3;
	check(menu_waveformSkip(8, 1) == 8 && menu_waveformSkip(9, 1) == 38 && menu_waveformSkip(37, -1) == 8 &&
	      menu_waveformSkip(38, -1) == 38 && menu_waveformSkip(5, 1) == 5, "the menu jumps over the empty wavetable slots");
	waveTables = 0;
	check(menu_waveformSkip(6, 1) == 38 && menu_waveformSkip(37, -1) == 5, "no wavetables: PWM to the first sample");
	printf("%s %u assertions\n", failures ? "SAMPLEBANK FAIL" : "SAMPLEBANK PASS", checks);
	return failures != 0;
}
"""


def function(text, name):
    m = re.search(r'^[^\n]*\b' + name + r'\([^)]*\)\s*\{', text, re.M)
    assert m, name
    pos, depth = m.end(), 1
    while depth:
        depth += (text[pos] == '{') - (text[pos] == '}')
        pos += 1
    return text[m.start():pos]


def check_firmware(folder, file_a, file_b):
    build = folder / 'build'
    build.mkdir()
    bank = mutate('SampleBank.c', (ROOT / 'Core/Src/Soundengine/DSPAudio/SampleBank.c').read_text(encoding='utf-8').replace('\r\n', '\n'))
    wave = (ROOT / 'Core/Src/Soundengine/DSPAudio/WaveBank.c').read_text(encoding='utf-8')
    osc = mutate('Oscillator.c', (ROOT / 'Core/Src/Soundengine/DSPAudio/Oscillator.c').read_text(encoding='utf-8').replace('\r\n', '\n'))
    osc_code = '\n'.join(re.findall(r'^#define OSC_SAMPLE_\w+ .*$', osc, re.M)) + '\n'
    for name in ('osc_isSample', 'osc_readSample', 'osc_sampleStep', 'calcSampleBankBlock', 'calcSampleBankFmBlock', 'osc_calcSampleBankFreq'):
        osc_code += function(osc, name).replace('static inline', 'static __inline') + '\n'
    (build / 'stm32f7xx_hal.h').write_text(STUB_HAL, encoding='utf-8')
    (build / 'fatfs.h').write_text(STUB_FATFS, encoding='utf-8')
    (build / 'SampleBank.c').write_text('#include <stdint.h>\nextern uint8_t flashMem[];\nextern uint32_t deviceBytes;\n' + bank, encoding='utf-8')
    (build / 'crc.c').write_text('#include <stdint.h>\n' + function(wave, 'waveBank_crc') + '\n', encoding='utf-8')
    menu = mutate('menu.c', (ROOT / 'Core/Src/menu/menu.c').read_text(encoding='utf-8').replace('\r\n', '\n'))
    menu_code = function(menu, 'menu_waveformSkip')
    (build / 'test.c').write_text(TEST.replace('OSC_CODE', osc_code).replace('MENU_CODE', menu_code), encoding='utf-8')
    command = (f'call "{VS}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /I. /I"{ROOT / "Core/Inc"}" '
               f'"/DWAVEBANK_FLASH_ADDRESS=((uintptr_t)flashMem)" /DSAMPLEBANK_DEVICE_BYTES=deviceBytes /D_CRT_SECURE_NO_WARNINGS '
               f'/Fe:samplebank.exe test.c SampleBank.c crc.c >build.log && .\\samplebank.exe "{file_a}" "{file_b}"')
    result = subprocess.run(command, shell=True, cwd=build)
    if result.returncode:
        log = build / 'build.log'
        if log.exists():
            print(log.read_text(errors='replace')[-3000:])
    check(result.returncode == 0, 'firmware SampleBank.c and sample oscillator')


def main():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        folder = Path(tmp)
        small = check_tool(folder)
        check_converter()
        file_b = folder / 'b.bin'
        ramp = [i * 100 for i in range(300)]
        file_b.write_bytes(ms.build([('rmp', 'ramp', ramp + [0], 44100), ('two', 'two', [5, 6], 8000)]))
        file_a = folder / 'mutador.bin'
        if not file_a.exists():
            file_a.write_bytes(ms.build([('big', 'big', [1] * 200000, 44100)]))
        check_firmware(folder, file_a, file_b)
        del small
    print(f'{"FAIL" if failures else "PASS"} {checks} sample tool, converter and firmware checks')
    sys.exit(failures != 0)


if __name__ == '__main__':
    main()
