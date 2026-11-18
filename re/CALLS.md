# Call system: entry points (in progress)

Goal: the handful of functions and events our custom UI needs from Gigaset's
call system (DECT side). Addresses are real CPU addresses. Unless a row says
*hypothesis*, it was read from disassembly/decompiler output.

## Route in: the Bluetooth headset bridge

The headset (HFG) bridge has to drive calls, so its code leads to the call
system. Its state machine tables sit at file 0x1C6B00–0x1C7200: each state is
~38 event handlers stored as CPU/2, followed by the state name pointer
(`CALL_ST_ICALL_SETUP`, `CALL_ST_OCALL_SETUP`, `CALL_ST_CALL`, `SRV_ST_*`) and a
state index. Handlers live at 0x213C00–0x214E00.

Nearly all calls from those handlers that leave the bridge land in one block,
0x1DFDD2–0x1E13DC.

## The call-event task (0x1DF622)

| Addr | Role |
|---|---|
| 0x1DF622 | task main loop: `0x1CBD76` = queue not empty, `0x1CBE42` = dequeue message id, then dispatch by id (0x01–0x06, 0x20–0x29, 0x30–0x49) |
| 0x1DFAB2 / 0x1DFC9E | message receive: store id in **0x873629**, copy the body (0x4C / 0x40 bytes) to **0x87362A**, then run state machines at 0x873676 (`0x214E4C`, …) |
| 0x873629 | id of the last message received (idle: 0x3C) |
| 0x87362A | body of the last message |
| 0x1DFDD2, 0x1DFEE0, 0x1DFFBE, 0x1E0034, 0x1E00A2, … | per-message handlers that branch on [0x873629] (ids `'0'`,`'1'`,`'2'`,`'9'`,`':'`,`';'`,`'<'`,0xA8,0xAB) |

### Live result (test call, 2026-11-18)

Incoming call, rang ~5 s, answered, ~12 s active, hung up on the handset; then
an outgoing call to an unreachable number:

| t | [0x873629] | Step |
|---|---|---|
| 18.7 s | 0x3C → **0x3B** | answered (no event while ringing) |
| 31.4 s | 0x3B → **0x3C** | hung up |

The outgoing call produced no event (it never connected). So this task only
learns **call connected (0x3B) / call ended (0x3C)**.

## Call-control module (0x141200–0x143100)

| Addr | Role |
|---|---|
| 0x1DF5BA | post a message to the call-event task (`0x1CBE52`, `0x1CBEFA`, `0x1CBE60`), id in r2 |
| 0x1415E4 | **call connected** notifier: posts 0x3B, `[0x8744BE] = [0x8744BE] & ~2 \| 4` |
| 0x141624 | **call ended** notifier: posts 0x3C, clears bits 1, 2, 15 of 0x8744BE, then 0x1424D0, 0x142328 |
| 0x8744BE | call status bit-field, set/cleared all over 0x1412E2–0x14302A (bits 1,3,4,6,8,9,11–15) |

*Hypothesis:* bit 1 = ringing/setup, bit 2 = active. To be labelled live.

*Earlier hypothesis:* the ids 0x30–0x49 are call events from the DECT stack (setup,
alerting, connect, release, …). Next step is to map them live: watch
0x873628/0x87362A with `monitor/mon.py watch` while making and receiving a
test call.
