/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only
 * User wavetables in flash sectors 7 to 11, see WaveBank.h.
 */
#include "Soundengine/DSPAudio/WaveBank.h"
#include "stm32f7xx_hal.h"
#include "fatfs.h"
#include <string.h>

static const char waveBank_magic[8] = {'L','X','R','W','T','0','0','3'};
static uint8_t waveBank_tables = 0;
static uint16_t waveBank_firstFrame[WAVEBANK_MAX];

#define WAVEBANK_HEADER ((const WaveBankHeader*)WAVEBANK_FLASH_ADDRESS)
#define WAVEBANK_DATA ((const int16_t*)(WAVEBANK_FLASH_ADDRESS + WAVEBANK_HEADER_BYTES))
#define WAVEBANK_CHUNK 128u // words read from the card at once
// names and frames lie together in the header and share the CRC with the data
#define WAVEBANK_CRC_HEAD (sizeof(((WaveBankHeader*)0)->names) + sizeof(((WaveBankHeader*)0)->frames))

// sectors 8 to 11 exist only on the 2 MB chip; the flash size register says which one this is
#ifndef WAVEBANK_DEVICE_BYTES
#define WAVEBANK_DEVICE_BYTES ((uint32_t)*(const volatile uint16_t*)FLASHSIZE_BASE * 1024u)
#endif

static uint32_t waveBank_available(void)
{
	const uint32_t device = WAVEBANK_DEVICE_BYTES;
	const uint32_t start = WAVEBANK_FIRST_SECTOR_OFFSET;
	if(device <= start) return 0;
	return device - start < WAVEBANK_FLASH_BYTES ? device - start : WAVEBANK_FLASH_BYTES;
}

typedef char WaveBankHeaderSize[(sizeof(WaveBankHeader) == WAVEBANK_HEADER_BYTES) ? 1 : -1];

// CRC-32 as in zlib, a nibble at a time
uint32_t waveBank_crc(uint32_t crc, const uint8_t *data, uint32_t bytes)
{
	static const uint32_t nibble[16] =
	{
		0x00000000u, 0x1DB71064u, 0x3B6E20C8u, 0x26D930ACu, 0x76DC4190u, 0x6B6B51F4u, 0x4DB26158u, 0x5005713Cu,
		0xEDB88320u, 0xF00F9344u, 0xD6D6A3E8u, 0xCB61B38Cu, 0x9B64C2B0u, 0x86D3D2D4u, 0xA00AE278u, 0xBDBDF21Cu
	};
	crc = ~crc;
	while(bytes--)
	{
		crc ^= *data++;
		crc = (crc >> 4) ^ nibble[crc & 15u];
		crc = (crc >> 4) ^ nibble[crc & 15u];
	}
	return ~crc;
}

uint8_t waveBank_headerValid(const WaveBankHeader *h)
{
	if(memcmp(h->magic, waveBank_magic, sizeof(waveBank_magic))) return 0;
	if(h->count < 1 || h->count > WAVEBANK_MAX) return 0;
	if(h->levels != WAVEBANK_LEVELS || h->length != WAVEBANK_LENGTH || h->reserved) return 0;
	uint32_t frames = 0;
	for(uint8_t i=0;i<WAVEBANK_MAX;i++)
	{
		if(h->names[i][3]) return 0;
		if((i < h->count) != (h->frames[i] != 0)) return 0;
		frames += h->frames[i];
	}
	if(frames > WAVEBANK_MAX_FRAMES) return 0;
	if(h->dataBytes != frames*WAVEBANK_FRAME_SAMPLES*2u) return 0;
	return 1;
}

void waveBank_init(void)
{
	const WaveBankHeader *h = WAVEBANK_HEADER;
	waveBank_tables = 0;
	if(!waveBank_headerValid(h) || WAVEBANK_HEADER_BYTES + h->dataBytes > waveBank_available()) return;
	uint32_t crc = waveBank_crc(0, (const uint8_t*)h->names, WAVEBANK_CRC_HEAD);
	crc = waveBank_crc(crc, (const uint8_t*)WAVEBANK_DATA, h->dataBytes);
	if(crc != h->crc) return;
	uint16_t first = 0;
	for(uint8_t i=0;i<h->count;i++)
	{
		waveBank_firstFrame[i] = first;
		first += h->frames[i];
	}
	waveBank_tables = (uint8_t)h->count;
}

uint8_t waveBank_count(void)
{
	return waveBank_tables;
}

uint32_t waveBank_flashBytes(void)
{
	return waveBank_tables ? WAVEBANK_HEADER_BYTES + WAVEBANK_HEADER->dataBytes : 0;
}

const char* waveBank_name(uint8_t table)
{
	return table < waveBank_tables ? WAVEBANK_HEADER->names[table] : "---";
}

uint8_t waveBank_frames(uint8_t table)
{
	return table < waveBank_tables ? WAVEBANK_HEADER->frames[table] : 0;
}

