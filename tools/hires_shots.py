"""High-resolution (2x) screenshots for the report and slides, from saved sessions (no model calls).

Sessions: "trace" (tools.trace_shots), "demos" (tools.demo_runs), "report" (tools.report_data).
Needs a server on port 8001 without an access code:  ACCESS_CODE=" " uvicorn backend.main:app --port 8001
Run: python -m tools.hires_shots report/shots/hi     then: python report/make_crops.py
"""

import sys
from pathlib import Path

import pypdfium2 as pdfium

from backend import pdfdocs, runtime

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "report/shots/hi")
OUT.mkdir(parents=True, exist_ok=True)
API = "http://localhost:8001"

SHOTS = [   # (session, name, view, viewport height); width 1700 CSS px, captured at 2x
    ("trace", "t_approvals", "#therapist/approvals", 1050),
    ("trace", "t_costs", "#therapist/costs", 1050),
    ("trace", "t_wa_valentina", "#therapist/messages/wa:p_valentina", 1050),
    ("demos", "d_wa_valentina", "#therapist/messages/wa:p_valentina", 1500),
    ("demos", "d_wa_javier", "#therapist/messages/wa:p_javier", 1300),
    ("demos", "d_health", "#therapist/chat/health", 1300),
    ("demos", "d_ops", "#therapist/chat/ops", 1500),
    ("demos", "d_daily", "#therapist/report", 1150),
    ("report", "r_wa_tom", "#therapist/messages/wa:p_tom", 1000),
    ("report", "r_wa_hector", "#therapist/messages/wa:p_hector", 1000),
]


BUBBLES = [   # (session, view, text inside the message, name)
    ("demos", "#therapist/chat/health", "Drafted Javier", "b_demo2_drafts"),
    ("demos", "#therapist/chat/ops", "The week was busy", "b_demo3_week"),
]


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        for sid, frag, text, name in BUBBLES:   # one chat message, re-wrapped to a slide column's width
            page = b.new_page(viewport={"width": 1700, "height": 1500}, device_scale_factor=2)
            page.goto(f"{API}/?session={sid}{frag}", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            skip = page.get_by_role("button", name="Skip")
            if skip.count():
                skip.first.click()
            page.wait_for_timeout(1000)
            handle = page.evaluate_handle("""(t) => {
                const hit = [...document.querySelectorAll('*')].filter(e => e.children.length === 0 && e.textContent.includes(t)).pop();
                let e = hit;
                while (e && getComputedStyle(e).backgroundColor === 'rgba(0, 0, 0, 0)') e = e.parentElement;
                e.style.maxWidth = '430px'; e.style.width = '430px';
                return e;
            }""", text)
            page.wait_for_timeout(300)
            handle.as_element().screenshot(path=str(OUT / f"{name}.png"))
            page.close()
            print(name)
        for sid, name, frag, h in SHOTS:
            page = b.new_page(viewport={"width": 1700, "height": h}, device_scale_factor=2)
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
    c = runtime.get_session("demos").c   # Demo 2's drafted evaluation and plan, rendered sharp
    for kind, name in (("evaluation", "d_pdf_eval"), ("treatment_plan", "d_pdf_plan")):
        docs = [d for d in c["documents"].values() if d["patient_id"] == "p_javier" and d["kind"] == kind]
        if docs:
            pdfium.PdfDocument(pdfdocs.render(c, docs[-1]))[0].render(scale=2.8).to_pil().save(OUT / f"{name}.png")
            print(name)


main()
