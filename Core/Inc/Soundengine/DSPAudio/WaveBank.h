/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only
 * User wavetables in flash sectors 7 to 11 (the LXR-02 has 2 MB, single bank). tools/make_wavetables.py builds
 * WAVES/WAVES.BIN on the SD card; at boot the firmware copies it to the
 * sector when its header differs from the one there.
 *
 * Up to 32 wavetables with 1 to 255 frames each (Serum files have several),
 * at most WAVEBANK_MAX_FRAMES frames in all. Every frame holds 10 octave
 * levels; level j plays below 55 Hz * 2^j. The high levels need few
 * partials, so they are short: 1024, 512, 256, 128 and then 64 samples.
 */
#ifndef WAVEBANK_H_
#define WAVEBANK_H_

#include <stdint.h>

#define WAVEBANK_MAX 32
#define WAVEBANK_LEVELS 10
#define WAVEBANK_LENGTH 1024				// samples of level 0
#define WAVEBANK_FRAME_SAMPLES 2304u		// 1024+512+256+128+6*64
#define WAVEBANK_HEADER_BYTES 256u
#define WAVEBANK_FILE "/WAVES/WAVES.BIN"
#ifndef WAVEBANK_FLASH_ADDRESS
#define WAVEBANK_FLASH_ADDRESS 0x080C0000u // sector 7
#endif
#define WAVEBANK_FIRST_SECTOR 7u
#define WAVEBANK_FIRST_SECTOR_OFFSET 0xC0000u	// sector 7 from the start of flash
#define WAVEBANK_SECTORS 5u					// 7 to 11
#define WAVEBANK_SECTOR_BYTES 0x40000u		// 256 KB each
#define WAVEBANK_FLASH_BYTES (WAVEBANK_SECTORS*WAVEBANK_SECTOR_BYTES)	// 1280 KB
#define WAVEBANK_MAX_FRAMES ((WAVEBANK_FLASH_BYTES-WAVEBANK_HEADER_BYTES)/(WAVEBANK_FRAME_SAMPLES*2u)) // 284

typedef struct WaveBankHeaderStruct
{
	char magic[8];			// "LXRWT003"
	uint16_t count;			// wavetables, 1..WAVEBANK_MAX
	uint16_t levels;		// WAVEBANK_LEVELS
	uint16_t length;		// WAVEBANK_LENGTH
	uint16_t reserved;
	uint32_t dataBytes;		// frames in all * WAVEBANK_FRAME_SAMPLES * 2
	uint32_t crc;			// CRC-32 (zlib) of names, frames and data
	char names[WAVEBANK_MAX][4];
	uint8_t frames[WAVEBANK_MAX];	// frames per wavetable, 0 past count
	uint8_t pad[WAVEBANK_HEADER_BYTES-24-WAVEBANK_MAX*5];
} WaveBankHeader;

enum WaveBankInstallResult
{
	WAVEBANK_UNCHANGED,		// the flash already holds this file
	WAVEBANK_WRITTEN,
	WAVEBANK_NO_FILE,		// no WAVES.BIN, the flash is kept
	WAVEBANK_BAD_FILE,		// header or CRC wrong, the flash is kept
	WAVEBANK_FLASH_ERROR
};

// Level j of a frame: 2^bits samples starting at the offset
static inline uint8_t waveBank_levelBits(uint8_t level)
{
	return level < 4 ? (uint8_t)(10-level) : 6;
}
static inline uint16_t waveBank_levelOffset(uint8_t level)
{
	if(level > WAVEBANK_LEVELS-1) level = WAVEBANK_LEVELS-1;
	return level < 4 ? (uint16_t)(2048-(2048>>level)) : (uint16_t)(1920+64*(level-4));
}

// Checks the flash copy and makes its wavetables available; 0 if invalid
void waveBank_init(void);
uint8_t waveBank_count(void);
// header and data in flash, 0 without valid wavetables
uint32_t waveBank_flashBytes(void);
// Three letters, or "---" past the count
const char* waveBank_name(uint8_t table);
// Frames of one wavetable, 0 past the count
uint8_t waveBank_frames(uint8_t table);
// One frame (WAVEBANK_FRAME_SAMPLES samples, all levels), or 0
const int16_t* waveBank_frame(uint8_t table, uint8_t frame);
// Level for a frequency: level j plays below 55 Hz * 2^j
uint8_t waveBank_level(float freq);
uint32_t waveBank_crc(uint32_t crc, const uint8_t *data, uint32_t bytes);
uint8_t waveBank_headerValid(const WaveBankHeader *h);
// Boot only: SD to flash, needs a mounted card and no running audio.
// progress (may be 0) gets 0..100 while a new file is copied.
uint8_t waveBank_installFromSd(void (*progress)(uint8_t percent));

#endif /* WAVEBANK_H_ */
