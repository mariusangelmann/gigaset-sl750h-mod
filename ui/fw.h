/* Stock-firmware routines and registers the custom UI uses (SL750H PRO,
 * firmware 116.076.x). Addresses are real CPU addresses; the routines are
 * bound in ui/ram.ld. See re/DISPLAY.md and re/CALLS.md. */
#ifndef FW_H
#define FW_H

/* LCD (ST7789 on SPI 0xFF4940). All are synchronous and safe from any task. */
void gpio_set(unsigned pin, unsigned val);             /* CS = pin 6, D/C = pin 0x2F (1 = command) */
void spi_cfg(unsigned mode, unsigned clk, unsigned wide); /* wide: 0 = 8-bit, 1 = 16-bit words */
void spi_w8(const void *p, unsigned long n);           /* n bytes */
void spi_w16(const void *p, unsigned long n);          /* n native (little-endian) words */

/* Key event queue of the stock UI: empty it. */
void kq_clear(void);

#define REG8(a)  (*(volatile unsigned char *)(a))
#define REG16(a) (*(volatile unsigned short *)(a))

#define WDOG_KICK() (REG16(0xFF4C00) = 0xFF)
/* Raw keypad state, refreshed by the keyboard interrupt: low byte = row
 * bitmask, high byte = column bitmask, 0 = no key. */
#define KEY_RAW     REG16(0x875678)
/* Stock key queue lock: while nonzero, key_available() 0x14CFE6 reports none. */
#define KEY_LOCK    REG8(0x874E02)
#define LCD_FLAGS   REG8(0x874630)   /* bit 4 set: SPI clock setting 2, else 1 */

#endif
