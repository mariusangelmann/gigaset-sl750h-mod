# snake.s - Snake for Gigaset SL750H PRO (Dialog SC14441, CR16C+).
# Assembles with:  cr16-elf-as -m cr16c snake.s -o snake.o
#                  cr16-elf-ld -Ttext 0x2be29e -e snake_entry snake.o -o snake.elf
#                  cr16-elf-objcopy -O binary snake.elf snake.bin
# Placed at file offset 0x1ce29e => CPU 0x2be29e (flash base 0xF0000).
#
# Hardware: ST7735 TFT over QSPI (regs at 0xFF0C00..), LCD control lines on a
# GPIO port (P1 at 0xFF4840; pins below are TODO-confirm against app code),
# keypad read via a RAM cell filled by read_key stub (TODO real keypad GPIO).
#
# Game: 16x20 cells of 8x8 px on a 128x160 LCD. Arrows steer, 9/End exits,
# wall or self collision = game over flash, then exit key returns to caller.

.set QSPI_CTRL,   0xFF0C00
.set QSPI_STATUS, 0xFF0C14
.set QSPI_TX8,    0xFF0C18
.set P1_DATA,     0xFF4840
.set LCD_CS,      0x0001
.set LCD_RS,      0x0002
.set LCD_RST,     0x0004

.set LCD_W, 128
.set LCD_H, 160
.set COLS, 16
.set ROWS, 20
.set MAXLEN, 320

# RAM layout (RAM 0x0..0x2000)
.set snake_x,  0x0100
.set snake_y,  0x0200
.set var_len,  0x0400
.set var_dir,  0x0402
.set var_fx,   0x0404
.set var_fy,   0x0406
.set var_rng,  0x0408
.set var_key,  0x040A

.text
.globl snake_entry
snake_entry:
    bal (ra), snake_main
    jump (ra)   # return to boot hook after game


# ---------- LCD low level ----------
# r0 = byte to send on QSPI (8-bit)
qspi_put8:
1:  loadw 0xFF0C14:m, r1
    andw $0x0001, r1
    bne 1b
    storb r0, 0xFF0C18:m
    jump (ra)

# r0 = LCD command byte
lcd_cmd:
    push $0x4, r0, ra
    loadw 0xFF4840:m, r1
    andw $0xFFFC, r1          # clear RS|CS
    storw r1, 0xFF4840:m
    pop $0x2, r0
    bal (ra), qspi_put8
    loadw 0xFF4840:m, r1
    orw $LCD_CS, r1
    storw r1, 0xFF4840:m
    pop $0x2, ra
    jump (ra)

# r0 = LCD data byte
lcd_data:
    push $0x4, r0, ra
    loadw 0xFF4840:m, r1
    andw $0xFFFE, r1          # clear CS
    orw $LCD_RS, r1           # set RS
    storw r1, 0xFF4840:m
    pop $0x2, r0
    bal (ra), qspi_put8
    loadw 0xFF4840:m, r1
    orw $LCD_CS, r1
    storw r1, 0xFF4840:m
    pop $0x2, ra
    jump (ra)

lcd_init:
    push $0x2, ra
    # reset pulse
    loadw 0xFF4840:l, r1
    andw $0xFFFB, r1
    storw r1, 0xFF4840:l
    movd $100000, (r2, r1)
1:  subd $1, (r2, r1)
    bne 1b
    loadw 0xFF4840:l, r1
    orw $LCD_RST, r1
    storw r1, 0xFF4840:l
    movd $200000, (r2, r1)
2:  subd $1, (r2, r1)
    bne 2b
    movb $0x01, r0
    bal (ra), lcd_cmd       # SWRESET
    movd $200000, (r2, r1)
3:  subd $1, (r2, r1)
    bne 3b
    movb $0x11, r0
    bal (ra), lcd_cmd       # SLPOUT
    movd $200000, (r2, r1)
