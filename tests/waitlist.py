"""Freed slot -> therapist card -> offer -> waitlisted patient says yes -> booked.
Run: python -m tests.waitlist"""

import asyncio
import sys

from backend import agents, approvals, runtime, sim

sys.stdout.reconfigure(encoding="utf-8")


def show(s, since):
    for m in s.c["messages"]:
        if int(m["id"][1:]) > since:
            print(f"  [{m['thread']}] {m['author']}: {m['text'][:160]}")


async def scenario(s, when, event_who):
    ev = next(e for e in s.c["events"] if e["who"] == event_who and e["time"] == when)
    s.c["now"] = when
    seq = s.c["seq"]
    await sim.fire_event(s, ev)
    show(s, seq)
    cards = [a for a in s.c["approvals"].values() if a["kind"] == "waitlist_offer" and a["status"] == "pending"]
    print("CARDS:", [(a["title"], [o["label"] for o in a["options"]]) for a in cards])
    if not cards:
        return
    print("  if_approve:", cards[0]["if_approve"], "\n  preview:", cards[0]["preview"])
    seq = s.c["seq"]
    approvals.resolve(s, cards[0]["id"], "offer")
    to = s.c["approvals"][cards[0]["id"]]["offered_to"]
    await sim.replies_to_outreach(s, seq, "rW", only={to})
    show(s, seq)


async def main():
    s = runtime.reset_session("waitlist_test")
    sim.schedule_week(s)
    s.c["mode"] = "therapist"
    print("== Marisol cancels Thu 13:00 (Paola wants Thursday afternoons)")
    await scenario(s, "2026-10-28T09:30", "p_marisol")
    print("\n== Diego cancels Tue 19:00 the same day (Luis wants after 18:00)")
    await scenario(s, "2026-10-27T15:00", "p_diego")
    print("PENDING WAITLIST CARDS:", [a["title"] for a in s.c["approvals"].values() if a["kind"] == "waitlist_offer" and a["status"] == "pending"])

    print("\n== Decline path (code only): Paola back on the list, says no, nobody else fits")
    s.c["waitlist"] = ["p_paola"]
    seq = s.c["seq"]
    agents.make_offer(s, "p_paola", "2026-10-30T13:00", ["p_paola"])
    sim.quick_reply(s, "p_paola", "Oh no, I can't on Friday, sorry!")
    show(s, seq)
    print("\nRECOVERED:", s.c["recovered"])
    print("WAITLIST:", s.c["waitlist"])
    print("USD", round(s.c["spend"]["usd"], 5))


asyncio.run(main())
