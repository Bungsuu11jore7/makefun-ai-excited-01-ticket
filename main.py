#!/usr/bin/env python3
"""The Night We Won — make.fun ai-excited-01 ticket entry.

Pure-stdlib Python 3 renderer. Draws a 1024x1024 night-stadium scene:
a creased final-match ticket stub (EAGLES vs WOLVES, 3-2 in extra time)
under gold confetti, with a supporter's handwritten note across it.

Deterministic: every random choice comes from fixed-seed generators,
so two runs produce byte-identical PNGs. Run with
MAKEFUN_OUTPUT_DIR=out python3 main.py  ->  out/entry.png
"""

import math
import os
import random
import struct
import zlib

W, H = 1024, 1024
OUT_ENV = "MAKEFUN_OUTPUT_DIR"
CLEAR = (255, 0, 255)  # sentinel "transparent" colour for offscreen layers

# ---------------------------------------------------------------- font
# Hand-drawn 5x7 pixel glyphs. '#' = ink, '.' = empty. Written from
# scratch for this entry; only the characters the artwork needs.
GLYPHS = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "...#.", "..#..", "..#..", "..#.."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".....", "..#.."),
    ",": (".....", ".....", ".....", ".....", ".....", "..#..", ".#..."),
    ":": (".....", "..#..", ".....", ".....", ".....", "..#..", "....."),
    "'": ("..#..", "..#..", ".....", ".....", ".....", ".....", "....."),
    "/": ("....#", "...#.", "...#.", "..#..", "..#..", ".#...", "#...."),
    "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    "&": (".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    "=": (".....", ".....", "#####", ".....", "#####", ".....", "....."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
}

GLYPH_W, GLYPH_H = 5, 7


def text_width(s, scale, tracking=1):
    """Pixel width of a string at a given glyph scale."""
    if not s:
        return 0
    return len(s) * (GLYPH_W + tracking) * scale - tracking * scale


