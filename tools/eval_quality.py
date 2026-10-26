"""Quality of the Clinical Scribe on the 30 sample therapist notes (live model, about $0.06, 3-5 minutes).

For each note: run the same scribe the Health Advisor uses (evaluation form for first visits, SOAP for
follow-ups) and measure
  - completeness: share of form fields filled (evaluation: 38 fields; SOAP: S, O, A, P)
  - grounding: share of numbers in the draft that also appear in the therapist's notes. A number in the
    draft that is not in the notes is a candidate invented value; each one is listed for manual review.
  - latency and cost per document.

Run: python -m tools.eval_quality <out.json>
"""

import asyncio
import json
import re
import sys
import time

from backend import agents, config, runtime, sim, store

sys.stdout.reconfigure(encoding="utf-8")
OUT = sys.argv[1] if len(sys.argv) > 1 else "eval_quality.json"
NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])")


def numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in NUM.findall(text or "")}


def flat(v) -> str:
    return json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v


async def one(s, note: dict, sem: asyncio.Semaphore) -> dict:
    text = sim.note_text(note)
    p = s.c["patients"][note["patient_id"]]
    ctx = agents.Ctx(s=s, agent="clinical_scribe", run_id=f"q_{note['id']}", thread="health")
    t0 = time.time()
    usd0 = s.c["spend"]["usd"]
    async with sem:
        if note["note_kind"] == "evaluation":
            draft = await agents.run("clinical_scribe", agents.clinical_scribe_eval, ctx,
                                     f"FORM: initial evaluation.\nPATIENT: {p['name']}, {p['age']}, {p['condition']}\n"
                                     f"INTAKE CHAT ANSWERS (source intake_chat): {{}}\nTHERAPIST SESSION NOTES (source session_notes): {text}",
                                     lead=False)
            fields, data, vals, missing = agents.evaluation_parts(draft.model_dump(), {})
            filled = sum(1 for f in fields if f["value"])
            total = len(fields)
            out_text = " ".join(flat(v) for v in vals.values() if v) + " " + flat(data)
            extra = {"dx": bool(vals.get("pt_impression")), "prognosis": bool(vals.get("prognosis")),
                     "rom_rows": len(data["rom"]), "strength_rows": len(data["strength"]), "tests_rows": len(data["special_tests"])}
        else:
            draft = await agents.run("clinical_scribe", agents.clinical_scribe_soap, ctx,
                                     f"FORM: SOAP note for today's session.\nPATIENT: {p['name']}, {p['condition']}\nNOTES: {text}", lead=False)
            v = draft.model_dump()
            filled = sum(1 for k in ("subjective", "objective", "assessment", "plan") if v.get(k))
            total = 4
            out_text = " ".join(flat(v.get(k) or "") for k in ("subjective", "objective", "assessment", "plan"))
            extra = {}
    src_nums, out_nums = numbers(text), numbers(out_text)
    ungrounded = sorted(out_nums - src_nums, key=lambda x: float(x))
    return {"note": note["name"], "kind": note["note_kind"], "patient": p["name"], "filled": filled, "total": total,
            "numbers_in_draft": len(out_nums), "grounded": len(out_nums) - len(ungrounded), "ungrounded": ungrounded,
            "seconds": round(time.time() - t0, 1), "usd": round(s.c["spend"]["usd"] - usd0, 6), **extra}


async def main():
    s = runtime.reset_session("quality_eval")
    sem = asyncio.Semaphore(1)  # one at a time so cost and latency per document are clean
    rows = []
    for n in sim.NOTE_FILES:
        r = await one(s, n, sem)
        rows.append(r)
        print(f"{r['kind']:10} {r['patient']:18} filled {r['filled']}/{r['total']}  grounded {r['grounded']}/{r['numbers_in_draft']}  "
              f"{r['seconds']}s ${r['usd']:.5f}  ungrounded={r['ungrounded']}")
    summary = {}
    for kind in ("evaluation", "soap"):
        xs = [r for r in rows if r["kind"] == kind]
        nums = sum(r["numbers_in_draft"] for r in xs)
        summary[kind] = {"documents": len(xs),
                         "completeness_pct": round(100 * sum(r["filled"] for r in xs) / sum(r["total"] for r in xs), 1),
                         "grounded_numbers_pct": round(100 * sum(r["grounded"] for r in xs) / nums, 1) if nums else None,
                         "numbers_checked": nums,
                         "median_seconds": sorted(r["seconds"] for r in xs)[len(xs) // 2],
                         "avg_usd": round(sum(r["usd"] for r in xs) / len(xs), 6)}
        if kind == "evaluation":
            summary[kind]["dx_captured"] = sum(r["dx"] for r in xs)
            summary[kind]["prognosis_captured"] = sum(r["prognosis"] for r in xs)
    data = {"model": config.MODEL_NAME, "measured": time.strftime("%Y-%m-%d %H:%M"), "summary": summary, "rows": rows}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, indent=1))


asyncio.run(main())
