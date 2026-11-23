"""Build deliverables/report.html and deliverables/slides.html as single self-contained files (dev only).

Inputs: deliverables/src/report.src.html and slides.src.html (templates), screenshots in evidence/screens/
(from scripts/capture_evidence.py), sprites in frontend/public/art/, and reveal.js plus the Atkinson Hyperlegible
woff2 files from a local npm folder (pass --deps). Every image, font, style and script is inlined as base64 or
text, so both files open by double-click offline.

    python scripts/build_deliverables.py --deps <folder containing node_modules>
"""
from __future__ import annotations

import argparse
import base64
import io
import re
from pathlib import Path

from PIL import Image

SCREENS = Path("evidence/screens")
ART = Path("frontend/public/art")
SRC = Path("deliverables/src")
OUT = Path("deliverables")

# name: (file, crop box in the 2x screenshot's pixels or None, output width)
CROPS = {
    "desk": ("04_desk_q1.png", None, 1700),
    "team_answer": ("05_team_answer.png", None, 900),
    "isin": ("06_isin_blocked.png", (0, 700, 1340, 1504), 900),
    "ticket": ("07_ticket_q1.png", (2060, 0, 2800, 1210), 700),
    "predict": ("08_predict.png", None, 1500),
    "shock": ("09_shock_q1.png", None, 1700),
    "vera": ("10_vera_q1.png", (80, 400, 2800, 1590), 1600),
    "report_card": ("12_report_card.png", (345, 140, 2495, 3990), 1200),
    "report_card_top": ("12_report_card.png", (345, 140, 2495, 1400), 1300),
    "trace": ("13_trace.png", (0, 0, 2880, 2560), 1600),
    "costs": ("14_experiments.png", (40, 3050, 2840, 3600), 1600),
    "safety": ("15_safety_lab.png", (60, 130, 2820, 1950), 1600),
    "companies": ("02_companies.png", None, 1500),
    "collapse": ("19_shock_q5.png", None, 1500),
    "welcome": ("01_welcome.png", None, 1500),
}
SPRITES = ["vera_neutral", "vera_pleased", "morty_neutral", "bonnie_neutral", "swap_neutral", "seamore_neutral",
           "cat_alert", "office_day"]


def jpeg(path: Path, box, width: int) -> str:
    im = Image.open(path).convert("RGB")
    if box:
        im = im.crop(box)
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def png(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def fill(template: str, assets: dict[str, str]) -> str:
    def sub(m):
        key = m.group(1)
        if key not in assets:
            raise SystemExit(f"unknown asset {key}")
        return assets[key]
    return re.sub(r"\{\{(\w+)\}\}", sub, template)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deps", required=True)
    a = ap.parse_args()
    nm = Path(a.deps) / "node_modules"
    assets = {f"img_{k}": jpeg(SCREENS / f, box, w) for k, (f, box, w) in CROPS.items()}
    assets.update({f"sprite_{s}": png(ART / f"{s}.png") for s in SPRITES})
    font = nm / "@fontsource/atkinson-hyperlegible/files"
    assets["font_400"] = b64(font / "atkinson-hyperlegible-latin-400-normal.woff2", "font/woff2")
    assets["font_700"] = b64(font / "atkinson-hyperlegible-latin-700-normal.woff2", "font/woff2")
    assets["reveal_css"] = (nm / "reveal.js/dist/reveal.css").read_text(encoding="utf-8")
    assets["reveal_js"] = (nm / "reveal.js/dist/reveal.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    for name in ("report", "slides"):
        html = fill((SRC / f"{name}.src.html").read_text(encoding="utf-8"), assets)
        out = OUT / f"{name}.html"
        out.write_text(html, encoding="utf-8")
        print(f"{out}: {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
