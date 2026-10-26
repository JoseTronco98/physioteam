"""Print report.html to a letter PDF (like a grader would), count pages, and render page previews.
Also screenshot the first slides. Run: python ..\\deliverable_src\\check.py <preview_dir>"""

import sys
from pathlib import Path

import pypdfium2 as pdfium
from playwright.sync_api import sync_playwright

SRC = Path(__file__).parent
DEL = SRC / "out"
PREV = Path(sys.argv[1] if len(sys.argv) > 1 else SRC / "preview")
PREV.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    page = b.new_page()
    page.goto((DEL / "report.html").as_uri(), wait_until="load")
    pdf_path = PREV / "report_print.pdf"
    page.pdf(path=str(pdf_path), format="Letter", print_background=True,
             margin={"top": "0.6in", "bottom": "0.6in", "left": "0.65in", "right": "0.65in"})
    s = b.new_page(viewport={"width": 1280, "height": 760})
    s.goto((DEL / "slides.html").as_uri(), wait_until="load")
    s.wait_for_timeout(2500)
    for i in range(10):
        s.screenshot(path=str(PREV / f"slide_{i + 1}.png"))
        s.keyboard.press("ArrowRight")
        s.wait_for_timeout(700)
    b.close()

pdf = pdfium.PdfDocument(str(pdf_path))
print("report pages:", len(pdf))
for i in range(len(pdf)):
    pdf[i].render(scale=0.9).to_pil().save(PREV / f"page_{i + 1:02d}.png")

