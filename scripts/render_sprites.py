"""Generate the game's pixel art in code and render a contact sheet for review (dev-only; needs Pillow).

Run from the repo folder:  python scripts/render_sprites.py
Writes frontend/public/art/*.png (portraits 64x64, cat 48x48, office backgrounds 480x270)
and evidence/sprites_contact_sheet.png plus evidence/office_backgrounds.png.

Style rules: light from the top left; every material has a five-step color ramp (deep shadow, shadow,
base, light, highlight); outlines are the darkest step of the material they wrap, never pure black;
portraits sit in a round badge with sky and a city skyline, like a character select screen.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "art"
EVIDENCE = ROOT / "evidence"


def hx(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def ramp(*cols: str) -> list[tuple[int, int, int]]:
    return [hx(c) for c in cols]


def mix(a, b, t: float):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------- material ramps (deep shadow -> highlight)

R = {
    "skin_deep": ramp("#3b2219", "#5c3523", "#7d4a2f", "#9a6040", "#b57a55"),
    "skin_light": ramp("#6b4434", "#b77c64", "#d99c80", "#f0bfa0", "#fbd8bf"),
    "skin_tan": ramp("#5e3a26", "#a0663f", "#c48455", "#dca26f", "#efc093"),
    "skin_warm": ramp("#4a2c1c", "#7f4c2e", "#a4673f", "#c08352", "#d9a06d"),
    "skin_fair": ramp("#6b4434", "#c08a6c", "#e0a888", "#f3c8a8", "#fde0c8"),
    "hair_silver": ramp("#3e4452", "#6f7787", "#a4abb9", "#cfd4de", "#f0f2f6"),
    "hair_grey": ramp("#4a4d55", "#7c808a", "#a9adb6", "#cfd2d9", "#eceef2"),
    "hair_blueblack": ramp("#141626", "#22263d", "#323a5c", "#46548a", "#6a7fc0"),
    "hair_black": ramp("#15120f", "#2a221c", "#3d3129", "#55463a", "#7a6656"),
    "hair_plum": ramp("#120f16", "#241d2b", "#362c40", "#4c3f5a", "#6e5d82"),
    "emerald": ramp("#0b3b28", "#11583b", "#1a774f", "#239866", "#3cb882"),
    "steel": ramp("#1f2f3a", "#34505f", "#4a6c7f", "#62889c", "#86a9bb"),
    "pru_blue": ramp("#06264a", "#0a3d72", "#0b5aa0", "#007ac1", "#3aa0dc"),
    "navy": ramp("#060f24", "#0d1b3d", "#14295a", "#1f3a78", "#34529a"),
    "slate": ramp("#232a36", "#394456", "#4f5d74", "#687896", "#8a9ab6"),
    "shirt": ramp("#8f9aa8", "#b9c2cd", "#dce2e9", "#f3f6f9", "#ffffff"),
    "gold": ramp("#6b4a00", "#a87400", "#d49b10", "#f2c230", "#ffe27a"),
    "headset": ramp("#0e1420", "#1d2738", "#2f3d55", "#46597a", "#6f86ab"),
    "tie": ramp("#3a0d14", "#6b1624", "#962033", "#b8304a", "#d65a70"),
    "orange": ramp("#5a2a0a", "#9c4f17", "#cf7a2a", "#ef9f45", "#ffc77e"),
    "white_fur": ramp("#7d828c", "#bfc4cc", "#e1e4ea", "#f4f5f8", "#ffffff"),
    "desk": ramp("#0a1326", "#13213f", "#1d3160", "#2a4480", "#3d5ca3"),
}
INK = hx("#1b1f3b")
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
WHITE = hx("#ffffff")
EYE_WHITE = hx("#f4f1ea")


# ---------------------------------------------------------------- shape helpers (pixel sets)

def ellipse(cx, cy, rx, ry) -> set:
    out = set()
    for y in range(math.floor(cy - ry) - 1, math.ceil(cy + ry) + 2):
        for x in range(math.floor(cx - rx) - 1, math.ceil(cx + rx) + 2):
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1:
                out.add((x, y))
    return out


def poly(points) -> set:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    out = set()
    for y in range(math.floor(min(ys)), math.ceil(max(ys)) + 1):
        for x in range(math.floor(min(xs)), math.ceil(max(xs)) + 1):
            px, py = x + 0.5, y + 0.5
            inside = False
            j = len(points) - 1
            for i in range(len(points)):
                xi, yi = points[i]
                xj, yj = points[j]
                if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi:
                    inside = not inside
                j = i
            if inside:
                out.add((x, y))
    return out


def rect(x0, y0, x1, y1) -> set:
    return {(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}


# ---------------------------------------------------------------- the sprite builder

class Sprite:
    """Regions are painted in order (later covers earlier), shaded by edge-bevel with light from the top left,
    then details are drawn on top and a colored outline wraps the silhouette."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.owner: dict[tuple[int, int], str] = {}
        self.ramps: dict[str, list] = {}
        self.opts: dict[str, dict] = {}
        self.detail: dict[tuple[int, int], tuple] = {}
        self.tone_override: dict[tuple[int, int], int] = {}

    def region(self, name: str, pts: set, rmp: list, **opts) -> None:
        self.ramps[name] = rmp
        self.opts[name] = opts
        for p in pts:
            if 0 <= p[0] < self.w and 0 <= p[1] < self.h:
                self.owner[p] = name
                self.tone_override.pop(p, None)

    def px(self, x: int, y: int, col) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.detail[(x, y)] = col

    def tone(self, x: int, y: int, t: int) -> None:
        self.tone_override[(x, y)] = t

    def pts_of(self, name: str) -> set:
        return {p for p, r in self.owner.items() if r == name}

    def render(self, bg=None, outline=True, clip=None) -> Image.Image:
        img = bg.copy() if bg is not None else Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        pix = img.load()
        boxes: dict[str, tuple] = {}
        for (x, y), r in self.owner.items():
            b = boxes.get(r, (x, y, x, y))
            boxes[r] = (min(b[0], x), min(b[1], y), max(b[2], x), max(b[3], y))

        def same(p, r):
            return self.owner.get(p) == r

        for (x, y), r in self.owner.items():
            o = self.opts[r]
            t = 3
            if not same((x + 1, y), r) or not same((x, y + 1), r):
                t = 2
            elif o.get("hl", True) and (not same((x - 1, y), r) or not same((x, y - 1), r)):
                t = 4
            bx0, by0, bx1, by1 = boxes[r]
            wfrac = (x - bx0) / max(1, bx1 - bx0)
            if wfrac > o.get("shade_right", 0.78):
                t = min(t, 2)
            if o.get("deep_right") and wfrac > o["deep_right"]:
                t = min(t, 1)
            t = self.tone_override.get((x, y), t)
            pix[x, y] = (*self.ramps[r][t], 255)
        for (x, y), col in self.detail.items():
            pix[x, y] = (*col, 255)
        if outline:
            inside = set(self.owner) | set(self.detail)
            for (x, y) in list(self.owner):
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    q = (x + dx, y + dy)
                    if q in inside:
                        continue
                    if clip is not None and not clip(*q):
                        continue  # the badge edge crops the figure: no outline there
                    pix[x, y] = (*self.ramps[self.owner[(x, y)]][0], 255)
                    break
        if clip is not None:  # crop to the badge
            for y in range(self.h):
                for x in range(self.w):
                    if not clip(x, y) and (x, y) in self.owner and bg is not None:
                        pix[x, y] = bg.getpixel((x, y))
        return img


