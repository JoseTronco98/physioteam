"""Live checks: 5-week outlook, a new patient's plan books 3x/week, end-of-week doctor reports.
Run: python -m tests.weeks"""

import asyncio
import sys

from backend import agents, approvals, runtime, sim, store

sys.stdout.reconfigure(encoding="utf-8")


def show(s, since, threads=None):
    for m in s.c["messages"]:
        if int(m["id"][1:]) > since and (not threads or m["thread"] in threads):
            print(f"  [{m['thread']}] {m['author']}: {m['text'][:300]}".replace("\n", " "))


async def main():
    s = runtime.reset_session("weeks_test")
    sim.ensure_demo_attachments(s)
    sim.schedule_week(s)
    s.c["mode"] = "therapist"

    print("== Outlook")
    seq = s.c["seq"]
    await agents.therapist_turn(s, "ops", "How full is my agenda over the next 4 weeks, and whose plans end soon?", "w1")
    show(s, seq, {"ops"})

    print("\n== First visit -> plan approved -> sessions booked")
    await sim.try_mission(s, "t_first_visit", "w2")
    ask = next(m for m in s.c["messages"][::-1] if m.get("suggest_attachment"))
    await agents.therapist_turn(s, "health", "Here are my notes from the session.", "w2b", ask["suggest_attachment"]["id"])
    plan = next((a for a in s.c["approvals"].values() if a["kind"] == "plan_change" and a["status"] == "pending"), None)
    if plan:
        seq = s.c["seq"]
        approvals.resolve(s, plan["id"], "approve")
        show(s, seq)
        pid = plan["patient_id"]
        print("  booked:", [store.nice(a["start"]) for a in store.upcoming_for(s.c, pid)][:8])

    print("\n== End of week: doctor reports")
    seq = s.c["seq"]
    await sim.try_mission(s, "t_weekly_reports", "w3")
    card = next(a for a in s.c["approvals"].values() if a["kind"] == "weekly_reports")
    print("  card:", card["title"], "|", card["detail"][:300].replace("\n", " "))
    approvals.resolve(s, card["id"], "approve")
    await sim.draft_weekly_reports(s, "w3b")
    show(s, seq, {"health"})
    sends = [a for a in s.c["approvals"].values() if a["kind"] == "outbound_message" and a["status"] == "pending"]
    print("  send cards:", [a["title"] for a in sends])
    for d in s.c["documents"].values():
        if d["kind"] == "progress_report":
            print("  ", store.doc_filename(s.c, d))
    print("\nUSD product", round(sum(b["usd"] for b in s.c["spend"]["product"].values()), 5))


asyncio.run(main())
