# monitor.s - On-device memory monitor for the Gigaset SL750H PRO
# (Dialog SC1444x, CR16C+). Hooked onto the AT command ^GCTRACER.
#
# Placement: free flash. Link with -Ttext <MON_BASE> (build.sh; default
# 0x2C1900, after Snake). Entry: mon_entry; the ^GCTRACER table record's
# handler/2 field must hold mon_entry/2 (the dispatcher does jal value*2).
#
# ARGUMENT POINTER (the fix):
# The first monitor read the arg from (r5,r4) because a subagent reported the
# dispatcher passes it there. On the handset that was wrong - every '=' command
# returned ERROR because (r5,r4) did not point at the argument text. So this
# version does NOT trust any passed register. It recomputes the argument
# pointer exactly like the firmware's own dispatcher helper at 0x1024EE:
#     arg = *(u32*)[0x874887] + (u16)[0x8748a7]
# [0x874887] is a pointer to the received command line; [0x8748a7] is the
# offset of the argument within it (the firmware advances it past '=', see the
# line parser at 0x1023FE). at_begin (0x101FB4) only clears struct fields at
# [0x874887]+0x10..+0x18, so the pointer and offset are stable across it.
#
# SELF-DIAGNOSIS: on a parse failure the handler first emits three "0x%X" lines
# - the computed arg pointer (high word, low word) and the first 16-bit word at
# that pointer - then returns ERROR. If a flash still fails, those bytes reveal
# the real buffer layout without another guess (e.g. "8756.." for "875678",
# "4347" for 'GC' of "GCTRACER", or junk for a bad pointer).
#
# AT formatter (0x10201A): (r3,r2) = format string; varargs at the caller's sp.
# %X/%x/%i/%p each take one 16-bit word; %s/%S a 32-bit pointer. The caller
# reserves the word on the stack before the call (addd $-4,(sp); storw v,0(sp)).
#
# Syntax (hex case-insensitive, leading '=' optional; debug tool, no range
# guard; address parsed as 32 bits, value as 16). An optional letter after '='
# picks the operation:
#   =<addr>           read the 16-bit word at <addr>, reply "0x<VAL>", then OK
#   =<addr>,<val>     write 16-bit <val> to <addr>, then OK
#   =B<addr>,<val>    write the low BYTE of <val> to <addr>, then OK
#   =C<addr>          CALL code at <addr> (as jal, address halved internally to
#                     match jump-to-pair*2), reply "0x<R0>", then OK
# Stage code into RAM with =B writes, end it with jump (ra) (EE 0A), then =C.
# No hex digits for <addr> or <val> -> diagnostic lines + ERROR, memory intact.
#
# CR16C: "cmp A,B ; bCC" branches when A CC B. r7..r13 are callee-saved.

.set AT_STRUCT, 0x874887       # loadd here = pointer to the command line
.set AT_ARGOFF, 0x8748a7       # loadw here = offset of the argument

.text

# ---- device entry: AT handler ABI (args ignored; arg ptr recomputed) ----
.globl mon_entry
mon_entry:
    push $5, r7, RA            # saves r7..r11 and RA
    bal (ra), at_begin
    loadd AT_STRUCT, (r5,r4)   # (r5,r4) = *[0x874887]  (command-line pointer)
    loadw AT_ARGOFF, r0        # r0 = [0x8748a7]         (argument offset)
    movzw r0, (r1,r0)
    addd (r1,r0), (r5,r4)      # (r5,r4) = arg pointer
    br mon_body

# ---- test entry: (r5,r4) = arg pointer already (sim only) ----
.globl mon_test
mon_test:
    push $5, r7, RA
    movd (r5,r4), (r8,r7)
    bal (ra), at_begin
    movd (r8,r7), (r5,r4)
    # fall through

mon_body:
    movd (r5,r4), (r8,r7)      # keep the original arg pointer for diagnostics
    loadb 0(r5,r4), r0
    cmpb $0x3d, r0             # skip an optional '='
    bne mon_op
    addd $1, (r5,r4)
mon_op:
    movb $0, r11               # r11 = op: 0 word, 'B' byte, 'C' call
    loadb 0(r5,r4), r0
    andb $0xdf, r0             # fold to upper case
    cmpb $0x42, r0             # 'B'
    beq mon_op_set
    cmpb $0x43, r0             # 'C'
    bne mon_addr
mon_op_set:
    movb r0, r11
    addd $1, (r5,r4)
mon_addr:
    bal (ra), parse_hex        # (r1,r0) = address, r3 = digit count
    cmpw $0, r3
    beq mon_err
    movd (r1,r0), (r10,r9)     # address
    cmpb $0x43, r11            # 'C' -> call
    beq mon_call
    loadb 0(r5,r4), r0
    cmpb $0x2c, r0             # ',' -> write form
    beq mon_write
    # ---- read word ----
    loadw 0(r10,r9), r0
    bal (ra), emit
    br mon_ok
mon_write:
    addd $1, (r5,r4)           # skip ','
    bal (ra), parse_hex        # r0 = value (low 16 bits)
    cmpw $0, r3
    beq mon_err
    cmpb $0x42, r11            # 'B' -> byte write
    beq mon_wbyte
    storw r0, 0(r10,r9)
    br mon_ok
mon_wbyte:
    storb r0, 0(r10,r9)
    br mon_ok
mon_call:
    lshd $-1, (r10,r9)         # jal jumps to (pair)*2, so pass addr/2
    jal (r10,r9)               # call the staged routine; it returns here
    bal (ra), emit             # reply the routine's r0
mon_ok:
    bal (ra), at_send_ok
    movw $1, r0
    popret $5, r7, RA
mon_err:
    movw r8, r0                # diagnostic: arg pointer high word
    bal (ra), emit
    movw r7, r0                # arg pointer low word
    bal (ra), emit
    loadw 0(r8,r7), r0         # first word at the arg pointer
    bal (ra), emit
    bal (ra), at_send_error
    movw $1, r0
    popret $5, r7, RA

# emit(r0 = 16-bit word): send one "0x<WORD>" response line.
emit:
    push RA
    addd $-4, (sp)
    storw r0, 0(sp)            # vararg 1
    movd $fmt_hex, (r3,r2)
    bal (ra), at_send_response_line
    addd $4, (sp)
    popret RA

# parse_hex: hex digits at (r5,r4) -> (r1,r0) (32-bit), r3 = digit count;
# (r5,r4) is left on the first non-hex byte. Clobbers r2.
parse_hex:
    movd $0, (r1,r0)
    movw $0, r3
ph_loop:
    loadb 0(r5,r4), r2
    cmpb $0x30, r2
    bhi ph_done                # r2 < '0'
    cmpb $0x39, r2
    blo ph_az                  # r2 > '9'
    subb $0x30, r2
    br ph_acc
ph_az:
    andb $0xdf, r2             # fold a-f to A-F
    cmpb $0x41, r2
    bhi ph_done                # r2 < 'A'
    cmpb $0x46, r2
    blo ph_done                # r2 > 'F'
    subb $0x37, r2
ph_acc:
    ashud $4, (r1,r0)
    movzb r2, r2
    orw r2, r0
    addw $1, r3
    addd $1, (r5,r4)
    br ph_loop
ph_done:
    jump (ra)

fmt_hex:
    .asciz "0x%X"
