# snake.s - Snake for the Gigaset SL750H PRO (Dialog SC1444x, CR16C+).
#
# Placement: free flash at CPU 0x2C1244 (image file offset 0x1ce29e).
# Entry: snake_entry, called like a menu action handler (push/popret frame,
# returns r0 = 1 = "handled"). Self-contained: drives the LCD SPI directly and
# polls the keypad bitmask. It must NOT call lcd_write (0x20EB6A) or lcd_flush
# (0x20E7F0): those post task 0 and spin, which deadlocks inside a handler
# because the cooperative scheduler only drains tasks when the handler returns.
#
# Hardware facts (real CPU addresses = image file offset + 0xF2FA6):
#   LCD ST7789H2 240x320 RGB565; SPI CTRL 0xFF4940 (bit 11 = TX busy),
#   TX 0xFF4942, CTRL1 0xFF4948 (bit 3 = transfer busy).
#   D/C = GPIO pin 0x2F (1 = command, 0 = data); CS = GPIO pin 6 (1 = asserted).
#   Row offset (panel variant) = word at 0x8753A0, added to RASET rows.
#   Watchdog: write 0xFF to 0xFF4C00 at least every few hundred ms.
#   Keypad raw bitmasks, active high, refreshed by the keyboard ISR:
#     row byte 0x875678, col byte 0x875679.
# Firmware leaf helpers used (synchronous, no task posting):
#   gpio_set(r2 = pin, r3 = level)          0x1DA3E6
#   spi_cfg(r2 = 0, r3 = clock, r4 = 0 8-bit / 1 16-bit)  0x1DCE12
#
# CR16C notes: "cmp A,B ; bCC" branches when A CC B (e.g. cmpw $8,r7; bls =
# branch if 8 <= r7, unsigned). Only cmp/tbit set the flags used by branches;
# add/sub do not set Z, so every loop compares explicitly.

.set WDOG,      0xff4c00
.set SPI_CTRL,  0xff4940
.set SPI_TX,    0xff4942
.set SPI_CTRL1, 0xff4948
.set KROW,      0x875678
.set KCOL,      0x875679
.set ROWOFF,    0x8753a0
.set PANELFLG,  0x874630

.set PIN_CS,    6
.set PIN_DC,    0x2f

.set COLS,      15          # 240 / 16
.set ROWS,      19          # rows 1..19 playfield, row 0 = score bar
.set CELL,      16
.set MAXLEN,    120
.set DELAY0,    40000
.set K_HASH_R, 0x40          # '#' = second exit key
.set K_HASH_C, 0x04

# RGB565 colours (written as signed 16-bit where >= 0x8000)
.set C_BG,      0x0000      # black
.set C_BODY,    0x07e0      # green
.set C_HEAD,    0x07ff      # cyan
.set C_FOOD,    -0x0800     # 0xF800 red
.set C_BAR,     -0x0020     # 0xFFE0 yellow score pips
.set C_EDGE,    0x39e7      # dark grey score-bar background
.set C_OVER,    -0x07e1     # 0xF81F magenta game-over flash

# keys (row mask, col mask)
.set K_UP_R,  0x01
.set K_UP_C,  0x02
.set K_DN_R,  0x10
.set K_DN_C,  0x02
.set K_LT_R,  0x02
.set K_LT_C,  0x01
.set K_RT_R,  0x02
.set K_RT_C,  0x04
.set K_OK_R,  0x02
.set K_OK_C,  0x02
.set K_RED_R, 0x01
.set K_RED_C, 0x08

# Frame layout, base r12 (= sp after allocation)
.set F_X,       0x000       # byte x[MAXLEN]
.set F_Y,       0x078       # byte y[MAXLEN]
.set F_LEN,     0x0f0       # word length
.set F_DIR,     0x0f2       # word 0=right 1=down 2=left 3=up
.set F_NDIR,    0x0f4       # word requested direction
.set F_RNG,     0x0f6       # word xorshift state
.set F_FX,      0x0f8       # word food x
.set F_FY,      0x0fa       # word food y
.set F_WBUF,    0x0fc       # 4-byte command data buffer
.set F_SCORE,   0x100       # word food eaten
.set FRAME,     0x104

