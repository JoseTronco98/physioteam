"""Screenshots for the report and slides (headless Chrome against a local server) plus document images.

Needs a server on port 8001 without an access code, and the "report" session made by tools.report_data:
  ACCESS_CODE=" " uvicorn backend.main:app --port 8001
Run: python -m tools.shots <outdir>
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import pypdfium2 as pdfium

from backend import pdfdocs, runtime, store

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "shots")
OUT.mkdir(parents=True, exist_ok=True)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE = "http://localhost:8001/?session=report"

SHOTS = [
    ("hub", "#start", 1600, 1000),
    ("how", "#how", 1600, 1100),
    ("team_chat", "#therapist/chat/team", 1700, 1000),
    ("health_chat", "#therapist/chat/health", 1700, 1000),
    ("ops_chat", "#therapist/chat/ops", 1700, 1000),
    ("wa_valentina", "#therapist/messages/wa:p_valentina", 1700, 1000),
    ("wa_tom", "#therapist/messages/wa:p_tom", 1700, 1000),
    ("wa_hector", "#therapist/messages/wa:p_hector", 1700, 1000),
    ("wa_javier", "#therapist/messages/wa:p_javier", 1700, 1000),
    ("doc_ortiz", "#therapist/messages/doc:d_ortiz", 1700, 1000),
    ("approvals", "#therapist/approvals", 1700, 1000),
    ("agenda", "#therapist/agenda", 1700, 1050),
    ("folder_hector", "#therapist/folders/p_hector", 1700, 1100),
    ("folder_javier", "#therapist/folders/p_javier", 1700, 1100),
    ("costs", "#therapist/costs", 1700, 1050),
    ("daily", "#therapist/report", 1700, 1050),
    ("patient_valeria", "#patient/valeria", 1700, 1000),
]


def shot(browser, name: str, frag: str, w: int, h: int) -> None:
    """Playwright with the installed Chrome (headless Chrome's --screenshot hangs on the live event stream)."""
    out = OUT / f"{name}.png"
    page = browser.new_page(viewport={"width": w, "height": h})
    page.goto(BASE + frag, wait_until="domcontentloaded")
    page.wait_for_timeout(4500)
    page.screenshot(path=str(out))
    page.close()
    print(name, out.stat().st_size if out.exists() else "MISSING")


def pdf_pages(c: dict, pid: str, kind: str, name: str, pages: int = 1) -> None:
    docs = [d for d in c["documents"].values() if d["patient_id"] == pid and d["kind"] == kind]
    if not docs:
        print("no doc", pid, kind)
        return
    d = docs[-1] if kind != "soap" else docs[min(2, len(docs) - 1)]
    pdf = pdfium.PdfDocument(pdfdocs.render(c, d))
    for i in range(min(pages, len(pdf))):
        pdf[i].render(scale=1.4).to_pil().save(OUT / f"{name}_p{i + 1}.png")
    print(name, store.doc_filename(c, d), len(pdf), "pages")


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for args in SHOTS:
            shot(browser, *args)
        browser.close()
    c = runtime.get_session("report").c
    pdf_pages(c, "p_hector", "evaluation", "pdf_eval_hector", 2)
    pdf_pages(c, "p_hector", "soap", "pdf_soap_hector")
    pdf_pages(c, "p_javier", "evaluation", "pdf_eval_javier", 2)
    pdf_pages(c, "p_javier", "treatment_plan", "pdf_plan_javier", 2)
    pdf_pages(c, "p_hector", "progress_report", "pdf_progress_hector", 2)
    pdf_pages(c, "p_hector", "feedback", "pdf_feedback_hector")


main()
