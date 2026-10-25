"""Therapist mode, first events of the week via the HTTP API. Run: python -m tests.api_week_start"""

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8000"
H = {"X-Session": f"week{int(time.time())}", "Content-Type": "application/json"}
sys.stdout.reconfigure(encoding="utf-8")


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, headers=H,
                                 data=json.dumps(body or {}).encode() if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"null")


def wait_idle(limit=180):
    time.sleep(1.5)
    t0 = time.time()
    while time.time() - t0 < limit and call("GET", "/api/state")["busy"]:
        time.sleep(1.5)


call("POST", "/api/session/reset")
call("POST", "/api/session/mode", {"mode": "therapist"})
for _ in range(2):          # Mariana's inquiry, then Dr. Ortiz
    call("POST", "/api/sim/next_event")
    wait_idle()
for th in ("wa:p_mariana", "team", "health", "doc:d_ortiz"):
    print(f"--- {th}")
    for m in call("GET", f"/api/threads/{th}/messages"):
        print(f"  {m['author'][:28]:>28}: {m['text'][:230]}")
print("APPROVALS:", [(a["title"], a["status"]) for a in call("GET", "/api/approvals")])
print("CONVERSATIONS:", [(c["name"], c["flags"]) for c in call("GET", "/api/conversations")][:5])
print("SPEND:", call("GET", "/api/spend")["session_usd"])