.macro KICK
    movw $0xff, r0
    storw r0, WDOG
.endm

# (r1,r0) = &frame[off + idx]; idx is a word register; clobbers r4,r5
.macro EADDR off, idx
    movzw \idx, (r5, r4)
    movd (r12), (r1, r0)
    addd $\off, (r1, r0)
    addd (r5, r4), (r1, r0)
.endm

# branch to \miss unless key (rm,cm) is down; expects r2 = row, r3 = col
.macro KEY rm, cm, miss
    movb r2, r0
    andb $\rm, r0
    cmpb $0, r0
    beq \miss
    movb r3, r0
    andb $\cm, r0
    cmpb $0, r0
    beq \miss
.endm

.text
# ---- Menu hook trampoline (lives at the payload base 0x2C1244) ----
# Reached from the patched main-menu event handler (br here replaces the inline
# `cmpw $0x1a,r7 ; beq OKTail`). r7 = event code, preserved from 0x16fc20.
# KState (0x16fdb2) returns [0x87546c] in (r1,r0); byte +1 = highlighted main
# item index (verified: renderer 0x16e76a does loadb 1(state),*14 into table
# 0x2ae8fa). Netzdienste = index 3. OKTail (0x16fd82) = original OK handling;
# ChainNext (0x16fc50) = the next event comparison for non-OK events.
.globl hook_entry
hook_entry:
    cmpw $0x1a, r7
    bne hk_resume
    bal (ra), KState
    loadb 1(r1, r0), r0
    cmpb $3, r0
    bne hk_oknorm
    bal (ra), snake_entry
hk_oknorm:
    br OKTail
hk_resume:
    br ChainNext

.globl snake_entry
snake_entry:
    push $0x7, r7, ra
    addd $-FRAME, (sp)
    movd (sp), (r12)

    movb $1, r3
    movb $PIN_CS, r2
    bal (ra), gpio_set          # assert CS for the whole session

    loadw KROW, r0              # seed RNG from keypad state + a constant
    xorw $0x5a3c, r0
    orw $1, r0
    storw r0, F_RNG(r12)

    bal (ra), wait_release      # OK from the menu may still be held

new_game:
    bal (ra), game_new

game_loop:
    KICK
    bal (ra), poll_keys         # r0 = 1 if RED
    cmpb $0, r0
    bne quit
    bal (ra), step              # r0 = 1 on collision
    cmpb $0, r0
    bne over
    bal (ra), frame_delay       # polls keys during the wait too
    cmpb $0, r0
    bne quit
    br game_loop

over:
    bal (ra), game_over         # r0 = 1 quit, 0 restart
    cmpb $0, r0
    beq new_game

quit:
    bal (ra), lcd_restore
    movb $1, r0
    addd $FRAME, (sp)
    popret $0x7, r7, ra


# ---------------- SPI / LCD ----------------
# spi_mode(r4 = 0 8-bit / 1 16-bit), same clock choice as the firmware
spi_mode:
    push RA
    movb $1, r3
    tbitb $4, PANELFLG
    bfc 1f
    movb $2, r3
1:  movb $0, r2
    bal (ra), spi_cfg
    popret RA

spi_wait_done:
1:  tbitw $3, SPI_CTRL1
    bfs 1b
    jump (ra)

# wr_cmd(r2 = command)
wr_cmd:
    push $0x1, r7, ra
    movw r2, r7
    bal (ra), spi_wait_done
    movb $1, r3
    movb $PIN_DC, r2
    bal (ra), gpio_set
    movb $0, r4
    bal (ra), spi_mode
1:  tbitw $11, SPI_CTRL
    bfs 1b
    storw r7, SPI_TX
    bal (ra), spi_wait_done
    pop $0x1, r7, ra
    jump (ra)

