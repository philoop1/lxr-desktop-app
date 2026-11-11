/*
 * usb_manager.c
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 *
 *
 *  Created on: 26.10.2012
 *      Author: Julian Schmidt
 */
#include "Soundengine/USB/usb_manager.h"
#include <string.h>
#include "usbd_cdc_if.h"
#include "Soundengine/MIDI/MidiParser.h"




enum {
	USB_NOT_DETECTED,
	USB_DETECTED,
};
//USBD_HandleTypeDef           USB_OTG_dev;
//-------------------------------------------------------------------------------
#if 0
void usb_init()
{
#if HAL_USB
	  if (USBD_Init(&hUsbDeviceFS, &FS_Desc, DEVICE_FS) != USBD_OK)
	  {
	    Error_Handler();
	  }
	  if (USBD_RegisterClass(&hUsbDeviceFS, &USBD_CDC) != USBD_OK)
	  {
	    Error_Handler();
	  }
	  if (USBD_CDC_RegisterInterface(&hUsbDeviceFS, &USBD_Interface_fops_FS) != USBD_OK)
	  {
	    Error_Handler();
	  }
	  if (USBD_Start(&hUsbDeviceFS) != USBD_OK)
	  {
	    Error_Handler();
	  }
#else

	  usb_start();
#endif
}
//-------------------------------------------------------------------------------
void usb_stop()
{
	//stop usb port
	USBD_DeInit(&USB_OTG_dev);
}
#endif
//-------------------------------------------------------------------------------
void usb_tick()
{
	usb_flushMidi();
}
//-------------------------------------------------------------------------------
void usb_processMidiIn(uint8_t max)
{
	static volatile uint8_t busy;
	const uint32_t irq = __get_PRIMASK();
	__disable_irq();
	if(busy) {
		__set_PRIMASK(irq);
		return;
	}
	busy = 1;
	__set_PRIMASK(irq);
	MidiMsg msg;
	while(max-- && usb_getMidi(&msg)) midiParser_parseMidiMessage(msg);
	busy = 0;
}
//-------------------------------------------------------------------------------
#if 0
void usb_start()
{
	//zero init the usb receive buffer
	memset(usb_MidiMessages,0, sizeof(MidiMsg)*USB_MIDI_INPUT_BUFFER_SIZE);

	//start usb port
	 USBD_Init(&USB_OTG_dev,
	            &USR_desc,
				DEVICE_FS);

	 if (USBD_RegisterClass(&USB_OTG_dev, &MIDI_cb) != USBD_OK)

	 // if (USBD_CDC_RegisterInterface(&USB_OTG_dev, &USBD_Interface_fops_FS) != USBD_OK)
	  {
		//Error_Handler();
	  }
	  if (USBD_Start(&USB_OTG_dev) != USBD_OK)
	  {
		//Error_Handler();
	  }
}
#endif
//-------------------------------------------------------------------------------
/* Publish complete USB-MIDI events from the main loop and timer ISR. */
#define USB_TX_EVENTS (TOTAL_MIDI_BUF_SIZE * NUM_SUB_BUFFERS / sizeof(MidiDataUsb))
static MidiDataUsb txQueue[USB_TX_EVENTS];
static unsigned txRead, txWrite;

void usb_resetMidiQueues(void)
{
	const uint32_t irq = __get_PRIMASK();
	__disable_irq();
	txRead = txWrite = 0;
	usb_MidiMessagesRead = usb_MidiMessagesWrite = 0;
	__set_PRIMASK(irq);
}

void usb_sendMidi(MidiMsg msg)
{
	const MidiDataUsb event = {msg.status >> 4, msg.status, msg.data1, msg.data2};
	const uint32_t irq = __get_PRIMASK();
	__disable_irq();
	const unsigned next = (txWrite + 1u) % USB_TX_EVENTS;
	if(next != txRead) {
		txQueue[txWrite] = event;
		txWrite = next;
	}
	__set_PRIMASK(irq);
}

void usb_flushMidi(void)
{
	const uint32_t irq = __get_PRIMASK();
	__disable_irq();
	if(txRead != txWrite) {
		unsigned count = (txRead < txWrite ? txWrite : USB_TX_EVENTS) - txRead;
		const unsigned maxEvents = CDC_DATA_FS_IN_PACKET_SIZE / sizeof(MidiDataUsb);
		if(count > maxEvents) count = maxEvents;
		/* CDC copies accepted events into its dedicated in-flight buffer. */
		if(CDC_Transmit_FS((uint8_t *)&txQueue[txRead], count * sizeof(MidiDataUsb)) == USBD_OK)
			txRead = (txRead + count) % USB_TX_EVENTS;
	}
	__set_PRIMASK(irq);
}

uint8_t usb_getMidi(MidiMsg* msg)
{
	const uint32_t irq = __get_PRIMASK();
	__disable_irq();
	if(usb_MidiMessagesRead != usb_MidiMessagesWrite) {
		*msg = usb_MidiMessages[usb_MidiMessagesRead];
		usb_MidiMessagesRead = (usb_MidiMessagesRead + 1u) & USB_MIDI_INPUT_BUFFER_MASK;
		USBD_CDC_ResumeMidiRx();
		__set_PRIMASK(irq);
		return 1;
	}
	__set_PRIMASK(irq);
	return 0; //no messages
}

