/* Link a RAM stub at its real address (default CR16 script rejects RAM). */
ENTRY(draw)
SECTIONS
{
  . = 0x879000;
  .text : { *(.text) }
  .data : { *(.data) }
  /DISCARD/ : { *(*) }
}
