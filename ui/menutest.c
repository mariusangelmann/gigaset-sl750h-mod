/* Live test of the custom UI: a scrolling list menu steered with the phone's
 * keys, run from RAM through the AT monitor (ui/run.py).
 *
 * The program runs in steps. Each call of start() does ~10 ms of work and
 * returns, so the stock firmware's scheduler keeps running in between; the
 * monitor re-runs the call for as long as the PC keeps the serial port open.
 * Blocking the scheduler for ~5 s reset the phone, so never loop inside one
 * call. While the menu runs, the stock UI's key queue is locked and emptied.
 * Red key, or IDLE_TICKS without a key, ends it: it presses OK and red for the
 * stock UI so that it repaints the whole screen, then start() returns 0x0E0D.
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

enum { S_START, S_RUN, S_QUIT, S_REDRAW, S_DONE };
enum { V_LIST, V_INFO };
static unsigned char state, view;
static unsigned short info_sig;       /* minute and battery last drawn on Info */
static unsigned char last_min;        /* minute seen last step */
static unsigned char repaint_in;      /* steps until a full repaint, 0 = none */
#define KEY_RED  0x0801               /* KEY_RAW of the red key (row 0, column 3) */
#define REPAINT_DELAY 25              /* ~0.35 s: let the stock UI finish drawing first */
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

/* ---- Info screen: clock, date, battery ---- */

static char *put2(char *p, unsigned v)
{
    *p++ = '0' + v / 10 % 10;
    *p++ = '0' + v % 10;
    return p;
}

static void info_values(void)
{
    static const char wd[7][3] = { "Mo", "Di", "Mi", "Do", "Fr", "Sa", "So" };
    static const unsigned char pct[] = { 20, 60, 100 };
    unsigned char b = BATT_STATE, wday = CLOCK.wday;
    unsigned year = CLOCK.year;
    char t[24], *p;

    p = put2(t, CLOCK.hour); *p++ = ':'; p = put2(p, CLOCK.min); *p = 0;
    lcd_label(0, 70, LCD_W, 40, -1, t, &FONT_L, C_WHITE, C_BG);

    p = t;
    if (wday < 7) { *p++ = wd[wday][0]; *p++ = wd[wday][1]; *p++ = ','; *p++ = ' '; }
    p = put2(p, CLOCK.day); *p++ = '.'; p = put2(p, CLOCK.month); *p++ = '.';
    p = put2(p, year / 100); p = put2(p, year); *p = 0;
    lcd_label(0, 110, LCD_W, 30, -1, t, &FONT_S, C_TEXT, C_BG);

    p = t;
    *p++ = 'A'; *p++ = 'k'; *p++ = 'k'; *p++ = 'u'; *p++ = ':'; *p++ = ' ';
    if (b >= 3 && b <= 8) {
        unsigned v = pct[(b - 3) % 3];
        if (v == 100) *p++ = '1';
        p = put2(p, v); *p++ = ' '; *p++ = '%';
    } else if (b == 9) {
        *p++ = '0'; *p++ = ' '; *p++ = '%';
    } else {
        *p++ = '?'; *p++ = ' '; *p++ = '('; p = put2(p, b); *p++ = ')';
    }
    if (b >= 6 && b <= 9) { *p++ = ','; *p++ = ' '; *p++ = 'l'; *p++ = '\xe4'; *p++ = 'd'; *p++ = 't'; }
    *p = 0;
    lcd_label(0, 170, LCD_W, 40, 16, t, &FONT_L, C_TEXT, C_BG);
    info_sig = CLOCK.min | b << 8;
}

static void open_info(void)
{
    view = V_INFO;
    lcd_begin();
    lcd_label(0, 0, LCD_W, HEAD_H, -1, "Info", &FONT_L, C_WHITE, C_BAR);
    lcd_fill(0, HEAD_H, LCD_W, FOOT_Y - HEAD_H, C_BG);
    info_values();
    footer("Rot = Zur\xfc" "ck", 0);
    lcd_end();
}

static void open_list(void)
{
    view = V_LIST;
    lcd_begin();
    lcd_label(0, 0, LCD_W, HEAD_H, -1, "Men\xfc", &FONT_L, C_WHITE, C_BAR);
    draw_list();
    footer("Rot = Ende", 0);
    lcd_end();
}

static void handle(char k, unsigned short raw)
{
    if (view == V_INFO) {
        if (k == 'X' || k == 'L')
            open_list();
        return;
    }
    if (k == 'U' || k == 'D') {
        move(k == 'U' ? -1 : 1);
    } else if (k >= '1' && k <= '9' && k - '1' < N_ITEMS) {
        move(k - '1' - sel);
    } else if (k == 'O' || k == 'R') {
        if (sel == N_ITEMS - 1) {
            open_info();
            return;
        }
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
    if (state != S_REDRAW) {
        KEY_LOCK = 1;                /* stock UI: "no key available" */
        kq_clear();
    }
    if (state == S_START) {
        last_min = CLOCK.min;
        open_list();
        state = S_RUN;
        return 0x600D;
    }
    tick();
    raw = KEY_RAW;
    /* The stock UI still draws while we run: red always reaches it (post_key
     * unlocks the key queue for red, 0x14CE14) and it jumps to its idle
     * screen, and it redraws its clock every minute. Repaint after it. */
    if (state == S_RUN) {
        if (raw == KEY_RED || CLOCK.min != last_min)
            repaint_in = REPAINT_DELAY;
        last_min = CLOCK.min;
        if (repaint_in && !--repaint_in) {
            if (view == V_INFO)
                open_info();
            else
                open_list();
        }
    }
    if (state == S_QUIT) {           /* wait until all keys are up, then hand back */
        idle = raw ? 0 : idle + 1;
        if (idle < 10)
            return 0x600D;
        kq_clear();
        KEY_LOCK = 0;
        post_key(0x19);              /* OK: stock menu, full-screen repaint */
        state = S_REDRAW;
        idle = 0;
        return 0x600D;
    }
    if (state == S_REDRAW) {         /* ~0.5 s later red: back to a fully drawn idle */
        if (++idle < 30)
            return 0x600D;
        post_key(0x23);
        state = S_DONE;
        return 0x0E0D;
    }
    if (view == V_INFO && (CLOCK.min | BATT_STATE << 8) != info_sig) {
        lcd_begin();
        info_values();
        lcd_end();
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
        footer(raw ? "" : view == V_INFO ? "Rot = Zur\xfc" "ck" : "Rot = Ende", raw);
        lcd_end();
        if (!raw)
            return 0x600D;
    }
    handle(k, raw);
    if (state == S_QUIT)
        idle = 0;
    return 0x600D;
}
