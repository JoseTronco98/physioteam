"""Therapist asks to move a session; Patient Success messages the patient; the bot patient answers."""
import asyncio
import sys

from backend import runtime, sim

sys.stdout.reconfigure(encoding="utf-8")


async def main():
    s = runtime.reset_session("outreach")
    sim.ensure_demo_attachments(s)
    sim.schedule_week(s)
    s.c["mode"] = "therapist"
    s.c["now"] = "2026-10-26T10:20"
    await sim.therapist_with_replies(s, "team", "I'm running 40 minutes late, move my 11:00 and let the patient know", "rA")
    for m in s.c["messages"]:
        if m["thread"] in ("team", "wa:p_lucia") and m["time"] >= "2026-10-26":
            print(f"[{m['thread']}] {m['author']}: {m['text'][:260]}")
    print("ACTIVITY:")
    for a in s.c["activity"][-14:]:
        print("  ", a["time"][-5:], a.get("agent", ""), a["text"][:120], a.get("cost_usd", ""))
    print("USD", round(s.c["spend"]["usd"], 5), "sim", s.c["spend"]["simulator"].get("simulator", {}).get("usd"))


asyncio.run(main())
