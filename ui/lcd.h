#ifndef UI_LCD_H
#define UI_LCD_H

#define LCD_W 240
#define LCD_H 320

/* RGB565 */
#define RGB(r, g, b) ((unsigned short)((((r) & 0xf8) << 8) | (((g) & 0xfc) << 3) | ((b) >> 3)))

typedef struct {
    unsigned char w, h;              /* glyph cell in pixels, w <= 16 */
    const unsigned char *bits;       /* fontgen.py layout */
} font_t;

extern const font_t FONT_S;          /* Spleen 8x16 */
extern const font_t FONT_L;          /* Spleen 12x24 */

void lcd_begin(void);                /* select the display; call before drawing */
void lcd_end(void);                  /* restore the stock window and release the display */
void lcd_fill(int x, int y, int w, int h, unsigned short c);
/* Draw Latin-1 text clipped to the screen; returns its width in pixels. */
int lcd_text(int x, int y, const char *s, const font_t *f, unsigned short fg, unsigned short bg);
/* Fill a w x h box and put the text in it, vertically centred, left-aligned
 * at pad (or centred when pad < 0). */
void lcd_label(int x, int y, int w, int h, int pad, const char *s, const font_t *f,
               unsigned short fg, unsigned short bg);
int text_width(const char *s, const font_t *f);

#endif
