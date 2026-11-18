# fillrect.s - draw a filled rectangle on the ST7789 display, run from RAM via
# the AT monitor's =C command. Mirrors the firmware's own LCD send path
# (0x20E5E6 / 0x20E648 / 0x20E688 / 0x20E676):
#   gpio_set(pin r2, level r3)        0x1DA3E6  CS = pin 6 (1 = selected),
#                                               D/C = pin 0x2F (1 = command)
#   spi_cfg(r2=0, r3=clock, r4=width) 0x1DCE12  width 0 = 8-bit, 1 = 16-bit;
#                                               clock 2 if [0x874630] bit 4 else 1
#   spi_w8 ((r3,r2) ptr, (r5,r4) n)   0x1DCE5E  bytes, blocking
#   spi_w16((r3,r2) ptr, (r5,r4) n)   0x1DCE82  16-bit words, blocking
# One-shot via FLAG (the monitor re-dispatches =C). Afterwards CASET/RASET are
# set back to the full 240x320 window the firmware assumes, and CS is released.
# Returns r0 = 0x600D after drawing, 0x0D0E if FLAG was set.
# Link with monitor/stubs/ram.ld (base 0x879000), defsyms X0 X1 Y0 Y1 COLOR.

.set FLAG,     0x879800
.set WDOG,     0xff4c00

.text
.globl draw
draw:
    push $5, r7, RA
    loadb FLAG, r0
    cmpb $0, r0
    bne already
    movb $1, r0
    storb r0, FLAG

    movb $1, r0                      # SPI clock like the firmware
    tbitb $4, 0x874630
    bfc 1f
    movb $2, r0
1:  storb r0, clk

    movb $1, r3                      # select the display
    movb $6, r2
    bal (ra), gpio_set

    movd $c_caset, (r3,r2)
    bal (ra), cmd1
    movd $d_caset, (r3,r2)
    bal (ra), data4
    movd $c_raset, (r3,r2)
    bal (ra), cmd1
    movd $d_raset, (r3,r2)
    bal (ra), data4
    movd $c_ramwr, (r3,r2)
    bal (ra), cmd1

    movb $0, r3                      # pixels: data mode, 16-bit SPI
    movb $0x2f, r2
    bal (ra), gpio_set
    movb $1, r4
    loadb clk, r3
    movb $0, r2
    bal (ra), spi_cfg
    movw $CHUNKS, r8
2:  movd $pix, (r3,r2)
    movd $32, (r5,r4)
    bal (ra), spi_w16
    movw $0xff, r0
    storw r0, WDOG
    addw $-1, r8
    cmpw $0, r8
    bne 2b

    movd $c_caset, (r3,r2)           # restore the full window
    bal (ra), cmd1
    movd $d_full_x, (r3,r2)
    bal (ra), data4
    movd $c_raset, (r3,r2)
    bal (ra), cmd1
    movd $d_full_y, (r3,r2)
    bal (ra), data4

    movb $0, r3                      # data mode, release the display
    movb $0x2f, r2
    bal (ra), gpio_set
    movb $0, r3
    movb $6, r2
    bal (ra), gpio_set
    movw $0x600D, r0
    popret $5, r7, RA
already:
    movw $0x0D0E, r0
    popret $5, r7, RA

# cmd1: send 1 command byte at (r3,r2). data4: send 4 data bytes at (r3,r2).
cmd1:
    movb $1, r6
    movd $1, (r5,r4)
    br send8
data4:
    movb $0, r6
    movd $4, (r5,r4)
# send8: D/C = r6, 8-bit SPI, write (r5,r4) bytes from (r3,r2).
send8:
    push $4, r7, RA
    movd (r3,r2), (r8,r7)
    movd (r5,r4), (r10,r9)
    movw r6, r3
    movb $0x2f, r2
    bal (ra), gpio_set
    movb $0, r4
    loadb clk, r3
    movb $0, r2
    bal (ra), spi_cfg
    movd (r8,r7), (r3,r2)
    movd (r10,r9), (r5,r4)
    bal (ra), spi_w8
    popret $4, r7, RA

.data
clk:      .byte 0
c_caset:  .byte 0x2a
c_raset:  .byte 0x2b
c_ramwr:  .byte 0x2c
d_caset:  .byte 0, X0, 0, X1
d_raset:  .byte (Y0 >> 8), (Y0 & 0xff), (Y1 >> 8), (Y1 & 0xff)
d_full_x: .byte 0, 0, 0, 0xef
d_full_y: .byte 0, 0, 0x01, 0x3f
.balign 2
pix:      .rept 32
          .word COLOR
          .endr
