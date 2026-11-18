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

### Live result 2: incoming call (watch 0x8744B0–0x8744D0)

| t | Change | Step |
|---|---|---|
| 21.99 s | [0x8744CC] = 0xCD | just before ringing |
| 22.73 s | **[0x8744C0] 0 → 1** | incoming call, ringing |
| 25.57 s | [0x873629] → 0x3B, **[0x8744BE] 0 → 4** | answered, active |
| 25.97 s | [0x8744CC] = 0x06 | right after answer |
| 29.36 s | [0x8744CC] = 0x89 | right before hang-up |
| 29.83 s | [0x873629] → 0x3C, [0x8744BE] → 0, [0x8744C0] → 0 | call ended |

Verified call state (one incoming call):

| State | [0x8744C0] | [0x8744BE] bit 2 |
|---|---|---|
| idle | 0 | 0 |
| ringing | 1 | 0 |
| active | 1 | 1 |

Bit 1 of 0x8744BE did **not** change, so the earlier "bit 1 = ringing" guess is
wrong. [0x8744CC] looks like the last UI event code (background 0x27/0x9D;
*hypothesis*). [0x8744CA] bit 15 pulses briefly at ring start and at answer.

### Live result 3: outgoing call (SIP line, reached voicemail)

| t | Change | Step |
|---|---|---|
| 10–18 s | [0x8744CC] = 0x86 repeatedly (with 0x1C/0xA7/0x15) | dialling digits (*hypothesis*) |
| 18.55 s | [0x8744CC] = **0xCD** | call setup (same code as before the incoming ring) |
| 18.72 s | **[0x8744C0] 0 → 1** | call started |
| 19.69 s | [0x8744CC] = 0x06 | (also seen right after answering an incoming call) |
| 45.69 s | [0x8744CC] = **0x89** | hang up (same code as for the incoming call) |
| 46.04 s | **[0x8744C0] 1 → 0** | call ended |

[0x8744BE] bit 2 was **never** set and no 0x3B message came, although the far
end (voicemail) picked up. On this SIP base the DECT call counts as set up when
dialling; ringback and the voicemail greeting are in-band audio, so the handset
gets no separate "remote answered" signal.

**For the custom UI:** "call in progress" = [0x8744C0] != 0 (both directions);
incoming ringing vs answered = [0x8744BE] bit 2; outgoing shows "in call" with a
timer. UI event codes seen in both directions: 0xCD = call setup, 0x89 = hang up,
0x06 = speech path open (*hypothesis*).

*Earlier hypothesis:* the ids 0x30–0x49 are call events from the DECT stack (setup,
alerting, connect, release, …). Next step is to map them live: watch
0x873628/0x87362A with `monitor/mon.py watch` while making and receiving a
test call.