const int16_t* waveBank_frame(uint8_t table, uint8_t frame)
{
	if(table >= waveBank_tables || frame >= WAVEBANK_HEADER->frames[table]) return 0;
	return WAVEBANK_DATA + (uint32_t)(waveBank_firstFrame[table] + frame)*WAVEBANK_FRAME_SAMPLES;
}

uint8_t waveBank_level(float freq)
{
	// the generator keeps level j below 20 kHz up to 55 Hz * 2^j
	uint32_t ratio = freq > 0.f ? (uint32_t)(freq*(1.f/55.f)) : 0;
	uint8_t level = 0;
	while(ratio && level < WAVEBANK_LEVELS-1)
	{
		level++;
		ratio >>= 1;
	}
	return level;
}

uint8_t waveBank_installFromSd(void (*progress)(uint8_t percent))
{
	static uint32_t chunk[WAVEBANK_CHUNK];
	WaveBankHeader h;
	UINT got = 0;
	uint32_t remaining, crc;
	uintptr_t addr;
	uint32_t sectorError = 0;
	FLASH_EraseInitTypeDef erase = {0};
	uint8_t result = WAVEBANK_BAD_FILE;

	if(f_open(&SDFile, WAVEBANK_FILE, FA_OPEN_EXISTING | FA_READ) != FR_OK)
		return WAVEBANK_NO_FILE;
	if(f_read(&SDFile, &h, sizeof(h), &got) != FR_OK || got != sizeof(h) ||
	   !waveBank_headerValid(&h) || f_size(&SDFile) != WAVEBANK_HEADER_BYTES + h.dataBytes ||
	   WAVEBANK_HEADER_BYTES + h.dataBytes > waveBank_available())
		goto done;
	if(waveBank_tables && !memcmp(&h, WAVEBANK_HEADER, sizeof(h)))
	{
		result = WAVEBANK_UNCHANGED;
		goto done;
	}

	// the whole file must match its CRC before the flash is erased
	crc = waveBank_crc(0, (const uint8_t*)h.names, WAVEBANK_CRC_HEAD);
	for(remaining = h.dataBytes; remaining; remaining -= got)
	{
		const UINT want = remaining < sizeof(chunk) ? remaining : sizeof(chunk);
		if(f_read(&SDFile, chunk, want, &got) != FR_OK || got != want) goto done;
		crc = waveBank_crc(crc, (const uint8_t*)chunk, got);
	}
	if(crc != h.crc || f_lseek(&SDFile, WAVEBANK_HEADER_BYTES) != FR_OK) goto done;

	// erase only the sectors the file needs, one by one for the progress
	const uint32_t sectors = (WAVEBANK_HEADER_BYTES + h.dataBytes + WAVEBANK_SECTOR_BYTES - 1u)/WAVEBANK_SECTOR_BYTES;
	const uint32_t steps = sectors + h.dataBytes/sizeof(chunk) + 1u;
	uint32_t step = 0;
	result = WAVEBANK_FLASH_ERROR;
	HAL_FLASH_Unlock();
	erase.TypeErase = FLASH_TYPEERASE_SECTORS;
	erase.NbSectors = 1;
	erase.VoltageRange = FLASH_VOLTAGE_RANGE_3;
	for(uint32_t i=0;i<sectors;i++)
	{
		if(progress) progress((uint8_t)(step++*100u/steps));
		erase.Sector = WAVEBANK_FIRST_SECTOR + i;
		if(HAL_FLASHEx_Erase(&erase, &sectorError) != HAL_OK || sectorError != 0xFFFFFFFFu) goto lock;
	}

	// data first, the header last: an interrupted copy leaves no valid header
	addr = WAVEBANK_FLASH_ADDRESS + WAVEBANK_HEADER_BYTES;
	for(remaining = h.dataBytes; remaining; remaining -= got)
	{
		const UINT want = remaining < sizeof(chunk) ? remaining : sizeof(chunk);
		if(f_read(&SDFile, chunk, want, &got) != FR_OK || got != want) goto lock;
		if(progress && (step++ & 31u) == 0) progress((uint8_t)(step*100u/steps));
		for(uint32_t i=0;i<got/4u;i++, addr += 4u)
			if(HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, addr, chunk[i]) != HAL_OK) goto lock;
	}
	addr = WAVEBANK_FLASH_ADDRESS;
	for(uint32_t i=0;i<WAVEBANK_HEADER_BYTES/4u;i++, addr += 4u)
	{
		uint32_t word;
		memcpy(&word, (const uint8_t*)&h + i*4u, 4);
		if(HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, addr, word) != HAL_OK) goto lock;
	}
	result = WAVEBANK_WRITTEN;
	if(progress) progress(100);

lock:
	HAL_FLASH_Lock();
	SCB_InvalidateDCache_by_Addr((uint32_t*)WAVEBANK_FLASH_ADDRESS, (int32_t)WAVEBANK_FLASH_BYTES);
done:
	f_close(&SDFile);
	waveBank_init();
	if(result == WAVEBANK_WRITTEN && !waveBank_tables) result = WAVEBANK_FLASH_ERROR;
	return result;
}
