"""Generate the clinical history of the active patients (run once; the JSON is committed).

For each patient: the initial evaluation (clinic form, every section), the treatment plan (3x/week,
phases, goals) and one SOAP note per session already done, progressing realistically. All fictional,
written by the course model playing the clinic's therapist.

Run: python -m tools.make_history
"""

import asyncio
import json
import sys
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from backend import agents, config, store

sys.stdout.reconfigure(encoding="utf-8")
OUT = config.BACKEND / "clinical_history.json"


class PlanDraft(BaseModel):
    conventional_sessions: int
    redcord_sessions: int
    shockwave_sessions: int
    focus: str
    goals: str
    next_session: str
    review_point: str
    phases: list[agents.PlanPhase]
    short_term_goals: list[str]
    long_term_goals: list[str]
    precautions: list[str]
    home_program: list[str] = Field(description="Numbered exercises: name, sets x reps, frequency, one cue")
    review_points: list[str]


class SoapEntry(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str


class SoapSeries(BaseModel):
    sessions: list[SoapEntry]


EVAL = """You are the clinic's physical therapist. Fill the clinic's initial evaluation form for this patient as you did
at the first visit, in English, complete and realistic: every section (family history with the checklist, personal
history, lifestyle with alcohol/smoking/exercise/stress/sleep, height/weight/BMI, mechanism and date, patient goals, pain
VAS best/worst/now with pattern and description, aggravating and relieving, posture and body chart, imaging, medications,
sensation, palpation with inflammation/scar/joint play, ROM table, strength table, special tests table, functional tests,
observations, problems, short and long-term goals, treatment, your physiotherapy diagnosis, your prognosis). Values must be
consistent with the condition and with these known facts (write it as the real form; never call anything illustrative,
hypothetical or a placeholder):"""

PLAN = """You are the clinic's physical therapist. Write the treatment plan you agreed at the first visit: exactly {total}
sessions at 3 sessions per week, split between conventional, Redcord and shockwave as fits the condition (usual therapy:
{service}), with 2-3 phases (weeks, focus, interventions), SMART goals, precautions, a 3-5 exercise home program and review
points. Consistent with this evaluation:"""

SOAPS = """You are the clinic's physical therapist. Write the SOAP notes of this patient's first {n} treatment sessions
(3 per week), one entry per session in order, in English. Each: S (report, pain VAS, adherence), O (re-measured values and
the treatment given with sets x reps / modality), A (response, progress toward goals), P (next session). Show realistic,
gradual progress from the evaluation (with one or two small setbacks), consistent with the plan. Write them as the real
notes of this clinic: never call them illustrative, hypothetical, example or placeholder. Evaluation and plan:"""

writer_eval = Agent(output_type=agents.EvaluationDraft)
writer_plan = Agent(output_type=PlanDraft)
writer_soap = Agent(output_type=SoapSeries)
SET = {"max_tokens": 9000, "timeout": 240}


async def patient(row, sem) -> tuple[str, dict]:
    pid, name, age, cond, status, service, done, total, doc, slots, bal, flags = row
    c = store.new_clinic("hist")
    p = c["patients"][pid]
    dates = store.past_session_dates(slots, done)
    eval_date = store.ts(store.dt(dates[0]) - store.timedelta(days=2)) if dates else "2026-10-19T12:00"
    facts = {"name": name, "age": age, "condition": cond, "referring_doctor": c["doctors"].get(doc or "", {}).get("name"),
             "restrictions": p.get("restrictions"), "evaluation_date": store.nice(eval_date), **store._BASELINES.get(pid, {})}
    async with sem:
        ev = (await writer_eval.run(f"{EVAL}\n{json.dumps(facts, ensure_ascii=False)}", model=agents.model(), model_settings=SET)).output
    fields, data, vals, _ = agents.evaluation_parts(ev.model_dump(), {})
    for f in fields:
        if f["value"]:
            f["source"] = "therapist"
    brief = {k: vals.get(k) for k in ("medical_diagnosis", "pt_impression", "pain_vas", "rom", "strength", "pt_goals", "prognosis")}
    async with sem:
        pl = (await writer_plan.run(f"{PLAN.format(total=total, service=service)}\n{json.dumps(brief, ensure_ascii=False)}",
                                    model=agents.model(), model_settings=SET)).output
    n_conv, n_red, n_shock = pl.conventional_sessions, pl.redcord_sessions, pl.shockwave_sessions
    if n_conv + n_red + n_shock != total:  # keep the agreed total
        n_conv = max(0, total - n_red - n_shock)
    pf, pdata, *_ = agents.plan_parts(p, n_conv, n_red, n_shock, "3x/week", pl.focus, pl.goals, pl.next_session, pl.review_point,
                                      "Per session or 10-session package", pl.phases, pl.short_term_goals, pl.long_term_goals,
                                      pl.precautions, pl.home_program, pl.review_points)
    soaps = []
    if done:
        async with sem:
            ser = (await writer_soap.run(f"{SOAPS.format(n=done)}\n{json.dumps({**brief, 'plan_focus': pl.focus, 'phases': [x.model_dump() for x in pl.phases]}, ensure_ascii=False)}",
                                         model=agents.model(), model_settings=SET)).output
        for i, (d, e) in enumerate(zip(dates, ser.sessions)):
            soaps.append({"date": d, "session": i + 1, **e.model_dump()})
    print(f"{name}: evaluation, plan ({total}), {len(soaps)}/{done} SOAPs")
    return pid, {"eval_date": eval_date, "evaluation": {"fields": fields, "data": data},
                 "plan": {"fields": pf, "data": pdata}, "home_program": "\n".join(pl.home_program), "soaps": soaps}


async def main():
    """No arguments: every patient. With patient ids: only those, merged into the existing file."""
    sem = asyncio.Semaphore(8)
    only = set(sys.argv[1:])
    rows = await asyncio.gather(*(patient(r, sem) for r in store._PATIENTS if not only or r[0] in only))
    old = json.loads(OUT.read_text(encoding="utf-8")) if only and OUT.is_file() else {}
    OUT.write_text(json.dumps({**old, **dict(rows)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT)


asyncio.run(main())
