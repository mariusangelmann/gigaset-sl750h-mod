# presskey.s - inject one key press through the firmware's post_key (0x14CDFE),
# run from RAM via the AT monitor's =C command.
#
# The monitor's set syntax re-dispatches (the handler runs many times until the
# serial port closes), so the stub is one-shot: it posts the key only while
# FLAG is 0 and then sets FLAG. Clear FLAG (byte write 0) before each press.
#
# Build: cr16-elf-as --defsym CODE=0x22 presskey.s ; link -Ttext 0x10000 (the
# code is position-independent: relative branches, absolute constants only;
# the default linker script rejects RAM addresses). presskey.py uploads it.
# Returns r0 = 0x600D when it posted the key, 0x0D0E when FLAG was already set.
# Key codes (verified live): green 0x22, red 0x23, OK 0x19, digits 0x40-0x49.

.set POST_KEY_HALF, 0xa66ff         # post_key 0x14CDFE / 2
.ifndef FLAG
.set FLAG, 0x878900
.endif

.text
.globl press
press:
    push RA
    loadb FLAG, r0
    cmpb $0, r0
    bne done
    movb $1, r0
    storb r0, FLAG
    movb $CODE, r2
    movd $POST_KEY_HALF, (r1,r0)    # jal jumps to (pair)*2
    jal (r1,r0)
    movw $0x600D, r0
    popret RA
done:
    movw $0x0D0E, r0
    popret RA