4:  subd $1, (r2, r1)
    bne 4b
    movb $0x3A, r0
    bal (ra), lcd_cmd       # COLMOD
    movb $0x05, r0
    bal (ra), lcd_data      # 16bpp
    movb $0x36, r0
    bal (ra), lcd_cmd       # MADCTL
    movb $0x00, r0
    bal (ra), lcd_data
    movb $0x29, r0
    bal (ra), lcd_cmd       # DISPON
    pop $0x2, ra
    jump (ra)

# fill rect: r0=x r1=y r2=w r3=h r4=color(565)
lcd_fill:
    push $0x2, ra
    push $0x2, r3
    push $0x2, r2
    push $0x2, r1
    push $0x2, r0
    # set window x: r0..r0+r2-1
    push $0x2, r0
    addw r2, r0
    subw $1, r0
    push $0x2, r0           # x1
    pop $0x2, r2            # r2 = x1 ; r0 = x0 still pushed? -- simplified below
    # (full window setup omitted in this skeleton; see lcd_set_window in snake.c)
    pop $0x2, r0
    pop $0x2, r1
    pop $0x2, r2
    pop $0x2, r3
    pop $0x2, ra
    jump (ra)

# ---------- input stub ----------
# returns key in r0: 0 none, 1 up, 2 down, 3 left, 4 right, 9 exit
read_key:
    loadw var_key:l, r0
    jump (ra)

# ---------- rng ----------
rnd:
    loadw var_rng:l, r0
    mulw $25173, r0
    addw $13849, r0
    storw r0, var_rng:l
    jump (ra)

# ---------- game ----------
snake_main:
    push $0x2, ra
    bal (ra), lcd_init
    # snake_len=3, body at (5,10),(4,10),(3,10), dir=0(right)
    movw $3, r0
    storw r0, var_len:l
    movw $0, r0
    storw r0, var_dir:l
    movb $5, r0
    storb r0, snake_x+0:l
    movb $4, r0
    storb r0, snake_x+1:l
    movb $3, r0
    storb r0, snake_x+2:l
    movb $10, r0
    storb r0, snake_y+0:l
    storb r0, snake_y+1:l
    storb r0, snake_y+2:l
    # food
    movb $8, r0
    storb r0, var_fx:l
    movb $5, r0
    storb r0, var_fy:l

gameloop:
    bal (ra), read_key
    cmpw $9, r0
    beq game_exit
    cmpw $1, r0
    beq key_up
    cmpw $2, r0
    beq key_down
    cmpw $3, r0
    beq key_left
    cmpw $4, r0
    beq key_right
    br gameloop_continue
key_up:    loadw var_dir:l, r1
    cmpw $1, r1
    beq gameloop_continue
    movw $3, r0
    storw r0, var_dir:l
    br gameloop_continue
key_down:  loadw var_dir:l, r1
    cmpw $3, r1
    beq gameloop_continue
    movw $1, r0
    storw r0, var_dir:l
    br gameloop_continue
key_left:  loadw var_dir:l, r1
    cmpw $0, r1
    beq gameloop_continue
    movw $2, r0
    storw r0, var_dir:l
    br gameloop_continue
key_right: loadw var_dir:l, r1
    cmpw $2, r1
    beq gameloop_continue
    movw $0, r0
    storw r0, var_dir:l

gameloop_continue:
    # head move
    loadb snake_x+0:l, r0     # hx
    loadb snake_y+0:l, r1     # hy
    loadw var_dir:l, r2
    cmpw $0, r2
    beq mv_right
    cmpw $1, r2
    beq mv_down
    cmpw $2, r2
    beq mv_left
    # up
    subw $1, r1
    br mv_done
mv_right: addw $1, r0
    br mv_done
mv_down:  addw $1, r1
    br mv_done
mv_left:  subw $1, r0
mv_done:
    # bounds check
    cmpw $0, r0
    blt game_over
    cmpw $COLS, r0
    bge game_over
    cmpw $0, r1
    blt game_over
    cmpw $ROWS, r1
    bge game_over
    # TODO: self-collision + draw + food + delay
    br gameloop

game_over:
    # flash red 3x
    movw $3, r5
go_flash:
    # (fill screen red would go here)
    subw $1, r5
    bgt go_flash
game_exit:
    pop $0x2, ra
    jump (ra)   # return to boot hook
