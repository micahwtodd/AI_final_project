"""Generate the pixel art in code and render a contact sheet for review (dev-only; needs Pillow).

Run from the repo folder:  python scripts/render_sprites.py
Writes frontend/src/sprites/sprites.json (palette + palette-index grids) and
evidence/sprites_contact_sheet.png (every sprite at 8x).

Art rules (build plan 11.1): one fixed 16-color palette, 1-pixel dark outline,
light from the top left, the same proportions for the whole cast.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PALETTE = [
    "#00000000",  # 0 transparent
    "#1b1f3b",    # 1 outline
    "#f2f2f2",    # 2 white
    "#f2c9a0",    # 3 skin light
    "#d6a06c",    # 4 skin tan
    "#a8693f",    # 5 skin brown
    "#6e4326",    # 6 skin deep
    "#2a2a33",    # 7 hair black
    "#c9ccd6",    # 8 silver
    "#1f8a5b",    # 9 emerald
    "#12613f",    # 10 emerald dark
    "#007ac1",    # 11 Prudential blue
    "#0b2a5c",    # 12 navy
    "#537d93",    # 13 steel
    "#e2a400",    # 14 gold
    "#c8504a",    # 15 red
]
SHADE = {2: 8, 3: 4, 4: 5, 5: 6, 6: 7, 7: 1, 8: 13, 9: 10, 10: 1, 11: 12, 12: 1, 13: 12, 14: 5, 15: 6}
LIGHT = {4: 3, 5: 4, 6: 5, 9: 9, 11: 11, 13: 8}


class Canvas:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.px = [[0] * w for _ in range(h)]

    def set(self, x: int, y: int, c: int) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def get(self, x: int, y: int) -> int:
        return self.px[y][x] if 0 <= x < self.w and 0 <= y < self.h else 0

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set(x, y, c)

    def ellipse(self, cx, cy, rx, ry, c, only_empty=False):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    if not only_empty or self.get(x, y) == 0:
                        self.set(x, y, c)

    def outline(self, color: int = 1) -> None:
        """1-pixel dark outline around every shape."""
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.px[y][x] == 0 and any(self.get(x + dx, y + dy) not in (0, color)
                                              for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    add.append((x, y))
        for x, y in add:
            self.px[y][x] = color

    def rows(self) -> list[str]:
        return ["".join("0123456789abcdef"[c] for c in row) for row in self.px]


# ---------------------------------------------------------------- portraits (64 x 64)

CX, CY, RX, RY = 32, 28, 12, 14

CAST = {
    "amara": {"skin": 5, "hair": "locs", "hair_c": 8, "top": "blazer", "top_c": 9, "inner": 2, "glasses": False, "age": "older"},
    "walt": {"skin": 3, "hair": "balding", "hair_c": 8, "top": "cardigan", "top_c": 13, "inner": 2, "glasses": True, "age": "older"},
    "priya": {"skin": 4, "hair": "ponytail", "hair_c": 7, "top": "jacket", "top_c": 11, "inner": 2, "glasses": False, "age": "mid"},
    "teo": {"skin": 4, "hair": "spiky", "hair_c": 7, "top": "hoodie", "top_c": 12, "inner": 14, "glasses": False, "headset": True, "age": "young"},
    "sam": {"skin": 3, "hair": "bob", "hair_c": 7, "top": "blazer", "top_c": 13, "inner": 2, "glasses": True, "age": "mid"},
}


def torso(c: Canvas, p: dict) -> None:
    top, inner = p["top_c"], p["inner"]
    for y in range(45, 64):
        half = 11 + (y - 45) * 0.75
        for x in range(int(CX - half), int(CX + half) + 1):
            c.set(x, y, top)
    for y in range(40, 47):  # neck
        for x in range(28, 37):
            c.set(x, y, p["skin"] if y < 45 else top)
    for x in range(29, 36):  # one row of shade under the chin
        c.set(x, 43, SHADE[p["skin"]])
    if p["top"] in ("blazer", "cardigan"):  # V opening with shirt
        for y in range(45, 64):
            w = max(0, 6 - (y - 45) // 3)
            for x in range(CX - w, CX + w + 1):
                c.set(x, y, inner)
        for y in range(45, 64):  # lapel edges
            w = max(0, 6 - (y - 45) // 3)
            c.set(CX - w - 1, y, SHADE[top])
            c.set(CX + w + 1, y, SHADE[top])
        if p["top"] == "cardigan":
            for y in (52, 57, 62):
                c.set(CX + 3, y, 14)
    elif p["top"] == "jacket":
        for y in range(45, 64):
            c.set(CX, y, 2)  # zipper
        for x in range(CX - 5, CX + 6):
            c.set(x, 45, 2)  # collar
    elif p["top"] == "hoodie":
        for x in range(CX - 9, CX + 10):
            c.set(x, 45, SHADE[top])
        for y in range(46, 56):  # drawstrings
            c.set(CX - 3, y, inner)
            c.set(CX + 3, y, inner)
    for y in range(47, 64):  # shading on the right (light from the top left)
        half = 11 + (y - 45) * 0.75
        for x in range(int(CX + half * 0.8), int(CX + half) + 1):
            if c.get(x, y) == top:
                c.set(x, y, SHADE[top])


def head(c: Canvas, p: dict) -> None:
    s = p["skin"]
    c.ellipse(CX - 13, 29, 2, 3, s)  # ears
    c.ellipse(CX + 13, 29, 2, 3, s)
    c.ellipse(CX, CY, RX, RY, s)
    for y in range(CY - RY, CY + RY + 1):  # shade the lower right of the face
        for x in range(CX - RX, CX + RX + 1):
            if c.get(x, y) == s and (((x - CX) / RX > 0.68 and y > CY - 6) or ((y - CY) / RY > 0.82 and x > CX - 2)):
                c.set(x, y, SHADE[s])
    c.set(CX + 13, 29, SHADE[s])


def hairline(c: Canvas, p: dict, drop: int = 0) -> None:
    """Re-open the face below a gentle hairline so hair never covers the brows."""
    s = p["skin"]
    for x in range(CX - RX + 2, CX + RX - 1):
        top = int(CY - 8 + drop + ((x - CX) / RX) ** 2 * 5)
        for y in range(top, CY + RY):
            if ((x - CX) / (RX - 0.5)) ** 2 + ((y - CY) / (RY - 0.5)) ** 2 <= 1:
                if c.get(x, y) not in (s, SHADE[s]):
                    c.set(x, y, SHADE[s] if (x - CX) / RX > 0.68 else s)


def hair(c: Canvas, p: dict) -> None:
    h, style = p["hair_c"], p["hair"]
    hs = SHADE[h]
    if style == "locs":
        c.ellipse(CX, CY - 6, RX + 3, RY - 3, h)
        for x in range(CX - RX - 4, CX + RX + 5):  # hanging locs on a solid backing
            if abs(x - CX) <= RX - 3:
                continue
            for y in range(CY - 8, 50 - (abs(x - CX) > RX + 2) * 2):
                c.set(x, y, h if x % 2 == 0 else hs)
        for x in range(CX - RX - 1, CX + RX + 2, 3):  # continuous strands on top
            for y in range(CY - RY - 2, CY - 7):
                if c.get(x, y) == h:
                    c.set(x, y, hs)
        for y in range(CY + 8, 46):  # fill behind the locs beside the neck
            for x in list(range(CX - RX - 4, CX - 4)) + list(range(CX + 5, CX + RX + 5)):
                if c.get(x, y) == 0:
                    c.set(x, y, hs)
        hairline(c, p, drop=1)
    elif style == "balding":
        for side in (-1, 1):
            for y in range(CY - 6, CY + 5):
                for dx in range(0, 3):
                    c.set(CX + side * (RX - dx), y, h if dx else hs)
        for x in range(CX - 5, CX + 6, 2):  # a few wisps on top
            c.set(x, CY - RY, h)
    elif style == "ponytail":
        c.ellipse(CX, CY - 7, RX + 1, RY - 5, h)
        for y in range(CY - 13, CY - 4):  # center part
            c.set(CX, y, hs)
        for y in range(CY - 6, CY + 14):  # ponytail behind the right side
            for x in range(CX + RX - 1, CX + RX + 4):
                if c.get(x, y) in (0, p["skin"], SHADE[p["skin"]]) and abs(x - (CX + RX + 1)) <= 2 - (y > CY + 10):
                    c.set(x, y, h if x < CX + RX + 2 else hs)
        hairline(c, p)
    elif style == "spiky":
        c.ellipse(CX, CY - 8, RX + 1, RY - 6, h)
        for x0 in (CX - 8, CX - 3, CX + 2, CX + 7):  # four tufts leaning right
            for k in range(4):
                c.set(x0 + k // 2, CY - RY - 1 - k, h)
                c.set(x0 + 1 + k // 2, CY - RY - 1 - k, h if k < 3 else hs)
        hairline(c, p)
    elif style == "bob":
        c.ellipse(CX, CY - 4, RX + 2, RY - 1, h)
        for y in range(CY - 4, CY + 9):  # sides down to the jaw
            for x in list(range(CX - RX - 2, CX - RX + 2)) + list(range(CX + RX - 1, CX + RX + 3)):
                c.set(x, y, h if x < CX else hs)
        hairline(c, p)
        for x in range(CX - 10, CX + 2):  # side-swept fringe
            for y in range(CY - 6, CY - 6 + max(1, (x - (CX - 10)) // 4)):
                c.set(x, y, h)
    for y in range(CY - RY - 4, CY + 2):  # hair highlight on the top left
        for x in range(CX - RX - 4, CX):
            if h != 7 and c.get(x, y) == h and c.get(x + 1, y + 1) == h and (x + y) % 6 == 0 and y < CY - 9:
                c.set(x, y, 2)


def face(c: Canvas, p: dict, mood: str) -> None:
    s = p["skin"]
    ey = CY + 1
    dark = 1
    for ex in (CX - 5, CX + 4):  # eyes 2x2 with a white highlight
        c.rect(ex, ey, ex + 1, ey + 1, dark)
        c.set(ex, ey, 2)
    by = ey - 3
    if mood == "concerned":  # inner ends raised
        brows = [(CX - 7, by + 1), (CX - 6, by + 1), (CX - 5, by), (CX - 4, by - 1),
                 (CX + 3, by - 1), (CX + 4, by), (CX + 5, by + 1), (CX + 6, by + 1)]
    elif mood == "pleased":
        brows = [(CX - 7, by), (CX - 6, by - 1), (CX - 5, by - 1), (CX - 4, by),
                 (CX + 3, by), (CX + 4, by - 1), (CX + 5, by - 1), (CX + 6, by)]
    else:
        brows = [(CX - 7, by), (CX - 6, by), (CX - 5, by), (CX - 4, by),
                 (CX + 3, by), (CX + 4, by), (CX + 5, by), (CX + 6, by)]
    bc = 1 if p["hair_c"] == 7 or s >= 5 else 13
    for x, y in brows:
        c.set(x, y, bc)
    c.set(CX + 1, ey + 3, SHADE[s])  # nose
    c.set(CX + 1, ey + 4, SHADE[s])
    c.set(CX, ey + 5, SHADE[s])
    my = ey + 8
    if mood == "pleased":
        mouth = [(CX - 4, my - 1), (CX - 3, my), (CX - 2, my), (CX - 1, my), (CX, my), (CX + 1, my), (CX + 2, my), (CX + 3, my - 1)]
        for x in range(CX - 2, CX + 2):
            c.set(x, my - 1, 2)  # teeth
    elif mood == "concerned":
        mouth = [(CX - 3, my + 1), (CX - 2, my), (CX - 1, my), (CX, my), (CX + 1, my), (CX + 2, my + 1)]
    else:
        mouth = [(CX - 2, my), (CX - 1, my), (CX, my), (CX + 1, my)]
    for x, y in mouth:
        c.set(x, y, 15 if s <= 4 else 1)



def glasses(c: Canvas) -> None:
    ey = CY + 1
    for ex in (CX - 5, CX + 4):
        for x in range(ex - 2, ex + 4):
            c.set(x, ey - 2, 1)
            c.set(x, ey + 3, 1)
        for y in range(ey - 2, ey + 4):
            c.set(ex - 2, y, 1)
            c.set(ex + 3, y, 1)
    c.set(CX, ey, 1)
    c.set(CX - 1, ey, 1)


def headset(c: Canvas) -> None:
    for x in range(CX - RX - 1, CX + RX + 2):  # band over the head
        y = int(CY - RY + 1 + ((x - CX) / (RX + 1)) ** 2 * 9)
        c.set(x, y - 1, 12)
        c.set(x, y, 13)
    for side in (-1, 1):  # ear cups
        c.rect(CX + side * 13 - 2, 26, CX + side * 13 + 2, 32, 12)
        c.rect(CX + side * 13 - 1, 27, CX + side * 13 + 1, 31, 13)
    for i in range(6):  # mic boom from the right cup toward the mouth corner
        c.set(CX + 12 - i, 33 + i // 2, 12)
    c.rect(CX + 5, 36, CX + 6, 37, 1)


def portrait(name: str, mood: str) -> Canvas:
    p = CAST[name]
    c = Canvas(64, 64)
    torso(c, p)
    head(c, p)
    hair(c, p)
    face(c, p, mood)
    if p.get("glasses"):
        glasses(c)
    if p.get("headset"):
        headset(c)
    c.outline()
    return c


# ---------------------------------------------------------------- Convexity the office cat (32 x 32)

def cat(state: str) -> Canvas:
    c = Canvas(32, 32)
    fur, shade = 14, 5
    if state == "nap":
        c.ellipse(16, 24, 11, 5, fur)            # curled body
        c.ellipse(8, 22, 5, 4, fur)              # head
        for x, y in ((5, 17), (6, 16), (6, 17), (10, 17), (11, 16), (11, 17)):  # ears
            c.set(x, y, fur)
        for x in range(13, 27):                   # tail wrapped round
            c.set(x, 28, shade)
        for x in range(10, 24, 4):                # stripes
            c.set(x, 20, shade); c.set(x + 1, 21, shade)
        c.set(6, 22, 1); c.set(7, 22, 1); c.set(9, 22, 1); c.set(10, 22, 1)  # closed eyes
        for x, y in ((20, 8), (21, 8), (22, 8), (21, 9), (20, 10), (21, 10), (22, 10)):  # z
            c.set(x, y, 13)
        for x, y in ((25, 4), (26, 4), (26, 5), (25, 6), (26, 6)):
            c.set(x, y, 13)
    elif state == "alert":
        c.ellipse(16, 23, 7, 7, fur)             # sitting body
        c.ellipse(16, 12, 6, 5, fur)             # head
        for x, y in ((11, 6), (11, 7), (12, 7), (20, 6), (20, 7), (19, 7)):  # ears up
            c.set(x, y, fur)
        for y in range(18, 30):                   # tail up the side
            c.set(24 + (y > 24), y, shade)
        for ex in (13, 18):                       # wide eyes
            c.rect(ex, 11, ex + 1, 12, 2)
            c.set(ex + 1, 12, 1)
        c.set(15, 14, 15); c.set(16, 14, 15)    # nose
        for x in range(13, 20, 3):
            c.set(x, 20, shade)
    else:  # hiding under a desk: only eyes and ears showing
        c.rect(0, 10, 31, 13, 12)                 # desk top
        c.rect(2, 14, 3, 31, 12)                  # legs
        c.rect(28, 14, 29, 31, 12)
        c.ellipse(16, 27, 7, 4, shade)           # cat in the shadow
        for x, y in ((11, 22), (12, 23), (20, 22), (19, 23)):
            c.set(x, y, shade)
        for ex in (13, 18):
            c.rect(ex, 25, ex + 1, 26, 14)        # eyes glowing
            c.set(ex + 1, 26, 1)
    c.outline()
    return c


# ---------------------------------------------------------------- output

def build() -> dict:
    sprites = {}
    for name in CAST:
        for mood in ("neutral", "pleased", "concerned"):
            sprites[f"{name}_{mood}"] = portrait(name, mood).rows()
    for state in ("nap", "alert", "hide"):
        sprites[f"cat_{state}"] = cat(state).rows()
    return {"palette": PALETTE, "sprites": sprites,
            "_note": "Generated by scripts/render_sprites.py. Rows are palette indexes in hex (0 = transparent)."}


def contact_sheet(data: dict, path: Path, scale: int = 8) -> None:
    from PIL import Image, ImageDraw

    pal = [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + ((0,) if len(h) > 7 else (255,)) for h in data["palette"]]
    names = list(data["sprites"])
    cols, cell = 5, 64 * scale + 24
    rows = math.ceil(len(names) / cols)
    sheet = Image.new("RGBA", (cols * cell, rows * (cell + 20)), (243, 246, 250, 255))
    draw = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        grid = data["sprites"][n]
        h, w = len(grid), len(grid[0])
        img = Image.new("RGBA", (w, h))
        img.putdata([pal[int(ch, 16)] for row in grid for ch in row])
        img = img.resize((w * scale, h * scale), Image.NEAREST)
        x, y = (i % cols) * cell + 12, (i // cols) * (cell + 20) + 12
        sheet.alpha_composite(img, (x, y))
        draw.text((x, y + 64 * scale + 2), n, fill=(13, 31, 60, 255))
    sheet.save(path)


def main() -> None:
    data = build()
    out = ROOT / "frontend" / "src" / "sprites"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sprites.json").write_text(json.dumps(data), encoding="utf-8")
    sheet = ROOT / "evidence" / "sprites_contact_sheet.png"
    sheet.parent.mkdir(exist_ok=True)
    contact_sheet(data, sheet)
    print(f"{len(data['sprites'])} sprites -> {out / 'sprites.json'} and {sheet}")


if __name__ == "__main__":
    sys.exit(main())
