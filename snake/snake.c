/* snake.c — Snake for the Gigaset SL750H PRO (Dialog SC14441 / CR16C+).
 *
 * Freestanding, no libc. Drives the ST7735 TFT over the QSPI controller and
 * polls the keypad over GPIO directly, so it does not depend on the stock
 * UI framework. Compiled with:  cr16-elf-gcc -mcr16c -Os -ffreestanding -nostdlib
 *
 * Memory map (from firmware RE):
 *   flash window base 0xF0000 (CPU addr = image file offset + 0xF0000)
 *   RAM 0x0..0x2000, peripherals 0xFF0000-0xFFC00
 *   QSPI controller 0xFF0C00, GPIO ports P0..P3 at 0xFF4830..0xFF4868
 *
 * TODO(confirm against app code): LCD CS/RS GPIO lines, keypad row/col pins,
 * and the display geometry (ST7735: 128x160 or 160x128).
 */

typedef unsigned short u16;
typedef unsigned int u32;

#define MMIO8(a)  (*(volatile unsigned char *)(a))
#define MMIO16(a) (*(volatile unsigned short *)(a))
#define MMIO32(a) (*(volatile unsigned int *)(a))

/* QSPI controller (SC14441) */
#define QSPI_CTRL   MMIO32(0xFF0C00)
#define QSPI_CFG    MMIO16(0xFF0C04)
#define QSPI_STATUS MMIO16(0xFF0C14)
#define QSPI_TX8    MMIO8(0xFF0C18)
#define QSPI_BUSY   0x0001

/* GPIO ports */
#define P0_DATA MMIO16(0xFF4830)
#define P1_DATA MMIO16(0xFF4840)
#define P2_DATA MMIO16(0xFF4850)
#define P3_DATA MMIO16(0xFF4860)

/* LCD control lines — TODO: confirm which GPIO/pin the SL750H uses */
#define LCD_CS_PIN   (1 << 0)   /* TODO */
#define LCD_RS_PIN   (1 << 1)   /* TODO: 0 = command, 1 = data */
#define LCD_RST_PIN  (1 << 2)   /* TODO */
#define LCD_PORT     P1_DATA

/* Display geometry: ST7735 128x160 (portrait). Snake cell = 8x8 px */
#define LCD_W 128
#define LCD_H 160
#define COLS (LCD_W / 8)   /* 16 */
#define ROWS (LCD_H / 8)   /* 20 */

static void gpio_out(unsigned short pin, int hi) {
    if (hi) LCD_PORT |= pin; else LCD_PORT &= ~pin;
}

static void qspi_put8(unsigned char b) {
    while (QSPI_STATUS & QSPI_BUSY) {}
    QSPI_TX8 = b;
}

static void lcd_cmd(unsigned char c) {
    gpio_out(LCD_RS_PIN, 0);
    gpio_out(LCD_CS_PIN, 0);
    qspi_put8(c);
    gpio_out(LCD_CS_PIN, 1);
}

static void lcd_data(unsigned char d) {
    gpio_out(LCD_RS_PIN, 1);
    gpio_out(LCD_CS_PIN, 0);
    qspi_put8(d);
    gpio_out(LCD_CS_PIN, 1);
}

static void lcd_init(void) {
    gpio_out(LCD_RST_PIN, 0);
    for (volatile int i = 0; i < 10000; i++) {}
    gpio_out(LCD_RST_PIN, 1);
    for (volatile int i = 0; i < 100000; i++) {}
    lcd_cmd(0x01);              /* SWRESET */
    for (volatile int i = 0; i < 100000; i++) {}
    lcd_cmd(0x11);              /* SLPOUT */
    for (volatile int i = 0; i < 100000; i++) {}
    lcd_cmd(0x3A); lcd_data(0x05);  /* 16-bit/pixel (RGB565) */
    lcd_cmd(0x36); lcd_data(0x00);  /* MADCTL */
    lcd_cmd(0x29);              /* DISPON */
}

