"""User wavetables: tools/make_wavetables.py and the firmware WaveBank.c.

The generator part builds WAVES.BIN from synthetic sources: a Surge WAV
(`srge` frame size), a Serum WAV (`clm ` chunk), a Serum WAV without a chunk,
a folder of single cycles (16 and 24 bit, stereo, float, DC offset) and a
Surge .wt with more frames than fit. It checks names, frames, frame order and
spacing, layout, CRC, peak, DC and the band limit of every octave level, and
the --each mode.
The firmware part compiles WaveBank.c on the host with RAM as flash sectors 7
to 11 (only 1 to 0 bit changes, like NOR flash) and stubbed FatFS: a valid
file is copied with progress, only the sectors it needs are erased, the same
file is skipped, a bad CRC or a short file keeps the flash, a write cut off
before the end leaves no valid bank, and a 1 MB chip keeps to sector 7.
--mutate drops the CRC check from WaveBank.c; the check must then fail.
"""

import importlib.util
import math
import struct
import subprocess
import sys
import tempfile
import wave
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"

spec = importlib.util.spec_from_file_location('make_wavetables', ROOT / 'tools/make_wavetables.py')
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

checks = failures = 0


def check(ok, name):
    global checks, failures
    checks += 1
    if not ok:
        failures += 1
        print('FAIL', name)


def riff(fmt, data, extra=b''):
    body = b'WAVE' + b'fmt ' + struct.pack('<I', len(fmt)) + fmt + extra + b'data' + struct.pack('<I', len(data)) + data
    return b'RIFF' + struct.pack('<I', len(body)) + body


def write_wav(path, samples, bits=16, channels=1, float32=False, extra=b''):
    if float32:
        data = b''.join(struct.pack('<f', s) * channels for s in samples)
        fmt = struct.pack('<HHIIHH', 3, channels, 48000, 48000 * 4 * channels, 4 * channels, 32)
        path.write_bytes(riff(fmt, data, extra))
        return
    width = bits // 8
    full = (1 << (bits - 1)) - 1
    frames = b''.join(int(round(s * full)).to_bytes(width, 'little', signed=True) * channels for s in samples)
    if extra:
        fmt = struct.pack('<HHIIHH', 1, channels, 48000, 48000 * width * channels, width * channels, bits)
        path.write_bytes(riff(fmt, frames, extra))
        return
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(48000)
        w.writeframes(frames)


def chunk(tag, body):
    return tag + struct.pack('<I', len(body)) + body + (b'\0' if len(body) & 1 else b'')


def write_wt(path, frames, float32=False, full_range=False):
    size, count = len(frames[0]), len(frames)
    flags = 0 if float32 else 0x04 | (0x08 if full_range else 0)
    scale = 32767 if full_range else 16384
    if float32:
        data = b''.join(struct.pack('<f', v) for f in frames for v in f)
    else:
        data = b''.join(struct.pack('<h', int(round(v * scale))) for f in frames for v in f)
    path.write_bytes(b'vawt' + struct.pack('<IHH', size, count, flags) + data)


def read_bank(path):
    blob = path.read_bytes()
    count, levels, length, reserved, data_bytes, crc = struct.unpack_from('<HHHHII', blob, 8)
    names = [blob[24 + 4 * i:27 + 4 * i].decode() for i in range(count)]
    frames = list(blob[152:152 + count])
    data = struct.unpack_from(f'<{data_bytes // 2}h', blob, 256)
    tables, pos = [], 0
    for f in frames:
        table = []
        for _ in range(f):
            levels_out = []
            for n in gen.LEVEL_LENGTHS:
                levels_out.append(data[pos:pos + n])
                pos += n
            table.append(levels_out)
        tables.append(table)
    return blob, count, levels, length, reserved, data_bytes, crc, names, frames, tables


def sine(n, amp=0.5):
    return [amp * math.sin(2 * math.pi * i / n) for i in range(n)]


