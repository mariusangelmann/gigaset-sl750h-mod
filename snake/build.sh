#!/bin/bash
# Assemble and link the Snake payload for CPU 0x2C1244 (image file 0x1ce29e).
# Output: snake/snake.bin (hook trampoline first, then the game).
# Needs cr16-elf binutils (build-toolchain.sh); set CR16=<prefix>/bin if not on PATH.
set -e
cd "$(dirname "$0")"
B=${CR16:+$CR16/}cr16-elf-
${B}as snake.s -o snake.o
${B}ld -Ttext 0x2c1244 -e hook_entry \
  --defsym gpio_set=0x1da3e6 --defsym spi_cfg=0x1dce12 \
  --defsym KState=0x16fdb2 --defsym OKTail=0x16fd82 --defsym ChainNext=0x16fc50 \
  snake.o -o snake.elf
${B}objcopy -O binary snake.elf snake.bin
echo "snake.bin: $(wc -c < snake.bin) bytes"
