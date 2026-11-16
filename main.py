#!/usr/bin/env python3
"""ai-excited-01 - "The Night We Won"

Pure-stdlib Python renderer (no PIL, no network, no external fonts).
A creased final-match ticket stub, gold confetti bursting through a night
stadium, and a supporter's handwritten note across it: "WE DID IT!!!
3-2 IN EXTRA TIME". One clear subject, huge legible text, gold + red.

Writes a deterministic 1024x1024 PNG to /output/entry.png
(or $MAKEFUN_OUTPUT_DIR/entry.png outside the grader).
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024

# --- palette -------------------------------------------------------------
SKY_TOP = (10, 14, 48)
SKY_MID = (38, 18, 72)
SKY_LOW = (96, 16, 36)
BEAM = (255, 244, 200)
GOLD = (255, 196, 48)
GOLD_DEEP = (224, 148, 20)
GOLD_PALE = (255, 224, 130)
RED = (214, 30, 44)
RED_DARK = (140, 12, 28)
RED_BRIGHT = (255, 64, 64)
CREAM = (252, 242, 214)
CREAM_DARK = (232, 214, 170)
INK = (28, 20, 44)
BLUE_INK = (34, 58, 158)
WHITE = (255, 255, 255)
CROWD = (12, 10, 30)
TAPE = (255, 226, 120)


class Canvas:
    """RGB canvas backed by one bytearray; shapes clip to the edges."""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def fill_rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            o = (yy * self.w + x0) * 3
            self.px[o:o + len(row)] = row

    def set_px(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            o = (y * self.w + x) * 3
            self.px[o:o + 3] = bytes(color)

    def blend_px(self, x, y, color, alpha):
        if 0 <= x < self.w and 0 <= y < self.h:
            o = (y * self.w + x) * 3
            for i in range(3):
                self.px[o + i] = round(
                    self.px[o + i] + (color[i] - self.px[o + i]) * alpha)

    def blend_rect(self, x, y, w, h, color, alpha):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                self.blend_px(xx, yy, color, alpha)

    def disc(self, cx, cy, r, color):
        for dy in range(-r, r + 1):
            yy = cy + dy
            if yy < 0 or yy >= self.h:
                continue
            half = math.isqrt(max(0, r * r - dy * dy))
            self.fill_rect(cx - half, yy, 2 * half + 1, 1, color)

    def line(self, x0, y0, x1, y1, color, width=1):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(steps + 1):
            t = i / steps
            x = round(x0 + (x1 - x0) * t)
            y = round(y0 + (y1 - y0) * t)
            self.fill_rect(x - width // 2, y - width // 2, width, width,
                           color)

    def poly(self, pts, color):
        """Scanline polygon fill for a convex-ish polygon."""
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            if len(xs) >= 2:
                xs.sort()
                self.fill_rect(int(xs[0]), y, int(xs[-1]) - int(xs[0]) + 1,
                               1, color)

    def blend_poly(self, pts, color, alpha):
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            if len(xs) >= 2:
                xs.sort()
                self.blend_rect(int(xs[0]), y,
                                int(xs[-1]) - int(xs[0]) + 1, 1, color,
                                alpha)

    def star(self, cx, cy, r, color):
        """Four-point sparkle: two thin diamonds."""
        self.poly([(cx, cy - r), (cx + r // 3, cy - r // 3),
                   (cx + r, cy), (cx + r // 3, cy + r // 3),
                   (cx, cy + r), (cx - r // 3, cy + r // 3),
                   (cx - r, cy), (cx - r // 3, cy - r // 3)], color)


# --- 5x7 bitmap font, drawn fresh for this entry ('#' = ink) --------------
FONT = {
    'A': (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'B': ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    'C': (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    'D': ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    'E': ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    'F': ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    'G': (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    'H': ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'I': (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    'J': ("..###", "....#", "....#", "....#", "....#", "#...#", ".###."),
    'K': ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    'L': ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    'M': ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    'N': ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    'O': (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'P': ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    'Q': (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    'R': ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    'S': (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    'T': ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    'U': ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'V': ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    'W': ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    'X': ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    'Y': ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    'Z': ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
}

FONT.update({
    '0': (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    '1': ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    '2': (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    '3': ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    '4': ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    '5': ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    '6': (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    '7': ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    '8': (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    '9': (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    '.': (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ',': (".....", ".....", ".....", ".....", ".....", ".##..", ".#..."),
    '!': ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    '-': (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    ':': (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    '/': ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    ' ': (".....", ".....", ".....", ".....", ".....", ".....", "....."),
})


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(cv, s, x, y, scale, color, skew=0):
    """Left-aligned bitmap text; skew shifts each row right (italic lean)."""
    for ch in s:
        glyph = FONT.get(ch)
        if glyph:
            for r, line in enumerate(glyph):
                for c, bit in enumerate(line):
                    if bit == '#':
                        cv.fill_rect(x + c * scale + r * skew,
                                     y + r * scale, scale, scale, color)
        x += 6 * scale


def draw_text_c(cv, s, cx, y, scale, color, skew=0):
    draw_text(cv, s, cx - text_width(s, scale) // 2, y, scale, color, skew)


def draw_text_outline(cv, s, cx, y, scale, color, edge, skew=0):
    """Text with a 1-cell outline: draw edge colour offset in 8 directions."""
    w = text_width(s, scale)
    x0 = cx - w // 2
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                   (-1, -1), (1, -1), (-1, 1), (1, 1)):
        draw_text(cv, s, x0 + dx * scale, y + dy * scale, scale, edge, skew)
    draw_text(cv, s, x0, y, scale, color, skew)


def png_bytes(rgb, w, h):
    raw = b''.join(b'\x00' + bytes(rgb[y * w * 3:(y + 1) * w * 3])
                   for y in range(h))

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data +
                struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) +
            chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def lcg(state):
    return (state * 1103515245 + 12345) & 0x7fffffff


def draw_background(cv):
    """Night stadium: navy-to-crimson gradient, floodlight beams,
    gold burst rays from behind the ticket, crowd along the bottom."""
    for y in range(H):
        if y < 560:
            t = y / 560.0
            c = tuple(round(SKY_TOP[i] + (SKY_MID[i] - SKY_TOP[i]) * t)
                      for i in range(3))
        else:
            t = (y - 560) / 464.0
            c = tuple(round(SKY_MID[i] + (SKY_LOW[i] - SKY_MID[i]) * t)
                      for i in range(3))
        o = y * W * 3
        cv.px[o:o + W * 3] = bytes(c) * W

    # floodlight beams from the top corners, soft translucent wedges
    cv.blend_poly([(0, 0), (330, 0), (700, 1024), (300, 1024)],
                  BEAM, 0.10)
    cv.blend_poly([(1024, 0), (694, 0), (330, 1024), (724, 1024)],
                  BEAM, 0.10)
    cv.blend_poly([(0, 0), (150, 0), (560, 1024), (380, 1024)],
                  BEAM, 0.07)
    cv.blend_poly([(1024, 0), (874, 0), (470, 1024), (650, 1024)],
                  BEAM, 0.07)

    # gold burst rays radiating from the ticket centre (512, 560)
    cx, cy = 512, 560
    for k in range(24):
        a = math.radians(k * 15.0 + 7.5)
        a2 = math.radians(k * 15.0 + 11.0)
        far = 780
        col = GOLD if k % 2 == 0 else GOLD_PALE
        cv.blend_poly(
            [(cx, cy),
             (cx + int(760 * math.cos(a)), cy + int(760 * math.sin(a))),
             (cx + int(760 * math.cos(a2)), cy + int(760 * math.sin(a2)))],
            col, 0.10 if k % 2 == 0 else 0.06)

    # stadium light dots, two rows of tiny floodlights
    for x in range(60, 1024, 88):
        cv.disc(x, 46, 7, GOLD_PALE)
        cv.disc(x, 46, 3, WHITE)
    for x in range(104, 1024, 88):
        cv.disc(x, 92, 5, GOLD)
        cv.disc(x, 92, 2, WHITE)

    # crowd: dark heads + raised arms along the bottom
    state = 20240
    for x in range(-20, 1060, 34):
        state = lcg(state)
        r = 20 + state % 14
        cv.disc(x, 1024 - 8, r + 14, CROWD)
        cv.disc(x, 1000 - r, r, CROWD)
    for x in range(10, 1020, 52):
        state = lcg(state)
        arm = 30 + state % 26
        cv.line(x, 1000, x - 12, 1000 - arm, CROWD, 7)
        cv.line(x + 26, 1002, x + 38, 1002 - arm, CROWD, 7)

    # confetti: fixed-seed deterministic pieces over the whole scene
    confetti = (GOLD, GOLD_PALE, RED_BRIGHT, WHITE, (120, 180, 255),
                GOLD_DEEP)
    state = 987654321
    for _ in range(260):
        state = lcg(state)
        x = 20 + state % 984
        state = lcg(state)
        y = 20 + state % 984
        state = lcg(state)
        size = 5 + state % 9
        state = lcg(state)
        col = confetti[state % len(confetti)]
        state = lcg(state)
        kind = state % 3
        if kind == 0:
            cv.fill_rect(x, y, size, size // 2 + 2, col)
        elif kind == 1:
            cv.poly([(x, y - size // 2), (x + size // 2, y),
                     (x, y + size // 2), (x - size // 2, y)], col)
        else:
            cv.line(x - size // 2, y, x + size // 2, y, col, 3)
            cv.line(x, y - size // 2, x, y + size // 2, col, 3)
    # a few big sparkles
    for sx, sy, sr in ((150, 210, 26), (880, 180, 30), (920, 830, 24),
                       (110, 800, 22), (880, 262, 20)):
        cv.star(sx, sy, sr, GOLD_PALE)
        cv.star(sx, sy, sr // 2, WHITE)


def draw_text_slope(cv, s, x, y, scale, color, slope, skew=0):
    """Text following a slope: each glyph drops by slope per pixel of x."""
    x0 = x
    for ch in s:
        glyph = FONT.get(ch)
        gy = y + int(slope * (x - x0))
        if glyph:
            for r, line in enumerate(glyph):
                for c, bit in enumerate(line):
                    if bit == '#':
                        cv.fill_rect(x + c * scale + r * skew,
                                     gy + r * scale, scale, scale, color)
        x += 6 * scale


def ticket_point(u, v):
    """Ticket-local (u right, v down) -> screen coords; top edge slopes
    gently down to the right, giving the whole stub a dynamic tilt."""
    return (150 + u, int(400 - 0.096 * u + v))


def draw_ticket(cv):
    # red outer edge, then cream face, slightly inset
    outer = [ticket_point(u, v) for u, v in
             ((-8, -8), (738, -8), (738, 398), (-8, 398))]
    cv.poly(outer, RED_DARK)
    face = [ticket_point(u, v) for u, v in
            ((0, 0), (730, 0), (730, 390), (0, 390))]
    cv.poly(face, CREAM)
    # inner gold frame
    frame = [ticket_point(u, v) for u, v in
             ((14, 14), (716, 14), (716, 376), (14, 376))]
    for i in range(4):
        x0, y0 = frame[i]
        x1, y1 = frame[(i + 1) % 4]
        cv.line(x0, y0, x1, y1, GOLD_DEEP, 3)
    # punched notches on the left and right edges
    nx, ny = ticket_point(0, 195)
    cv.disc(nx, ny, 16, SKY_MID)
    nx, ny = ticket_point(730, 195)
    cv.disc(nx, ny, 16, SKY_MID)
    # crease lines: the stub has been folded in a pocket all night
    for (u0, v0, u1, v1) in ((90, 0, 190, 390), (620, 0, 560, 390)):
        a = ticket_point(u0, v0)
        b = ticket_point(u1, v1)
        cv.line(a[0], a[1], b[0], b[1], CREAM_DARK, 3)
    # perforation between the main ticket and the stub
    for k in range(26):
        v = 8 + k * 15
        a = ticket_point(500, v)
        b = ticket_point(500, v + 8)
        cv.line(a[0], a[1], b[0], b[1], RED_DARK, 3)

    slope = -0.096
    # --- left section: the match --------------------------------------
    x, y = ticket_point(40, 42)
    draw_text_slope(cv, "THE FINAL", x, y, 4, RED, slope)
    x, y = ticket_point(40, 108)
    draw_text_slope(cv, "EAGLES", x, y, 5, INK, slope)
    x, y = ticket_point(40, 168)
    draw_text_slope(cv, "VS", x, y, 4, RED, slope)
    x, y = ticket_point(150, 168)
    draw_text_slope(cv, "WOLVES", x, y, 5, INK, slope)
    # gold band: extra time
    band = [ticket_point(u, v) for u, v in
            ((40, 238), (470, 238), (470, 288), (40, 288))]
    cv.poly(band, GOLD)
    x, y = ticket_point(52, 248)
    draw_text_slope(cv, "EXTRA TIME", x, y, 3, INK, slope)
    x, y = ticket_point(40, 312)
    draw_text_slope(cv, "ADMIT ONE", x, y, 3, RED_DARK, slope)
    x, y = ticket_point(300, 312)
    draw_text_slope(cv, "SAT 15 NOV", x, y, 3, INK, slope)
    x, y = ticket_point(40, 348)
    draw_text_slope(cv, "ROW 7 - SEAT 12", x, y, 2, INK, slope)

    # --- right stub: the score, huge ------------------------------------
    x, y = ticket_point(528, 96)
    draw_text_slope(cv, "3-2", x, y, 11, RED, slope)
    x, y = ticket_point(528, 200)
    draw_text_slope(cv, "WINNERS", x, y, 3, INK, slope)
    # barcode stripes along the stub bottom
    state = 555
    bx = 528
    while bx < 700:
        state = lcg(state)
        wdt = 3 + state % 6
        a = ticket_point(bx, 300)
        b = ticket_point(bx, 360)
        cv.line(a[0], a[1], b[0], b[1], INK, wdt)
        bx += wdt + 4 + state % 5
    # tape holding the stub's top corner
    tape = [ticket_point(u, v) for u, v in
            ((640, -16), (730, -16), (730, 22), (640, 22))]
    cv.poly(tape, TAPE)


def draw_note(cv):
    """The supporter's handwritten note, torn paper strip across the
    ticket's lower half, blue ink with a red underline swash."""
    strip = [(90, 800), (950, 730), (950, 852), (90, 922)]
    cv.poly(strip, (255, 250, 235))
    cv.line(90, 800, 950, 730, RED, 4)
    cv.line(950, 852, 90, 922, RED, 4)
    # torn left edge: small zigzag
    for k in range(6):
        y0 = 800 + k * 20
        cv.line(90, y0, 98, y0 + 10, (255, 250, 235), 6)
    slope = -0.081
    draw_text_slope(cv, "WE DID IT!!!", 150, 806, 5, BLUE_INK, slope, skew=1)
    draw_text_slope(cv, "3-2 IN EXTRA TIME", 150, 862, 4, BLUE_INK, slope,
                    skew=1)
    # red underline swash under the second line
    cv.line(150, 902, 500, 874, RED_BRIGHT, 5)
    cv.line(500, 874, 545, 864, RED_BRIGHT, 5)
    # a small gold star the fan drew next to the note
    cv.star(880, 796, 22, GOLD_DEEP)
    cv.star(880, 796, 12, GOLD)


