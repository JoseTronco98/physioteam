"""End-to-end journey through the HTTP API (server must be running). Run: python -m tests.api_journey"""

import json
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
H = {"X-Session": f"journey{int(time.time())}", "Content-Type": "application/json"}
sys.stdout.reconfigure(encoding="utf-8")


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, headers=H, data=json.dumps(body or {}).encode() if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"null")


def wait_idle(limit=120):
    t0 = time.time()
    time.sleep(1.5)
    while time.time() - t0 < limit:
        if not call("GET", "/api/state")["busy"]:
            return
        time.sleep(1.5)


def say(text, attachment=None):
    call("POST", "/api/threads/wa:p_sofia/send", {"text": text, "attachment_id": attachment})
    wait_idle()


call("POST", "/api/session/reset")
call("POST", "/api/personas/sofia/start", {"lang": "en"})
say("Hi! Dr. Ortiz referred me for physio after my arm fracture. How much is it, and what's the difference between Redcord and conventional?")
say("Here is my referral", "demo_referral")
say("Could I come Wednesday afternoon?")
msgs = call("GET", "/api/threads/wa:p_sofia/messages")
last = msgs[-1]["text"]
print("ASSISTANT:", last[:300])
slot_pick = "The first one works for me"
say(slot_pick)
say("I fell on my arm skiing in September, surgery with a plate on Sept 12. Pain 4/10, I work at an office, no other conditions, I take ibuprofen sometimes.")
call("POST", "/api/personas/sofia/day_before")
wait_idle()
call("POST", "/api/personas/sofia/session_happens")
wait_idle(240)
for m in call("GET", "/api/threads/wa:p_sofia/messages"):
    print(f"{m['role']:>8} > {m['text'][:240]}")
folder = call("GET", "/api/patients/p_sofia")
for d in folder["documents"]:
    filled = [f for f in d["fields"] if f["value"]]
    print("DOC", d["kind"], "v", d["version"], d["status"], f"{len(filled)}/{len(d['fields'])} filled",
          sorted({f['source'] for f in filled}))
print("HEALTH THREAD:", [m["text"][:200] for m in call("GET", "/api/threads/health/messages")][-3:])
sp = call("GET", "/api/spend")
print("SPEND product", sp["session_usd"], "sim", sp["simulator"]["usd"])
print("MISSIONS", [m["id"] for m in call("GET", "/api/missions?mode=patient") if m["done"]])
