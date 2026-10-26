"""Screenshots of the three replayed demos (session "demos" made by tools.demo_runs).

Needs a server on port 8001 without an access code:  ACCESS_CODE=" " uvicorn backend.main:app --port 8001
Run: python -m tools.demo_shots report/shots     (no model calls)
"""

import sys
from pathlib import Path

import pypdfium2 as pdfium

from backend import pdfdocs, runtime

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "report/shots")
OUT.mkdir(parents=True, exist_ok=True)
API = "http://localhost:8001"

SHOTS = [   # (session, name, view, height)
    ("demos", "demo1_whatsapp", "#therapist/messages/wa:p_valentina", 1500),
    ("demos", "demo1_ops", "#therapist/chat/ops", 1300),
    ("demos", "demo1_agenda", "#therapist/agenda", 1150),
    ("demos", "demo2_health", "#therapist/chat/health", 1300),
    ("demos", "demo2_whatsapp", "#therapist/messages/wa:p_javier", 1300),
    ("demos", "demo2_folder", "#therapist/folders/p_javier", 1150),
    ("demos", "demo3_ops", "#therapist/chat/ops", 1500),
    ("demos", "demo3_daily", "#therapist/report", 1150),
]


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        for sid, name, frag, h in SHOTS:
            page = b.new_page(viewport={"width": 1700, "height": h})
            page.goto(f"{API}/?session={sid}{frag}", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            skip = page.get_by_role("button", name="Skip")
            if skip.count():
                skip.first.click()
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / f"{name}.png"))
            page.close()
            print(name)
        b.close()
    c = runtime.get_session("demos").c   # the drafted evaluation and plan from Demo 2, as PDFs
    for kind, name in (("evaluation", "demo2_pdf_eval"), ("treatment_plan", "demo2_pdf_plan")):
        docs = [d for d in c["documents"].values() if d["patient_id"] == "p_javier" and d["kind"] == kind]
        if docs:
            pdfium.PdfDocument(pdfdocs.render(c, docs[-1]))[0].render(scale=1.4).to_pil().save(OUT / f"{name}_p1.png")
            print(name)


main()
