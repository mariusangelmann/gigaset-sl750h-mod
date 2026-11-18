/* Minimal ST7789 driver on top of the stock firmware's SPI routines. */
#include "fw.h"
#include "lcd.h"

extern const unsigned char font_s[], font_l[];
const font_t FONT_S = { 8, 16, font_s };
const font_t FONT_L = { 12, 24, font_l };

static unsigned char clk;
static unsigned short line[LCD_W];

static void send(unsigned dc, const unsigned char *p, unsigned long n)
{
    gpio_set(0x2f, dc);
    spi_cfg(0, clk, 0);
    spi_w8(p, n);
}

static void window(int x0, int y0, int x1, int y1)
{
    static const unsigned char caset = 0x2a, raset = 0x2b, ramwr = 0x2c;
    unsigned char b[4];

    b[0] = x0 >> 8; b[1] = x0; b[2] = x1 >> 8; b[3] = x1;
    send(1, &caset, 1);
    send(0, b, 4);
    b[0] = y0 >> 8; b[1] = y0; b[2] = y1 >> 8; b[3] = y1;
    send(1, &raset, 1);
    send(0, b, 4);
    send(1, &ramwr, 1);
    gpio_set(0x2f, 0);               /* pixels follow as 16-bit data */
    spi_cfg(0, clk, 1);
}

void lcd_begin(void)
{
    clk = (LCD_FLAGS & 0x10) ? 2 : 1;
    gpio_set(6, 1);
}

void lcd_end(void)
{
    window(0, 0, LCD_W - 1, LCD_H - 1);  /* the stock UI only ever sets rows */
    gpio_set(0x2f, 0);
    gpio_set(6, 0);
}

void lcd_fill(int x, int y, int w, int h, unsigned short c)
{
    int i;

    if (w <= 0 || h <= 0)
        return;
    window(x, y, x + w - 1, y + h - 1);
    for (i = 0; i < w; i++)
        line[i] = c;
    while (h--) {
        spi_w16(line, w);
        WDOG_KICK();
    }
}

static int glyph_index(unsigned char c)
{
    if (c >= 0x20 && c < 0x7f)
        return c - 0x20;
    switch (c) {                     /* order of EXTRA in fontgen.py */
    case 0xe4: return 95;            /* ä */
    case 0xf6: return 96;            /* ö */
    case 0xfc: return 97;            /* ü */
    case 0xc4: return 98;            /* Ä */
    case 0xd6: return 99;            /* Ö */
    case 0xdc: return 100;           /* Ü */
    case 0xdf: return 101;           /* ß */
    case 0xb0: return 102;           /* ° */
    }
    return '?' - 0x20;
}

int text_width(const char *s, const font_t *f)
{
    int n = 0;

    while (s[n])
        n++;
    return n * f->w;
}

int lcd_text(int x, int y, const char *s, const font_t *f, unsigned short fg, unsigned short bg)
{
    int n = 0, r, i, k, bpr = (f->w + 7) / 8, gsize = f->h * bpr;

    while (s[n] && x + (n + 1) * f->w <= LCD_W)
        n++;
    if (!n)
        return 0;
    window(x, y, x + n * f->w - 1, y + f->h - 1);
    for (r = 0; r < f->h; r++) {
        unsigned short *p = line;
        for (i = 0; i < n; i++) {
            const unsigned char *g = f->bits + glyph_index(s[i]) * gsize + r * bpr;
            unsigned short bits = g[0] << 8;
            if (bpr > 1)
                bits |= g[1];
            for (k = 0; k < f->w; k++) {
                *p++ = (bits & 0x8000) ? fg : bg;
                bits <<= 1;
            }
        }
        spi_w16(line, n * f->w);
        WDOG_KICK();
    }
    return n * f->w;
}

void lcd_label(int x, int y, int w, int h, int pad, const char *s, const font_t *f,
               unsigned short fg, unsigned short bg)
{
    int tw = text_width(s, f), ty = y + (h - f->h) / 2, tx;

    if (tw > w)
        tw = w / f->w * f->w;
    tx = pad < 0 ? x + (w - tw) / 2 : x + pad;
    lcd_fill(x, y, w, ty - y, bg);                          /* above */
    lcd_fill(x, ty + f->h, w, y + h - ty - f->h, bg);       /* below */
    lcd_fill(x, ty, tx - x, f->h, bg);                      /* left */
    tw = lcd_text(tx, ty, s, f, fg, bg);
    lcd_fill(tx + tw, ty, x + w - tx - tw, f->h, bg);       /* right */
}
