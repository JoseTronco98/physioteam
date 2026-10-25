"""Agents produce the PDF deliverables end to end. Session notes come from the simulator's therapist bot.
Run: python -m tests.deliverables <outdir>"""

import asyncio
import sys
from pathlib import Path

from backend import agents, pdfdocs, runtime, sim, store

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")


async def main():
    s = runtime.reset_session("deliv")
    sim.schedule_week(s)
    s.c["mode"] = "therapist"
    p = s.c["patients"]["p_mariana"]
    p["status"] = "new"
    notes = await sim.therapist_notes(s, "p_mariana", first_visit=True)
    print("BOT NOTES:\n", notes, "\n")
    await agents.therapist_turn(s, "health", f"First visit notes for Mariana Lopez. Complete the evaluation and propose the treatment plan:\n{notes}", "rD1")
    await agents.therapist_turn(s, "team", "Create a progress report for Hector Ruiz and save it in his folder", "rD2")
    for pid, kind in (("p_mariana", "evaluation"), ("p_mariana", "treatment_plan"), ("p_hector", "progress_report")):
        d = store.find_doc(s.c, pid, kind)
        if not d:
            print("MISSING", pid, kind)
            continue
        data = d["versions"][-1].get("data") or {}
        print(kind, "v", d["version"], {k: (len(v) if isinstance(v, list) else bool(v)) for k, v in data.items()})
        (OUT / f"{pid}_{kind}.pdf").write_bytes(pdfdocs.render(s.c, d))
    print("USD", round(s.c["spend"]["usd"], 5))


asyncio.run(main())
