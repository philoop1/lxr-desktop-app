/* Copyright (C) 2026. SPDX-License-Identifier: GPL-3.0-only
 * One-shot user samples in flash after the wavetables, see SampleBank.h.
 */
#include "Soundengine/DSPAudio/SampleBank.h"
#include "Soundengine/DSPAudio/WaveBank.h"
#include "stm32f7xx_hal.h"
#include "fatfs.h"
#include <string.h>

static const char sampleBank_magic[8] = {'L','X','R','S','M','0','0','1'};
static uint8_t sampleBank_samples = 0;
static uintptr_t sampleBank_address = 0;	// header of the flash copy

#define SAMPLEBANK_CHUNK 128u // words read from the card at once
#define SAMPLEBANK_HEADER ((const SampleBankHeader*)sampleBank_address)
#define SAMPLEBANK_DATA ((const uint8_t*)(sampleBank_address + SAMPLEBANK_HEADER_BYTES))
// the entries lie in the header and share the CRC with the data
#define SAMPLEBANK_CRC_HEAD (sizeof(((SampleBankHeader*)0)->entries))

#ifndef SAMPLEBANK_DEVICE_BYTES
#define SAMPLEBANK_DEVICE_BYTES ((uint32_t)*(const volatile uint16_t*)FLASHSIZE_BASE * 1024u)
#endif

typedef char SampleBankHeaderSize[(sizeof(SampleBankHeader) == SAMPLEBANK_HEADER_BYTES) ? 1 : -1];

// first sector after the wavetables, sector 8 at the earliest
static uint32_t sampleBank_firstSector(void)
{
	const uint32_t waveBytes = waveBank_flashBytes();
	const uint32_t sector = WAVEBANK_FIRST_SECTOR + (waveBytes + WAVEBANK_SECTOR_BYTES - 1u)/WAVEBANK_SECTOR_BYTES;
	return sector < SAMPLEBANK_FIRST_SECTOR ? SAMPLEBANK_FIRST_SECTOR : sector;
}

// bytes from the first sector to the end of sector 11 or of a smaller chip
static uint32_t sampleBank_available(uint32_t sector)
{
	if(sector > SAMPLEBANK_LAST_SECTOR) return 0;
	const uint32_t start = WAVEBANK_FIRST_SECTOR_OFFSET + (sector - WAVEBANK_FIRST_SECTOR)*WAVEBANK_SECTOR_BYTES;
	uint32_t end = WAVEBANK_FIRST_SECTOR_OFFSET + (SAMPLEBANK_LAST_SECTOR + 1u - WAVEBANK_FIRST_SECTOR)*WAVEBANK_SECTOR_BYTES;
	const uint32_t device = SAMPLEBANK_DEVICE_BYTES;
	if(device < end) end = device;
	return end > start ? end - start : 0;
}

static uintptr_t sampleBank_sectorAddress(uint32_t sector)
{
	return WAVEBANK_FLASH_ADDRESS + (sector - WAVEBANK_FIRST_SECTOR)*WAVEBANK_SECTOR_BYTES;
}

uint8_t sampleBank_headerValid(const SampleBankHeader *h)
{
	if(memcmp(h->magic, sampleBank_magic, sizeof(sampleBank_magic))) return 0;
	if(h->count < 1 || h->count > SAMPLEBANK_MAX || h->reserved || h->reserved2) return 0;
	if(h->dataBytes & 3u) return 0;
	for(uint8_t i=0;i<SAMPLEBANK_MAX;i++)
	{
		const SampleBankEntry *e = &h->entries[i];
		if(i >= h->count)
		{
			if(e->frames || e->offset || e->rate) return 0;
			continue;
		}
		if(e->name[3] || (e->offset & 3u) || e->frames < 2) return 0;
		if(e->rate < SAMPLEBANK_MIN_RATE || e->rate > SAMPLEBANK_MAX_RATE) return 0;
		if(e->offset > h->dataBytes || e->frames > (h->dataBytes - e->offset)/2u) return 0;
		// the phase holds 20 bits of frames
		if(e->frames >= (1u << (32u - SAMPLEBANK_PHASE_BITS))) return 0;
	}
	return 1;
}

void sampleBank_init(void)
{
	const uint32_t sector = sampleBank_firstSector();
	sampleBank_samples = 0;
	sampleBank_address = sampleBank_sectorAddress(sector);
	const SampleBankHeader *h = SAMPLEBANK_HEADER;
	const uint32_t available = sampleBank_available(sector);
	if(available < SAMPLEBANK_HEADER_BYTES || !sampleBank_headerValid(h) ||
	   h->dataBytes > available - SAMPLEBANK_HEADER_BYTES) return;
	uint32_t crc = waveBank_crc(0, (const uint8_t*)h->entries, SAMPLEBANK_CRC_HEAD);
	crc = waveBank_crc(crc, SAMPLEBANK_DATA, h->dataBytes);
	if(crc != h->crc) return;
	sampleBank_samples = (uint8_t)h->count;
}

uint8_t sampleBank_count(void)
{
	return sampleBank_samples;
}

const char* sampleBank_name(uint8_t sample)
{
	return sample < sampleBank_samples ? SAMPLEBANK_HEADER->entries[sample].name : "---";
}

