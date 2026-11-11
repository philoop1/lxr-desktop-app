/*
 * freezeDiag.c
 *
 * Mutador 0.2.85d freeze diagnosis build, see freezeDiag.h.
 *
 * - The 1 ms SysTick (preempt priority 0, above audio TIM2 = 4 and the main
 *   loop) samples the PC it interrupted. If TIM2 is running but has not
 *   calculated a block for 500 ms, or the main loop has not turned for 20 s
 *   while audio runs, it stores that PC/LR and resets.
 * - The fault handlers store the stacked PC/LR and the fault status and reset.
 * - The hardware watchdog (about 32 s, refreshed by the SysTick) resets a
 *   lockup that stops the SysTick itself: interrupts off, or a stuck display
 *   timer (same priority as the SysTick). The markers and the last PC samples
 *   then show where.
 * - At the next boot the display shows the record; the encoder button steps
 *   through three screens and then boots normally.
 *
 * SPDX-License-Identifier: GPL-3.0-only
 */
#include "freezeDiag.h"

#if LXR_FREEZE_DIAG

#include "main.h"
#include "lcd.h"
#include "encoder.h"
#include "menu/screensaver.h"

#define FREEZE_MAGIC 0x46525A31UL /* "FRZ1" */
#define AUDIO_STALL_MS 500u
#define MAIN_STALL_MS 20000u

static uint8_t freezeDiag_watching;
static uint32_t freezeDiag_lastAudio, freezeDiag_lastMain;
static uint32_t freezeDiag_audioStill, freezeDiag_mainStill;

static void freezeDiag_enableBackupSram(void)
{
	RCC->APB1ENR |= RCC_APB1ENR_PWREN;
	(void)RCC->APB1ENR;
	PWR->CR1 |= PWR_CR1_DBP;
	RCC->AHB1ENR |= RCC_AHB1ENR_BKPSRAMEN;
	(void)RCC->AHB1ENR;
}

static void freezeDiag_clear(void)
{
	volatile FreezeDiag *d = FREEZE_DIAG;
	volatile uint8_t *p = (volatile uint8_t *)d;
	for(uint32_t i = 0; i < sizeof(FreezeDiag); i++) p[i] = 0;
	d->magic = FREEZE_MAGIC;
	d->check = ~FREEZE_MAGIC;
}

/* store and reset: called with the stacked exception frame of the interrupted code */
static void freezeDiag_trip(uint8_t kind, const uint32_t *frame)
{
	volatile FreezeDiag *d = FREEZE_DIAG;
	d->kind = kind;
	d->pc = frame ? frame[6] : 0;
	d->lr = frame ? frame[5] : 0;
	d->cfsr = SCB->CFSR;
	d->hfsr = SCB->HFSR;
	__DSB();
	NVIC_SystemReset();
}

/* frame pointer from the naked handlers below */
void freezeDiag_faultC(const uint32_t *frame)
{
	freezeDiag_trip('F', frame);
}

void freezeDiag_sysTickC(const uint32_t *frame)
{
	/* the original SysTick work */
	HAL_IncTick();
	screensaver_timer++;
	encoder_callback();

	volatile FreezeDiag *d = FREEZE_DIAG;
	d->sample[d->sampleIdx & 3u] = frame[6];
	d->sampleIdx++;
	if(!freezeDiag_watching) return;
	IWDG->KR = 0xAAAAu;

	const uint8_t audioOn = (TIM2->CR1 & TIM_CR1_CEN) && (TIM2->DIER & TIM_DIER_UIE);
	const uint32_t a = d->audioBeat, m = d->mainBeat;
	if(!audioOn || a != freezeDiag_lastAudio) { freezeDiag_lastAudio = a; freezeDiag_audioStill = 0; }
	else if(++freezeDiag_audioStill >= AUDIO_STALL_MS) freezeDiag_trip('A', frame);
	/* the main loop may block for long on purpose while audio is stopped (saving) */
	if(!audioOn || m != freezeDiag_lastMain) { freezeDiag_lastMain = m; freezeDiag_mainStill = 0; }
	else if(++freezeDiag_mainStill >= MAIN_STALL_MS) freezeDiag_trip('M', frame);
}