# ---------------------------------------------------------------- canvas
class Pix:
    """A plain RGB canvas backed by one bytearray."""

    def __init__(self, w, h, fill=(0, 0, 0)):
        self.w, self.h = w, h
        self.buf = bytearray(w * h * 3)
        for i in range(0, len(self.buf), 3):
            self.buf[i] = fill[0]
            self.buf[i + 1] = fill[1]
            self.buf[i + 2] = fill[2]

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def inside(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def put(self, x, y, col):
        if self.inside(x, y):
            i = self._idx(x, y)
            self.buf[i] = col[0]
            self.buf[i + 1] = col[1]
            self.buf[i + 2] = col[2]

    def blend(self, x, y, col, a):
        """Alpha-blend colour `col` over pixel (x, y); a in 0..1."""
        if not self.inside(x, y) or a <= 0:
            return
        if a >= 1:
            self.put(x, y, col)
            return
        i = self._idx(x, y)
        b = self.buf
        b[i] = int(b[i] + (col[0] - b[i]) * a)
        b[i + 1] = int(b[i + 1] + (col[1] - b[i + 1]) * a)
        b[i + 2] = int(b[i + 2] + (col[2] - b[i + 2]) * a)

    def get(self, x, y):
        if not self.inside(x, y):
            return (0, 0, 0)
        i = self._idx(x, y)
        return (self.buf[i], self.buf[i + 1], self.buf[i + 2])

    def rect(self, x, y, w, h, col, alpha=1.0):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.blend(xx, yy, col, alpha)

    def disc(self, cx, cy, r, col, alpha=1.0):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    self.blend(xx, yy, col, alpha)

    def line(self, x0, y0, x1, y1, col, thick=1, alpha=1.0):
        """Bresenham line with square brush of side `thick`."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        half = thick // 2
        while True:
            for oy in range(-half, half + 1):
                for ox in range(-half, half + 1):
                    self.blend(x0 + ox, y0 + oy, col, alpha)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def poly(self, pts, col, alpha=1.0):
        """Scanline fill of a simple polygon (list of (x, y))."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for yy in range(min(ys), max(ys) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                ax, ay = pts[i]
                bx, by = pts[(i + 1) % n]
                if ay == by:
                    continue
                if (ay <= yy < by) or (by <= yy < ay):
                    t = (yy - ay) / (by - ay)
                    xs.append(ax + t * (bx - ax))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                for xx in range(int(xs[k]), int(xs[k + 1]) + 1):
                    self.blend(xx, yy, col, alpha)

    def star4(self, cx, cy, r, col, alpha=1.0):
        """Four-point sparkle: a tall thin diamond + a wide flat one."""
        self.poly([(cx, cy - r), (cx + r // 4, cy), (cx, cy + r),
                   (cx - r // 4, cy)], col, alpha)
        self.poly([(cx - r, cy), (cx, cy - r // 4), (cx + r, cy),
                   (cx, cy + r // 4)], col, alpha)

    def blit_rotated(self, src, cx, cy, deg):
        """Paste `src` centred at (cx, cy), rotated by `deg` degrees.

        Pixels equal to CLEAR in the source are treated as transparent.
        Nearest-neighbour sampling; deterministic.
        """
        rad = math.radians(deg)
        co, si = math.cos(rad), math.sin(rad)
        hw, hh = src.w / 2.0, src.h / 2.0
        x0 = int(cx - (abs(hw * co) + abs(hh * si))) - 2
        x1 = int(cx + (abs(hw * co) + abs(hh * si))) + 2
        y0 = int(cy - (abs(hw * si) + abs(hh * co))) - 2
        y1 = int(cy + (abs(hw * si) + abs(hh * co))) + 2
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                dx, dy = xx - cx, yy - cy
                sx = int(dx * co + dy * si + hw)
                sy = int(-dx * si + dy * co + hh)
                if 0 <= sx < src.w and 0 <= sy < src.h:
                    col = src.get(sx, sy)
                    if col != CLEAR:
                        self.put(xx, yy, col)


def draw_text(cv, x, y, s, scale, col, shear=0, wobble=None, tracking=1):
    """Draw a string with the 5x7 glyphs.

    shear shifts each glyph row sideways (italic slant); wobble is an
    optional list of per-character vertical offsets (handwritten feel).
    """
    cx = x
    for ci, ch in enumerate(s):
        rows = GLYPHS.get(ch.upper(), GLYPHS[" "])
        dy = 0
        if wobble:
            dy = wobble[ci % len(wobble)]
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit == "#":
                    bx = cx + rx * scale + int(shear * (GLYPH_H - ry))
                    by = y + ry * scale + dy
                    cv.rect(bx, by, scale, scale, col)
        cx += (GLYPH_W + tracking) * scale


# ---------------------------------------------------------------- PNG out
def _chunk(kind, payload):
    out = struct.pack(">I", len(payload)) + kind + payload
    out += struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    return out


def encode_png(cv):
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.buf[y * stride:(y + 1) * stride]
    idat = zlib.compress(bytes(raw), 9)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


# ---------------------------------------------------------------- palette
NAVY = (24, 24, 64)
SKY_TOP = (13, 12, 44)
SKY_MID = (52, 24, 76)
SKY_LOW = (96, 32, 66)
GOLD = (255, 198, 66)
GOLD_DEEP = (232, 168, 32)
RED = (178, 26, 38)
RED_DARK = (140, 18, 30)
CREAM = (250, 240, 205)
CREAM_NOTE = (253, 245, 216)
INK_BLUE = (38, 68, 180)
WHITE = (245, 245, 240)
DARK = (10, 10, 26)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------- backdrop
def paint_sky(cv, rng):
    """Night gradient, stars, floodlight beams and glowing towers."""
    for y in range(H):
        t = y / (H - 1)
        if t < 0.62:
            col = _lerp(SKY_TOP, SKY_MID, t / 0.62)
        else:
            col = _lerp(SKY_MID, SKY_LOW, (t - 0.62) / 0.38)
        cv.rect(0, y, W, 1, col)
    # stars
    for _ in range(150):
        x = rng.randrange(0, W)
        y = rng.randrange(0, 420)
        r = rng.choice([1, 1, 1, 2])
        cv.disc(x, y, r, WHITE, alpha=rng.choice([0.35, 0.55, 0.8]))
    # floodlight beams fanning down from the top corners
    for bx, spread in ((170, 260), (854, 260)):
        for k in range(3):
            off = (k - 1) * 90
            cv.poly([(bx + off, 0), (bx + off + 60, 0),
                     (bx + off + spread, H), (bx + off + spread - 170, H)],
                    (255, 244, 200), alpha=0.045)
    # floodlight towers: halo + bright lamp grid (kept clear of headline)
    for tx, ty in ((64, 215), (960, 215)):
        cv.disc(tx, ty, 62, (255, 240, 180), alpha=0.10)
        cv.disc(tx, ty, 30, (255, 246, 210), alpha=0.22)
        for gy in range(ty - 14, ty + 16, 10):
            for gx in range(tx - 22, tx + 23, 11):
                cv.disc(gx, gy, 4, (255, 252, 230))


def paint_stands(cv, rng):
    """Tiered stands with pinprick crowd lights, then a front-row mass."""
    for band_y, hgt, shade in ((640, 70, (26, 20, 52)),
                               (712, 80, (20, 15, 42)),
                               (794, 90, (15, 11, 34))):
        cv.rect(0, band_y, W, hgt, shade)
        cv.line(0, band_y, W, band_y, (70, 60, 110), thick=2, alpha=0.7)
        for _ in range(260):
            x = rng.randrange(0, W)
            y = rng.randrange(band_y + 8, band_y + hgt - 6)
            cv.disc(x, y, 1, rng.choice([GOLD, WHITE, (150, 180, 255),
                                          (255, 120, 120)]),
                    alpha=rng.choice([0.4, 0.6, 0.9]))
    # front-row silhouette: overlapping heads along the bottom edge
    x = -20
    while x < W + 20:
        r = rng.randrange(24, 42)
        cv.disc(x, H + 6, r, DARK)
        x += rng.randrange(28, 48)
    x = 10
    while x < W + 20:
        r = rng.randrange(16, 26)
        cv.disc(x, H - 26, r, (14, 13, 30))
        x += rng.randrange(30, 52)


# ---------------------------------------------------------------- ticket
def make_ticket(rng):
    """The creased final-match stub, drawn flat on its own layer."""
    tw, th = 880, 440
    t = Pix(tw, th, fill=CLEAR)
    t.rect(0, 0, tw, th, CREAM)
    t.rect(4, 4, tw - 8, th - 8, RED)              # outer frame
    t.rect(10, 10, tw - 20, th - 20, CREAM)
    # thin gold inner frame
    t.rect(22, 22, tw - 44, 3, GOLD_DEEP)
    t.rect(22, th - 25, tw - 44, 3, GOLD_DEEP)
    t.rect(22, 22, 3, th - 44, GOLD_DEEP)
    t.rect(tw - 25, 22, 3, th - 44, GOLD_DEEP)
    # header + teams
    draw_text(t, 48, 42, "THE FINAL", 4, RED)
    draw_text(t, 48, 96, "EAGLES", 8, NAVY)
    draw_text(t, 48, 178, "VS", 4, RED)
    draw_text(t, 148, 168, "WOLVES", 8, NAVY)
    # gold extra-time bar
    t.rect(48, 250, 420, 64, GOLD)
    draw_text(t, 138, 268, "EXTRA TIME", 4, NAVY)
    # seat details
    draw_text(t, 48, 336, "ADMIT ONE", 4, RED)
    draw_text(t, 48, 382, "ROW 7 - SEAT 12", 3, NAVY)
    draw_text(t, 408, 382, "SAT 15 NOV", 3, NAVY)
    # perforation between stub and main body
    for y in range(28, th - 24, 14):
        t.rect(640, y, 3, 8, RED_DARK)
    t.disc(640, 14, 9, NAVY)
    t.disc(640, th - 14, 9, NAVY)
    # score stub
    draw_text(t, 668, 82, "3-2", 11, RED)
    draw_text(t, 668, 182, "WINNERS", 4, NAVY)
    # barcode: deterministic bar widths
    bx = 668
    while bx < 856:
        bw = rng.choice([2, 3, 3, 4, 5, 7])
        t.rect(bx, 238, bw, 108, NAVY)
        bx += bw + rng.choice([2, 3, 4, 6])
    draw_text(t, 668, 356, "NO. 0719", 3, NAVY)
    # creases: pale diagonal wear + one hard fold
    t.line(60, 0, 300, th, (190, 170, 120), thick=2, alpha=0.28)
    t.line(700, 0, 520, th, (190, 170, 120), thick=2, alpha=0.22)
    t.line(0, 300, tw, 240, (150, 128, 84), thick=3, alpha=0.20)
    # masking-tape corner, top right
    t.rect(748, 0, 100, 34, (255, 226, 130), alpha=0.55)
    t.line(748, 34, 848, 34, (200, 170, 80), thick=2, alpha=0.5)
    return t


# ---------------------------------------------------------------- note
def make_note():
    """Supporter's handwritten note on a torn paper strip."""
    nw, nh = 920, 170
    n = Pix(nw, nh, fill=CLEAR)
    n.rect(0, 0, nw, nh, CREAM_NOTE)
    n.rect(0, nh - 6, nw, 6, RED)                  # red rule along the foot
    n.rect(0, 0, nw, 3, (210, 190, 140))
    wob1 = [0, -3, 2, -2, 0, 3, -2, 0, 2, -3, 0, 2]
    wob2 = [2, 0, -2, 3, 0, -3, 2, 0, -2, 3, 0, -2, 2, 0, -3, 2, 0]
    draw_text(n, 56, 20, "WE DID IT!!!", 6, INK_BLUE, shear=1, wobble=wob1)
    draw_text(n, 56, 86, "3-2 IN EXTRA TIME", 6, INK_BLUE, shear=1, wobble=wob2)
    # red underline swoosh under the second line
    n.line(56, 148, 690, 140, RED, thick=4, alpha=0.85)
    n.line(60, 156, 520, 150, RED, thick=2, alpha=0.5)
    n.star4(838, 62, 26, GOLD_DEEP)
    n.star4(872, 110, 14, GOLD)
    return n


# ---------------------------------------------------------------- confetti
def scatter_confetti(cv, rng, count):
    """Gold-led confetti: squares, diamonds and plus signs."""
    palette = [GOLD, GOLD, GOLD_DEEP, (255, 90, 90), WHITE,
               (120, 170, 255), (255, 240, 180)]
    for _ in range(count):
        x = rng.randrange(8, W - 8)
        y = rng.randrange(8, H - 8)
        col = rng.choice(palette)
        kind = rng.randrange(3)
        s = rng.randrange(3, 9)
        if kind == 0:
            cv.rect(x - s // 2, y - s // 2, s, s, col)
        elif kind == 1:
            cv.poly([(x, y - s), (x + s // 2, y), (x, y + s),
                     (x - s // 2, y)], col)
        else:
            cv.line(x - s, y, x + s, y, col, thick=2)
            cv.line(x, y - s, x, y + s, col, thick=2)


# ---------------------------------------------------------------- compose
def render():
    rng = random.Random(20261116)
    cv = Pix(W, H, fill=SKY_TOP)
    paint_sky(cv, rng)
    paint_stands(cv, rng)

    # headline with a dark-red drop outline, then gold on top
    head = "THE NIGHT WE WON"
    hx = (W - text_width(head, 9)) // 2
    for ox, oy in ((-4, 0), (4, 0), (0, -4), (0, 4), (-4, -4), (4, 4)):
        draw_text(cv, hx + ox, 62 + oy, head, 9, RED_DARK)
    draw_text(cv, hx, 62, head, 9, GOLD)
    sub = "ONE TICKET. ONE NIGHT. FOREVER."
    draw_text(cv, (W - text_width(sub, 2)) // 2, 152, sub, 2,
              (255, 226, 150))

    scatter_confetti(cv, rng, 240)          # confetti behind the ticket
    cv.blit_rotated(make_ticket(rng), 512, 530, -4)
    cv.blit_rotated(make_note(), 512, 862, 3)
    scatter_confetti(cv, rng, 170)          # confetti raining in front
    cv.star4(150, 210, 34, GOLD)
    cv.star4(886, 268, 26, GOLD)
    cv.star4(120, 700, 20, (255, 240, 180))
    cv.star4(918, 640, 22, GOLD)
    return cv


def main():
    outdir = os.environ.get(OUT_ENV, "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(encode_png(render()))
    print("wrote", path, os.path.getsize(path), "bytes")


if __name__ == "__main__":
    main()