uint32_t sampleBank_frames(uint8_t sample)
{
	return sample < sampleBank_samples ? SAMPLEBANK_HEADER->entries[sample].frames : 0;
}

uint32_t sampleBank_rate(uint8_t sample)
{
	return sample < sampleBank_samples ? SAMPLEBANK_HEADER->entries[sample].rate : 0;
}

const int16_t* sampleBank_data(uint8_t sample)
{
	if(sample >= sampleBank_samples) return 0;
	return (const int16_t*)(SAMPLEBANK_DATA + SAMPLEBANK_HEADER->entries[sample].offset);
}

uint8_t sampleBank_installFromSd(void (*progress)(uint8_t percent))
{
	static uint32_t chunk[SAMPLEBANK_CHUNK];
	SampleBankHeader h;
	UINT got = 0;
	uint32_t remaining, crc;
	uintptr_t addr;
	uint32_t sectorError = 0;
	FLASH_EraseInitTypeDef erase = {0};
	uint8_t result = SAMPLEBANK_BAD_FILE;
	const uint32_t sector = sampleBank_firstSector();
	const uintptr_t base = sampleBank_sectorAddress(sector);
	const uint32_t available = sampleBank_available(sector);

	if(f_open(&SDFile, SAMPLEBANK_FILE, FA_OPEN_EXISTING | FA_READ) != FR_OK)
		return SAMPLEBANK_NO_FILE;
	if(f_read(&SDFile, &h, sizeof(h), &got) != FR_OK || got != sizeof(h) ||
	   !sampleBank_headerValid(&h) || f_size(&SDFile) != SAMPLEBANK_HEADER_BYTES + h.dataBytes)
		goto done;
	if(available < SAMPLEBANK_HEADER_BYTES || h.dataBytes > available - SAMPLEBANK_HEADER_BYTES)
	{
		result = SAMPLEBANK_NO_SPACE;
		goto done;
	}
	if(sampleBank_samples && sampleBank_address == base && !memcmp(&h, SAMPLEBANK_HEADER, sizeof(h)))
	{
		result = SAMPLEBANK_UNCHANGED;
		goto done;
	}

	// the whole file must match its CRC before the flash is erased
	crc = waveBank_crc(0, (const uint8_t*)h.entries, SAMPLEBANK_CRC_HEAD);
	for(remaining = h.dataBytes; remaining; remaining -= got)
	{
		const UINT want = remaining < sizeof(chunk) ? remaining : sizeof(chunk);
		if(f_read(&SDFile, chunk, want, &got) != FR_OK || got != want) goto done;
		crc = waveBank_crc(crc, (const uint8_t*)chunk, got);
	}
	if(crc != h.crc || f_lseek(&SDFile, SAMPLEBANK_HEADER_BYTES) != FR_OK) goto done;

	// erase only the sectors the file needs
	const uint32_t sectors = (SAMPLEBANK_HEADER_BYTES + h.dataBytes + WAVEBANK_SECTOR_BYTES - 1u)/WAVEBANK_SECTOR_BYTES;
	const uint32_t steps = sectors + h.dataBytes/sizeof(chunk) + 1u;
	uint32_t step = 0;
	result = SAMPLEBANK_FLASH_ERROR;
	sampleBank_samples = 0;
	HAL_FLASH_Unlock();
	erase.TypeErase = FLASH_TYPEERASE_SECTORS;
	erase.NbSectors = 1;
	erase.VoltageRange = FLASH_VOLTAGE_RANGE_3;
	for(uint32_t i=0;i<sectors;i++)
	{
		if(progress) progress((uint8_t)(step++*100u/steps));
		erase.Sector = sector + i;
		if(HAL_FLASHEx_Erase(&erase, &sectorError) != HAL_OK || sectorError != 0xFFFFFFFFu) goto lock;
	}

	// data first, the header last: an interrupted copy leaves no valid header
	addr = base + SAMPLEBANK_HEADER_BYTES;
	for(remaining = h.dataBytes; remaining; remaining -= got)
	{
		const UINT want = remaining < sizeof(chunk) ? remaining : sizeof(chunk);
		if(f_read(&SDFile, chunk, want, &got) != FR_OK || got != want) goto lock;
		if(progress && (step++ & 31u) == 0) progress((uint8_t)(step*100u/steps));
		for(uint32_t i=0;i<got/4u;i++, addr += 4u)
			if(HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, addr, chunk[i]) != HAL_OK) goto lock;
	}
	addr = base;
	for(uint32_t i=0;i<SAMPLEBANK_HEADER_BYTES/4u;i++, addr += 4u)
	{
		uint32_t word;
		memcpy(&word, (const uint8_t*)&h + i*4u, 4);
		if(HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, addr, word) != HAL_OK) goto lock;
	}
	result = SAMPLEBANK_WRITTEN;
	if(progress) progress(100);

lock:
	HAL_FLASH_Lock();
	SCB_InvalidateDCache_by_Addr((uint32_t*)base, (int32_t)(sectors*WAVEBANK_SECTOR_BYTES));
done:
	f_close(&SDFile);
	sampleBank_init();
	if(result == SAMPLEBANK_WRITTEN && !sampleBank_samples) result = SAMPLEBANK_FLASH_ERROR;
	return result;
}
