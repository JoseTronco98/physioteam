import asyncio, sys
from backend import agents, runtime, sim, store
sys.stdout.reconfigure(encoding="utf-8")

async def main():
    s = runtime.reset_session("prog")
    sim.schedule_week(s); s.c["mode"] = "therapist"
    await agents.therapist_turn(s, "team", "Create a progress report for Hector Ruiz and save it in his folder", "rP")
    print([m["text"][:400] for m in s.c["messages"] if m["thread"] == "team"][-1])
    d = store.find_doc(s.c, "p_hector", "progress_report")
    print("DOC:", d["title"], d["status"], "\n", d["versions"][-1]["body_md"][:900])
    print("APPROVALS:", [a["title"] for a in s.c["approvals"].values()])
    print("USD", round(s.c["spend"]["usd"], 5))
asyncio.run(main())
