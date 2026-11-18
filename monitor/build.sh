#!/bin/bash
# Assemble and link the memory-monitor payload for the ^GCTRACER AT command.
# Output: monitor/monitor.bin (raw code, entry mon_entry at MON_BASE).
#
# MON_BASE is a placeholder free-flash base (0x2C2000). The real free-flash
# region starts at 0x2C1244, but Snake occupies the start, so pick a base past
# Snake and pass it here. Change MON_BASE to relocate.
#
# Needs cr16-elf binutils; set CR16=<prefix>/bin if not on PATH.
set -e
cd "$(dirname "$0")"
B=${CR16:+$CR16/}cr16-elf-
MON_BASE=${MON_BASE:-0x2c2000}
${B}as monitor.s -o monitor.o
${B}ld -Ttext "$MON_BASE" -e mon_entry \
  --defsym at_begin=0x101fb4 \
  --defsym at_send_response_line=0x10201a \
  --defsym at_send_ok=0x1022ee \
  --defsym at_send_error=0x1022f8 \
  monitor.o -o monitor.elf
${B}objcopy -O binary monitor.elf monitor.bin
echo "monitor.bin: $(wc -c < monitor.bin) bytes (base $MON_BASE)"
