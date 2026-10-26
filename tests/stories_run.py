"""Play every story end to end on a fresh clinic each (live model). Prints the conversation per step.
Run: python -m tests.stories_run [story ids...] > out.txt"""

import asyncio
import sys
import time

from backend import runtime, sim, stories

sys.stdout.reconfigure(encoding="utf-8")


async def play(sid: str) -> list[str]:
    s = runtime.reset_session(f"story_{sid}")
    sim.ensure_demo_attachments(s)
    sim.schedule_week(s)
    s.c["mode"] = "therapist"
    out = [f"\n################ {stories.BY_ID[sid]['title']}"]
    t0 = time.time()
    for (step, actor, title, *_rest) in stories.BY_ID[sid]["steps"]:
        seq = s.c["seq"]
        try:
            await stories.run_step(s, sid, step, f"r_{sid}_{step}")
        except Exception as exc:  # noqa: BLE001
            out.append(f"!! {step} FAILED: {type(exc).__name__}: {exc}")
        out.append(f"\n== [{actor}] {title}   (clock {s.c['now']})")
        for m in s.c["messages"]:
            if int(m["id"][1:]) > seq:
                out.append(f"  [{m['thread']}] {m['author']}: {m['text'][:420]}".replace("\n", " "))
        pend = [f"{a['kind']}:{a['title']}" for a in s.c["approvals"].values() if a["status"] == "pending"]
        out.append(f"  pending cards: {pend}")
    prod = sum(b["usd"] for b in s.c["spend"]["product"].values())
    out.append(f"\n-- {sid}: product ${prod:.4f}, total ${s.c['spend']['usd']:.4f}, {time.time() - t0:.0f}s, "
               f"done {len(s.c['stories'][sid]['done'])}/{len(stories.BY_ID[sid]['steps'])}")
    return out


async def main():
    ids = sys.argv[1:] or [x["id"] for x in stories.STORIES]
    for lines in await asyncio.gather(*(play(i) for i in ids)):
        print("\n".join(lines))


asyncio.run(main())