# wr_wbuf: send the 4 bytes at F_WBUF as data
wr_wbuf:
    push $0x2, r7, ra
    movb $0, r3
    movb $PIN_DC, r2
    bal (ra), gpio_set
    movb $0, r4
    bal (ra), spi_mode
    movw $0, r7
2:  movd (r12), (r1, r0)
    addd $F_WBUF, (r1, r0)
    movzw r7, (r5, r4)
    addd (r5, r4), (r1, r0)
    loadb 0(r1, r0), r8
    movzb r8, r8
1:  tbitw $11, SPI_CTRL
    bfs 1b
    storw r8, SPI_TX
    addw $1, r7
    cmpw $4, r7
    bne 2b
    bal (ra), spi_wait_done
    pop $0x2, r7, ra
    jump (ra)

# put4(r2 = a, r3 = b): F_WBUF = a>>8, a, b>>8, b
put4:
    movw r2, r0
    lshw $-8, r0
    storb r0, F_WBUF(r12)
    storb r2, F_WBUF+1(r12)
    movw r3, r0
    lshw $-8, r0
    storb r0, F_WBUF+2(r12)
    storb r3, F_WBUF+3(r12)
    jump (ra)

# set_window(r2 = x0, r3 = x1, r4 = y0, r5 = y1), then RAMWR
set_window:
    push $0x4, r7, ra
    movw r2, r7
    movw r3, r8
    movw r4, r9
    movw r5, r10
    loadw ROWOFF, r0
    addw r0, r9
    addw r0, r10
    movw $0x2a, r2
    bal (ra), wr_cmd
    movw r7, r2
    movw r8, r3
    bal (ra), put4
    bal (ra), wr_wbuf
    movw $0x2b, r2
    bal (ra), wr_cmd
    movw r9, r2
    movw r10, r3
    bal (ra), put4
    bal (ra), wr_wbuf
    movw $0x2c, r2
    bal (ra), wr_cmd
    pop $0x4, r7, ra
    jump (ra)

# fill(r2 = colour, (r4,r3) = pixel count): stream one colour, 16-bit words
fill:
    push $0x3, r7, ra
    movw r2, r7
    movd (r4, r3), (r9, r8)
    movb $0, r3
    movb $PIN_DC, r2
    bal (ra), gpio_set
    movb $1, r4
    bal (ra), spi_mode
1:  cmpd $0, (r9, r8)
    beq 3f
2:  tbitw $11, SPI_CTRL
    bfs 2b
    storw r7, SPI_TX
    addd $-1, (r9, r8)
    br 1b
3:  bal (ra), spi_wait_done
    KICK
    pop $0x3, r7, ra
    jump (ra)

# rect(r2 = x0, r3 = y0, r4 = w, r5 = h, r6 = colour)
rect:
    push $0x5, r7, ra
    movw r2, r7
    movw r3, r8
    movw r4, r9
    movw r5, r10
    movw r6, r11
    movw r7, r2                 # x0
    movw r7, r3
    addw r9, r3
    addw $-1, r3                # x1
    movw r8, r4                 # y0
    movw r8, r5
    addw r10, r5
    addw $-1, r5                # y1
    bal (ra), set_window
    movw r9, r0
    mulw r10, r0                # w*h fits 16 bits for every rect we draw
    movzw r0, (r4, r3)
    movw r11, r2
    bal (ra), fill
    pop $0x5, r7, ra
    jump (ra)

# clear_screen(r2 = colour)
clear_screen:
    push $0x1, r7, ra
    movw r2, r7
    movw $0, r2
    movw $239, r3
    movw $0, r4
    movw $319, r5
    bal (ra), set_window
    movw r7, r2
    movd $76800, (r4, r3)
    bal (ra), fill
    pop $0x1, r7, ra
    jump (ra)

