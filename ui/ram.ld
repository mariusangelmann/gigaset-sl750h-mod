/* Link the custom UI for RAM 0x876000 (unused by the stock firmware, see
 * monitor/README.md), started through the AT monitor's =C command at that
 * address. Stock-firmware routines are bound here (see fw.h). */
_gpio_set = 0x1DA3E6;
_spi_cfg  = 0x1DCE12;
_spi_w8   = 0x1DCE5E;
_spi_w16  = 0x1DCE82;
_kq_clear = 0x14D0B4;
_post_key = 0x14CDFE;

ENTRY(_start)
SECTIONS
{
  . = 0x876000;
  .text : { *(.text.start) *(.text*) *(.rodata*) }
  /* .bss lives inside .data so the uploaded image carries its zeros. */
  .data : { *(.data*) *(.bss*) *(COMMON) }
  __end = .;
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