static void lcd_set_window(u16 x0, u16 y0, u16 x1, u16 y1) {
    lcd_cmd(0x2A); lcd_data(x0 >> 8); lcd_data(x0 & 0xFF); lcd_data(x1 >> 8); lcd_data(x1 & 0xFF);
    lcd_cmd(0x2B); lcd_data(y0 >> 8); lcd_data(y0 & 0xFF); lcd_data(y1 >> 8); lcd_data(y1 & 0xFF);
    lcd_cmd(0x2C);
}

static void lcd_fill_rect(u16 x, u16 y, u16 w, u16 h, u16 color) {
    lcd_set_window(x, y, x + w - 1, y + h - 1);
    gpio_out(LCD_RS_PIN, 1);
    gpio_out(LCD_CS_PIN, 0);
    u32 n = (u32)w * h;
    while (n--) { qspi_put8(color >> 8); qspi_put8(color & 0xFF); }
    gpio_out(LCD_CS_PIN, 1);
}

/* Keypad — TODO: confirm row/col pins; returns 0=none 1=up 2=down 3=left 4=right 9=exit */
static int read_key(void) {
    /* TODO: drive row outputs, read col inputs on the keypad GPIOs */
    return 0;
}

static void delay(volatile u32 n) { while (n--) {} }

/* ---- game state ---- */
static unsigned char snake_x[COLS * ROWS];
static unsigned char snake_y[COLS * ROWS];
static int snake_len;
static int dir;                 /* 0=right 1=down 2=left 3=up */
static unsigned char food_x, food_y;
static u32 rng = 0x12345678;

static u32 rnd(void) { rng = rng * 1103515245 + 12345; return (rng >> 16) & 0x7FFF; }

static int cell_free(int x, int y) {
    for (int i = 0; i < snake_len; i++)
        if (snake_x[i] == x && snake_y[i] == y) return 0;
    return 1;
}

static void place_food(void) {
    do { food_x = rnd() % COLS; food_y = rnd() % ROWS; } while (!cell_free(food_x, food_y));
}

void snake_main(void) {
    lcd_init();
    lcd_fill_rect(0, 0, LCD_W, LCD_H, 0x0000);

    snake_len = 3; dir = 0;
    for (int i = 0; i < snake_len; i++) { snake_x[i] = 5 - i; snake_y[i] = 10; }
    place_food();

    for (;;) {
        int k = read_key();
        if (k == 9) return;                 /* exit key -> back to boot */
        if (k == 1 && dir != 1) dir = 3;
        else if (k == 2 && dir != 3) dir = 1;
        else if (k == 3 && dir != 0) dir = 2;
        else if (k == 4 && dir != 2) dir = 0;

        int hx = snake_x[0], hy = snake_y[0];
        if (dir == 0) hx++; else if (dir == 1) hy++;
        else if (dir == 2) hx--; else hy--;
        if (hx < 0 || hy < 0 || hx >= COLS || hy >= ROWS) break;   /* wall = game over */
        if (!cell_free(hx, hy)) break;                             /* self = game over */

        for (int i = snake_len - 1; i > 0; i--) { snake_x[i] = snake_x[i-1]; snake_y[i] = snake_y[i-1]; }
        snake_x[0] = hx; snake_y[0] = hy;

        if (hx == food_x && hy == food_y) {
            if (snake_len < COLS * ROWS) {
                snake_x[snake_len] = snake_x[snake_len-1];
                snake_y[snake_len] = snake_y[snake_len-1];
                snake_len++;
            }
            place_food();
        }

        /* draw */
        lcd_fill_rect(0, 0, LCD_W, LCD_H, 0x0000);
        lcd_fill_rect(food_x * 8, food_y * 8, 8, 8, 0xF800);      /* red food */
        for (int i = 0; i < snake_len; i++)
            lcd_fill_rect(snake_x[i] * 8, snake_y[i] * 8, 8, 8, i == 0 ? 0x07E0 : 0x07FF); /* green */

        delay(30000);   /* ~game speed; calibrate */
    }

    /* game over: flash screen, wait for exit key */
    for (int f = 0; f < 3; f++) {
        lcd_fill_rect(0, 0, LCD_W, LCD_H, 0xF800);
        delay(60000);
        lcd_fill_rect(0, 0, LCD_W, LCD_H, 0x0000);
        delay(60000);
    }
    while (read_key() != 9) delay(10000);
}
