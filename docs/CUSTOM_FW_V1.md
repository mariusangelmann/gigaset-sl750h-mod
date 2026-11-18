# Custom firmware — version 1 scope

Goal: a fully custom user interface for the SL750H PRO. Gigaset's low-level
parts (DECT radio and protocol, voice path, audio playback, battery charging,
USB update) are kept as a "modem layer"; everything the user sees is ours.
Writing DECT from scratch is out of scope (not realistic).

Decided with the owner on 2026-11-18.

## In version 1

| Area | Decision |
|---|---|
| Calls | Dial, answer, hang up, mute, volume, call waiting, hold, transfer |
| Call lists | Missed, received, dialled; voicemail indicator |
| Contacts | Name + one number, stored on the phone, editable on the phone |
| Ringtones / vibration | Ringtones and vibration on/off; uploads via companion app |
| Interface | Simple list menu |
| Language | German and English, switchable in settings |
| Idle screen | Clock, date, battery, signal |
| Keypad lock | Manual only (long-press a key) |
| Do not disturb | Night mode with set times, allowed contacts |
| Companion app | Android (Expo + native module) over Bluetooth SPP: contacts, ringtones |

Also needed, though not optional features: standby/sleep, battery and charging
indicator, earpiece/speaker/headset switching, display and keypad lighting,
time and date from the base, base pairing kept from stock, USB update path
must stay intact.

## Not in version 1

- Bluetooth headset support (not needed)
- Games and extras (Snake etc.) — later
- iPhone companion app: not possible. The firmware's Bluetooth stack is CSR
  BCHS classic only (connection manager, security, service discovery,
  handsfree, SPP); there is no GATT/ATT/Low Energy component, and iOS apps can
  only use Low Energy.
- Booting stock as a fallback: ours only. Stock comes back by reflashing via
  4+6 recovery.

## Safety precondition

Before the first flash of our own firmware, confirm that the 4+6 recovery
mode lives outside the region we overwrite. No flash until that is verified.

## First steps

1. Confirm the 4+6 recovery location (no flash).
2. Find the modem-layer entry points in Ghidra: incoming call event, answer,
   hang up, dial, hold/transfer, ringer start/stop, vibration pin, battery
   level, signal/base status, time from base.
3. Prove screen drawing and key reading live over the USB monitor (no flash).
