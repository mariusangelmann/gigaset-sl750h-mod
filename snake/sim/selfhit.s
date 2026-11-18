# Self-collision check used by test_snake.py: preset a 5-cell body and call step once.
.set FRAME,0x104
.set F_X,0x000
.set F_Y,0x078
.set F_LEN,0x0f0
.set F_DIR,0x0f2
.set F_NDIR,0x0f4
.set F_FX,0x0f8
.set F_FY,0x0fa
.globl _start
_start:
    movd $0x40000,(r1,r0)
    addd $-FRAME,(r1,r0)
    movd (r1,r0),(r12)
    movd (r1,r0),(sp)
    # body length 5, head (5,5) going UP(3); body curls so cell above head (5,4) is a mid segment
    # layout (head..tail): (5,5)(4,5)(4,4)(5,4)(6,4)   -> moving up to (5,4) hits segment index3 (non-tail)
    movw $5,r0
    storw r0,F_LEN(r12)
    movw $3,r0            # dir up
    storw r0,F_DIR(r12)
    storw r0,F_NDIR(r12)
    # F_X: 5,4,4,5,6   F_Y:5,5,4,4,4
    movb $5,r0; storb r0,F_X+0(r12)
    movb $4,r0; storb r0,F_X+1(r12)
    movb $4,r0; storb r0,F_X+2(r12)
    movb $5,r0; storb r0,F_X+3(r12)
    movb $6,r0; storb r0,F_X+4(r12)
    movb $5,r0; storb r0,F_Y+0(r12)
    movb $5,r0; storb r0,F_Y+1(r12)
    movb $4,r0; storb r0,F_Y+2(r12)
    movb $4,r0; storb r0,F_Y+3(r12)
    movb $4,r0; storb r0,F_Y+4(r12)
    movw $99,r0; storb r0,F_FX(r12); storb r0,F_FY(r12)  # food off-field
    bal (ra),step
    storb r0,0x20000      # expect 1 (self collision)
    movw $1,r2
    movd $0x20000,(r4,r3)
    movw $1,r5
    movd $0x404,(r1,r0)
    excp 8
    movw $0,r2
    movd $0x410,(r1,r0)
    excp 8
.globl gpio_set
gpio_set: jump (ra)
.globl spi_cfg
spi_cfg: jump (ra)
