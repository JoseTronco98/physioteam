"""Embed every <img src="shots/x.png"> as a JPEG data URI, and reveal.js (report/vendor, v5.1.0) inline,
so the report and slides open offline with a double-click.
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


VENDOR = {"reveal.css": "dist/reveal.css", "white.css": "dist/theme/white.css", "reveal.js": "dist/reveal.js"}


def inline_reveal(html: str) -> str:
    for f, path in VENDOR.items():
        code = (R / "vendor" / f).read_text(encoding="utf-8")
        url = f"https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/{path}"
        if f.endswith(".css"):
            code = re.sub(r"@import url\([^)]*\);", "", code)   # theme web font: system fonts are used instead
            html, n = re.subn(rf'<link rel="stylesheet" href="{re.escape(url)}"\s*/?>', lambda m: f"<style>{code}</style>", html)
        else:
            html, n = re.subn(rf'<script src="{re.escape(url)}"></script>', lambda m: f"<script>{code}</script>", html)
        if n != 1:
            raise SystemExit(f"reveal.js reference not found once: {url}")
    return html


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
    if name == "slides":
        html = inline_reveal(html)
    (OUT / f"{name}.html").write_text(html, encoding="utf-8")
    if CANVAS.is_dir():   # only on the author's machine
        shutil.copy(OUT / f"{name}.html", CANVAS / f"{name}.html")
    print(f"{name}.html {len(html) / 1e6:.1f} MB", "MISSING: " + ", ".join(missing) if missing else "")
