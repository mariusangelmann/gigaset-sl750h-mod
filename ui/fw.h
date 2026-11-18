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

/* Key event queue of the stock UI: empty it, or post a key code
 * (green 0x22, red 0x23, OK 0x19, digits 0x40..0x49). */
void kq_clear(void);
void post_key(unsigned code);

#define REG8(a)  (*(volatile unsigned char *)(a))
#define REG16(a) (*(volatile unsigned short *)(a))

#define WDOG_KICK() (REG16(0xFF4C00) = 0xFF)
/* Raw keypad state, refreshed by the keyboard interrupt: low byte = row
 * bitmask, high byte = column bitmask, 0 = no key. */
#define KEY_RAW     REG16(0x875678)
/* Stock key queue lock: while nonzero, key_available() 0x14CFE6 reports none. */
#define KEY_LOCK    REG8(0x874E02)
/* Clock kept by the stock firmware (synced from the base), see re/STATUS.md. */
typedef struct {
    unsigned short year;             /* e.g. 2026 */
    unsigned char month, day;        /* 1..12, 1..31 */
    unsigned char hour, min;         /* 0..23, 0..59 */
    unsigned char wday;              /* 0 = Monday */
} fw_clock_t;
#define CLOCK       (*(volatile fw_clock_t *)0x87451C)
/* Battery state (status table 0x874B92, index 2, read by AT+CBC):
 * 3/4/5 = 20/60/100 %, 6/7/8 = charging 20/60/100 %, 9 = charging, empty. */
#define BATT_STATE  REG8(0x874B94)
#define LCD_FLAGS   REG8(0x874630)   /* bit 4 set: SPI clock setting 2, else 1 */

#endif