# cell(r2 = cx, r3 = cy, r4 = colour): 14x14 block inside the 16x16 cell,
# playfield row cy is drawn at screen row cy+1 (row 0 = score bar)
cell:
    push RA
    movw r4, r6
    mulw $CELL, r2
    addw $1, r2
    addw $1, r3
    mulw $CELL, r3
    addw $1, r3
    movw $CELL-2, r4
    movw $CELL-2, r5
    bal (ra), rect
    popret RA

# lcd_restore: blank, restore full window (firmware assumes CASET 0..239),
# return SPI to the firmware's 16-bit default, release CS.
lcd_restore:
    push RA
    movw $C_BG, r2
    bal (ra), clear_screen      # also leaves CASET 0..239 / RASET 0..319
    movb $1, r4
    bal (ra), spi_mode
    movb $0, r3
    movb $PIN_CS, r2
    bal (ra), gpio_set
    popret RA


# wait_release: until no key is down, at most ~0x30000 polls
wait_release:
    movd $0x30000, (r3, r2)
1:  KICK
    loadb KROW, r0
    cmpb $0, r0
    beq 9f
    addd $-1, (r3, r2)
    cmpd $0, (r3, r2)
    bne 1b
9:  jump (ra)

# ---------------- game ----------------
rnd16:                          # xorshift16 (7,9,8) -> r0
    loadw F_RNG(r12), r0
    movw r0, r1
    lshw $7, r1
    xorw r1, r0
    movw r0, r1
    lshw $-9, r1
    xorw r1, r0
    movw r0, r1
    lshw $8, r1
    xorw r1, r0
    storw r0, F_RNG(r12)
    jump (ra)

# umod(r0 = value, r2 = modulus) -> r0
umod:
1:  cmpw r2, r0
    bhi 9f                      # modulus > value
    subw r2, r0
    br 1b
9:  jump (ra)

draw_score:
    push $0x2, r7, ra
    movw $0, r2                 # bar background
    movw $0, r3
    movw $240, r4
    movw $16, r5
    movw $C_EDGE, r6
    bal (ra), rect
    loadw F_SCORE(r12), r8      # one 6x10 pip per food, max 30
    cmpw $30, r8
    bhs 1f                      # 30 >= score
    movw $30, r8
1:  movw $0, r7
2:  cmpw r8, r7
    bls 3f                      # done when score <= i
    movw r7, r2
    mulw $8, r2
    addw $1, r2
    movw $3, r3
    movw $6, r4
    movw $10, r5
    movw $C_BAR, r6
    bal (ra), rect
    addw $1, r7
    br 2b
3:  pop $0x2, r7, ra
    jump (ra)

game_new:
    push $0x1, r7, ra
    movw $C_BG, r2
    bal (ra), clear_screen
    movw $3, r0
    storw r0, F_LEN(r12)
    movw $0, r0
    storw r0, F_DIR(r12)
    storw r0, F_NDIR(r12)
    storw r0, F_SCORE(r12)
    movw $0, r7                 # body = (7,9) (6,9) (5,9)
1:  EADDR F_X, r7
    movw $7, r2
    subw r7, r2
    storb r2, 0(r1, r0)
    EADDR F_Y, r7
    movw $9, r2
    storb r2, 0(r1, r0)
    movw r7, r2
    movw $7, r0
    subw r7, r0
    movw r0, r2
    movw $9, r3
    movw $C_BODY, r4
    cmpw $0, r7
    bne 2f
    movw $C_HEAD, r4
2:  bal (ra), cell
    addw $1, r7
    cmpw $3, r7
    bne 1b
    bal (ra), draw_score
    bal (ra), place_food
    pop $0x1, r7, ra
    jump (ra)

# on_snake(r2 = x, r3 = y, r6 = cells to check) -> r0 = 1 if occupied
on_snake:
    push $0x4, r7, ra
    movw r2, r8
    movw r3, r9
    movw r6, r10
    movw $0, r7
1:  cmpw r10, r7
    bls 8f                      # n <= i
    EADDR F_X, r7
    loadb 0(r1, r0), r2
    movzb r2, r2
    cmpw r2, r8
    bne 2f
    EADDR F_Y, r7
    loadb 0(r1, r0), r2
    movzb r2, r2
    cmpw r2, r9
    bne 2f
    movb $1, r0
    br 9f