# ---------------------------------------------------------------- portrait badge background

def badge_bg(size: int = 64) -> Image.Image:
    """Round badge: sky, a few clouds, a pale city skyline, a glass tower; transparent outside the circle."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    p = img.load()
    c = (size - 1) / 2
    rnd = random.Random(7)
    sky_top, sky_bot = hx("#7fc0ec"), hx("#d8effb")
    inside = lambda x, y: (x - c) ** 2 + (y - c) ** 2 <= (size / 2 - 0.5) ** 2  # noqa: E731
    for y in range(size):
        for x in range(size):
            if inside(x, y):
                bayer = BAYER[y % 4][x % 4] / 16
                col = mix(sky_top, sky_bot, max(0, min(1, y / size * 1.15 + (bayer - 0.5) * 0.12)))
                p[x, y] = (*col, 255)
    for cx, cy, w in ((14, 12, 9), (46, 8, 7), (54, 19, 5)):
        for (x, y) in ellipse(cx, cy, w, 2.2) | ellipse(cx - w * 0.3, cy - 1.5, w * 0.45, 2):
            if 0 <= x < size and 0 <= y < size and inside(x, y):
                p[x, y] = (*(hx("#e3f2fb") if y > cy else WHITE), 255)
    far, far_win = hx("#a9c4db"), hx("#d3e4f1")
    x = 0
    while x < size:
        w = rnd.randint(4, 8)
        top = rnd.randint(34, 44)
        for xx in range(x, min(size, x + w)):
            for yy in range(top, size):
                if inside(xx, yy):
                    win = (yy - top) % 3 == 1 and (xx - x) % 2 == 1 and xx - x < w - 1
                    p[xx, yy] = (*(far_win if win else far), 255)
        x += w + rnd.randint(0, 2)
    for x0, x1, top, glass in ((45, 53, 24, True), (6, 14, 30, False)):
        for xx in range(x0, x1 + 1):
            for yy in range(top, size):
                if not inside(xx, yy):
                    continue
                if glass:
                    col = hx("#6f9fd4") if (xx - x0) in (1, 2) else mix(hx("#2c4f7c"), hx("#1b3558"), (xx - x0) / 10)
                    if (yy - top) % 4 == 0:
                        col = mix(col, hx("#9cc4ea"), 0.4)
                else:
                    col = hx("#efe3cc") if (xx - x0) % 3 == 0 else hx("#c9b89a")
                    if (yy - top) % 3 == 1 and (xx - x0) % 3 != 0:
                        col = hx("#7d8fa3")
                p[xx, yy] = (*col, 255)
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - c, y - c)
            if size / 2 - 1.5 <= d <= size / 2 - 0.5:
                p[x, y] = (*hx("#f4fbff"), 255)
            elif size / 2 - 2.5 <= d < size / 2 - 1.5:
                p[x, y] = (*hx("#c2d9ea"), 255)
    return img


def in_badge(size: int = 64):
    c = (size - 1) / 2
    return lambda x, y: (x - c) ** 2 + (y - c) ** 2 <= (size / 2 - 2.5) ** 2


# ---------------------------------------------------------------- the human portrait

CX = 31.5  # the face is symmetric about this line (even width)
EYES = {"L": 22, "R": 38}  # left x of each 4-pixel eye
EYE_Y = 28  # the upper lid row
MOUTH_Y = 38


def line_pts(x0, y0, x1, y1) -> list:
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    return [(round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)) for i in range(n + 1)]


def face_pts(top=14, chin=43) -> set:
    pts = set()
    for y in range(top, chin + 1):
        t = y - top
        if t < 3:
            hw = 9.5 + t * 1.2
        elif y <= 32:
            hw = 13
        else:
            hw = 13 - (y - 32) * 0.85
        for x in range(round(CX - hw + 0.5), round(CX + hw - 0.5) + 1):
            pts.add((x, y))
    return pts


def torso_pts(top=47) -> set:
    pts = set()
    for y in range(top, 64):
        t = y - top
        hw = 14 + min(t, 4) * 2.4 + max(0, t - 4) * 0.8
        if t == 0:
            hw -= 3
        for x in range(round(CX - hw + 0.5), round(CX + hw - 0.5) + 1):
            pts.add((x, y))
    return pts


def shade_hair(s: Sprite, names, sheen=None, strands=(), deep_bottom=0.8):
    """Hair: lit on the left, shadowed on the right and at the ends, a sheen band, a few drawn strands."""
    pts = [p for p, r in s.owner.items() if r in names]
    if not pts:
        return
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    for (x, y) in pts:
        fx, fy = (x - x0) / max(1, x1 - x0), (y - y0) / max(1, y1 - y0)
        t = 3 if fx < 0.42 else 2
        if fx > 0.82 or fy > deep_bottom:
            t = min(t, 1 if fx > 0.9 else 2)
        if sheen:
            cx, cy, rx, ry = sheen
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if 0.45 < d < 1.0 and x < cx + rx * 0.4:
                t = 4
        s.tone(x, y, t)
    for a, b in strands:
        for p in line_pts(*a, *b):
            if s.owner.get(p) in names:
                s.tone(*p, 1)


def cast_shadow(s: Sprite, onto=("face",), from_prefix=("hair", "crown", "fringe", "bangs", "locs", "scalp_none")):
    """Hair casts a one-pixel shadow onto the forehead and temples."""
    for (x, y), r in list(s.owner.items()):
        if r in onto:
            above = s.owner.get((x, y - 1), "")
            if any(above.startswith(f) for f in from_prefix):
                s.tone(x, y, 2)
                if s.owner.get((x, y + 1)) in onto and (x, y + 1) not in s.tone_override:
                    s.tone(x, y + 1, 3)


def eyes(s: Sprite, iris, mood: str, lashes=False, skin=None):
    for side, x0 in EYES.items():
        if mood == "pleased":  # smiling eyes: an upward arc with a lash flick
            for dx, dy in ((0, 2), (1, 1), (2, 1), (3, 2)):
                s.px(x0 + dx, EYE_Y + dy, INK)
            if lashes:
                s.px(x0 - 1 if side == "L" else x0 + 4, EYE_Y + 1, INK)
            continue
        for dx in range(4):
            s.px(x0 + dx, EYE_Y, INK)  # upper lid
        s.px(x0, EYE_Y + 1, EYE_WHITE)
        s.px(x0 + 1, EYE_Y + 1, WHITE)  # catch-light
        s.px(x0 + 2, EYE_Y + 1, mix(iris, INK, 0.7))  # pupil
        s.px(x0 + 3, EYE_Y + 1, EYE_WHITE)
        s.px(x0, EYE_Y + 2, EYE_WHITE)
        s.px(x0 + 1, EYE_Y + 2, iris)
        s.px(x0 + 2, EYE_Y + 2, mix(iris, INK, 0.25))
        s.px(x0 + 3, EYE_Y + 2, mix(EYE_WHITE, skin[2] if skin else EYE_WHITE, 0.4))
        if skin:  # soft lower lid
            s.px(x0 + 1, EYE_Y + 3, skin[2])
            s.px(x0 + 2, EYE_Y + 3, skin[2])
        if lashes:
            s.px(x0 - 1 if side == "L" else x0 + 4, EYE_Y - 1, INK)
            s.px(x0 - 1 if side == "L" else x0 + 4, EYE_Y, INK)
        if mood == "concerned":  # worried: a lid line droops at the inner corner
            s.px(x0 + (3 if side == "L" else 0), EYE_Y + 1, mix(INK, EYE_WHITE, 0.5))


def brows(s: Sprite, col, mood: str):
    for side, x0 in EYES.items():
        xs = list(range(x0 - 1, x0 + 4)) if side == "L" else list(range(x0, x0 + 5))
        for i, x in enumerate(xs):
            k = i if side == "L" else 4 - i  # 0 = outer end, 4 = inner end
            if mood == "concerned":
                y = EYE_Y - 2 - (1 if k >= 3 else 0) + (1 if k == 0 else 0)
            elif mood == "pleased":
                y = EYE_Y - 3 + (1 if k in (0, 4) else 0)
            else:
                y = EYE_Y - 2 - (1 if k in (1, 2) else 0)
            s.px(x, y, col)


def nose_mouth(s: Sprite, skin, lip, mood: str, mouth_y=MOUTH_Y):
    s.px(31, 31, skin[4])
    s.px(31, 32, skin[4])
    s.px(33, 32, skin[2])
    s.px(33, 33, skin[1])
    s.px(30, 35, skin[1])
    s.px(31, 35, skin[0])
    s.px(32, 35, skin[1])
    s.px(33, 34, skin[1])
    if mood == "pleased":
        s.px(28, mouth_y - 1, skin[1])
        s.px(35, mouth_y - 1, skin[1])
        for x in range(28, 36):
            s.px(x, mouth_y, INK if x in (28, 35) else WHITE)
        for x in range(29, 35):
            s.px(x, mouth_y + 1, mix(lip, INK, 0.3) if x in (29, 34) else lip)
        for x in range(30, 34):
            s.px(x, mouth_y + 2, skin[1])
        for bx in (19, 20, 43, 44):
            s.px(bx, 34, mix(skin[3], hx("#e8707a"), 0.45))
    elif mood == "concerned":
        for x in range(30, 34):
            s.px(x, mouth_y, mix(lip, INK, 0.55))
        s.px(29, mouth_y + 1, mix(lip, INK, 0.55))
        s.px(34, mouth_y + 1, mix(lip, INK, 0.55))
        for x in range(30, 34):
            s.px(x, mouth_y + 1, lip)
    else:
        for x in range(29, 35):
            s.px(x, mouth_y, mix(lip, INK, 0.45))
        for x in range(30, 34):
            s.px(x, mouth_y + 1, lip)
        s.px(31, mouth_y + 1, mix(lip, WHITE, 0.3))
    s.px(31, mouth_y + 3, skin[2])  # chin dimple shadow
    s.px(32, mouth_y + 3, skin[2])


def sweat(s: Sprite):
    for (x, y), col in {(48, 19): "#bfe6ff", (48, 20): "#8fd0ff", (47, 21): "#8fd0ff", (48, 21): "#5ab4f0",
                        (49, 21): "#8fd0ff", (48, 22): "#5ab4f0"}.items():
        s.px(x, y, hx(col))
    s.px(47, 20, WHITE)


def base_body(s: Sprite, skin, coat, *, shirt=True, lapels=True):
    s.region("torso", torso_pts(), coat, shade_right=0.72)
    if shirt:
        s.region("shirt", poly([(26.5, 46), (36.5, 46), (31.5, 57)]), R["shirt"], shade_right=0.85)
    s.region("neck", rect(27, 39, 36, 48), skin, shade_right=0.8)
    for x in range(27, 37):  # shadow under the jaw
        s.tone(x, 44, 1)
        s.tone(x, 45, 2)
    if lapels:
        for y in range(47, 61):
            for x in (26 + (y - 47) // 2, 37 - (y - 47) // 2):
                if s.owner.get((x, y)) == "torso":
                    s.tone(x, y, 1)
                    if s.owner.get((x - 1, y)) == "torso":
                        s.tone(x - 1, y, 4)
    s.region("face", face_pts(), skin, shade_right=0.88, deep_right=0.985)
    for (x, y) in ((20, 32), (21, 32), (20, 33), (21, 31)):  # cheekbone highlight
        s.tone(x, y, 4)
    for y in range(40, 44):  # jaw shadow
        for x in range(36, 45):
            if s.owner.get((x, y)) == "face":
                s.tone(x, y, 2)
    for side in (-1, 1):  # ears
        cx = CX + side * 13.6
        s.region("ear" + str(side), ellipse(cx, 30, 1.9, 3), skin, shade_right=0.6)
        s.tone(round(cx), 30, 1)
        s.tone(round(cx), 31, 1)


# ---------------------------------------------------------------- the cast

def vera(mood: str) -> Image.Image:
    s = Sprite(64, 64)
    skin, hair = R["skin_deep"], R["hair_silver"]
    base_body(s, skin, R["emerald"])
    # a short silver natural cut: a soft rounded halo with curl texture
    halo = ellipse(CX, 17, 18, 11.5)
    for a in range(0, 360, 20):  # a bumpy, curly edge
        halo |= ellipse(CX + 17.3 * math.cos(math.radians(a)), 17 + 11 * math.sin(math.radians(a)), 2.2, 2.2)
    halo = {p for p in halo if p[1] < 32 and (p[1] <= 18 or not (19 <= p[0] <= 44))}
    s.region("hair", halo, hair, hl=False)
    shade_hair(s, ("hair",), sheen=(26, 12, 14, 6))
    for (x, y) in s.pts_of("hair"):
        lit = s.tone_override.get((x, y), 3) >= 3
        if (x * 3 + y * 5) % 7 == 0:
            s.tone(x, y, 4 if lit else 1)  # curls catching the light
        elif (x * 5 + y * 3) % 9 == 0:
            s.tone(x, y, 2 if lit else 1)
    cast_shadow(s)
    eyes(s, hx("#4a2a18"), mood, lashes=True, skin=skin)
    brows(s, hx("#d5d8e0"), mood)
    nose_mouth(s, skin, hx("#7a3b3b"), mood)
    for x, y, t in ((17, 33, 3), (17, 34, 1), (46, 33, 3), (46, 34, 1)):  # gold earrings
        s.px(x, y, R["gold"][t])
    for i, x in enumerate(range(27, 37)):  # gold necklace
        s.px(x, 48 + (1 if 29 <= x <= 34 else 0), R["gold"][4 if i % 2 else 2])
    s.px(31, 50, R["gold"][4])
    s.px(32, 50, R["gold"][2])
    if mood == "concerned":
        sweat(s)
    return s.render(badge_bg(), clip=in_badge())


def morty(mood: str) -> Image.Image:
    s = Sprite(64, 64)
    skin, hair = R["skin_light"], R["hair_grey"]
    base_body(s, skin, R["steel"])
    s.region("tie", poly([(30, 47), (33, 47), (34.5, 56), (31.5, 59), (28.5, 56)]), R["tie"])
    for y in (51, 55, 59):  # cardigan buttons
        s.px(39, y, R["gold"][3])
    s.region("scalp", ellipse(CX, 17, 13.5, 8), skin, shade_right=0.74)
    for p in ((23, 12), (24, 12), (25, 12), (23, 13), (24, 13), (26, 11)):
        s.px(*p, skin[4])  # the shine on a bald head
    for sx in (-1, 1):
        s.region("hair%d" % sx, ellipse(CX + sx * 13.2, 25, 3.2, 6.5), hair)
    shade_hair(s, ("hair-1", "hair1"), strands=[((17, 21), (19, 30)), ((45, 21), (44, 30))])
    for x in range(25, 39, 3):  # forehead lines
        s.px(x, 19, skin[2])
        s.px(x + 1, 19, skin[2])
    eyes(s, hx("#3c6e9e"), mood, skin=skin)
    brows(s, hair[1], mood)
    s.region("stache", poly([(25, 36), (38, 36), (37, 38.6), (31.5, 37.6), (26, 38.6)]), hair)
    shade_hair(s, ("stache",), strands=[((28, 37), (30, 37)), ((33, 37), (35, 37))])
    nose_mouth(s, skin, hx("#b0605a"), mood, mouth_y=39)
    frame = R["navy"][2]
    for x0 in (19, 35):
        for x in range(x0, x0 + 10):
            s.px(x, 26, frame)
            s.px(x, 33, frame)
        for y in range(26, 34):
            s.px(x0, y, frame)
            s.px(x0 + 9, y, frame)
        s.px(x0 + 1, 27, WHITE)
        s.px(x0 + 2, 27, mix(WHITE, skin[3], 0.4))
        s.px(x0 + 1, 28, mix(WHITE, skin[3], 0.4))
    for x in range(29, 35):
        s.px(x, 28, frame)
    if mood == "concerned":
        sweat(s)
    return s.render(badge_bg(), clip=in_badge())


def bonnie(mood: str) -> Image.Image:
    s = Sprite(64, 64)
    skin, hair = R["skin_tan"], R["hair_blueblack"]
    s.region("hair_tail", ellipse(51, 21, 5, 7) | ellipse(54, 31, 4.5, 7.5) | ellipse(52, 41, 3.5, 5.5), hair, hl=False)
    s.region("hair_back", ellipse(CX, 25, 16, 14) - rect(0, 41, 63, 63), hair, hl=False)
    base_body(s, skin, R["pru_blue"])
    s.region("hair_crown", ellipse(CX, 15.5, 16, 10), hair, hl=False)
    fringe = {(x, y) for x in range(17, 47) for y in range(14, 28) if y <= 27 - (x - 17) * 0.32}
    s.region("hair_fringe", fringe, hair, hl=False)
    s.region("hair_side", rect(17, 22, 20, 40) | {(18, 41), (19, 41)}, hair, hl=False)
    shade_hair(s, ("hair_tail", "hair_back", "hair_crown", "hair_fringe", "hair_side"), sheen=(28, 15, 13, 6),
               strands=[((33, 17), (22, 26)), ((40, 17), (31, 23)), ((53, 18), (55, 34)), ((18, 27), (19, 38))])
    s.region("band", rect(46, 13, 48, 17), R["gold"])  # hair tie
    cast_shadow(s)
    eyes(s, hx("#3a2416"), mood, lashes=True, skin=skin)
    brows(s, hair[1], mood)
    nose_mouth(s, skin, hx("#a24a4a"), mood)
    s.px(17, 34, WHITE)
    s.px(46, 34, WHITE)  # pearl earrings
    if mood == "concerned":
        sweat(s)
    return s.render(badge_bg(), clip=in_badge())


def swap(mood: str) -> Image.Image:
    """Swap Dogg: a crunchy old hippie trader. Long silver hair, tie-dye headband, beard, round tinted glasses."""
    s = Sprite(64, 64)
    skin, hair = R["skin_tan"], R["hair_grey"]
    s.region("hair_back", {p for p in ellipse(CX, 28, 17.5, 22) if p[1] <= 56}, hair, hl=False)
    base_body(s, skin, R["shirt"], shirt=False, lapels=False)
    torso = s.pts_of("torso")
    dye = ["#e85d5d", "#f2a541", "#f5dd5b", "#6cc46a", "#4f9de0", "#9b6ad6"]
    for (x, y) in torso:  # a tie-dye swirl
        ang = math.atan2(y - 56, x - CX)
        k = int((ang * 3 + math.hypot(x - CX, y - 56) / 3)) % len(dye)
        col = hx(dye[k])
        if x > CX + 12:
            col = mix(col, INK, 0.25)
        s.px(x, y, col)
    vest = R["orange"]
    suede = [mix(c, hx("#8a6a48"), 0.65) for c in vest]
    for sx in (-1, 1):  # a fringed suede vest
        side = {(x, y) for (x, y) in torso if (x - CX) * sx > 7 + (y - 47) * 0.15}
        s.region("vest%d" % sx, side, suede)
        for (x, y) in side:
            s.detail.pop((x, y), None)
        for x in range(min(p[0] for p in side), max(p[0] for p in side) + 1):
            if x % 2 == 0:
                s.px(x, 63, suede[1])
    s.px(31, 52, R["shirt"][4])  # peace pendant on a cord
    s.px(32, 52, R["shirt"][4])
    s.px(31, 53, R["shirt"][2])
    s.px(32, 53, R["shirt"][2])
    for x, y in ((28, 48), (29, 49), (30, 50), (35, 48), (34, 49), (33, 50)):
        s.px(x, y, hx("#6b4a2a"))
    s.region("hair_crown", ellipse(CX, 16, 16.5, 9.5), hair, hl=False)
    shade_hair(s, ("hair_back", "hair_crown"), sheen=(27, 13, 13, 6),
               strands=[((31, 8), (31, 15)), ((22, 14), (16, 40)), ((19, 20), (15, 48)), ((41, 14), (47, 40)), ((44, 20), (48, 48))])
    for x in range(17, 47):  # tie-dye headband
        for y in (17, 18):
            s.px(x, y, mix(hx(dye[(x // 3) % len(dye)]), INK, 0.15 if y == 18 else 0))
    cast_shadow(s, from_prefix=("hair",))
    for x in range(24, 40, 3):  # forehead and crow's feet lines
        s.px(x, 21, skin[2])
    for x, y in ((19, 29), (19, 31), (44, 29), (44, 31)):
        s.px(x, y, skin[1])
    eyes(s, hx("#5a7a4a"), mood, skin=skin)
    brows(s, hair[1], mood)
    beard = poly([(18.5, 32), (22, 31), (26, 35), (37, 35), (41, 31), (44.5, 32), (43, 42), (37, 49), (31.5, 51), (26, 49), (20, 42)])
    s.region("beard", beard, hair)
    shade_hair(s, ("beard",), strands=[((24, 38), (27, 47)), ((31, 40), (31, 50)), ((39, 38), (36, 47))])
    s.region("stache", poly([(25, 35.5), (38, 35.5), (37.5, 38), (31.5, 37), (25.5, 38)]), hair)
    nose_mouth(s, skin, hx("#7a3e34"), mood, mouth_y=39)
    for x in range(28, 36):  # the beard hides the chin: draw the mouth into it
        for y in (40, 41, 42):
            if (x, y) in s.detail and s.owner.get((x, y)) == "beard" and y > 40:
                s.detail.pop((x, y))
    for cx in (23.5, 39.5):  # round, orange-tinted granny glasses
        for (x, y) in ellipse(cx, 29.5, 4, 3.6):
            base = s.detail.get((x, y))
            under = base if base is not None else s.ramps[s.owner[(x, y)]][3] if (x, y) in s.owner else hx("#ffffff")
            s.px(x, y, mix(under, hx("#f2a03a"), 0.35))
        for a in range(0, 360, 12):
            s.px(round(cx + 4.3 * math.cos(math.radians(a))), round(29.5 + 3.9 * math.sin(math.radians(a))), R["gold"][1])
        s.px(round(cx) - 2, 27, WHITE)
    for x in range(28, 36):
        s.px(x, 28, R["gold"][1])
    if mood == "concerned":
        sweat(s)
    return s.render(badge_bg(), clip=in_badge())


def seamore(mood: str) -> Image.Image:
    """Seamore Tenkays: a young analyst with a neat side part, round gold glasses and a bow tie."""
    s = Sprite(64, 64)
    skin = R["skin_fair"]
    hair = ramp("#1e140e", "#3a2618", "#57391f", "#76502c", "#9a6c3e")
    base_body(s, skin, R["slate"])
    s.region("hair_crown", ellipse(CX, 15, 15.5, 8.5), hair, hl=False)
    s.region("hair_swoop", {(x, y) for x in range(24, 46) for y in range(15, 21) if y <= 20 - (x - 24) * 0.18}, hair, hl=False)
    for sx in (-1, 1):  # short sides and sideburns
        xs = range(17, 21) if sx < 0 else range(43, 47)
        s.region("hair_side%d" % sx, {(x, y) for x in xs for y in range(17, 28)}, hair, hl=False)
    shade_hair(s, ("hair_crown", "hair_swoop", "hair_side-1", "hair_side1"), sheen=(33, 11, 11, 4.5),
               strands=[((25, 8), (25, 17)), ((30, 9), (40, 18)), ((35, 9), (44, 16))])
    cast_shadow(s, from_prefix=("hair",))
    bow = poly([(26, 45), (31, 47), (26, 50)]) | poly([(37, 45), (32, 47), (37, 50)])
    s.region("bow", bow, R["pru_blue"])
    s.region("knot", rect(31, 46, 32, 48), R["navy"])
    s.px(41, 53, R["gold"][3])  # a small pin on the lapel
    s.px(42, 53, R["gold"][1])
    eyes(s, hx("#3f7a55"), mood, skin=skin)
    brows(s, hair[0], mood)
    for side, x0 in EYES.items():  # a heavier brow
        for x in (range(x0, x0 + 3) if side == "L" else range(x0 + 1, x0 + 4)):
            y = min((yy for (xx, yy) in s.detail if xx == x and EYE_Y - 4 <= yy <= EYE_Y - 1), default=None)
            if y is not None:
                s.px(x, y - 1, hair[1])
    nose_mouth(s, skin, hx("#b4625e"), mood)
    for x in range(22, 42):  # a firmer jaw
        if s.owner.get((x, 42)) == "face":
            s.tone(x, 42, 2)
    for cx in (23.5, 39.5):  # round gold glasses
        for a in range(0, 360, 10):
            x = round(cx + 5.3 * math.cos(math.radians(a)))
            y = round(30 + 4.6 * math.sin(math.radians(a)))
            s.px(x, y, R["gold"][2] if 20 < a < 200 else R["gold"][4])
        s.px(round(cx) - 3, 28, WHITE)
        s.px(round(cx) - 2, 27, mix(WHITE, skin[3], 0.4))
    for x in range(29, 35):
        s.px(x, 28, R["gold"][2])
    if mood == "concerned":
        sweat(s)
    return s.render(badge_bg(), clip=in_badge())


CAST = {"vera": vera, "morty": morty, "bonnie": bonnie, "swap": swap, "seamore": seamore}
MOODS = ["neutral", "pleased", "concerned"]


# ---------------------------------------------------------------- Convexity the cat (48x48, transparent)

def cat(state: str) -> Image.Image:
    s = Sprite(48, 48)
    fur, white = R["orange"], R["white_fur"]
    eye_col = hx("#3fae5a")
    if state == "nap":
        s.region("tail", {(x, y) for x in range(8, 42) for y in range(39, 45)
                          if abs(y - (41.5 + 1.5 * math.sin((x - 8) / 5))) < 1.6}, fur)
        s.region("body", ellipse(26, 33, 17, 9), fur, shade_right=0.8)
        s.region("head", ellipse(13, 32, 8, 7), fur)
        s.region("earL", poly([(6, 28), (8, 21), (12, 27)]), fur)
        s.region("earR", poly([(13, 26), (17, 21), (19, 28)]), fur)
        s.region("muzzle", ellipse(11, 35, 4, 2.6), white)
        for x0 in (22, 27, 32, 37):  # tabby stripes
            for y in range(25, 31):
                s.tone(x0 + (y % 2), y, 1)
        for x in range(8, 12):
            s.px(x, 31, INK)
        for x in range(14, 18):
            s.px(x, 31, INK)
        s.px(11, 34, hx("#e88fa0"))
        for (x, y) in ((8, 23), (16, 23)):
            s.px(x, y, hx("#f2a3b3"))
        zz = [(30, 12), (31, 12), (32, 12), (31, 13), (30, 14), (31, 14), (32, 14),
              (36, 6), (37, 6), (38, 6), (39, 6), (38, 7), (37, 8), (36, 9), (37, 9), (38, 9), (39, 9)]
        for p in zz:
            s.px(*p, hx("#6f9fd0"))
    elif state == "alert":
        s.region("tail", {(x, y) for y in range(14, 44) for x in range(28, 46)
                          if abs(x - (31 + (44 - y) * 0.45 + 3 * math.sin((44 - y) / 6))) < 1.6}, fur)
        s.region("body", ellipse(24, 35, 10.5, 11), fur, shade_right=0.8)
        s.region("chest", ellipse(23, 36, 5, 7), white)
        s.region("pawL", ellipse(19, 45, 3, 2), white)
        s.region("pawR", ellipse(28, 45, 3, 2), white)
        s.region("head", ellipse(24, 18, 10, 8.5), fur)
        s.region("earL", poly([(15, 14), (16, 4), (22, 11)]), fur)
        s.region("earR", poly([(26, 11), (32, 4), (33, 14)]), fur)
        s.region("muzzle", ellipse(24, 22, 4.5, 3), white)
        for x0 in (18, 24, 30):
            s.tone(x0, 11, 1)
            s.tone(x0, 12, 1)
        for ex in (19, 27):  # wide green eyes
            for dx in range(3):
                for dy in range(3):
                    s.px(ex + dx, 16 + dy, eye_col)
            for dy in range(3):
                s.px(ex + 1, 16 + dy, INK)
            s.px(ex, 16, WHITE)
        s.px(23, 21, hx("#e88fa0"))
        s.px(24, 21, hx("#e88fa0"))
        for (x, y) in ((17, 8), (30, 8)):
            s.px(x, y, hx("#f2a3b3"))
        for x in (11, 12, 13):  # whiskers
            s.px(x, 21, white[1])
            s.px(x + 24, 21, white[1])
    else:  # hide: under the desk, eyes glowing in the shadow
        s.region("top", rect(0, 8, 47, 13), R["desk"])
        s.region("legL", rect(2, 14, 6, 47), R["desk"], shade_right=0.6)
        s.region("legR", rect(41, 14, 45, 47), R["desk"], shade_right=0.6)
        dark = [mix(c, hx("#101a3c"), 0.35) for c in fur]
        s.region("shadow", rect(7, 14, 40, 47), [hx("#070c1c"), hx("#0b1430"), hx("#111b3a"), hx("#16224a"), hx("#1c2a55")], hl=False)
        s.region("head", ellipse(24, 38, 8.5, 6.5), dark)
        s.region("earL", poly([(17, 35), (18, 28), (22, 33)]), dark)
        s.region("earR", poly([(26, 33), (30, 28), (31, 35)]), dark)
        for ex in (20, 26):
            s.px(ex, 37, hx("#9cf0a8"))
            s.px(ex + 1, 37, eye_col)
            s.px(ex, 38, eye_col)
            s.px(ex + 1, 38, mix(eye_col, INK, 0.4))
        for x in range(4, 44, 5):
            s.px(x, 9, R["desk"][4])
    return s.render(outline=True)


# ---------------------------------------------------------------- the office background (480x270), by season


SEASONS = {
    # sky top/bottom, clouds, far city, tree colors (base, light), weather
    "day": dict(sky=("#3a6fb8", "#d4ecfa"), cloud=("#ffffff", "#d6e8f5"), far="#93b2cc",
                trees=("#2f6b3a", "#3f8a48"), weather=None),
    "spring": dict(sky=("#5f9fdc", "#e4f4fb"), cloud=("#ffffff", "#dceaf4"), far="#9dbad2",
                   trees=("#e59ab4", "#f6c6d6"), weather="showers"),
    "summer": dict(sky=("#1f6fd0", "#bfe6ff"), cloud=("#ffffff", "#e2f1fb"), far="#8fb0d0",
                   trees=("#24713a", "#3d9a4c"), weather="sun"),
    "fall": dict(sky=("#6f8fb8", "#f6d9b4"), cloud=("#fff3e2", "#e8cfb0"), far="#a7a9b8",
                 trees=("#c8551f", "#f0a030"), weather="leaves"),
    "winter": dict(sky=("#76879e", "#e3e9f0"), cloud=("#f4f6f9", "#cfd7e2"), far="#a9b5c4",
                   trees=("#c9d6e2", "#f2f6fa"), weather="snow"),
}


def office(season: str = "day", storm: bool = False) -> Image.Image:
    W, H = 480, 270
    cfg = SEASONS[season]
    img = Image.new("RGB", (W, H))
    p = img.load()
    rnd = random.Random(409)
    win_top, win_bot, floor_y = 22, 192, 192
    dark = hx("#1a1f33")

    def stormy(col, k=0.45):
        return mix(col, dark, k) if storm else col

    sky_top, sky_bot = stormy(hx(cfg["sky"][0]), 0.55), stormy(hx(cfg["sky"][1]), 0.5)
    for y in range(win_top, win_bot):  # dithered sky gradient
        t = (y - win_top) / (win_bot - win_top)
        for x in range(W):
            a = mix(sky_top, sky_bot, t)
            b = mix(sky_top, sky_bot, min(1, t + 0.05))
            p[x, y] = b if (t * 20) % 1 * 16 > BAYER[y % 4][x % 4] else a
    if cfg["weather"] == "sun" and not storm:  # summer sun with a soft glow
        for (x, y) in ellipse(410, 52, 34, 34):
            if 0 <= x < W and win_top <= y < win_bot:
                p[x, y] = mix(p[x, y], hx("#fff4c2"), 0.35)
        for (x, y) in ellipse(410, 52, 15, 15):
            if win_top <= y < win_bot:
                p[x, y] = hx("#fff7d6") if (x - 405) ** 2 + (y - 47) ** 2 > 30 else WHITE
    if cfg["weather"] == "showers" and not storm:  # a spring rainbow
        bands = ["#e85d5d", "#f2a541", "#f5dd5b", "#6cc46a", "#4f9de0", "#7b68c8"]
        for (x, y) in [(x, y) for x in range(W) for y in range(win_top, win_bot)]:
            d = math.hypot(x - 240, (y - 230) * 1.0)
            k = int((d - 150) // 3)
            if 0 <= k < len(bands):
                p[x, y] = mix(p[x, y], hx(bands[k]), 0.45)
    lit, shade = stormy(hx(cfg["cloud"][0]), 0.4), stormy(hx(cfg["cloud"][1]), 0.45)
    for _ in range(12 if storm else 8):  # clouds
        cx, cy, w = rnd.randint(0, W), rnd.randint(30, 92 if storm else 84), rnd.randint(18, 46 if storm else 40)
        for (x, y) in ellipse(cx, cy, w, 5) | ellipse(cx - w * 0.3, cy - 4, w * 0.45, 5) | ellipse(cx + w * 0.25, cy - 3, w * 0.35, 4):
            if 0 <= x < W and win_top <= y < win_bot:
                p[x, y] = lit if y < cy + 1 else shade
    roofs: list[tuple[int, int, int]] = []  # (x0, x1, top) for snow caps
    x = 0
    while x < W:  # far skyline
        w = rnd.randint(10, 26)
        top = rnd.randint(118, 150)
        base = stormy(hx(cfg["far"]), 0.5)
        roofs.append((x, min(W, x + w), top))
        for xx in range(x, min(W, x + w)):
            for yy in range(top, win_bot):
                win_lit = (yy - top) % 4 == 2 and (xx - x) % 3 == 1
                if storm:
                    p[xx, yy] = mix(base, hx("#f7e7a8"), 0.55) if win_lit and (xx * 7 + yy) % 5 < 2 else base
                else:
                    p[xx, yy] = mix(base, WHITE, 0.25) if win_lit else base
        x += w + rnd.randint(1, 4)

    def tower(x0, w, top, body, light, glass=True):
        roofs.append((x0, x0 + w, top))
        for xx in range(x0, x0 + w):
            for yy in range(top, win_bot):
                if not 0 <= xx < W:
                    continue
                f = (xx - x0) / w
                if glass:
                    col = mix(hx(light), hx(body), min(1, f * 4)) if f < 0.25 else mix(hx(body), hx("#0f2140"), (f - 0.25) * 0.8)
                    if (yy - top) % 4 == 0:
                        col = mix(col, hx("#9cc4ea"), 0.35)
                    if (xx - x0) % 9 == 0:
                        col = mix(col, hx("#cfe6ff"), 0.35)
                    if season == "fall" and not storm:
                        col = mix(col, hx("#f2b06a"), 0.18)  # warm reflections
                else:
                    col = hx(light) if (xx - x0) % 4 == 0 else hx(body)
                    if (yy - top) % 4 in (1, 2) and (xx - x0) % 4 != 0:
                        col = hx("#6c7f96")
                        if storm and (xx * 3 + yy) % 7 < 2:
                            col = hx("#e8c96a")
                p[xx, yy] = stormy(col)

    tower(28, 46, 70, "#c9b89a", "#efe3cc", glass=False)
    tower(168, 30, 54, "#1f3d66", "#6f9fd4")
    tower(196, 34, 62, "#1a3459", "#5f8fc4")
    roofs.append((250, 300, 128))
    for xx in range(250, 300):  # brick block with a roof garden
        for yy in range(128, win_bot):
            col = hx("#a8553a") if (yy % 5 and xx % 6) else hx("#7a3a28")
            if yy < 131:
                col = hx(cfg["trees"][0]) if (xx + yy) % 3 else hx(cfg["trees"][1])
            p[xx, yy] = stormy(col)
    tower(360, 40, 84, "#2a4a75", "#7aa8d8")
    tower(420, 30, 104, "#c2b08f", "#e6dac2", glass=False)
    if season == "winter":  # snow on every roof
        for x0, x1, top in roofs:
            for xx in range(max(0, x0), min(W, x1)):
                for yy in range(top, top + 2 + (xx % 3 == 0)):
                    if win_top <= yy < win_bot:
                        p[xx, yy] = stormy(hx("#f6f9fc"), 0.3)
    tb, tl = hx(cfg["trees"][0]), hx(cfg["trees"][1])
    for xx in range(W):  # tree tops at the bottom of the view
        h = 176 + round(4 * math.sin(xx / 7) + 3 * math.sin(xx / 3.1))
        for yy in range(h, win_bot):
            col = tl if (xx + yy) % 4 == 0 or yy < h + 2 else tb
            if season == "spring" and (xx * 7 + yy * 3) % 11 == 0:
                col = hx("#7fbf6a")  # fresh green among the blossoms
            if season == "fall" and (xx * 5 + yy) % 9 == 0:
                col = hx("#e8c23a")
            if season == "winter" and yy > h + 3:
                col = hx("#7d8a7a") if (xx + yy) % 3 else hx("#5d6b5c")
            p[xx, yy] = stormy(col, 0.5)

    # weather outside the glass
    wx = cfg["weather"]
    if wx in ("showers",) or (storm and wx in ("sun", "leaves")):
        n = 520 if storm else 160
        for _ in range(n):
            x0, y0 = rnd.randint(0, W - 1), rnd.randint(win_top, win_bot - 1)
            for k in range(6 if storm else 4):
                xx, yy = x0 - k // 2, y0 + k
                if 0 <= xx < W and win_top <= yy < win_bot:
                    p[xx, yy] = mix(p[xx, yy], hx("#c9d6f0"), 0.6 if storm else 0.4)
    if wx == "showers":  # pink petals drifting
        for _ in range(50 if not storm else 90):
            x0, y0 = rnd.randint(0, W - 2), rnd.randint(win_top + 4, win_bot - 4)
            p[x0, y0] = hx("#f7b6cb")
            p[x0 + 1, y0] = hx("#fbd3e0")
    if wx == "leaves":
        for _ in range(70 if not storm else 160):
            x0, y0 = rnd.randint(0, W - 3), rnd.randint(win_top + 4, win_bot - 4)
            col = hx(rnd.choice(["#d9541e", "#f0a030", "#b8371a", "#e8c23a"]))
            p[x0, y0] = col
            p[x0 + 1, y0] = col
            p[x0 + 1, y0 + 1] = mix(col, dark, 0.3)
    if wx == "snow":
        for _ in range(260 if not storm else 700):
            x0, y0 = rnd.randint(0, W - 1), rnd.randint(win_top, win_bot - 1)
            p[x0, y0] = hx("#ffffff")
            if storm and x0 + 1 < W:
                p[x0 + 1, y0] = hx("#e6edf5")
    if wx == "sun" and not storm:  # summer birds
        for bx, by in ((120, 60), (134, 54), (300, 48), (312, 56)):
            for dx, dy in ((-2, -1), (-1, 0), (0, 1), (1, 0), (2, -1)):
                p[bx + dx, by + dy] = hx("#2a3550")
    if storm and wx in ("showers", "sun"):  # lightning
        x0 = 330 if wx == "showers" else 120
        for y in range(win_top, 122):
            x0 += rnd.choice((-1, 0, 1, 1))
            for dx in (0, 1):
                p[x0 + dx, y] = hx("#fff6c8")

    frame, frame_hi = hx("#1e2633"), hx("#3a4658")  # window mullions and transom
    for xx in range(0, W, 80):
        for dx in range(4):
            for yy in range(win_top, win_bot):
                p[(xx + dx) % W, yy] = frame_hi if dx == 0 else frame
    for yy in (win_top, win_top + 1, 62, 63):
        for xx in range(W):
            p[xx, yy] = frame
    for xx in range(W):  # glass glare
        for yy in range(win_top + 2, win_bot):
            if (xx - yy * 0.6) % 160 < 10 and (xx % 80) > 4:
                p[xx, yy] = mix(p[xx, yy], WHITE, 0.12)
    if season == "winter":  # frost in the bottom corners of each pane
        for x0 in range(0, W, 80):
            for k in range(18):
                for j in range(18 - k):
                    for xx in (x0 + 4 + j, x0 + 79 - j):
                        yy = win_bot - 1 - k
                        if 0 <= xx < W and (j + k) % 2 == 0 and rnd.random() < 0.75:
                            p[xx, yy] = mix(p[xx, yy], hx("#eef6ff"), 0.7)
        bulbs = ["#ff5a5a", "#ffd34a", "#5be37d", "#5ab4ff"]  # string lights along the transom
        for i, xx in enumerate(range(3, W, 7)):
            yy = 64 + round(2 * math.sin(xx / 9))
            p[xx, yy] = hx(bulbs[i % 4])
            p[xx, yy + 1] = mix(hx(bulbs[i % 4]), dark, 0.3)
            for k in range(7):
                if xx + k < W:
                    p[xx + k, 64 + round(2 * math.sin((xx + k) / 9)) - 1] = hx("#2a3a28")

    for yy in range(0, win_top):  # ceiling, light strips, market ticker
        for xx in range(W):
            p[xx, yy] = mix(hx("#141a26"), hx("#1f2736"), yy / win_top)
    for xx in range(20, W - 60, 120):
        for dx in range(60):
            p[xx + dx, 3] = hx("#ffe9b0")
            p[xx + dx, 4] = hx("#c9b27a")
    for xx in range(W):
        p[xx, 12] = hx("#0a0d14")
        p[xx, 18] = hx("#0a0d14")
    xx = 2
    while xx < W - 8:
        col = rnd.choice([hx("#5be37d"), hx("#ff6b7d"), hx("#ffc72c")])
        if storm:
            col = rnd.choice([hx("#ff6b7d"), hx("#ff6b7d"), hx("#ffc72c")])  # a red tape on shock days
        for k in range(rnd.randint(3, 7)):
            for yy in range(14, 17):
                if (xx * 5 + k * 3 + yy) % 10 < 7:
                    p[xx + k, yy] = col
        xx += rnd.randint(9, 15)
    for yy in range(floor_y, H):  # polished stone floor with window reflections
        t = (yy - floor_y) / (H - floor_y)
        for xx in range(W):
            base = mix(hx("#2a2f3c"), hx("#171a22"), t)
            src = win_bot - 1 - (yy - floor_y) * 2
            if (xx % 80) > 4 and t < 0.6 and src > win_top:
                base = mix(base, p[xx, src], 0.18 * (1 - t))
            if (xx + yy * 3) % 64 == 0:
                base = mix(base, WHITE, 0.08)
            p[xx, yy] = base
    for xx in range(W):
        p[xx, floor_y] = hx("#0d1017")
        p[xx, floor_y + 1] = hx("#3d4556")

    d = ImageDraw.Draw(img)

    def pot(x0):
        d.rectangle([x0 - 7, 236, x0 + 7, 262], fill=hx("#e8e2d6"))
        d.rectangle([x0 - 7, 236, x0 + 7, 238], fill=WHITE)
        d.rectangle([x0 + 3, 239, x0 + 7, 262], fill=hx("#c9c1b2"))

    def plant(x0, leaf=("#2f7a3c", "#4aa55a"), flowers=None):
        d.line([x0, 236, x0, 210], fill=hx("#5a3b22"))
        for (lx, ly, r) in ((0, 214, 9), (-8, 222, 7), (8, 220, 7), (-4, 204, 6), (5, 206, 6), (0, 196, 5)):
            d.ellipse([x0 + lx - r, ly - r * 0.7, x0 + lx + r, ly + r * 0.7], fill=hx(leaf[0]))
            d.ellipse([x0 + lx - r + 2, ly - r * 0.7 + 1, x0 + lx + r - 4, ly], fill=hx(leaf[1]))
        for (fx, fy) in (flowers or []):
            d.rectangle([x0 + fx - 1, fy - 1, x0 + fx + 1, fy + 1], fill=hx("#ffd34a" if season == "summer" else "#f25c7a"))
            d.point((x0 + fx, fy), fill=hx("#6b3a12" if season == "summer" else "#ffe0e8"))
        pot(x0)

    if season == "winter":  # poinsettias
        plant(18, ("#9e1b2c", "#d3313f"))
        plant(462, ("#9e1b2c", "#d3313f"))
    elif season == "fall":
        plant(18, ("#8a4a1a", "#c8742a"))
        plant(462, ("#2f7a3c", "#4aa55a"))
    elif season == "spring":  # tulips
        plant(18, flowers=[(-6, 200), (0, 194), (6, 199), (-2, 207), (4, 210)])
        plant(462, flowers=[(-5, 201), (2, 195), (7, 205)])
    elif season == "summer":  # sunflowers
        plant(18, flowers=[(-5, 199), (3, 194), (7, 205)])
        plant(462, flowers=[(-4, 197), (5, 201)])
    else:
        plant(18)
        plant(462)
    d.rectangle([300, 226, 430, 232], fill=hx("#6b4226"))  # walnut desk with two chart monitors
    d.rectangle([300, 226, 430, 227], fill=hx("#8c5a36"))
    d.rectangle([306, 233, 312, 266], fill=hx("#4a2d1a"))
    d.rectangle([418, 233, 424, 266], fill=hx("#4a2d1a"))
    for mx, up in ((322, not storm), (370, False)):
        d.rectangle([mx, 196, mx + 40, 222], fill=hx("#0d1220"))
        d.rectangle([mx + 2, 198, mx + 38, 220], fill=hx("#11203a"))
        pts = [(mx + 3 + i * 5, 212 + (-i if up else i) + (2 if i % 2 else 0)) for i in range(8)]
        d.line(pts, fill=hx("#5be37d" if up else "#ff6b7d"))
        d.rectangle([mx + 18, 222, mx + 22, 226], fill=hx("#2a2f3c"))
    if season == "fall":  # a pumpkin by the desk
        d.ellipse([280, 250, 298, 264], fill=hx("#d9681e"))
        d.ellipse([284, 250, 294, 264], fill=hx("#f08a2e"))
        d.rectangle([288, 246, 290, 250], fill=hx("#4a6a2a"))
    if season == "summer":  # an iced tea on the desk
        d.rectangle([412, 216, 418, 225], fill=hx("#c98a3a"))
        d.rectangle([412, 216, 418, 217], fill=hx("#f3e2c2"))
        d.line([416, 212, 417, 216], fill=hx("#5be37d"))
    if season == "winter":  # a mug of cocoa with steam
        d.rectangle([412, 219, 418, 225], fill=hx("#e8e2d6"))
        d.rectangle([418, 221, 419, 223], fill=hx("#e8e2d6"))
        for k, (sx, sy) in enumerate(((414, 216), (415, 214), (414, 212))):
            d.point((sx, sy), fill=hx("#cfd7e2"))
    d.rectangle([44, 228, 150, 252], fill=hx("#5a2f22"))  # leather sofa
    d.rectangle([44, 214, 150, 230], fill=hx("#6e3a2a"))
    d.rectangle([44, 214, 150, 216], fill=hx("#8a4d38"))
    d.rectangle([40, 220, 50, 254], fill=hx("#4a261b"))
    d.rectangle([144, 220, 154, 254], fill=hx("#4a261b"))
    for sx in (80, 114):
        d.line([sx, 230, sx, 250], fill=hx("#4a261b"))
    if season == "winter":  # a plaid blanket on the sofa
        for xx in range(96, 140):
            for yy in range(216, 236):
                if (xx // 4 + yy // 4) % 2 == 0:
                    img.putpixel((xx, yy), hx("#b8304a") if (xx + yy) % 2 else hx("#8f2238"))
    return img


# ---------------------------------------------------------------- build + contact sheets

OFFICES = [("day", False)] + [(s, st) for s in ("spring", "summer", "fall", "winter") for st in (False, True)]


def office_name(season: str, storm: bool) -> str:
    return f"office_{season}" + ("_storm" if storm else "")


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(exist_ok=True)
    sprites: dict[str, Image.Image] = {}
    for who, fn in CAST.items():
        for mood in MOODS:
            sprites[f"{who}_{mood}"] = fn(mood)
    for state in ("nap", "alert", "hide"):
        sprites[f"cat_{state}"] = cat(state)
    for name, im in sprites.items():
        im.save(OUT / f"{name}.png", optimize=True)
    offices = {office_name(s, st): office(s, st) for s, st in OFFICES}
    for name, im in offices.items():
        im.save(OUT / f"{name}.png", optimize=True)
    old = OUT / "office_storm.png"
    if old.exists():
        old.unlink()  # replaced by the seasonal storm scenes

    scale, pad, cols = 6, 18, 6
    cell = 64 * scale + pad
    rows = math.ceil(len(sprites) / cols)
    sheet = Image.new("RGB", (cols * cell + pad, rows * (cell + 16) + pad), hx("#f3f6fa"))
    dr = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for i, (name, im) in enumerate(sprites.items()):
        k = scale if im.width == 64 else 8
        big = im.resize((im.width * k, im.height * k), Image.NEAREST)
        x = pad + (i % cols) * cell
        y = pad + (i // cols) * (cell + 16)
        sheet.paste(big, (x, y), big)
        dr.text((x, y + 64 * scale + 2), name, fill=hx("#0d1f3c"), font=font)
    sheet.save(EVIDENCE / "sprites_contact_sheet.png")
    grid = Image.new("RGB", (480 * 3 + 20, 270 * 3 + 20), WHITE)
    for i, name in enumerate(offices):
        grid.paste(offices[name], ((i % 3) * 490, (i // 3) * 280))
    grid.save(EVIDENCE / "office_backgrounds.png")
    print(f"{len(sprites)} sprites + {len(offices)} office scenes -> {OUT}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build()
