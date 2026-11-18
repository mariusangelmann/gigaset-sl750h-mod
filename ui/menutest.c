/* Live test of the custom UI: a scrolling list menu steered with the phone's
 * keys, run from RAM through the AT monitor (ui/run.py).
 *
 * The program runs in steps. Each call of start() does ~10 ms of work and
 * returns, so the stock firmware's scheduler keeps running in between; the
 * monitor re-runs the call for as long as the PC keeps the serial port open.
 * Blocking the scheduler for ~5 s reset the phone, so never loop inside one
 * call. While the menu runs, the stock UI's key queue is locked and emptied.
 * Red key, or IDLE_TICKS without a key, ends it; start() then returns 0x0E0D.
 * All state is static: ram.ld puts .bss into the uploaded image, so every
 * upload starts fresh. */
#include "fw.h"
#include "lcd.h"

#ifndef TICK_LOOPS
#define TICK_LOOPS 6500UL            /* busy-loop iterations per ~10 ms tick (calibrated: 2000 = 3 ms) */
#endif
#define IDLE_TICKS 3000              /* ~30 s without a key ends the test */
#define REPEAT_FIRST 45              /* held UP/DOWN repeats after ~450 ms */
#define REPEAT_NEXT 12               /* then every ~120 ms */

/* Colours */
#define C_BG     RGB(0, 0, 0)
#define C_TEXT   RGB(220, 220, 220)
#define C_BAR    RGB(24, 40, 64)
#define C_SEL    RGB(30, 110, 230)
#define C_WHITE  RGB(255, 255, 255)
#define C_DIM    RGB(120, 140, 170)

/* Layout */
#define HEAD_H   44
#define ITEM_H   40
#define ROWS     6
#define LIST_Y   HEAD_H
#define FOOT_Y   (LIST_Y + ROWS * ITEM_H)
#define FOOT_H   (LCD_H - FOOT_Y)

static const char *const items[] = {
    "Anrufliste", "Kontakte", "Klingelt\xf6ne", "Vibration", "Nicht st\xf6ren",
    "Wecker", "Einstellungen", "Snake", "Info",
};
#define N_ITEMS (int)(sizeof items / sizeof items[0])

enum { S_START, S_RUN, S_QUIT, S_DONE };
static unsigned char state;
static unsigned short last, pend;     /* debounced and candidate key word */
static int sel, top, idle, held;

static void tick(void)
{
    volatile unsigned long i;

    for (i = 0; i < TICK_LOOPS; i++)
        ;
    WDOG_KICK();
}

/* Matrix position -> key. Rows = low byte, columns = high byte of KEY_RAW;
 * table from the stock firmware's keymap (re/RE_NOTES.md). */
static const char keymap[8][4] = {
    /*           col0 col1 col2 col3 */
    /* row0 */ { 's', 'U', 't', 'X' },   /* soft key, up, soft key, red */
    /* row1 */ { 'L', 'O', 'R', '?' },   /* left, OK, right */
    /* row2 */ { '?', 'a', '?', '?' },
    /* row3 */ { 'G', 'b', '3', '?' },   /* green */
    /* row4 */ { '1', 'D', '6', '?' },   /* down */
    /* row5 */ { '4', '2', '9', '?' },
    /* row6 */ { '7', '5', '#', '?' },
    /* row7 */ { '*', '8', '0', '?' },
};

static char decode(unsigned short raw)
{
    int r = 0, c = 0;
    unsigned char rows = raw, cols = raw >> 8;

    if (!rows || !cols)
        return 0;
    while (!(rows & 1)) { rows >>= 1; r++; }
    while (!(cols & 1)) { cols >>= 1; c++; }
    return c < 4 ? keymap[r][c] : '?';
}

static const char hex[] = "0123456789ABCDEF";

static void footer(const char *msg, unsigned short raw)
{
    char k[5];
    int i;

    for (i = 0; i < 4; i++)          /* raw key word, for checking the keymap */
        k[i] = hex[(raw >> (12 - 4 * i)) & 15];
    k[4] = 0;
    lcd_label(0, FOOT_Y, 180, FOOT_H, 10, msg, &FONT_S, C_DIM, C_BAR);
    lcd_label(180, FOOT_Y, 60, FOOT_H, 8, k, &FONT_S, C_DIM, C_BAR);
}

static void draw_item(int i)
{
    int y = LIST_Y + (i - top) * ITEM_H;
    int on = i == sel;

    lcd_label(0, y, LCD_W, ITEM_H, 16, items[i], &FONT_L, on ? C_WHITE : C_TEXT,
              on ? C_SEL : C_BG);
}

static void draw_list(void)
{
    int i;

    for (i = top; i < top + ROWS; i++)
        draw_item(i);
}

static void move(int d)
{
    int old = sel, oldtop = top;

    sel += d;
    if (sel < 0)
        sel = N_ITEMS - 1;
    if (sel >= N_ITEMS)
        sel = 0;
    if (sel < top)
        top = sel;
    if (sel >= top + ROWS)
        top = sel - ROWS + 1;
    lcd_begin();
    if (top != oldtop) {
        draw_list();
    } else {
        draw_item(old);
        draw_item(sel);
    }
    lcd_end();
}

static void handle(char k, unsigned short raw)
{
    if (k == 'U' || k == 'D') {
        move(k == 'U' ? -1 : 1);
    } else if (k >= '1' && k <= '9' && k - '1' < N_ITEMS) {
        move(k - '1' - sel);
    } else if (k == 'O' || k == 'R') {
        lcd_begin();
        footer(items[sel], raw);
        lcd_end();
    } else if (k == 'X') {
        state = S_QUIT;
    }
}

__attribute__((section(".text.start"))) unsigned short start(void)
{
    unsigned short raw;
    char k;

    if (state == S_DONE)
        return 0x0E0D;
    WDOG_KICK();
    KEY_LOCK = 1;                    /* stock UI: "no key available" */
    kq_clear();
    if (state == S_START) {
        lcd_begin();
        lcd_label(0, 0, LCD_W, HEAD_H, -1, "Men\xfc", &FONT_L, C_WHITE, C_BAR);
        draw_list();
        footer("Rot = Ende", 0);
        lcd_end();
        state = S_RUN;
        return 0x600D;
    }
    tick();
    raw = KEY_RAW;
    if (state == S_QUIT) {           /* wait until all keys are up, then hand back */
        idle = raw ? 0 : idle + 1;
        if (idle < 10)
            return 0x600D;
        kq_clear();
        KEY_LOCK = 0;
        state = S_DONE;
        return 0x0E0D;
    }
    if (raw != pend) {               /* a key word must be seen on two steps */
        pend = raw;
        return 0x600D;
    }
    k = decode(raw);
    if (raw == last) {
        if (!raw) {
            if (++idle >= IDLE_TICKS)
                state = S_QUIT, idle = 0;
            return 0x600D;
        }
        if (k != 'U' && k != 'D')
            return 0x600D;
        held++;                      /* auto-repeat for UP / DOWN */
        if (held < REPEAT_FIRST || (held - REPEAT_FIRST) % REPEAT_NEXT)
            return 0x600D;
    } else {
        held = idle = 0;
        last = raw;
        lcd_begin();
        footer(raw ? "" : "Rot = Ende", raw);
        lcd_end();
        if (!raw)
            return 0x600D;
    }
    handle(k, raw);
    if (state == S_QUIT)
        idle = 0;
    return 0x600D;
}
