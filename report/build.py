"""Embed every <img src="shots/x.png"> as a JPEG data URI so the report and slides open anywhere.
Writes report/out/report.html and slides.html, and copies them to ../../deliverable/ (the Canvas folder) if that folder exists.
Run: python report/build.py"""

import base64
import io
import re
import shutil
from pathlib import Path

from PIL import Image

R = Path(__file__).parent
OUT = R / "out"
OUT.mkdir(exist_ok=True)
CANVAS = R.parent.parent / "deliverable"   # Final Project/deliverable (outside the repo)


def data_uri(path: Path, max_w: int = 1500) -> str:
    im = Image.open(path).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=78, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


for name in ("report", "slides"):
    src = R / f"{name}.ready.html"
    html = src.read_text(encoding="utf-8")
    missing = []

    def repl(m):
        p = R / m.group(1)
        if not p.is_file():
            missing.append(m.group(1))
            return m.group(0)
        return f'src="{data_uri(p)}"'

    html = re.sub(r'src="(shots/[^"]+\.png)"', repl, html)
    (OUT / f"{name}.html").write_text(html, encoding="utf-8")
    if CANVAS.is_dir():   # only on the author's machine
        shutil.copy(OUT / f"{name}.html", CANVAS / f"{name}.html")
    print(f"{name}.html {len(html) / 1e6:.1f} MB", "MISSING: " + ", ".join(missing) if missing else "")
