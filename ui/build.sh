#!/bin/sh
# Build the custom-UI RAM test: ui/build/menutest.bin (start at 0x876000).
# Needs cr16-elf-gcc (GCC 11, see ui/README.md) in $CR16 or on PATH.
# Extra arguments go to the compiler, e.g. -DTICK_LOOPS=1234.
set -e
cd "$(dirname "$0")"
T=${CR16:+$CR16/}cr16-elf-
mkdir -p build
python3 fontgen.py fonts/spleen-8x16.bdf font_s > build/font_s.c
python3 fontgen.py fonts/spleen-12x24.bdf font_l > build/font_l.c
CFLAGS="-Os -mcr16cplus -ffreestanding -fno-builtin -nostdlib -Wall -fno-asynchronous-unwind-tables -I. $*"
${T}gcc $CFLAGS -T ram.ld -o build/menutest.elf \
    menutest.c lcd.c build/font_s.c build/font_l.c -lgcc
${T}objcopy -O binary build/menutest.elf build/menutest.bin
${T}nm build/menutest.elf | grep -E ' (_start|__end)$'
wc -c < build/menutest.bin