def main():
    cv = Canvas(W, H)
    draw_background(cv)
    draw_ticket(cv)
    draw_note(cv)

    # headline: huge gold letters with a dark-red outline
    draw_text_outline(cv, "THE NIGHT WE WON", 512, 108, 7, GOLD, RED_DARK)
    draw_text_c(cv, "ONE TICKET. ONE NIGHT. FOREVER.", 512, 196, 2,
                GOLD_PALE)

    # foreground confetti: a few pieces land on top of everything
    confetti = (GOLD, GOLD_PALE, RED_BRIGHT, WHITE, (120, 180, 255))
    state = 31415926
    for _ in range(90):
        state = lcg(state)
        x = 10 + state % 1004
        state = lcg(state)
        y = 10 + state % 1004
        state = lcg(state)
        size = 5 + state % 8
        state = lcg(state)
        col = confetti[state % len(confetti)]
        state = lcg(state)
        if state % 2 == 0:
            cv.fill_rect(x, y, size, size // 2 + 2, col)
        else:
            cv.poly([(x, y - size // 2), (x + size // 2, y),
                     (x, y + size // 2), (x - size // 2, y)], col)

    out_dir = os.environ.get('MAKEFUN_OUTPUT_DIR')
    if not out_dir:
        out_dir = '/output' if os.path.isdir('/output') else '.'
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, 'entry.png')
    data = png_bytes(cv.px, W, H)
    with open(out, 'wb') as f:
        f.write(data)
    print("wrote", out, len(data), "bytes")


if __name__ == '__main__':
    main()
