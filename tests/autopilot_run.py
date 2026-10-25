"""Run autopilot for N days and print the stats. Run: python -m tests.autopilot_run 1"""
import asyncio
import json
import sys
import time

from backend import runtime, sim

sys.stdout.reconfigure(encoding="utf-8")


async def main(days: int):
    s = runtime.reset_session(f"auto{days}")
    sim.ensure_demo_attachments(s)
    sim.schedule_week(s)
    s.c["mode"] = "autopilot"
    t0 = time.time()
    await sim.run_autopilot(s, days)
    st = sim.autopilot_stats(s)
    st.pop("log")
    print(json.dumps(st, indent=1))
    print("errors:", [m["text"][:200] for m in s.c["messages"] if m["author"] == "System"])
    print("product by agent:", {k: round(v["usd"], 5) for k, v in s.c["spend"]["product"].items()})
    print("seconds:", round(time.time() - t0))
    s.save()


asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 1))
