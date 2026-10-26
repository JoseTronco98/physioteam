"""Generate the sample therapist notes used in the demo (run once; the files are committed).

10 first-visit notes (one per new patient's evaluation this week) and 20 follow-up notes (the first
20 recurring sessions of the week). All patients are fictional. The notes are written by the course
model playing a therapist, in the shorthand a busy therapist uses, covering the sections of the
clinic's evaluation form or the SOAP sheet.

Run: python -m tools.make_notes
"""

import asyncio
import json
import sys

from pydantic_ai import Agent

from backend import agents, config, store

sys.stdout.reconfigure(encoding="utf-8")
OUT = config.DEMO_FILES / "notes"

EVAL_PROMPT = """You are an experienced physical therapist writing your notes right after a FIRST VISIT (evaluation).
Write realistic shorthand clinical notes in English, 18-28 lines, organised under these headings, in this order:
ID / Dx (medical dx; your physiotherapy dx) / Family hx (diabetes, HTN, cancer, heart...) / Personal hx (injuries, surgeries,
allergies, venous insufficiency, systemic) / Lifestyle (alcohol, smoking, exercise hrs/wk, stress, sleep, height, weight) /
Mechanism & date / Pt goals / Pain (location, radiation, VAS best/worst/now, pattern, description, aggravating, relieving) /
Posture & body chart / Imaging / Meds / Sensation / Palpation (inflammation, scar, joint play) / ROM (degrees, R and L) /
Strength (0-5, R and L) / Special tests (+/-) / Functional tests / Observations / Problems / Goals (short, long) /
Treatment today / Plan (sessions, frequency, therapy mix: conventional, Redcord or shockwave) / Prognosis.
Use realistic, internally consistent values for this condition. Leave 1-2 minor items "n/t" (not tested) like a busy
therapist. Output only the notes."""

SOAP_PROMPT = """You are an experienced physical therapist writing your notes right after a FOLLOW-UP session.
Write realistic shorthand clinical notes in English, 8-14 lines, under S: / O: / A: / P: headings.
S: patient report, pain VAS now and since last visit, home exercise adherence, function.
O: what you re-measured today (ROM in degrees, strength 0-5, a test or two, gait or swelling) and the treatment given
(techniques, exercises with sets x reps, modality such as Redcord or shockwave if used).
A: response and progress toward goals for this point of the plan (be realistic: most improve, some plateau).
P: next session focus, progressions, home program change.
Use values consistent with the condition and the session number. Output only the notes."""

writer = Agent(output_type=str)


def targets(c: dict) -> list[dict]:
    evals, follow = [], []
    for a in sorted(c["appointments"].values(), key=lambda x: x["start"]):
        if a["status"] != "booked" or a["start"] < store.WEEK_START:
            continue
        p = c["patients"][a["patient_id"]]
        if a["service"] == "evaluation":
            evals.append((a, p))
        elif len(follow) < 20:
            follow.append((a, p))
    return [{"kind": "evaluation", "a": a, "p": p} for a, p in evals] + [{"kind": "soap", "a": a, "p": p} for a, p in follow]


async def one(t: dict, sem: asyncio.Semaphore) -> dict:
    a, p = t["a"], t["p"]
    base = store._BASELINES.get(p["id"], {})
    if t["kind"] == "evaluation":
        brief = f"Patient: {p['name']}, {p['age']}. Reason: {p['condition']}. Planned usual therapy after the evaluation: {p['service']}."
        prompt = EVAL_PROMPT
    else:
        brief = (f"Patient: {p['name']}, {p['age']}. Condition: {p['condition']}. Session {a.get('session_number')} of "
                 f"{p.get('plan_total')}; therapy today: {a['service']}. Restrictions: {p.get('restrictions') or 'none'}. "
                 f"Baseline at evaluation: {json.dumps({k: base[k] for k in ('rom', 'strength', 'pain_vas') if k in base})}")
        prompt = SOAP_PROMPT
    async with sem:
        r = await writer.run(f"{prompt}\n\n{brief}", model=agents.model(),
                             model_settings={"max_tokens": 1600, "timeout": 120})
    day = a["start"][:10]
    fname = f"{'first_visit' if t['kind'] == 'evaluation' else 'session'}_{day}_{a['start'][11:13]}h_{p['name'].split()[0].lower()}.txt"
    title = f"{p['name']} · {'first visit (evaluation)' if t['kind'] == 'evaluation' else 'session ' + str(a.get('session_number'))} · {store.nice(a['start'])}"
    (OUT / fname).write_text(f"Session notes: {title}\n\n{r.output.strip()}\n", encoding="utf-8")
    print("wrote", fname, r.usage.output_tokens, "tokens")
    return {"file": fname, "patient_id": p["id"], "start": a["start"], "kind": t["kind"], "title": title}


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    c = store.new_clinic("notes")
    ts = targets(c)
    print(len([t for t in ts if t["kind"] == "evaluation"]), "first visits,", len([t for t in ts if t["kind"] == "soap"]), "follow-ups")
    sem = asyncio.Semaphore(6)
    index = await asyncio.gather(*(one(t, sem) for t in ts))
    (OUT / "index.json").write_text(json.dumps(sorted(index, key=lambda x: x["start"]), indent=1, ensure_ascii=False), encoding="utf-8")


asyncio.run(main())