2:  addw $1, r7
    br 1b
8:  movb $0, r0
9:  pop $0x4, r7, ra
    jump (ra)

place_food:
    push $0x2, r7, ra
1:  KICK
    bal (ra), rnd16
    movw $COLS, r2
    bal (ra), umod
    movw r0, r7
    bal (ra), rnd16
    movw $ROWS, r2
    bal (ra), umod
    movw r0, r8
    movw r7, r2
    movw r8, r3
    loadw F_LEN(r12), r6
    bal (ra), on_snake
    cmpb $0, r0
    bne 1b
    storw r7, F_FX(r12)
    storw r8, F_FY(r12)
    movw r7, r2
    movw r8, r3
    movw $C_FOOD, r4
    bal (ra), cell
    pop $0x2, r7, ra
    jump (ra)

# poll_keys -> r0 = 1 if RED; latches a requested direction (no reversal)
poll_keys:
    push $0x1, r7, ra
    loadb KROW, r2
    loadb KCOL, r3
    loadw F_DIR(r12), r7
    KEY K_RED_R, K_RED_C, 0f
    br 7f
0:  KEY K_HASH_R, K_HASH_C, 1f
7:  movb $1, r0
    br 9f
1:  KEY K_UP_R, K_UP_C, 2f
    movw $3, r0
    cmpw $1, r7
    bne 5f
2:  KEY K_DN_R, K_DN_C, 3f
    movw $1, r0
    cmpw $3, r7
    bne 5f
3:  KEY K_LT_R, K_LT_C, 4f
    movw $2, r0
    cmpw $0, r7
    bne 5f
4:  KEY K_RT_R, K_RT_C, 8f
    movw $0, r0
    cmpw $2, r7
    beq 8f
5:  storw r0, F_NDIR(r12)
8:  movb $0, r0
9:  pop $0x1, r7, ra
    jump (ra)

# frame_delay: wait (slower when short, faster as it grows), polling keys.
# -> r0 = 1 if RED pressed during the wait.
frame_delay:
    push $0x3, r7, ra
    loadw F_SCORE(r12), r0
    cmpw $18, r0
    bhs 1f                      # 18 >= score
    movw $18, r0
1:  mulw $1500, r0
    movw $DELAY0-0x10000, r7    # base loop count (tune on hardware)
    subw r0, r7                 # 40000 .. 13000
    movzw r7, (r9, r8)
3:  KICK
    movd (r9, r8), (r1, r0)
    andw $0x3ff, r0
    cmpw $0, r0
    bne 4f
    bal (ra), poll_keys
    cmpb $0, r0
    bne 9f
4:  addd $-1, (r9, r8)
    cmpd $0, (r9, r8)
    bne 3b
    movb $0, r0
9:  pop $0x3, r7, ra
    jump (ra)

# step -> r0 = 1 on collision
step:
    push $0x5, r7, ra
    loadw F_NDIR(r12), r0
    storw r0, F_DIR(r12)
    movw $0, r1
    EADDR F_X, r1
    loadb 0(r1, r0), r7
    movzb r7, r7
    movw $0, r1
    EADDR F_Y, r1
    loadb 0(r1, r0), r8
    movzb r8, r8
    loadw F_DIR(r12), r0
    cmpw $0, r0
    bne 1f
    addw $1, r7
    br 5f
1:  cmpw $1, r0
    bne 2f
    addw $1, r8
    br 5f
2:  cmpw $2, r0
    bne 3f
    addw $-1, r7
    br 5f
3:  addw $-1, r8
5:  andw $0xff, r7              # -1 becomes 255 -> out of range below
    andw $0xff, r8
    cmpw $COLS, r7
    bls st_over                 # COLS <= x (unsigned)
    cmpw $ROWS, r8
    bls st_over
    # food?
    movw $0, r11
    loadw F_FX(r12), r0
    cmpw r0, r7
    bne 6f
    loadw F_FY(r12), r0
    cmpw r0, r8
    bne 6f
    movw $1, r11
