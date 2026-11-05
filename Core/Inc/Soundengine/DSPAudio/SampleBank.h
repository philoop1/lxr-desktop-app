/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only
 * One-shot user samples in flash, after the user wavetables.
 *
 * SAMPLES/SAMPLES.BIN (tools/make_samples.py) holds a 1 KB header and the
 * samples as 16 bit mono. At boot the firmware copies it to flash when the
 * header differs. The bank starts at the first 256 KB sector after the
 * wavetables, at sector 8 at the earliest, so it needs the 2 MB chip. When
 * the wavetables grow into it, its header is erased and the next boot writes
 * the bank again behind them.
 *
 * Waveform numbers: 0..5 built-in, 6..37 wavetables, 38.. samples. Fixed
 * numbers keep kits valid when the number of wavetables changes.
 */
#ifndef SAMPLEBANK_H_
#define SAMPLEBANK_H_

#include <stdint.h>

#define SAMPLEBANK_MAX 48
#define SAMPLEBANK_FIRST_WAVE 38u			// NUM_OSC_WAVEFORMS + WAVEBANK_MAX
#define SAMPLEBANK_HEADER_BYTES 1024u
#define SAMPLEBANK_FILE "/SAMPLES/SAMPLES.BIN"
#define SAMPLEBANK_FIRST_SECTOR 8u			// sector 7 stays for the wavetables
#define SAMPLEBANK_LAST_SECTOR 11u
#define SAMPLEBANK_ROOT_NOTE 60				// coarse 0 (value 60) plays the sample at its own pitch
#define SAMPLEBANK_MIN_RATE 8000u
#define SAMPLEBANK_MAX_RATE 96000u
#define SAMPLEBANK_PHASE_BITS 12u			// phase: frame in the upper 20 bits, fraction in the lower 12

typedef struct SampleBankEntryStruct
{
	char name[4];			// three characters and 0
	uint32_t offset;		// bytes from the start of the data, a multiple of 4
	uint32_t frames;		// 16 bit mono frames, at least 2
	uint32_t rate;			// Hz, the pitch at the root note
} SampleBankEntry;

typedef struct SampleBankHeaderStruct
{
	char magic[8];			// "LXRSM001"
	uint16_t count;			// samples, 1..SAMPLEBANK_MAX
	uint16_t reserved;
	uint32_t dataBytes;		// all sample data with its padding
	uint32_t crc;			// CRC-32 (zlib) of the entries and the data
	uint32_t reserved2;
	SampleBankEntry entries[SAMPLEBANK_MAX];
	uint8_t pad[SAMPLEBANK_HEADER_BYTES-24-SAMPLEBANK_MAX*sizeof(SampleBankEntry)];
} SampleBankHeader;

enum SampleBankInstallResult
{
	SAMPLEBANK_UNCHANGED,	// the flash already holds this file
	SAMPLEBANK_WRITTEN,
	SAMPLEBANK_NO_FILE,		// no SAMPLES.BIN, the flash is kept
	SAMPLEBANK_BAD_FILE,	// header or CRC wrong, the flash is kept
	SAMPLEBANK_NO_SPACE,	// too big for the sectors after the wavetables
	SAMPLEBANK_FLASH_ERROR
};

// Checks the flash copy behind the wavetables; call after the wavetables are installed
void sampleBank_init(void);
uint8_t sampleBank_count(void);
// "---" past the count
const char* sampleBank_name(uint8_t sample);
uint32_t sampleBank_frames(uint8_t sample);
uint32_t sampleBank_rate(uint8_t sample);
// 0 past the count
const int16_t* sampleBank_data(uint8_t sample);
uint8_t sampleBank_headerValid(const SampleBankHeader *h);
// Copies SAMPLES.BIN to flash when it differs from the flash copy
uint8_t sampleBank_installFromSd(void (*progress)(uint8_t percent));

#endif /* SAMPLEBANK_H_ */
