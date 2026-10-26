"""Replay the three demos run with the therapist in the user test, and record every step for the report.

Demo 1 = story "The hard-to-book patient" (booking), Demo 2 = story "A new patient's month" up to the signed
evaluation and plan (clinical reports), Demo 3 = story "Running the clinic, and the results" (finances).
All three run one after the other in one clinic session ("demos"), as in the user test.
For every step it records: who acted, the messages it produced, each agent run (agent, tools called, tokens,
cost, seconds) from the audit trail, and approval cards. Live model: about $0.04 and 6 minutes.

Run: python -m tools.demo_runs report/data/demo_runs.json
Then screenshots (server on port 8001 without an access code): python -m tools.demo_shots report/shots
"""

import asyncio
import json
import sys
import time

from backend import config, runtime, sim, stories

sys.stdout.reconfigure(encoding="utf-8")
OUT = sys.argv[1] if len(sys.argv) > 1 else "demo_runs.json"

DEMOS = [
    {"id": "demo1", "story": "booking", "title": "Booking: the hard-to-book patient", "steps": None},
    {"id": "demo2", "story": "newpatient", "title": "Clinical reports: a new patient's first visit",
     "steps": ["hello", "intake", "ok", "session", "notes", "sign"]},
    {"id": "demo3", "story": "results", "title": "Finances: who owes money, and the results of the week",
     "steps": ["day", "late", "block", "family", "pay", "endday", "owes", "risk", "week", "ask"]},
]
FOCUS = {"demo3": {"endday", "owes", "week", "ask"}}   # steps shown in the video; the others set up the day
LABEL = {"patient_success": "Patient Success", "ops_partner": "Operations Partner", "health_advisor": "Health Advisor",
         "finance_ops": "Finance Ops", "clinical_scribe": "Clinical Scribe", "imaging_reader": "Imaging Reader",
         "router": "Router"}


def totals(s) -> dict:
    t = {"usd": 0.0, "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "calls": 0}
    for b in s.c["spend"]["product"].values():
        for k in t:
            t[k] += b[k]
    return t


def audit(session: str, run_id: str) -> list[dict]:
    rows = []
    for line in config.AUDIT_FILE.read_text(encoding="utf-8").splitlines():
        if run_id not in line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("session") == session and r.get("run_id") == run_id:
            rows.append(r)
    return rows


def short(text: str, n: int = 260) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n - 1].rsplit(" ", 1)[0] + " …"


SID = "demos"


async def play(demo: dict, first: bool) -> dict:
    s = runtime.reset_session(SID) if first else runtime.get_session(SID)
    if first:
        sim.ensure_demo_attachments(s)
        sim.schedule_week(s)
        s.c["mode"], s.c["tour_done"] = "therapist", True
    story = stories.BY_ID[demo["story"]]
    wanted = demo["steps"] or [x[0] for x in story["steps"]]
    out = []
    for (step, actor, title, *_r) in story["steps"]:
        if step not in wanted:
            continue
        before, nmsg, napp, w = totals(s), len(s.c["messages"]), len(s.c.get("approvals", {})), time.time()
        status0 = {k: a["status"] for k, a in s.c["approvals"].items()}
        rid = f"{demo['id']}_{step}_{int(time.time())}"   # unique per replay, so the audit rows are this run's only
        await stories.run_step(s, demo["story"], step, rid)
        after = totals(s)
        runs = []
        tools: list[dict] = []
        for r in audit(SID, rid):
            if r["event"] == "tool":
                tools.append({"agent": LABEL.get(r.get("agent"), r.get("agent")), "tool": r.get("tool"),
                              "summary": short(r.get("summary"), 160)})
            elif r["event"] == "agent_run":
                u = r.get("usage") or {}
                runs.append({"agent": LABEL.get(r.get("agent"), r.get("agent")), "thread": r.get("thread"),
                             "tools": [t["tool"] for t in tools if t["agent"] == LABEL.get(r.get("agent"), r.get("agent"))],
                             "input_tokens": u.get("input_tokens", 0), "cached_tokens": u.get("cached_tokens", 0),
                             "output_tokens": u.get("output_tokens", 0), "calls": u.get("calls", 0),
                             "usd": r.get("usd") or 0, "seconds": r.get("seconds"), "output": short(r.get("output"), 300)})
        msgs = [{"thread": m["thread"], "role": m["role"], "author": m["author"], "text": short(m["text"])}
                for m in s.c["messages"][nmsg:]]
        apps = list(s.c.get("approvals", {}).values())[napp:]
        decided = [{"title": short(a.get("title"), 120), "status": a["status"]} for k, a in s.c["approvals"].items()
                   if k in status0 and status0[k] != a["status"]]
        out.append({"step": step, "actor": actor, "title": title, "focus": step in FOCUS.get(demo["id"], {step}),
                    "seconds": round(time.time() - w, 1), "usd": round(after["usd"] - before["usd"], 6),
                    "input_tokens": after["input_tokens"] - before["input_tokens"],
                    "cached_tokens": after["cached_tokens"] - before["cached_tokens"],
                    "output_tokens": after["output_tokens"] - before["output_tokens"],
                    "calls": after["calls"] - before["calls"], "runs": runs, "tools": tools, "messages": msgs,
                    "approvals": [{"kind": a.get("kind"), "title": short(a.get("title"), 120)} for a in apps],
                    "decided": decided})
        print(f"{demo['id']} {step:8} ${out[-1]['usd']:.5f} runs={len(runs)} tools={len(tools)} msgs={len(msgs)}")
    s.save()
    return {"id": demo["id"], "story": demo["story"], "title": demo["title"], "steps": out,
            "usd": round(sum(x["usd"] for x in out), 6), "seconds": round(sum(x["seconds"] for x in out), 1)}


async def main():
    data = {"measured": time.strftime("%Y-%m-%d %H:%M"), "model": config.MODEL_NAME, "demos": []}
    for i, d in enumerate(DEMOS):
        data["demos"].append(await play(d, first=i == 0))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("wrote", OUT, "total $", round(sum(d["usd"] for d in data["demos"]), 4))


asyncio.run(main())
