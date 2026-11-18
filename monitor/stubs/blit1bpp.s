# blit1bpp.s - draw a 1-bit bitmap (e.g. rendered text) on the ST7789, run from
# RAM via the AT monitor's =C command. Same LCD primitives as fillrect.s.
# Each bitmap row is W/8 bytes, MSB = leftmost pixel; set bits get FG, clear
# bits BG. Colours are plain RGB565. Rows are expanded into LINE and sent with
# spi_w16, which reads native (little-endian) words, so colours are stored with
# .word (storing them high byte first swapped the bytes on screen).
# Defsyms: X0 Y0 W H (W multiple of 8, <= 240) FG BG, and the bitmap is pulled
# in with .incbin "bitmap.bin" (assemble with -I <dir>).
# One-shot via FLAG. Returns 0x600D after drawing, 0x0D0E if FLAG was set.

.set FLAG, 0x879800
.set LINE, 0x879c00
.set WDOG, 0xff4c00
.set X1, X0 + W - 1
.set Y1, Y0 + H - 1
.set WB, W / 8

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

    movd $bitmap, (r10,r9)
    movw $H, r7
row:
    movd $LINE, (r5,r4)
    movw $WB, r11
byte:
    loadb 0(r10,r9), r0
    addd $1, (r10,r9)
    movw $8, r1
bit:
    tbit $7, r0
    bfc 2f
    loadw fgw, r2
    br 3f
2:  loadw bgw, r2
3:  storw r2, 0(r5,r4)
    addd $2, (r5,r4)
    ashuw $1, r0
    addw $-1, r1
    cmpw $0, r1
    bne bit
    addw $-1, r11
    cmpw $0, r11
    bne byte
    movd $LINE, (r3,r2)
    movd $W, (r5,r4)
    bal (ra), spi_w16
    movw $0xff, r0
    storw r0, WDOG
    addw $-1, r7
    cmpw $0, r7
    bne row

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

cmd1:
    movb $1, r6
    movd $1, (r5,r4)
    br send8
data4:
    movb $0, r6
    movd $4, (r5,r4)
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
fgw:      .word FG
bgw:      .word BG
bitmap:   .incbin "bitmap.bin"
