"""Measure the numbers for the report (live model; about $0.06 and 6-8 minutes).

1. Plays the five stories in one clinic session ("report") and records tokens and cost per step and per agent.
   The session is saved, so the screenshots can be taken from it (open the app with ?session=report).
2. Runs a full simulated week on autopilot in another session and records the weekly totals.
3. Extracts one traced run (Valentina's first message) from the audit trail.

Run: python -m tools.report_data <out.json>
"""

import asyncio
import json
import sys
import time

from backend import config, runtime, sim, stories, store

sys.stdout.reconfigure(encoding="utf-8")
OUT = sys.argv[1] if len(sys.argv) > 1 else "report_data.json"


def totals(s) -> dict:
    t = {"usd": 0.0, "input_tokens": 0, "cached_tokens": 0, "cache_write_tokens": 0, "output_tokens": 0, "calls": 0}
    for b in s.c["spend"]["product"].values():
        for k in t:
            t[k] += b[k]
    return t


def diff(a: dict, b: dict) -> dict:
    return {k: round(b[k] - a[k], 6) if k == "usd" else b[k] - a[k] for k in a}


async def play_stories() -> dict:
    s = runtime.reset_session("report")
    sim.ensure_demo_attachments(s)
    sim.schedule_week(s)
    s.c["mode"], s.c["tour_done"] = "therapist", True
    steps, t0 = [], time.time()
    for story in stories.STORIES:
        for (step, actor, title, *_r) in story["steps"]:
            before, seq, w = totals(s), s.c["seq"], time.time()
            rid = f"rep_{story['id']}_{step}"
            await stories.run_step(s, story["id"], step, rid)
            d = diff(before, totals(s))
            steps.append({"story": story["id"], "step": step, "actor": actor, "title": title, "run_id": rid,
                          "seconds": round(time.time() - w, 1), "messages": s.c["seq"] - seq, **d})
            print(f"{story['id']:10} {step:9} ${d['usd']:.5f} in={d['input_tokens']} cached={d['cached_tokens']} out={d['output_tokens']}")
    s.save()
    return {"steps": steps, "by_agent": s.c["spend"]["product"], "total": totals(s),
            "simulator_usd": s.c["spend"]["simulator"].get("simulator", {}).get("usd", 0.0),
            "wall_seconds": round(time.time() - t0), "safety": s.c["safety"][-12:],
            "satisfaction": None}


async def autopilot_week() -> dict:
    s = runtime.reset_session("report_autopilot")
    sim.ensure_demo_attachments(s)
    sim.schedule_week(s)
    s.c["mode"] = "autopilot"
    t0 = time.time()
    await sim.run_autopilot(s, days=5)
    st = sim.autopilot_stats(s)
    st.update(wall_seconds=round(time.time() - t0), total=totals(s), by_agent=s.c["spend"]["product"],
              weekly_report=sim.weekly_report(s))
    s.save()
    return st


def trace(run_id: str) -> list[dict]:
    rows = []
    for line in config.AUDIT_FILE.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("session") == "report" and r.get("run_id") == run_id:
            rows.append({k: r.get(k) for k in ("event", "agent", "tool", "summary", "usage", "usd", "seconds", "thread")})
    return rows


def extras(data: dict) -> dict:
    """Facts the report needs from the two saved sessions (so the report rebuilds from this JSON alone)."""
    import collections
    rc = runtime.get_session("report").c
    ac = runtime.get_session("report_autopilot").c
    wa = [m for m in ac["messages"] if m["thread"].startswith("wa:")]
    fb = [f for f in ac.get("feedback", []) if f.get("rating") and f["asked"] >= store.WEEK_START]
    week = store.appointments_between(ac, store.WEEK_START[:10] + "T00:00", "2026-11-01T00:00")
    first = next(m["text"] for m in rc["messages"] if m["thread"] == "wa:p_valentina" and m["role"] == "patient")
    def fname(c, pid, kind):
        ds = [d for d in c["documents"].values() if d["patient_id"] == pid and d["kind"] == kind]
        return store.doc_filename(c, ds[-1]) if ds else ""
    data["week_activity"] = {
        "inbound": sum(1 for m in wa if m["role"] == "patient"),
        "feedback_ratings": len(fb), "feedback_avg": round(sum(f["rating"] for f in fb) / max(1, len(fb)), 2),
        "outbound_model": sum(1 for m in wa if m["role"] == "agent" and "cost_usd" in m),
        "outbound_code": sum(1 for m in wa if m["role"] == "agent" and "cost_usd" not in m),
        "reminders": sum(1 for m in wa if "Reminder:" in m["text"]),
        "sessions_done": sum(1 for a in week if a["status"] == "done"),
        "evaluations_done": sum(1 for a in week if a["status"] == "done" and a["service"] == "evaluation"),
        "agent_documents": dict(collections.Counter(d["kind"] for d in ac["documents"].values()
                                                    if d["versions"][-1]["author"] != "therapist" and d["versions"][-1]["created"] >= store.WEEK_START)),
        "approvals": dict(collections.Counter(f"{a['kind']}:{a['status']}" for a in ac["approvals"].values())),
        "escalations_now": sum(1 for m in ac["messages"] if m["thread"] in ("health", "ops") and "Needs you" in m["text"]),
        "batched_questions": len(ac.get("next_session_questions", [])),
        "recovered": ac.get("recovered", []),
    }
    data["t1_text"] = first
    data["files"] = {"eval_javier": fname(rc, "p_javier", "evaluation"), "plan_javier": fname(rc, "p_javier", "treatment_plan")}
    data["safety_log"] = dict(collections.Counter(e["kind"] for e in rc["safety"]))
    return data


async def main():
    if "--extras-only" in sys.argv:   # patch an existing JSON from the saved sessions, no model calls
        path = sys.argv[1]
        d = json.loads(open(path, encoding="utf-8").read())
        with open(path, "w", encoding="utf-8") as f:
            json.dump(extras(d), f, ensure_ascii=False, indent=1, default=str)
        print("extras added:", d["week_activity"], d["files"], d["safety_log"])
        return
    data = {"model": config.MODEL_NAME, "prices_per_million": config.PRICES[config.MODEL_NAME], "measured": time.strftime("%Y-%m-%d %H:%M")}
    data["stories"] = await play_stories()
    data["trace_valentina_ask"] = trace("rep_booking_ask")
    data["trace_javier_notes"] = trace("rep_newpatient_notes")
    data["autopilot"] = await autopilot_week()
    extras(data)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, default=str)
    a = data["autopilot"]
    print("\nstories total", data["stories"]["total"], "\nautopilot product $", a["product_usd"], "msgs", a["messages"],
          "cached%", a["cached_share_pct"], "tokens/patient-week", a["tokens_per_patient_week"])


asyncio.run(main())
