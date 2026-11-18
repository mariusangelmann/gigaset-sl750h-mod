# Test harness: drives the real snake logic in the CR16 sim.
# Memory map (flat 20MB): frame at sp below 0x60000; key script at 0x50000;
# output buffer at 0x58000. Hardware addresses used by snake (0x8756xx etc.)
# are plain RAM here. gpio_set/spi_cfg are stubbed to no-ops.
.set FRAME, 0x104
.set F_X,0x000
.set F_Y,0x078
.set F_LEN,0x0f0
.set F_DIR,0x0f2
.set F_NDIR,0x0f4
.set F_RNG,0x0f6
.set F_SCORE,0x100
.set KROW,0x9100
.set KCOL,0x9101
.set SCRIPT,0x50000     # bytes: pairs (row,col), terminated by row=0xff
.set OUT,0x58000        # dump area

.globl _start
_start:
    movd $0x60000, (sp)
    movd $0x60000, (r1,r0)
    addd $-FRAME, (r1,r0)
    movd (r1,r0), (r12)
    movd (r1,r0), (sp)
    # seed rng deterministically
    movw $0x1234, r0
    storw r0, F_RNG(r12)
    bal (ra), game_new
    # script pointer in r11 (use callee-saved across step)
    movd $SCRIPT, (r11,r10)
    movd $OUT, (r9,r8)
loop:
    loadb 0(r11,r10), r0        # row
    cmpb $0xff, r0
    beq done
    storb r0, KROW
    loadb 1(r11,r10), r0
    storb r0, KCOL
    addd $2, (r11,r10)
    bal (ra), poll_keys
    cmpb $0, r0
    bne done                    # RED in script = stop
    bal (ra), step
    # dump: [ret, len_lo, score_lo, hx, hy]
    storb r0, 0(r9,r8)
    loadw F_LEN(r12), r1
    storb r1, 1(r9,r8)
    loadw F_SCORE(r12), r1
    storb r1, 2(r9,r8)
    loadb F_X(r12), r1
    storb r1, 3(r9,r8)
    loadb F_Y(r12), r1
    storb r1, 4(r9,r8)
    addd $5, (r9,r8)
    cmpb $0, r0
    bne done                    # collision -> stop
    br loop
done:
    # write OUT..(r9,r8) to stdout via syscall
    movd $OUT, (r5,r4)
    movd (r9,r8), (r1,r0)
    movd $OUT, (r3,r2)
    subd (r3,r2), (r1,r0)       # length in r0
    movw r0, r5                 # PARM4 = len
    movw $1, r2                 # fd=1
    movd $OUT, (r4,r3)          # PARM2:PARM3 = ptr (lo in r3, hi in r4)
    movd $0x404, (r1,r0)
    excp 8
    movw $0, r2
    movd $0x410, (r1,r0)
    excp 8

.globl gpio_set
gpio_set:
    jump (ra)
.globl spi_cfg
spi_cfg:
    jump (ra)