def check_generator(folder):
    src = folder / 'src'
    src.mkdir()
    # Surge WAV: 60 frames of 512, frame i a sine of amplitude (i+1)/61, and 100 samples left over
    surge = [v for f in range(60) for v in sine(512, (f + 1) / 61)] + [0.0] * 100
    write_wav(src / 'surge_wave.wav', surge, extra=chunk(b'srge', struct.pack('<II', 1, 512)))
    # Serum WAV with a clm chunk: sine, saw, square of 2048
    serum = sine(2048) + [0.5 * (2 * i / 2048 - 1) for i in range(2048)] + [0.5 if i < 1024 else -0.5 for i in range(2048)]
    write_wav(src / 'serum_clm.wav', serum, float32=True, extra=chunk(b'clm ', b'<!>2048 20000000 wavetable (www.xferrecords.com)'))
    # Serum WAV without a chunk: 2 frames of 2048
    write_wav(src / 'plain_serum.wav', sine(2048) + sine(2048, 0.25))
    # a folder of single cycles: one wavetable with 3 frames
    singles = src / 'singles'
    singles.mkdir()
    write_wav(singles / 'a_saw.wav', [0.6 * (2 * i / 1024 - 1) + 0.3 for i in range(1024)])  # with DC
    write_wav(singles / 'b_square.wav', [0.5 if i < 300 else -0.5 for i in range(600)], bits=24, channels=2)
    write_wav(singles / 'c_sine.wav', sine(2048, 0.25), float32=True)
    # Surge .wt: 230 frames of 64, frame i a sine of amplitude (i+1)/231; more than fits
    write_wt(src / 'tiny.wt', [sine(64, (f + 1) / 231) for f in range(230)])
    sources = [src / 'surge_wave.wav', src / 'serum_clm.wav', singles, src / 'tiny.wt', src / 'plain_serum.wav']
    out = folder / 'card'
    gen.build(sources, out)
    blob, count, levels, length, reserved, data_bytes, crc, names, frames, tables = read_bank(out / 'WAVES/WAVES.BIN')
    check(blob[:8] == b'LXRWT003', 'magic')
    check((count, levels, length, reserved) == (5, 10, 1024, 0), 'counts')
    check(names == ['SUR', 'SER', 'SIN', 'TIN', 'PLA'], f'names {names}')
    check(frames == [60, 3, 3, 216, 2], f'frames {frames}')  # 298 frames, the .wt gives way to fit 284
    check(sum(frames) == gen.MAX_FRAMES == 284, 'frame budget')
    check(data_bytes == sum(frames) * 2304 * 2 and len(blob) == 256 + data_bytes <= 5 * 0x40000, 'sizes')
    check(crc == zlib.crc32(blob[24:184] + blob[256:]) & 0xFFFFFFFF, 'CRC over names, frames and data')
    check(blob[152 + count:256] == bytes(256 - 152 - count) and blob[24 + 4 * count:152] == bytes(128 - 4 * count),
          'unused names, frames and pad are zero')
    for t, table in enumerate(tables):
        peak = max(abs(v) for frame in table for level in frame for v in level)
        check(31900 <= peak <= 32000, f'table {t} peak {peak}')
        # every frame of short tables, a sample of the long ones
        for f in range(0, len(table), 1 if len(table) <= 4 else 23):
            for j, level in enumerate(table[f]):
                size = len(level)
                check(size == gen.LEVEL_LENGTHS[j], f'level {j} length')
                check(abs(sum(level)) / size < 2, f'table {t} frame {f} level {j} has no DC')
                bins = gen.fft([complex(v) for v in level])
                limit = gen.level_harmonics(j)
                above = max((abs(bins[k]) / size for k in range(limit + 1, size // 2)), default=0)
                check(above < 1.0, f'table {t} frame {f} level {j} above harmonic {limit}: {above:.2f}')
    for j in range(gen.LEVELS):
        check(gen.level_harmonics(j) * 55 * 2 ** j < 20000 and gen.level_harmonics(j) < gen.LEVEL_LENGTHS[j] // 2, f'level {j} limit')
    check(gen.LEVEL_LENGTHS == [1024, 512, 256, 128] + [64] * 6 and gen.FRAME_SAMPLES == 2304, 'level lengths')

    def harmonics(level):
        b = gen.fft([complex(v) for v in level])
        return [abs(x) / len(level) for x in b[:len(level) // 2]]
    # Surge frames: the srge size, in order, the leftover dropped
    peaks = [max(abs(v) for v in frame[0]) for frame in tables[0]]
    check(all(b > a for a, b in zip(peaks, peaks[1:])) and abs(peaks[0] / peaks[-1] - 1 / 60) < 0.002, 'srge frames in order')
    # Serum clm frames: sine, saw, square, and the saw keeps its partials on a short level
    h = [harmonics(tables[1][f][0]) for f in range(3)]
    check(max(h[0][2:]) < 1.0, 'Serum frame 1 is the sine')
    check(h[1][2] / h[1][1] > 0.45, 'Serum frame 2 is the saw')
    check(h[2][2] < 1.0 and h[2][3] / h[2][1] > 0.3, 'Serum frame 3 is the square')
    h4 = harmonics(tables[1][1][4])
    check(h4[22] / h4[1] > 0.02, 'short level keeps its partials')
    # the folder: saw, square, sine in name order
    h = [harmonics(tables[2][f][0]) for f in range(3)]
    check(h[0][2] / h[0][1] > 0.45 and h[1][2] < 1.0 and h[1][1] > 1000 and max(h[2][2:]) < 1.0 and h[2][1] > 1000,
          'folder frames in name order')
    # the thinned .wt keeps evenly spaced frames, the first and the last
    peaks = [max(abs(v) for v in frame[0]) for frame in tables[3]]
    kept = [round(p / peaks[-1] * 230) - 1 for p in peaks]
    expected = [round(i * 229 / (frames[3] - 1)) for i in range(frames[3])]
    check(kept == expected, 'evenly spaced frames')
    # the Serum file without a chunk: two frames, the second half as loud
    peaks = [max(abs(v) for v in frame[0]) for frame in tables[4]]
    check(abs(peaks[1] / peaks[0] - 0.5) < 0.01, 'plain Serum frames')

    # --each: every file of the folder is its own wavetable
    names_each, keep_each = gen.build([singles], folder / 'each', each=True)
    check(names_each == ['ASA', 'BSQ', 'CSI'] and keep_each == [1, 1, 1], f'--each {names_each} {keep_each}')
    many = src / 'many'
    many.mkdir()
    for i in range(34):
        write_wav(many / f'w{i:02d}.wav', sine(256, 0.1 + i / 100))
    names_many, keep_many = gen.build([many], folder / 'many', each=True)
    check(len(names_many) == 32 and names_many[0] == 'W00' and names_many[-1] == 'W31' and keep_many == [1] * 32,
          f'--each keeps the first 32 {names_many[:2]} {names_many[-1:]}')
    # readers and helpers
    flt = folder / 'float.wt'
    write_wt(flt, [sine(128), sine(128, 0.25)], float32=True)
    samples, size = gen.read_wt(flt)
    check(size == 128 and len(samples) == 256 and abs(max(samples) - 0.5) < 1e-6, 'float .wt')
    full = folder / 'full.wt'
    write_wt(full, [sine(64, 0.9)], full_range=True)
    samples, size = gen.read_wt(full)
    check(size == 64 and abs(max(samples) - 0.9) < 1e-3, 'full range int16 .wt')
    check(gen.pick_frames([300, 3, 1]) == [255, 3, 1] and gen.pick_frames([200, 200]) == [142, 142] and
          gen.pick_frames([4, 7]) == [4, 7], 'frame budget split')
    check(gen.spaced(list(range(10)), 4) == [0, 3, 6, 9] and gen.spaced([5, 6], 1) == [5], 'spaced frames')
    check(len(gen.split_frames([0.0] * 4096, 0)) == 2 and len(gen.split_frames([0.0] * 2048, 0)) == 1 and
          len(gen.split_frames([0.0] * 3000, 0)) == 1 and len(gen.split_frames([0.0] * 700, 64)) == 10, 'frame split')
    for k in (1, 7, 300):
        level = tables[2][0][0]
        direct = sum(v * complex(math.cos(2 * math.pi * k * i / 1024), -math.sin(2 * math.pi * k * i / 1024))
                     for i, v in enumerate(level))
        fast = gen.fft([complex(v) for v in level])[k]
        check(abs(direct - fast) < 1, f'FFT bin {k}')
    check(gen.short_names(['ab', 'Hello', 'help', 'x-y-z']) == ['AB_', 'HE1', 'HE2', 'XYZ'], 'short names')
    return out / 'WAVES/WAVES.BIN'


STUBS_HAL = r"""
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

STUBS_FATFS = r"""
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
#include "stm32f7xx_hal.h"
#include "fatfs.h"
#include "Soundengine/DSPAudio/WaveBank.h"

uint8_t flashMem[WAVEBANK_FLASH_BYTES];
uint32_t deviceBytes = 2048u*1024u;
FIL SDFile;
static uint8_t *card; static uint32_t cardSize; static int open, locked = 1;
static unsigned erases, programs, erasedMask; static long cutAfter = -1;
static int progressCalls, progressLast, progressBack;

HAL_StatusTypeDef HAL_FLASH_Unlock(void){locked = 0; return HAL_OK;}
HAL_StatusTypeDef HAL_FLASH_Lock(void){locked = 1; return HAL_OK;}
HAL_StatusTypeDef HAL_FLASHEx_Erase(FLASH_EraseInitTypeDef *e, uint32_t *sectorError)
{
	const uint32_t last = 6u + deviceBytes/1024u/256u - 2u; /* 11 on 2 MB, 7 on 1 MB */
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
	programs++;
	uint32_t old; memcpy(&old, (void*)address, 4);
	old &= (uint32_t)data; memcpy((void*)address, &old, 4);
	return HAL_OK;
}
void SCB_InvalidateDCache_by_Addr(uint32_t *addr, int32_t size){(void)addr; (void)size;}
FRESULT f_open(FIL *f, const char *path, uint8_t mode)
{
	(void)mode;
	if(!card || strcmp(path, "/WAVES/WAVES.BIN")) return FR_NO_FILE;
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
static void progress(uint8_t percent)
{
	if(progressCalls && percent < progressLast) progressBack = 1;
	progressCalls++; progressLast = percent;
}

static unsigned checks, failures;
static void check(int ok, const char *name){checks++; if(!ok){failures++; printf("FAIL %s\n", name);}}
static uint8_t *load(const char *path, uint32_t *size)
{
	FILE *fp = fopen(path, "rb"); fseek(fp, 0, SEEK_END); *size = (uint32_t)ftell(fp); fseek(fp, 0, SEEK_SET);
	uint8_t *b = malloc(*size); fread(b, 1, *size, fp); fclose(fp); return b;
}
static int flashHolds(const uint8_t *file, uint32_t size){return !memcmp(flashMem, file, size);}

int main(int argc, char **argv)
{
	(void)argc;
	uint32_t sizeA, sizeB; uint8_t *a = load(argv[1], &sizeA), *b = load(argv[2], &sizeB);
	memset(flashMem, 0xFF, sizeof(flashMem));
	check(WAVEBANK_MAX_FRAMES == 284 && WAVEBANK_FLASH_BYTES == 0x140000u && sizeA > 4u*0x40000u, "1280 KB, 284 frames, file A needs sector 11");

	waveBank_init();
	check(waveBank_count() == 0 && !waveBank_frame(0,0) && !waveBank_frames(0) && !strcmp(waveBank_name(0), "---"), "erased flash has no tables");
	check(waveBank_installFromSd(0) == WAVEBANK_NO_FILE && !erases, "no file keeps the flash");

	/* a 1 MB chip has only sector 7: file A is too big there */
	card = a; cardSize = sizeA; deviceBytes = 1024u*1024u;
	check(waveBank_installFromSd(0) == WAVEBANK_BAD_FILE && !erases && waveBank_count() == 0, "a 1 MB chip refuses a file past sector 7");
	deviceBytes = 2048u*1024u;

	check(waveBank_installFromSd(progress) == WAVEBANK_WRITTEN, "valid file is written");
	check(erasedMask == 0xF80u && erases == 5, "file A erases sectors 7 to 11");
	check(progressCalls > 5 && !progressBack && progressLast == 100, "progress runs up to 100");
	const uint8_t countA = a[8];
	check(countA == 5 && waveBank_count() == countA && flashHolds(a, sizeA) && !open && locked, "flash holds the file, closed and locked");
	{
		int names = 1, frames = 1, addresses = 1; uint32_t first = 0;
		for(uint8_t t=0;t<countA;t++)
		{
			names &= !memcmp(waveBank_name(t), a + 24 + 4*t, 4);
			frames &= waveBank_frames(t) == a[152 + t];
			for(uint8_t f=0;f<a[152 + t];f++)
				addresses &= (const uint8_t*)waveBank_frame(t,f) == flashMem + 256 + (first + f)*2304u*2u;
			addresses &= !waveBank_frame(t, a[152 + t]);
			first += a[152 + t];
		}
		check(names && !strcmp(waveBank_name(countA), "---"), "names");
		check(frames && !waveBank_frames(countA), "frame counts");
		check(addresses && !waveBank_frame(countA,0) && first == 284, "frame addresses up to the last frame");
	}
	/* a 1 MB chip does not trust a bank past sector 7 */
	deviceBytes = 1024u*1024u; waveBank_init();
	check(waveBank_count() == 0, "a 1 MB chip ignores a bank past sector 7");
	deviceBytes = 2048u*1024u; waveBank_init();
	check(waveBank_count() == countA, "a 2 MB chip uses it");

	unsigned erasesBefore = erases;
	progressCalls = 0;
	check(waveBank_installFromSd(progress) == WAVEBANK_UNCHANGED && erases == erasesBefore && !progressCalls, "same file is skipped");

	/* a changed name changes the header, so the CRC must catch it */
	a[24] ^= 1;
	check(waveBank_installFromSd(0) == WAVEBANK_BAD_FILE && erases == erasesBefore && waveBank_count() == countA, "bad CRC keeps the flash");
	/* a changed frame count is caught too */
	a[152] ^= 2;
	check(waveBank_installFromSd(0) == WAVEBANK_BAD_FILE && waveBank_count() == countA, "bad frame count keeps the flash");
	a[152] ^= 2;
	a[24] ^= 1;
	cardSize = sizeA - 2;
	check(waveBank_installFromSd(0) == WAVEBANK_BAD_FILE && waveBank_count() == countA, "short file keeps the flash");
	/* the frames must match the count and the size */
	{
		WaveBankHeader h; memcpy(&h, a, sizeof(h));
		check(waveBank_headerValid(&h), "file header is valid");
		check(WAVEBANK_MAX == 32 && sizeof(h) == 256, "32 wavetables, 256-byte header");
		h.count = WAVEBANK_MAX + 1; check(!waveBank_headerValid(&h), "more than 32 wavetables is invalid"); h.count = a[8];
		h.frames[h.count] = 1; check(!waveBank_headerValid(&h), "a frame past the count is invalid"); h.frames[h.count] = 0;
		const uint8_t keep = h.frames[0]; h.frames[0] = 0; check(!waveBank_headerValid(&h), "a wavetable without frames is invalid"); h.frames[0] = keep;
		h.frames[1]++; check(!waveBank_headerValid(&h), "more frames than the data is invalid"); h.frames[1]--;
		h.frames[1]++; h.dataBytes += 4608; check(!waveBank_headerValid(&h), "more than 284 frames is invalid");
	}

	/* a small file erases only sector 7; a cut before the end leaves no valid bank (header last) */
	card = b; cardSize = sizeB; cutAfter = programs + 1000; erasedMask = 0;
	check(waveBank_installFromSd(0) == WAVEBANK_FLASH_ERROR && waveBank_count() == 0 && locked, "cut write leaves no tables");
	check(erasedMask == 0x80u && !memcmp(flashMem + 0x40000u, a + 0x40000u, sizeA - 0x40000u), "a small file erases only sector 7");
	cutAfter = programs + (sizeB - 256)/4 + 5;
	check(waveBank_installFromSd(0) == WAVEBANK_FLASH_ERROR && waveBank_count() == 0, "cut in the header leaves no tables");
	cutAfter = -1;
	check(waveBank_installFromSd(0) == WAVEBANK_WRITTEN && waveBank_count() == 2 && waveBank_frames(1) == 1 && flashHolds(b, sizeB), "next boot writes it");
	deviceBytes = 1024u*1024u; waveBank_init();
	check(waveBank_count() == 2, "a small bank works on a 1 MB chip");
	deviceBytes = 2048u*1024u;

	/* a flipped bit in flash fails the CRC at init */
	flashMem[300] ^= 4; waveBank_init();
	check(waveBank_count() == 0, "corrupt flash gives no tables");
	flashMem[300] ^= 4; waveBank_init();
	check(waveBank_count() == 2, "restored flash is valid");

	check(waveBank_level(0.f) == 0 && waveBank_level(54.9f) == 0 && waveBank_level(55.5f) == 1 &&
	      waveBank_level(109.f) == 1 && waveBank_level(110.5f) == 2 && waveBank_level(14000.f) == 8 &&
	      waveBank_level(14200.f) == 9 && waveBank_level(30000.f) == 9 && waveBank_level(-5.f) == 0, "octave levels");
	check(waveBank_crc(0, (const uint8_t*)"123456789", 9) == 0xCBF43926u, "CRC-32 check value");
	{
		int ok = 1; uint16_t at = 0;
		for(uint8_t l=0;l<WAVEBANK_LEVELS;l++){ok &= waveBank_levelOffset(l) == at; at += (uint16_t)(1u << waveBank_levelBits(l));}
		check(ok && at == WAVEBANK_FRAME_SAMPLES && waveBank_levelBits(0) == 10 && waveBank_levelBits(4) == 6 &&
		      waveBank_levelOffset(12) == waveBank_levelOffset(9), "level layout");
	}
	printf("%s %u assertions\n", failures ? "WAVEBANK FAIL" : "WAVEBANK PASS", checks);
	return failures != 0;
}
"""


def check_firmware(folder, file_a):
    src = folder / 'srcb'
    src.mkdir()
    write_wav(src / 'tri.wav', [1 - 4 * abs(i / 1024 - 0.5) for i in range(1024)])
    write_wav(src / 'pulse.wav', [0.9 if i < 100 else -0.1 for i in range(1024)])
    gen.build([src], folder / 'cardb', each=True)
    file_b = folder / 'cardb/WAVES/WAVES.BIN'
    code = (ROOT / 'Core/Src/Soundengine/DSPAudio/WaveBank.c').read_text(encoding='utf-8')
    if '--mutate' in sys.argv:
        old = 'if(crc != h.crc || f_lseek'
        assert old in code, 'mutation anchor'
        code = code.replace(old, 'if(f_lseek')
    build = folder / 'build'
    build.mkdir()
    (build / 'stm32f7xx_hal.h').write_text(STUBS_HAL, encoding='utf-8')
    (build / 'fatfs.h').write_text(STUBS_FATFS, encoding='utf-8')
    (build / 'WaveBank.c').write_text('#include <stdint.h>\nextern uint8_t flashMem[];\nextern uint32_t deviceBytes;\n' + code,
                                      encoding='utf-8')
    (build / 'test.c').write_text(TEST, encoding='utf-8')
    command = (f'call "{VS}" -arch=x64 >nul && cl /nologo /O2 /W3 /TC /I. /I"{ROOT / "Core/Inc"}" '
               f'"/DWAVEBANK_FLASH_ADDRESS=((uintptr_t)flashMem)" /DWAVEBANK_DEVICE_BYTES=deviceBytes /D_CRT_SECURE_NO_WARNINGS '
               f'/Fe:wavebank.exe test.c WaveBank.c >build.log && .\\wavebank.exe "{file_a}" "{file_b}"')
    result = subprocess.run(command, shell=True, cwd=build)
    if result.returncode:
        log = build / 'build.log'
        if log.exists():
            print(log.read_text(errors='replace'))
    check(result.returncode == 0, 'firmware WaveBank.c')


def main():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        folder = Path(tmp)
        file_a = check_generator(folder)
        check_firmware(folder, file_a)
    print(f'{"FAIL" if failures else "PASS"} {checks} generator and firmware checks')
    sys.exit(failures != 0)


if __name__ == '__main__':
    main()
