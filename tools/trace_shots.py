"""Step-by-step screenshots of one traced run for the report (Exhibit "what each agent did").

Plays story 1 step 1 (a patient asks for a session) and story 3 step "notes" (first-visit notes become an
evaluation and a plan) in a fresh session, and captures after each: the conversation, and the
"Behind the scenes" panel that lists every agent and tool call. Also captures the app's token meter.
Needs a server on port 8001 without an access code:  ACCESS_CODE=" " uvicorn backend.main:app --port 8001
Run: python -m tools.trace_shots report/shots   (~$0.01 of model use)
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "report/shots")
OUT.mkdir(parents=True, exist_ok=True)
API = "http://localhost:8001"
SID = "trace"


def call(path, method="GET"):
    req = urllib.request.Request(f"{API}{path}{'&' if '?' in path else '?'}session={SID}", method=method,
                                 data=b"" if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def step_done(story, step):
    for s in call("/api/stories")["stories"]:
        if s["id"] == story:
            return next(x for x in s["steps"] if x["id"] == step)["done"]


def run(story, step, timeout=240):
    call(f"/api/stories/{story}/{step}/run", "POST")
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(3)
        if step_done(story, step):
            time.sleep(4)
            return
    raise SystemExit(f"timeout: {story}/{step}")


def main():
    from playwright.sync_api import sync_playwright
    call("/api/session/reset", "POST")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")

        def shot(name, frag, w=1700, h=1050, clip=None):
            page = b.new_page(viewport={"width": w, "height": h})
            page.goto(f"{API}/?session={SID}{frag}", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            skip = page.get_by_role("button", name="Skip")
            if skip.count():
                skip.first.click()   # the welcome tour would cover the screenshot
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / f"{name}.png"), clip=clip)
            page.close()
            print(name)

        run("booking", "ask")
        shot("trace1_whatsapp", "#therapist/messages/wa:p_valentina")
        shot("trace1_approvals", "#therapist/approvals")
        run("newpatient", "notes")
        shot("trace2_health", "#therapist/chat/health")
        shot("trace2_folder", "#therapist/folders/p_javier", h=1100)
        shot("trace_costs", "#therapist/costs")
        b.close()


main()