__attribute__((naked)) void SysTick_Handler(void)
{
	__asm volatile(
		"tst lr, #4\n"
		"ite eq\n"
		"mrseq r0, msp\n"
		"mrsne r0, psp\n"
		"b freezeDiag_sysTickC\n");
}

#define FREEZE_FAULT_ENTRY(name) \
__attribute__((naked)) void name(void) \
{ \
	__asm volatile( \
		"tst lr, #4\n" \
		"ite eq\n" \
		"mrseq r0, msp\n" \
		"mrsne r0, psp\n" \
		"b freezeDiag_faultC\n"); \
}
FREEZE_FAULT_ENTRY(HardFault_Handler)
FREEZE_FAULT_ENTRY(MemManage_Handler)
FREEZE_FAULT_ENTRY(BusFault_Handler)
FREEZE_FAULT_ENTRY(UsageFault_Handler)

static void freezeDiag_hex(char *out, uint32_t v)
{
	static const char digits[] = "0123456789ABCDEF";
	for(int i = 7; i >= 0; i--) { out[i] = digits[v & 15u]; v >>= 4; }
}

static void freezeDiag_hex2(char *out, uint8_t v)
{
	static const char digits[] = "0123456789ABCDEF";
	out[0] = digits[v >> 4];
	out[1] = digits[v & 15u];
}

static void freezeDiag_screen(const char *top, const char *bottom)
{
	lcd_clear();
	lcd_home();
	lcd_string(top);
	lcd_setcursor(0, 2);
	lcd_string(bottom);
	while(encode_readButton() == 0);
	while(encode_readButton() == 1);
}

void freezeDiag_boot(void)
{
	freezeDiag_enableBackupSram();
	volatile FreezeDiag *d = FREEZE_DIAG;
	const uint8_t valid = d->magic == FREEZE_MAGIC && d->check == ~FREEZE_MAGIC;
	const uint8_t watchdog = (RCC->CSR & RCC_CSR_IWDGRSTF) != 0;
	RCC->CSR |= RCC_CSR_RMVF;
	uint8_t kind = valid ? d->kind : 0;
	if(valid && !kind && d->armed && watchdog) kind = 'W';
	if(kind) {
		char top[17] = "FRZ x 00000000  ", bottom[17] = "LR    00000000  ";
		top[4] = (char)kind;
		freezeDiag_hex(&top[6], d->pc);
		freezeDiag_hex(&bottom[6], d->lr);
		freezeDiag_screen(top, bottom);

		char t2[17] = "CF 00000000     ", b2[17] = "cc0000 d000 s0m0";
		freezeDiag_hex(&t2[3], d->cfsr);
		freezeDiag_hex2(&b2[2], d->lastStatus);
		freezeDiag_hex2(&b2[4], d->lastData1);
		b2[8] = (char)('0' + (d->lastDest / 100u) % 10u);
		b2[9] = (char)('0' + (d->lastDest / 10u) % 10u);
		b2[10] = (char)('0' + d->lastDest % 10u);
		b2[13] = (char)('0' + (d->inSetDest ? 1 : 0));
		b2[15] = (char)('0' + (d->inMenuTick ? 1 : 0));
		freezeDiag_screen(t2, b2);

		char t3[17] = "1 00000000      ", b3[17] = "2 00000000      ";
		const uint32_t n = d->sampleIdx;
		freezeDiag_hex(&t3[2], d->sample[(n - 1u) & 3u]);
		freezeDiag_hex(&b3[2], d->sample[(n - 2u) & 3u]);
		freezeDiag_screen(t3, b3);
	}
	freezeDiag_clear();
}

void freezeDiag_arm(void)
{
	FREEZE_DIAG->armed = 1;
	freezeDiag_lastAudio = FREEZE_DIAG->audioBeat;
	freezeDiag_lastMain = FREEZE_DIAG->mainBeat;
	/* independent watchdog: LSI 32 kHz / 256, reload 4095 -> about 32 s */
	IWDG->KR = 0xCCCCu;
	IWDG->KR = 0x5555u;
	IWDG->PR = 6u;
	IWDG->RLR = 4095u;
	while(IWDG->SR) {}
	IWDG->KR = 0xAAAAu;
	freezeDiag_watching = 1;
}

#endif