6:  # self collision: the tail cell is vacated this tick unless we grow
    loadw F_LEN(r12), r6
    cmpw $1, r11
    beq 7f
    addw $-1, r6
7:  movw r7, r2
    movw r8, r3
    bal (ra), on_snake
    cmpb $0, r0
    bne st_over
    loadw F_LEN(r12), r9        # r9 = old length
    movw r9, r10
    addw $-1, r10               # r10 = old tail index
    cmpw $0, r11
    bne 8f
14: # erase old tail
    EADDR F_X, r10
    loadb 0(r1, r0), r2
    movzb r2, r2
    movw r2, r6
    EADDR F_Y, r10
    loadb 0(r1, r0), r3
    movzb r3, r3
    movw r6, r2
    movw $C_BG, r4
    bal (ra), cell
    br 9f
8:  # grow (bounded)
    cmpw $MAXLEN, r9
    bls 14b                     # MAXLEN <= len: move without growing
    movw r9, r10                # new tail index = old length
    addw $1, r9
    storw r9, F_LEN(r12)
9:  # shift body: for i = r10 down to 1: p[i] = p[i-1]
10: cmpw $0, r10
    beq 11f
    movw r10, r6
    addw $-1, r6
    EADDR F_X, r6
    loadb 0(r1, r0), r2
    EADDR F_X, r10
    storb r2, 0(r1, r0)
    EADDR F_Y, r6
    loadb 0(r1, r0), r2
    EADDR F_Y, r10
    storb r2, 0(r1, r0)
    addw $-1, r10
    br 10b
11: movw $0, r6
    EADDR F_X, r6
    storb r7, 0(r1, r0)
    EADDR F_Y, r6
    storb r8, 0(r1, r0)
    # previous head (now index 1) back to body colour
    movw $1, r6
    EADDR F_X, r6
    loadb 0(r1, r0), r2
    movzb r2, r2
    movw r2, r9
    EADDR F_Y, r6
    loadb 0(r1, r0), r3
    movzb r3, r3
    movw r9, r2
    movw $C_BODY, r4
    bal (ra), cell
    movw r7, r2
    movw r8, r3
    movw $C_HEAD, r4
    bal (ra), cell
    cmpw $0, r11
    beq 12f
    loadw F_SCORE(r12), r0
    addw $1, r0
    storw r0, F_SCORE(r12)
    bal (ra), draw_score
    bal (ra), place_food
12: movb $0, r0
    br 13f
st_over:
    movb $1, r0
13: pop $0x5, r7, ra
    jump (ra)

# game_over -> r0 = 1 quit (RED), 0 restart (OK)
game_over:
    push $0x2, r7, ra
    movw $3, r7
1:  movw $0, r2                 # flash the playfield border 3 times
    movw $16, r3
    movw $240, r4
    movw $4, r5
    movw $C_OVER, r6
    bal (ra), rect
    movw $0, r2
    movw $316, r3
    movw $240, r4
    movw $4, r5
    movw $C_OVER, r6
    bal (ra), rect
    movw $0, r2
    movw $16, r3
    movw $4, r4
    movw $304, r5
    movw $C_OVER, r6
    bal (ra), rect
    movw $236, r2
    movw $16, r3
    movw $4, r4
    movw $304, r5
    movw $C_OVER, r6
    bal (ra), rect
    addw $-1, r7
    cmpw $0, r7
    bne 1b
    bal (ra), wait_release
3:  KICK                        # then OK = restart, RED = quit
    loadb KROW, r2
    loadb KCOL, r3
    KEY K_RED_R, K_RED_C, 5f
    br 6f
5:  KEY K_HASH_R, K_HASH_C, 4f
6:  movb $1, r0
    br 9f
4:  KEY K_OK_R, K_OK_C, 3b
    movb $0, r0
9:  pop $0x2, r7, ra
    jump (ra)
