# monitor.s - On-device memory monitor for the Gigaset SL750H PRO
# (Dialog SC1444x, CR16C+). Hooked onto the AT command ^GCTRACER.
#
# Placement: free flash. Link with -Ttext <MON_BASE> (build.sh; placeholder
# 0x2C2000). The free-flash region starts at 0x2C1244 but Snake sits at its
# start, so the base is a link argument. The code is position-dependent only
# through the absolute fmt_hex address (resolved by the linker).
# Entry: mon_entry. The ^GCTRACER table record's handler/2 field must hold
# mon_entry/2 (the dispatcher does jal (value*2)).
#
# AT handler calling convention (verified at dispatcher 0x102494..0x1024dc):
#   r2      = command index byte        r3 = syntax-type byte
#   (r5,r4) = pointer to the command-line tail ("=9100,BEEF" for
#             AT^GCTRACER=9100,BEEF), computed as [0x874887] + [0x8748a7]
#   r6      = flag word ([0x8748a9])
# The dispatcher IGNORES the handler's r0 (it does `movb $1,r0` right after the
# jal at 0x1024de), so the handler must emit OK/ERROR itself, like the original
# handler 0x101324 and every other handler (e.g. 0x100c4e) do. We still return
# r0 = 1 for good measure.
# Every inspected handler first calls 0x101fb4 (at_begin: zeroes the response
# state at [0x874887]+0x14/+0x16 and clears the buffer at [0x874887]+0x10,
# length [+0x18]); we do the same, after saving the tail pointer.
#
# Firmware helpers (resolved via --defsym in build.sh; stubbed in the sim):
#   at_begin              = 0x101FB4  (no args)
#   at_send_response_line = 0x10201A  (r3,r2) = format; varargs at the caller's
#       sp: %X/%x/%i/%p take one 16-bit word, %s/%S a 32-bit pointer.
#       Caller pattern (0x100c4e): addd $-4,(sp); storw v,0(sp); bal; addd $4.
#       Firmware format strings carry no CR/LF, so neither does ours.
#   at_send_ok = 0x1022EE, at_send_error = 0x1022F8
#
# Syntax (hex digits case-insensitive, leading '=' optional; debug tool, no
# address-range guard; the address is parsed as 32 bits, the value as 16):
#   =<addr>          read the 16-bit word at <addr>, reply "0x<VAL>", then OK
#   =<addr>,<val>    write 16-bit <val> to <addr>, then OK (no reply line)
#   anything with no hex digits for <addr> or <val>  -> ERROR, memory untouched
# Parsing of each number stops at the first non-hex char; text after the
# address (other than ',') or after the value is ignored. Word accesses at odd
# addresses are passed straight to the CPU.
#
# CR16C notes: "cmp A,B ; bCC" branches when A CC B (cmpb $0x30,r2; bhi X =
# branch if 0x30 > r2). r7..r13 are callee-saved, hence push $4,r7,RA.

.text

.globl mon_entry
mon_entry:
    push $4, r7, RA             # saves r7..r10 and RA
    movd (r5,r4), (r8,r7)       # tail pointer survives at_begin
    bal (ra), at_begin
    movd (r8,r7), (r5,r4)       # (r5,r4) = parse cursor
    loadb 0(r5,r4), r0
    cmpb $0x3d, r0              # skip an optional '='
    bne mon_addr
    addd $1, (r5,r4)
mon_addr:
    bal (ra), parse_hex         # (r1,r0) = address, r3 = digit count
    cmpw $0, r3
    beq mon_err
    movd (r1,r0), (r10,r9)      # address
    loadb 0(r5,r4), r0
    cmpb $0x2c, r0              # ',' -> write form
    beq mon_write
    # ---- read ----
    loadw 0(r10,r9), r0
    addd $-4, (sp)
    storw r0, 0(sp)             # vararg 1 = value
    movd $fmt_hex, (r3,r2)
    bal (ra), at_send_response_line
    addd $4, (sp)
    br mon_ok
mon_write:
    addd $1, (r5,r4)            # skip ','
    bal (ra), parse_hex         # r0 = value (low 16 bits)
    cmpw $0, r3
    beq mon_err
    storw r0, 0(r10,r9)
mon_ok:
    bal (ra), at_send_ok
    movw $1, r0
    popret $4, r7, RA
mon_err:
    bal (ra), at_send_error
    movw $1, r0
    popret $4, r7, RA

# parse_hex: hex digits at (r5,r4) -> (r1,r0) (32-bit), r3 = digit count;
# (r5,r4) is left on the first non-hex byte. Clobbers r2.
parse_hex:
    movd $0, (r1,r0)
    movw $0, r3
ph_loop:
    loadb 0(r5,r4), r2
    cmpb $0x30, r2
    bhi ph_done                 # r2 < '0'
    cmpb $0x39, r2
    blo ph_az                   # r2 > '9'
    subb $0x30, r2
    br ph_acc
ph_az:
    andb $0xdf, r2              # fold a-f to A-F
    cmpb $0x41, r2
    bhi ph_done                 # r2 < 'A'
    cmpb $0x46, r2
    blo ph_done                 # r2 > 'F'
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
