"""Live checks for the open items: answers stay on topic, emergencies, feedback, notes -> documents,
English only, mission set-ups. Run: python -m tests.open_items <outdir>"""

import asyncio
import sys
from pathlib import Path

from backend import agents, pdfdocs, runtime, sim, store

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")


def show(s, since, threads=None):
    for m in s.c["messages"]:
        if int(m["id"][1:]) > since and (not threads or m["thread"] in threads):
            print(f"  [{m['thread']}] {m['author']}: {m['text'][:260]}".replace("\n", " "))


async def main():
    s = runtime.reset_session("open_items")
    sim.ensure_demo_attachments(s)
    sim.schedule_week(s)
    s.c["mode"] = "therapist"

    print("== 1. Valeria asks if we treat facial palsy (Patient Success should answer itself)")
    seq = s.c["seq"]
    await sim.try_mission(s, "t_condition_q", "r1")
    show(s, seq)

    print("\n== 2. Open question answered by a short therapist reply (forced escalation)")
    for x in s.c.get("open_questions", []):
        x["status"] = "answered"
    q = agents.open_question(s.c, "p_valeria", "Valeria asks whether we treat facial palsy for her mother Rosa (61), started Saturday.", "ops", "clinical_question")
    seq = s.c["seq"]
    await agents.therapist_turn(s, "ops", "Yes, we treat it. Find her a slot and book her.", "r2")
    show(s, seq)
    print("  question status:", q["status"])

    print("\n== 3. Red flag")
    seq = s.c["seq"]
    await sim.try_mission(s, "t_redflag", "r3")
    show(s, seq, {"wa:p_hector"})

    print("\n== 4. Spanish in, English out")
    seq = s.c["seq"]
    await sim.patient_message(s, "p_ana", "Hola, ¿a qué hora es mi próxima cita?", run_id="r4")
    show(s, seq, {"wa:p_ana"})

    print("\n== 5. Feedback after a session (bot answers in code) + a low rating by hand")
    seq = s.c["seq"]
    await sim.try_mission(s, "t_feedback", "r5")
    agents.ask_feedback(s, "p_jorge")
    sim.quick_reply(s, "p_jorge", "2")
    sim.quick_reply(s, "p_jorge", "We started 20 minutes late and it felt rushed.")
    show(s, seq, {"wa:p_jorge", "ops"})
    print("  satisfaction:", agents.satisfaction(s.c))

    print("\n== 6. First visit: Health Advisor asks; therapist sends sample notes")
    s.c["now"] = "2026-10-26T15:00"
    seq = s.c["seq"]
    await sim.try_mission(s, "t_first_visit", "r6")
    ask = next(m for m in s.c["messages"][::-1] if m.get("suggest_attachment"))
    print("  ask:", ask["text"][:140].replace("\n", " "), "| button:", ask["suggest_attachment"]["label"])
    await agents.therapist_turn(s, "health", "Here are my notes from the session.", "r6b", ask["suggest_attachment"]["id"])
    show(s, seq, {"health"})

    print("\n== 7. Follow-up: SOAP from sample notes")
    seq = s.c["seq"]
    await sim.try_mission(s, "t_soap", "r7")
    ask = next(m for m in s.c["messages"][::-1] if m.get("suggest_attachment"))
    await agents.therapist_turn(s, "health", "Here are my notes from the session.", "r7b", ask["suggest_attachment"]["id"])
    show(s, seq, {"health"})

    for pid in {n["patient_id"] for n in sim.NOTE_FILES}:
        for kind in ("evaluation", "treatment_plan", "soap"):
            d = store.find_doc(s.c, pid, kind)
            if d and d["versions"][-1]["author"] in ("clinical_scribe", "health_advisor"):
                f = {x["key"]: x["value"] for x in d["versions"][-1]["fields"]}
                filled = sum(1 for v in f.values() if v)
                print(f"  {pid} {kind} v{d['version']}: {filled}/{len(f)} fields; prognosis={bool(f.get('prognosis'))} dx={bool(f.get('pt_impression'))}")
                (OUT / f"{pid}_{kind}.pdf").write_bytes(pdfdocs.render(s.c, d))
    print("\nUSD product", round(sum(b["usd"] for b in s.c["spend"]["product"].values()), 5), "total", round(s.c["spend"]["usd"], 5))


asyncio.run(main())
