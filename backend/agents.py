"""The PydanticAI agent team.

Therapist-facing leads:   Operations Partner  |  Health Advisor
Sub-agents:               Patient Success, Finance Ops (report to Ops)  |  Clinical Scribe, Imaging Reader (report to Health)
Helpers:                  Router (group chat), simulator bots (outside the product, see sim.py)

Harness (Lecture 4): tools below; memory = per-thread history + clinic records; stopping rules = usage
limits and one cross-lead hand-off per request; guardrails = safety.py + approvals executed in code;
audit trail = runtime.audit for every run and tool call.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent, RunContext
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from . import config, runtime, safety, store
from .runtime import Session

AGENT_INFO = [
    {"id": "ops_partner", "name": "Operations Partner", "role": "Agenda, policies, money, daily ops report", "lead": True, "reports_to": None, "color": "#ff4fa3"},
    {"id": "health_advisor", "name": "Health Advisor", "role": "Evaluations, plans, progress, clinical report", "lead": True, "reports_to": None, "color": "#ff86c0"},
    {"id": "patient_success", "name": "Patient Success", "role": "Talks to patients on WhatsApp", "lead": False, "reports_to": "ops_partner", "color": "#6aa8ff"},
    {"id": "finance_ops", "name": "Finance Ops", "role": "Balances, charges, invoices, business pulse", "lead": False, "reports_to": "ops_partner", "color": "#ffb547"},
    {"id": "clinical_scribe", "name": "Clinical Scribe", "role": "Fills evaluation and SOAP forms", "lead": False, "reports_to": "health_advisor", "color": "#38d39f"},
    {"id": "imaging_reader", "name": "Imaging Reader", "role": "Reads study photos and PDFs (vision)", "lead": False, "reports_to": "health_advisor", "color": "#b48cff"},
    {"id": "router", "name": "Router", "role": "Sends group-chat messages to the right lead", "lead": False, "reports_to": None, "color": "#9a9aa6"},
    {"id": "safety", "name": "Safety layer", "role": "Code rules: injection, red flags, hidden text, caps", "lead": False, "reports_to": None, "color": "#38d39f"},
]
NAMES = {a["id"]: a["name"] for a in AGENT_INFO}

_MODEL: OpenAIResponsesModel | None = None


def model() -> OpenAIResponsesModel:
    global _MODEL
    if _MODEL is None:
        key = config.api_key()
        if not key:
            raise RuntimeError("No PORTKEY_API_KEY or OPENAI_API_KEY found. Put it in .env (this folder or the one above).")
        if config.using_portkey():
            client = AsyncOpenAI(api_key=key, base_url=config.PORTKEY_BASE_URL,
                                 default_headers={"x-portkey-provider": "openai"})
        else:
            client = AsyncOpenAI(api_key=key)
        _MODEL = OpenAIResponsesModel(config.MODEL_NAME, provider=OpenAIProvider(openai_client=client))
    return _MODEL


# ======================================================================================
# Run context
# ======================================================================================
@dataclass
class Ctx:
    s: Session
    agent: str
    run_id: str
    thread: str
    patient_id: str | None = None       # Patient Success: the WhatsApp contact it is talking to
    lang: str = "en"
    depth: int = 0
    shared: dict = field(default_factory=lambda: {"handoffs": 0, "delegations": 0, "tools": [], "agents": []})

    @property
    def c(self) -> dict:
        return self.s.c

    def log(self, tool: str, summary: str) -> None:
        ev = {"agent": self.agent, "tool": tool, "summary": summary[:160]}
        self.shared["tools"].append(ev)
        self.s.emit("tool_called", run_id=self.run_id, **ev)
        runtime.audit(self.s, "tool", run_id=self.run_id, **ev)

    def child(self, agent: str) -> "Ctx":
        return Ctx(s=self.s, agent=agent, run_id=self.run_id, thread=self.thread, patient_id=self.patient_id,
                   lang=self.lang, depth=self.depth + 1, shared=self.shared)


def _settings(s: Session, max_tokens: int = config.MAX_OUTPUT_TOKENS) -> ModelSettings:
    return ModelSettings(cache=bool(s.c.get("caching", True)), max_tokens=max_tokens, timeout=90)


def _trim(history: list) -> list:
    if len(history) <= config.HISTORY_MESSAGES:
        return history
    cut = len(history) - config.HISTORY_MESSAGES
    for i in range(cut, len(history)):
        m = history[i]
        if isinstance(m, ModelRequest) and any(isinstance(p, UserPromptPart) for p in m.parts):
            return history[i:]
    return history[-2:]


async def run(agent_id: str, ag: Agent, ctx: Ctx, prompt: Any, history_key: str | None = None,
              lead: bool = True, simulator: bool = False) -> Any:
    """Run one agent with budget check, events, spend metering, memory and audit."""
    s = ctx.s
    runtime.check_budget(s)
    s.emit("agent_started", run_id=ctx.run_id, agent=agent_id, task=task_label(prompt))
    if agent_id not in ctx.shared["agents"]:
        ctx.shared["agents"].append(agent_id)
    history = s.histories.get(history_key, []) if history_key else []
    limits = UsageLimits(request_limit=config.LEAD_REQUEST_LIMIT if lead else config.SUB_REQUEST_LIMIT,
                         tool_calls_limit=config.MAX_TOOL_CALLS)
    t0 = time.perf_counter()
    try:
        result = await ag.run(prompt, deps=ctx, model=model(), message_history=history or None,
                              usage_limits=limits, model_settings=_settings(s))
    finally:
        s.emit("agent_done", run_id=ctx.run_id, agent=agent_id)
    usd = runtime.record_spend(s, agent_id, result.usage, simulator=simulator)
    ctx.shared.setdefault("usd", 0.0)
    ctx.shared["usd"] += usd
    if history_key:
        s.histories[history_key] = _trim(result.all_messages())
    out = result.output
    runtime.audit(s, "agent_run", run_id=ctx.run_id, agent=agent_id, thread=ctx.thread,
                  prompt=prompt if isinstance(prompt, str) else "multimodal",
                  output=out.model_dump() if hasattr(out, "model_dump") else str(out),
                  usage=runtime.usage_dict(result.usage), usd=round(usd, 6),
                  seconds=round(time.perf_counter() - t0, 2))
    return out


def task_label(prompt: Any) -> str:
    """Human-readable label for the live dashboard (never the internal prompt)."""
    if not isinstance(prompt, str):
        return "Reading a document image"
    for line in prompt.splitlines():
        line = line.strip()
        for tag, prefix in (("THERAPIST", "Therapist: "), ("PATIENT MESSAGE:", "Patient: "), ("HAND-OFF from", "Hand-off: "),
                            ("A REFERRING DOCTOR", "Doctor: "), ("FORM:", "Filling form: ")):
            if line.startswith(tag):
                body = line.split(":", 1)[1].strip() if ":" in line else line
                return (prefix + body)[:90]
    first = next((l for l in prompt.splitlines() if l.strip() and not l.startswith("[")), prompt)
    return first.strip()[:90]


def now_line(c: dict) -> str:
    return f"[Clinic time now: {store.nice(c['now'])} ({c['now']})]"


# ======================================================================================
# Shared helpers used by tools
# ======================================================================================
def find_patient(c: dict, ref: str) -> dict | None:
    if not ref:
        return None
    if ref in c["patients"]:
        return c["patients"][ref]
    r = ref.lower().strip()
    for p in c["patients"].values():
        if r == p["name"].lower() or r in p["name"].lower() or p["name"].lower().split()[0] == r:
            return p
    return None


def patient_brief(c: dict, p: dict, private: bool = True) -> dict:
    up = store.upcoming_for(c, p["id"])
    plan = store.find_doc(c, p["id"], "treatment_plan")
    brief = {
        "patient_id": p["id"], "name": p["name"], "age": p["age"], "condition": p["condition"], "status": p["status"],
        "sessions_done": p["sessions_done"], "plan_total": p["plan_total"], "usual_service": p["service"],
        "balance_mxn": store.balance(c, p["id"]), "flags": p["flags"],
        "upcoming": [{"appointment_id": a["id"], "when": store.nice(a["start"]), "start": a["start"],
                      "service": a["service"], "status": a["status"]} for a in up[:6]],
        "household": [x["name"] for x in c["patients"].values() if p.get("household_id") and x.get("household_id") == p["household_id"] and x["id"] != p["id"]],
        "intake_answers": p.get("intake") or {},
        "home_program": p.get("home_program", ""),
        "restrictions": p.get("restrictions", ""),
    }
    if private and plan:
        brief["treatment_plan"] = store.fields_dict(plan)
    doc_id = p.get("referring_doctor_id")
    if doc_id:
        brief["referring_doctor"] = c["doctors"][doc_id]["name"]
    return brief


def appt_view(c: dict, a: dict) -> dict:
    p = c["patients"].get(a["patient_id"], {})
    return {"appointment_id": a["id"], "patient": p.get("name"), "patient_id": a["patient_id"],
            "patient_language": c.get("persona_lang", {}).get(a["patient_id"]) or p.get("lang", "en"),
            "when": store.nice(a["start"]), "start": a["start"], "service": a["service"], "status": a["status"],
            "session": f"{a['session_number']}/{a['plan_total']}" if a.get("session_number") else None,
            "flags": list(set(a.get("flags", []) + [f for f in p.get("flags", []) if f in ("owes", "red_flag", "at_risk")]))}


def parse_slot(c: dict, text: str) -> str | None:
    """Accept '2026-10-28T17:00' or 'Wed 17:00' style references."""
    if not text:
        return None
    t = text.strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{1,2}):(\d{2})", t)
    if m:
        return f"{m.group(1)}T{int(m.group(2)):02d}:{m.group(3)}"
    days = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "lun": 0, "mar": 1, "mie": 2, "mié": 2,
            "jue": 3, "vie": 4, "sab": 5, "sáb": 5}
    dm = re.search(r"(mon|tue|wed|thu|fri|sat|lun|mar|mi[eé]|jue|vie|s[aá]b)", t.lower())
    hm = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t.lower())
    if dm and hm:
        wd = days[dm.group(1)[:3].replace("mié", "mie")] if dm.group(1)[:3] in days else days.get(dm.group(1)[:3], 0)
        h = int(hm.group(1))
        if hm.group(3) == "pm" and h < 12:
            h += 12
        base = store.dt(c["now"]).replace(hour=0, minute=0)
        for d in range(0, 8):
            day = base + timedelta(days=d)
            if day.weekday() == wd:
                cand = store.ts(day.replace(hour=h))
                if cand > c["now"]:
                    return cand
    return None


def new_approval(ctx: Any, kind: str, title: str, detail: str, options: list[dict], payload: dict,
                 patient_id: str | None = None) -> dict:
    ctx = getattr(ctx, "deps", ctx)
    c = ctx.c
    a = {"id": store.new_id("ap"), "kind": kind, "title": title, "detail": detail, "patient_id": patient_id,
         "created": c["now"], "status": "pending", "options": options, "requested_by": ctx.agent, "payload": payload}
    a.update(describe_approval(c, a))
    c["approvals"][a["id"]] = a
    ctx.s.emit("approval", approval=public_approval(a))
    ctx.shared.setdefault("approvals", []).append(a["id"])
    return a


def describe_approval(c: dict, a: dict) -> dict:
    """Plain-language consequences and a preview of the exact message, so the therapist can decide in one tap.
    The texts mirror what approvals.resolve() actually does."""
    pl, kind = a["payload"], a["kind"]
    p = c["patients"].get(a.get("patient_id") or "", {})
    first = p.get("name", "").split(" ")[0]
    es = patient_lang(c, p["id"]) == "es" if p else False
    out: dict[str, Any] = {"if_approve": [], "if_decline": [], "preview": None, "context": ""}
    if p:
        bits = [p.get("condition", "")]
        intake = p.get("intake") or {}
        for k in ("pain_vas", "can_climb_stairs", "mechanism_and_date"):
            if intake.get(k):
                bits.append(f"{k.replace('_', ' ')}: {intake[k]}")
        if store.balance(c, p["id"]) > 0:
            bits.append(f"owes MXN {store.balance(c, p['id'])}")
        out["context"] = " · ".join(b for b in bits if b)
    if kind == "booking":
        ap = c["appointments"].get(pl["appointment_id"], {})
        when = store.nice(ap.get("start", c["now"]))
        alts = [store.nice(x) for x in store.free_slots(c, limit=2)]
        out["if_approve"] = [f"{when} is confirmed in your agenda", f"{first} gets the confirmation with the address",
                             "The evaluation form is ready for the visit"]
        out["if_decline"] = [f"{first} is offered {' or '.join(alts) or 'other times'} instead", "Nothing is charged"]
        text = (f"Confirmado, {first}: {when} ({ap.get('service')}). Dirección: {c['clinic']['address']} ¡Nos vemos!" if es else
                f"Confirmed, {first}: {when} ({ap.get('service')}). Address: {c['clinic']['address']} See you then!")
        out["preview"] = {"to": p.get("name", ""), "text": text}
    elif kind == "late_cancel_charge":
        amt = pl.get("amount")
        out["if_approve"] = [f"MXN {amt} is added to {first}'s balance", f"{first} is told kindly, citing the 24-hour policy"]
        out["if_decline"] = ["No charge this time (marked as waived once)", f"{first} is asked to give 24 h notice next time"]
        text = (f"Gracias por avisar, {first}. Como acordamos al inicio, las cancelaciones con menos de 24 h se cobran (MXN {amt}). Nos vemos en su próxima sesión." if es else
                f"Thanks for letting us know, {first}. As agreed at the start, cancellations under 24 h are charged (MXN {amt}). We'll see you at your next session.")
        out["preview"] = {"to": p.get("name", ""), "text": text}
    elif kind == "sign_document":
        d = c["documents"].get(pl.get("doc_id", ""), {})
        out["if_approve"] = [f"The {d.get('title', 'document').lower()} is signed and filed in {first}'s folder", "It can be exported to Word"]
        out["if_decline"] = ["It stays as a draft for you to edit"]
    elif kind == "plan_change":
        out["if_approve"] = [f"Plan becomes {pl.get('total')} sessions and replaces the current version", "Future sessions count against the new total"]
        out["if_decline"] = ["The current plan stays as it is"]
    elif kind == "outbound_message":
        did = pl.get("doctor_id")
        d = c["documents"].get(pl.get("doc_id", ""), {})
        body = (d.get("versions") or [{}])[-1].get("body_md") or ""
        to = c["doctors"][did]["name"] if did else p.get("name", "")
        out["if_approve"] = [f"It is sent to {to}", "A signed copy stays in the folder"]
        out["if_decline"] = ["Nothing is sent; the draft stays in the folder"]
        out["preview"] = {"to": to, "text": body[:700]}
    elif kind == "invoice_request":
        out["if_approve"] = ["The request goes to your accountant's outbox", f"{first} is told it's on its way"]
        out["if_decline"] = ["Nothing is sent to the accountant"]
    return out


def public_approval(a: dict) -> dict:
    out = {k: v for k, v in a.items() if k != "payload"}
    out["doc_id"] = (a.get("payload") or {}).get("doc_id")
    return out


APPROVE = [{"id": "approve", "label": "Approve", "primary": True}, {"id": "reject", "label": "Reject"}]


def patient_lang(c: dict, pid: str) -> str:
    return c.get("persona_lang", {}).get(pid) or c["patients"].get(pid, {}).get("lang", "en")


def send_to_patient(s: Session, pid: str, text: str, author: str = "Movimiento Fisioterapia (AI assistant)",
                    agent: str = "patient_success", **extra) -> dict:
    """All outbound patient messages pass the last safety check."""
    reason = safety.check_outbound(text)
    if reason:
        s.safety("injection_direct", "held", f"Held outgoing message to {s.c['patients'][pid]['name']}: {reason}", pid)
        text = ("Let me check that with the therapist and get back to you." if patient_lang(s.c, pid) == "en"
                else "Déjeme consultarlo con la terapeuta y le confirmo.")
    if needs_disclosure(s.c, pid) and not re.search(r"\bAI assistant|asistente (de IA|virtual)", text, re.I):
        text = (DISCLOSURE["es"] if patient_lang(s.c, pid) == "es" else DISCLOSURE["en"]) + "\n\n" + text
    return s.add_message(f"wa:{pid}", "agent", author, text, agent=agent, **extra)


DISCLOSURE = {
    "en": "Hi! I'm the AI assistant of Movimiento Fisioterapia. I help with appointments, payments and questions; anything clinical is reviewed by Lic. Ana.",
    "es": "¡Hola! Soy el asistente de IA de Movimiento Fisioterapia. Le ayudo con citas, pagos y dudas; todo lo clínico lo revisa la Lic. Ana.",
}


def needs_disclosure(c: dict, pid: str) -> bool:
    """A conversation starts when the clinic has not written in the last 12 hours: say we are an AI."""
    thread = [m for m in c["messages"] if m["thread"] == f"wa:{pid}"]
    last_agent = next((m for m in reversed(thread) if m["role"] == "agent"), None)
    if not last_agent:
        return True
    return (store.dt(c["now"]) - store.dt(last_agent["time"])).total_seconds() > 12 * 3600


# ======================================================================================
# Structured outputs
# ======================================================================================
class RomRow(BaseModel):
    joint: str = Field(description="e.g. 'Knee R', 'Shoulder L'")
    movement: str
    right: Optional[str] = None
    left: Optional[str] = None
    normal: Optional[str] = Field(None, description="Reference value only if stated or standard (e.g. knee flexion 135°)")


class StrengthRow(BaseModel):
    muscle: str
    right: Optional[str] = None
    left: Optional[str] = None


class TestRow(BaseModel):
    test: str
    right: Optional[str] = Field(None, description="'+', '-' or a short result")
    left: Optional[str] = None
    notes: Optional[str] = None


class FunctionalRow(BaseModel):
    test: str
    result: str


class PainInfo(BaseModel):
    best: Optional[str] = None
    worst: Optional[str] = None
    now: Optional[str] = None
    location: Optional[str] = None
    pattern: Optional[str] = None


class PlanPhase(BaseModel):
    name: str = Field(description="e.g. 'Phase 1 · Mobility and pain'")
    weeks: str = Field(description="e.g. '1-2'")
    focus: str
    interventions: str


class OutcomeRow(BaseModel):
    measure: str = Field(description="e.g. 'Knee flexion R', 'Pain (VAS)', 'Gait'")
    baseline: Optional[str] = None
    latest: Optional[str] = None
    change: Optional[str] = Field(None, description="e.g. '+23°', 'improving', 'not re-measured'")


class GoalStatus(BaseModel):
    goal: str
    status: str = Field(description="'met', 'progressing', 'not yet', or 'not re-measured'")


class EvaluationDraft(BaseModel):
    """Values for the clinic's evaluation form. Use null for anything not explicitly stated."""
    occupation: Optional[str] = None
    medical_diagnosis: Optional[str] = None
    referring_doctor: Optional[str] = None
    chief_complaint: Optional[str] = None
    mechanism_and_date: Optional[str] = None
    family_history: Optional[str] = None
    medical_history: Optional[str] = None
    previous_injuries: Optional[str] = None
    surgeries: Optional[str] = None
    allergies: Optional[str] = None
    medications: Optional[str] = None
    lifestyle: Optional[str] = None
    height_weight: Optional[str] = None
    can_climb_stairs: Optional[str] = None
    pain_location: Optional[str] = None
    pain_vas: Optional[str] = None
    pain_pattern: Optional[str] = None
    aggravating_factors: Optional[str] = None
    relieving_factors: Optional[str] = None
    posture: Optional[str] = None
    palpation: Optional[str] = None
    rom: Optional[str] = None
    strength: Optional[str] = None
    sensation: Optional[str] = None
    special_tests: Optional[str] = None
    functional_tests: Optional[str] = None
    imaging: Optional[str] = None
    patient_goals: Optional[str] = None
    pt_impression: Optional[str] = Field(None, description="Only if the therapist stated an impression; label it as the therapist's impression.")
    pt_problems: Optional[str] = None
    pt_goals: Optional[str] = None
    treatment: Optional[str] = None
    from_session_notes: list[str] = Field(default_factory=list, description="Keys whose value came from the session notes (not the intake chat).")
    missing_important: list[str] = Field(default_factory=list, description="Important keys still empty that the therapist should fill.")
    # Tables for the evaluation PDF. Only rows actually measured or stated; never invent values.
    pain_detail: Optional[PainInfo] = None
    rom_table: list[RomRow] = Field(default_factory=list)
    strength_table: list[StrengthRow] = Field(default_factory=list)
    special_tests_table: list[TestRow] = Field(default_factory=list)
    functional_table: list[FunctionalRow] = Field(default_factory=list)
    problem_list: list[str] = Field(default_factory=list, description="Physiotherapy problems derived from the findings")
    short_term_goals: list[str] = Field(default_factory=list, description="SMART goals, 2-4 weeks, only if the therapist stated or clearly implied them")
    long_term_goals: list[str] = Field(default_factory=list)


class SoapNote(BaseModel):
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    missing: list[str] = Field(default_factory=list)


class ImagingSummary(BaseModel):
    legible: bool
    study_type: Optional[str] = Field(None, description="X-ray, MRI, ultrasound, referral order, other")
    date: Optional[str] = None
    body_region: Optional[str] = None
    findings: Optional[str] = None
    impression: Optional[str] = None
    referral_request: Optional[str] = Field(None, description="If it is a doctor's referral: what the doctor asks for")
    urgent_terms: list[str] = Field(default_factory=list, description="Words like fracture, rupture, thrombosis, tumor, if present")


class Route(BaseModel):
    lead: Literal["ops", "health", "both"]
    reason: str


# ======================================================================================
# Agents
# ======================================================================================
def _instr(name: str) -> str:
    clinic = json.dumps(store.CLINIC, ensure_ascii=False, indent=1)
    return config.prompt(name) + "\n\n## Clinic profile (source of truth for prices, address, policies)\n" + clinic


patient_success = Agent(output_type=str, deps_type=Ctx, instructions=_instr("patient_success"))
finance_ops = Agent(output_type=str, deps_type=Ctx, instructions=_instr("finance_ops"))
ops_partner = Agent(output_type=str, deps_type=Ctx, instructions=_instr("ops_partner"))
health_advisor = Agent(output_type=str, deps_type=Ctx, instructions=_instr("health_advisor"))
clinical_scribe_eval = Agent(output_type=EvaluationDraft, deps_type=Ctx, instructions=config.prompt("clinical_scribe"))
clinical_scribe_soap = Agent(output_type=SoapNote, deps_type=Ctx, instructions=config.prompt("clinical_scribe"))
imaging_reader = Agent(output_type=ImagingSummary, deps_type=Ctx, instructions=config.prompt("imaging_reader"))
router = Agent(output_type=Route, deps_type=Ctx, instructions=config.prompt("router"))


# --------------------------------------------------------------------------------------
# Tools shared by several agents
# --------------------------------------------------------------------------------------
async def _clinic_info(ctx: RunContext[Ctx], topic: str = "all") -> dict:
    """Clinic facts: services and prices (MXN), packages, address and landmarks, map link, hours,
    payment methods, and policies. Always use this instead of guessing.

    Args:
        topic: 'prices', 'address', 'hours', 'payment', 'policies' or 'all'.
    """
    ctx.deps.log("clinic_info", topic)
    ci = ctx.deps.c["clinic"]
    if topic == "prices":
        ctx.deps.s.mission("s_prices")
        return {"services": ci["services"], "packages": ci["packages"], "usd_rate": ci["usd_rate"]}
    if topic == "address":
        ctx.deps.s.mission("s_address")
        return {"address": ci["address"], "landmarks": ci["landmarks"], "map_url": ci["map_url"]}
    if topic == "hours":
        return {"hours": ci["hours"]}
    if topic == "payment":
        return {"payment": ci["payment"]}
    if topic == "policies":
        return {"policies": ci["policies"]}
    return ci


async def _find_slots(ctx: RunContext[Ctx], weekday: Optional[str] = None, after_hour: Optional[int] = None,
                before_hour: Optional[int] = None, limit: int = 5) -> dict:
    """Free agenda slots (1 hour each) from now through Saturday, optionally filtered.

    Args:
        weekday: 'mon'..'sat' to restrict to one day.
        after_hour: earliest hour, e.g. 16 for 4 pm or later.
        before_hour: hours strictly before this, e.g. 13 for mornings.
        limit: maximum number of slots.
    """
    c = ctx.deps.c
    wd = None
    if weekday:
        wd = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5}.get(weekday.lower()[:3])
    slots = store.free_slots(c, weekday=wd, after_hour=after_hour, before_hour=before_hour, limit=limit)
    ctx.deps.log("find_slots", f"{len(slots)} free" + (f" on {weekday}" if weekday else ""))
    return {"slots": [{"start": x, "label": store.nice(x)} for x in slots]}


# ======================================================================================
# Patient Success tools (scoped to the contact it is talking to)
# ======================================================================================
patient_success.tool(_clinic_info, name="clinic_info")
patient_success.tool(_find_slots, name="find_slots")


def _contact(ctx: RunContext[Ctx]) -> dict:
    return ctx.deps.c["patients"][ctx.deps.patient_id]


def _allowed(ctx: RunContext[Ctx], pid: str | None) -> dict:
    """Patients may only act on themselves or their household (privacy guardrail in code)."""
    me = _contact(ctx)
    if not pid or pid == me["id"]:
        return me
    p = find_patient(ctx.deps.c, pid)
    if p and me.get("household_id") and p.get("household_id") == me["household_id"]:
        return p
    if p and p["id"] == "p_rosa" and me["id"] == "p_valeria":
        return p
    raise ValueError("You can only see or change appointments for yourself or your own family members.")


@patient_success.tool
async def my_profile(ctx: RunContext[Ctx]) -> dict:
    """The contact's own record: name, condition, upcoming appointments (with ids), balance, household
    members, home exercise program and restrictions. Only this contact's data is available."""
    c, me = ctx.deps.c, _contact(ctx)
    ctx.deps.log("my_profile", me["name"])
    out = patient_brief(c, me, private=False)
    out["household_patients"] = [patient_brief(c, x, private=False) for x in c["patients"].values()
                                 if me.get("household_id") and x.get("household_id") == me["household_id"] and x["id"] != me["id"]]
    return out


@patient_success.tool
async def request_booking(ctx: RunContext[Ctx], start: str, service: str = "evaluation", for_patient: Optional[str] = None,
                    reason: str = "") -> dict:
    """Hold a slot and ask the therapist to confirm. New patients and first visits always need the
    therapist's OK; you tell the patient it is pending confirmation.

    Args:
        start: slot start, 'YYYY-MM-DDTHH:MM' from find_slots.
        service: evaluation, conventional, redcord or shockwave.
        for_patient: a household member's name or id when booking for family; omit for the contact.
        reason: short reason (e.g. 'elbow fracture rehab, referred by Dr. Ortiz').
    """
    c = ctx.deps.c
    target = _allowed(ctx, for_patient) if for_patient else _contact(ctx)
    slot = parse_slot(c, start)
    if not slot:
        return {"ok": False, "error": "Unrecognised time. Use a slot from find_slots."}
    if store.busy_at(c, slot):
        return {"ok": False, "error": "That slot was just taken.", "alternatives": store.free_slots(c, slot, limit=3)}
    service = service if service in store.SERVICE_PRICE else "evaluation"
    a = store.add_appointment(c, target["id"], slot, service, status="pending_approval")
    if target["status"] == "inquiry":
        target["status"] = "new"
    new_approval(ctx, "booking", f"Book {target['name']}, {store.nice(slot)}",
                 f"**{target['name']}** ({target['condition']}) asks for **{service}** on **{store.nice(slot)}**.\n\nReason: {reason or '-'}",
                 APPROVE, {"appointment_id": a["id"]}, target["id"])
    ctx.deps.log("request_booking", f"{target['name']} {store.nice(slot)} (pending therapist)")
    ctx.deps.s.mission("s_book")
    if for_patient:
        ctx.deps.s.mission("s_household")
    return {"ok": True, "status": "pending therapist confirmation", "appointment_id": a["id"], "when": store.nice(slot),
            "price_mxn": store.SERVICE_PRICE[service]}


@patient_success.tool
async def save_intake(ctx: RunContext[Ctx], answers: dict[str, str], for_patient: Optional[str] = None) -> dict:
    """Save intake answers the patient gave in the chat so the evaluation form is pre-filled.
    Use short keys like occupation, chief_complaint, mechanism_and_date, medical_history, surgeries,
    medications, allergies, can_climb_stairs, pain_location, pain_vas, patient_goals, imaging.

    Args:
        answers: key -> the patient's own words.
        for_patient: household member name or id if the answers are about them.
    """
    target = _allowed(ctx, for_patient) if for_patient else _contact(ctx)
    target.setdefault("intake", {}).update({k: str(v)[:300] for k, v in answers.items() if v})
    ctx.deps.log("save_intake", f"{len(answers)} answers for {target['name']}")
    ctx.deps.s.mission("s_intake")
    prefill_from_intake(ctx.deps.c, target["id"])
    ctx.deps.s.emit("doc_updated", patient_id=target["id"], doc_id=(store.find_doc(ctx.deps.c, target["id"], "evaluation") or {}).get("id"), version=1)
    return {"ok": True, "saved": list(answers)}


@patient_success.tool
async def cancel_or_reschedule(ctx: RunContext[Ctx], appointment_id: str, new_start: Optional[str] = None,
                         reason: str = "") -> dict:
    """Cancel or move one of the contact's (or household's) appointments. The 24-hour policy is applied
    in code: under 24 hours the therapist decides whether to charge or waive. Offer make-up slots.

    Args:
        appointment_id: from my_profile.
        new_start: optional new slot 'YYYY-MM-DDTHH:MM' to reschedule to.
        reason: the patient's reason (work, illness...).
    """
    c, s = ctx.deps.c, ctx.deps.s
    a = c["appointments"].get(appointment_id)
    if not a:
        return {"ok": False, "error": "Unknown appointment id; call my_profile."}
    p = _allowed(ctx, a["patient_id"])
    hrs = store.hours_until(c, a["start"])
    late = 0 <= hrs < 24
    old = a["start"]
    result: dict[str, Any] = {"ok": True, "hours_notice": round(hrs, 1), "late": late}
    if new_start:
        slot = parse_slot(c, new_start)
        if not slot or store.busy_at(c, slot, ignore=a["id"]):
            return {"ok": False, "error": "That new time is not free.", "alternatives": [store.nice(x) for x in store.free_slots(c, limit=4)]}
        a["start"], a["end"] = slot, store.ts(store.dt(slot) + timedelta(hours=1))
        a["reminded"] = False
        result["moved_to"] = store.nice(slot)
        ctx.deps.log("cancel_or_reschedule", f"{p['name']} moved {store.nice(old)} -> {store.nice(slot)}")
        s.add_message("ops", "system", "Operations Partner", f"{p['name']} moved **{store.nice(old)}** to **{store.nice(slot)}** ({reason or 'no reason given'}).", agent="ops_partner")
        late = late and False  # moving within the week keeps the session, no charge
    else:
        a["status"] = "late_cancel" if late else "cancelled"
        ctx.deps.log("cancel_or_reschedule", f"{p['name']} cancelled {store.nice(old)} ({round(hrs, 1)} h notice)")
        _offer_waitlist(ctx.deps, old)
    if late and not new_start:
        waived_before = "waived_once" in p["flags"]
        opts = [{"id": "charge", "label": f"Charge MXN {store.SERVICE_PRICE[a['service']]}", "primary": True},
                {"id": "waive", "label": "Waive once" + (" (already waived before)" if waived_before else "")}]
        new_approval(ctx, "late_cancel_charge", f"Late cancellation: {p['name']} ({store.nice(old)})",
                     f"Cancelled with **{round(hrs, 1)} h** notice. Reason: {reason or '-'}.\n\n"
                     f"Policy: under 24 h is charged; you may waive once.{' This patient was already waived before.' if waived_before else ''}",
                     opts, {"patient_id": p["id"], "amount": store.SERVICE_PRICE[a["service"]], "appointment_id": a["id"]}, p["id"])
        result["policy"] = "Under 24 h: the therapist will decide whether it is charged. Offer make-up slots."
        s.mission("s_late_cancel")
    result["make_up_slots"] = [store.nice(x) for x in store.free_slots(c, limit=3)]
    return result


@patient_success.tool
async def my_balance(ctx: RunContext[Ctx]) -> dict:
    """What the contact (and household) owes and recent charges and payments."""
    c, me = ctx.deps.c, _contact(ctx)
    ids = [me["id"]] + [x["id"] for x in c["patients"].values() if me.get("household_id") and x.get("household_id") == me["household_id"] and x["id"] != me["id"]]
    rows = [e for e in c["ledger"] if e["patient_id"] in ids][-8:]
    ctx.deps.log("my_balance", me["name"])
    ctx.deps.s.mission("s_balance")
    return {"balances_mxn": {c["patients"][i]["name"]: store.balance(c, i) for i in ids},
            "recent": [{"when": store.nice(e["time"]), "kind": e["kind"], "amount_mxn": e["amount_mxn"], "note": e["note"]} for e in rows]}


@patient_success.tool
async def record_payment_proof(ctx: RunContext[Ctx], amount_mxn: int, method: Literal["transfer", "cash"] = "transfer",
                         note: str = "") -> dict:
    """Log a payment the patient says they made (e.g. sent a transfer receipt). Finance verifies it.

    Args:
        amount_mxn: amount in pesos.
        method: transfer or cash.
        note: e.g. 'transfer receipt sent in chat'.
    """
    me = _contact(ctx)
    e = store.add_ledger(ctx.deps.c, me["id"], "payment", amount_mxn, f"Reported by patient: {note or method} (to verify)", method)
    ctx.deps.log("record_payment_proof", f"{me['name']} MXN {amount_mxn}")
    ctx.deps.s.mission("s_payment")
    return {"ok": True, "logged": e["id"], "balance_now_mxn": store.balance(ctx.deps.c, me["id"])}


@patient_success.tool
async def request_invoice_or_receipt(ctx: RunContext[Ctx], kind: Literal["receipt", "invoice"], tax_details: str = "",
                               email: str = "") -> dict:
    """Ask Finance Ops for a receipt or an invoice (factura). Invoices need tax details and must be
    requested within the same month as the session.

    Args:
        kind: 'receipt' or 'invoice'.
        tax_details: RFC / tax regime / name if the patient gave them.
        email: where to send it.
    """
    me = _contact(ctx)
    ctx.deps.log("request_invoice_or_receipt", f"{kind} for {me['name']}")
    new_approval(ctx, "invoice_request", f"{kind.title()} for {me['name']}",
                 f"Patient asks for a **{kind}**. Tax details: {tax_details or 'not given yet'}. Email: {email or '-'}.\n\nOn approval it goes to the accountant's outbox.",
                 APPROVE, {"patient_id": me["id"], "kind": kind, "tax": tax_details, "email": email}, me["id"])
    ctx.deps.s.mission("s_invoice")
    return {"ok": True, "status": "sent to the therapist for approval, then to the accountant",
            "note": "Invoices are issued by the accountant within the same month."}


@patient_success.tool
async def resend_home_program(ctx: RunContext[Ctx], for_patient: Optional[str] = None) -> dict:
    """The home exercise program the therapist assigned (to resend when the patient forgot it)."""
    p = _allowed(ctx, for_patient) if for_patient else _contact(ctx)
    ctx.deps.log("resend_home_program", p["name"])
    ctx.deps.s.mission("s_home_program")
    return {"patient": p["name"], "home_program": p.get("home_program") or "No program on file yet."}


@patient_success.tool
async def escalate_to_therapist(ctx: RunContext[Ctx], summary: str, urgency: Literal["routine", "soon", "urgent"] = "routine",
                          kind: Literal["clinical_question", "exercise_check", "medication", "complaint", "other"] = "other") -> dict:
    """Pass something you must not answer yourself to the therapist. Use the LOWEST urgency that is safe:
    - routine (default): non-urgent clinical questions ('can I do this exercise?', mild soreness, gym,
      medication questions). They are NOT sent now; they go on the therapist's list for the next session.
    - soon: needs the therapist today (complaint, wants to stop treatment, pain clearly worse than usual).
    - urgent: a safety concern that cannot wait (the code already escalates classic red flags).
    Logistics (prices, booking, moving, cancelling, address, payments, receipts, exercises on file) you solve yourself.

    Args:
        summary: what the patient asked or reported, in one or two sentences.
        urgency: routine, soon or urgent.
        kind: type of question.
    """
    s, me = ctx.deps.s, _contact(ctx)
    ctx.deps.log("escalate_to_therapist", f"{kind} ({urgency})")
    if urgency == "routine":
        # Not critical: no interruption. Batched for the therapist's next session with this patient.
        up = store.upcoming_for(ctx.deps.c, me["id"])
        item = {"patient_id": me["id"], "patient": me["name"], "kind": kind, "summary": summary, "time": ctx.deps.c["now"],
                "next_session": store.nice(up[0]["start"]) if up else None}
        ctx.deps.c.setdefault("next_session_questions", []).append(item)
        if kind == "exercise_check":
            s.mission("s_exercise_link")
        if kind == "medication":
            s.mission("s_medication")
        return {"ok": True, "queued_for_next_session": item["next_session"] or "next contact",
                "tell_patient": "It is on the therapist's list for the next session; no need to wait for a reply now."}
    thread = "health" if kind in ("clinical_question", "exercise_check", "medication") else "ops"
    lead = "Health Advisor" if thread == "health" else "Operations Partner"
    s.add_message(thread, "agent", lead, f"**Needs you {'now' if urgency == 'urgent' else 'today'}: {me['name']}**: {summary}\n\n"
                  f"_Restrictions on file: {me.get('restrictions') or 'none'}_", agent="patient_success")
    if urgency == "urgent":
        s.alert("info", f"Urgent from {me['name']}: {summary}", me["id"])
    if kind == "exercise_check":
        s.mission("s_exercise_link")
    if kind == "medication":
        s.mission("s_medication")
    return {"ok": True, "told_patient": "The therapist will answer personally."}


@patient_success.tool
async def send_satisfaction_survey(ctx: RunContext[Ctx]) -> dict:
    """The anonymous satisfaction survey link (send at discharge or when asked)."""
    ctx.deps.log("send_satisfaction_survey", _contact(ctx)["name"])
    ctx.deps.s.mission("s_survey")
    return {"url": ctx.deps.c["clinic"]["survey_url"]}


def prefill_from_intake(c: dict, pid: str) -> dict:
    """Deterministic pre-fill: intake answers go into the evaluation draft with source 'intake_chat'."""
    p = c["patients"][pid]
    doc = store.find_doc(c, pid, "evaluation")
    current = store.fields_dict(doc) if doc else {}
    vals = {k: current.get(k) for k, _ in store.EVAL_FIELDS}
    sources = {}
    if doc:
        sources = {f["key"]: f["source"] for f in doc["versions"][doc["version"] - 1]["fields"]}
    for k, v in (p.get("intake") or {}).items():
        key = k if k in vals else None
        if key and not vals.get(key):
            vals[key] = v
            sources[key] = "intake_chat"
    if p.get("referring_doctor_id") and not vals.get("referring_doctor"):
        vals["referring_doctor"] = c["doctors"][p["referring_doctor_id"]]["name"]
        sources["referring_doctor"] = "intake_chat"
    fields = [{"key": k, "label": lbl, "value": vals.get(k), "source": sources.get(k, "empty") if vals.get(k) else "empty",
               "needs_review": not vals.get(k)} for k, lbl in store.EVAL_FIELDS]
    if doc and doc["status"] == "draft":
        doc["versions"][-1]["fields"] = fields
        return doc
    return store.add_document(c, pid, "evaluation", "Initial evaluation", fields, author="patient_success",
                              status="draft", reason="Pre-filled from the WhatsApp intake chat", doc_id=doc["id"] if doc else None)


# ======================================================================================
# Finance Ops tools
# ======================================================================================
@finance_ops.tool
async def balances(ctx: RunContext[Ctx]) -> dict:
    """Every patient with a balance due (MXN), largest first."""
    c = ctx.deps.c
    rows = [{"patient": p["name"], "patient_id": p["id"], "owes_mxn": store.balance(c, p["id"])} for p in c["patients"].values()]
    rows = sorted([r for r in rows if r["owes_mxn"] > 0], key=lambda r: -r["owes_mxn"])
    ctx.deps.log("balances", f"{len(rows)} patients owe")
    ctx.deps.s.mission("t_owes")
    return {"balances": rows, "total_outstanding_mxn": sum(r["owes_mxn"] for r in rows)}


@finance_ops.tool
async def patient_ledger(ctx: RunContext[Ctx], patient: str) -> dict:
    """Charges and payments for one patient.

    Args:
        patient: name or id.
    """
    c = ctx.deps.c
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    ctx.deps.log("patient_ledger", p["name"])
    return {"patient": p["name"], "balance_mxn": store.balance(c, p["id"]),
            "entries": [{"when": store.nice(e["time"]), "kind": e["kind"], "amount_mxn": e["amount_mxn"], "note": e["note"]}
                        for e in c["ledger"] if e["patient_id"] == p["id"]][-12:]}


@finance_ops.tool
async def record_payment(ctx: RunContext[Ctx], patient: str, amount_mxn: int, method: Literal["cash", "transfer"] = "cash") -> dict:
    """Record a payment the therapist received.

    Args:
        patient: name or id.
        amount_mxn: pesos.
        method: cash or transfer.
    """
    c = ctx.deps.c
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    store.add_ledger(c, p["id"], "payment", amount_mxn, "Recorded by therapist", method)
    ctx.deps.log("record_payment", f"{p['name']} MXN {amount_mxn}")
    return {"ok": True, "balance_now_mxn": store.balance(c, p["id"])}


@finance_ops.tool
async def request_invoice(ctx: RunContext[Ctx], patient: str, period: str = "this month", sessions: int = 0) -> dict:
    """Prepare an invoice request for the accountant (needs the therapist's approval).

    Args:
        patient: name or id.
        period: e.g. 'October 2026'.
        sessions: number of sessions to invoice (0 = all paid sessions in the period).
    """
    c = ctx.deps.c
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    paid = sum(e["amount_mxn"] for e in c["ledger"] if e["patient_id"] == p["id"] and e["kind"] == "payment")
    amount = sessions * store.SERVICE_PRICE[p["service"]] if sessions else paid
    new_approval(ctx, "invoice_request", f"Invoice request: {p['name']} ({period})",
                 f"Invoice **{p['name']}** for **{period}**: MXN {amount:,}. Goes to the accountant's outbox on approval. "
                 f"Reminder: the accountant cannot invoice a previous month after the cutoff.",
                 APPROVE, {"patient_id": p["id"], "kind": "invoice", "amount": amount, "period": period}, p["id"])
    ctx.deps.log("request_invoice", f"{p['name']} MXN {amount}")
    ctx.deps.s.mission("t_invoice")
    return {"ok": True, "pending_approval": True, "amount_mxn": amount}


def pulse(c: dict, period: str = "week") -> dict:
    start, end = store.WEEK_START[:10] + "T00:00", c["now"]
    appts = store.appointments_between(c, start, end)
    done = [a for a in appts if a["status"] in ("done", "booked", "confirmed") and a["end"] <= c["now"]]
    late = [a for a in appts if a["status"] == "late_cancel"]
    no_show = [a for a in appts if a["status"] == "no_show"]
    revenue = sum(store.SERVICE_PRICE[a["service"]] for a in done)
    collected = sum(e["amount_mxn"] for e in c["ledger"] if e["kind"] == "payment" and e["time"] >= start)
    hours_open = 0
    d = store.dt(start)
    while store.ts(d) < end:
        if store.ts(d)[:10] <= end[:10]:
            hours_open += len([h for h in store.open_hours(d) if store.ts(d.replace(hour=h)) < end])
        d += timedelta(days=1)
    by = {}
    for a in done:
        by.setdefault(a["service"], [0, 0])
        by[a["service"]][0] += 1
        by[a["service"]][1] += store.SERVICE_PRICE[a["service"]]
    lost = sum(store.SERVICE_PRICE[a["service"]] for a in late if not any(
        e["kind"] == "charge" and a["id"] in e.get("note", "") for e in c["ledger"])) + sum(store.SERVICE_PRICE[a["service"]] for a in no_show)
    outstanding = sum(max(store.balance(c, p), 0) for p in c["patients"])
    ai_usd = c["spend"]["usd"]
    ahead = [a for a in c["appointments"].values() if a["start"] >= end and a["start"] < "2026-11-01"
             and a["status"] in ("booked", "confirmed", "pending_approval")]
    return {"period": f"{store.nice(start)} to {store.nice(end)}", "revenue_mxn": revenue, "collected_mxn": collected,
            "outstanding_mxn": outstanding, "sessions_done": len(done),
            "utilization_pct": round(100 * len(done) / hours_open, 1) if hours_open else 0.0,
            "revenue_per_hour_mxn": round(revenue / hours_open) if hours_open else 0,
            "late_cancel_lost_mxn": lost,
            "by_service": [{"service": k, "sessions": v[0], "revenue_mxn": v[1]} for k, v in by.items()],
            "ai_cost_usd": round(ai_usd, 4),
            "booked_rest_of_week": len(ahead),
            "booked_rest_of_week_mxn": sum(store.SERVICE_PRICE[a["service"]] for a in ahead)}


@finance_ops.tool
async def business_pulse(ctx: RunContext[Ctx]) -> dict:
    """This week so far: revenue, collected, outstanding, sessions, utilization, revenue per open hour,
    money lost to late cancellations and no-shows, revenue by service, and the AI cost."""
    ctx.deps.log("business_pulse", "week to date")
    ctx.deps.s.mission("t_pulse")
    return pulse(ctx.deps.c)


@finance_ops.tool
async def what_if_price(ctx: RunContext[Ctx], service: Literal["conventional", "redcord", "shockwave", "evaluation"],
                  new_price_mxn: int, expected_volume_change_pct: float = 0.0) -> dict:
    """Simple what-if on next week's booked sessions if a service price changes.

    Args:
        service: which service.
        new_price_mxn: proposed price.
        expected_volume_change_pct: e.g. -5 if you expect 5% fewer sessions.
    """
    c = ctx.deps.c
    weekly = len([a for a in c["appointments"].values() if a["service"] == service and a["status"] in ("booked", "confirmed", "done")])
    old = store.SERVICE_PRICE[service]
    new_vol = weekly * (1 + expected_volume_change_pct / 100)
    ctx.deps.log("what_if_price", f"{service} {old} -> {new_price_mxn}")
    ctx.deps.s.mission("t_whatif")
    return {"service": service, "sessions_per_week": weekly, "current_price": old, "new_price": new_price_mxn,
            "weekly_revenue_now_mxn": weekly * old, "weekly_revenue_new_mxn": round(new_vol * new_price_mxn),
            "monthly_delta_mxn": round((new_vol * new_price_mxn - weekly * old) * 4.3)}


@finance_ops.tool
async def ai_cost(ctx: RunContext[Ctx]) -> dict:
    """What the AI agent team has cost in this demo so far, by agent (USD), and the caps."""
    ctx.deps.log("ai_cost", "spend")
    ctx.deps.s.mission("t_ai_cost")
    return runtime.spend_view(ctx.deps.s)


# ======================================================================================
# Operations Partner tools
# ======================================================================================
ops_partner.tool(_clinic_info, name="clinic_info")
ops_partner.tool(_find_slots, name="find_slots")


@ops_partner.tool
async def get_agenda(ctx: RunContext[Ctx], day: str = "today") -> dict:
    """Appointments for a day with patient, service, session number, flags (owes, red_flag...).

    Args:
        day: 'today', 'tomorrow', a weekday ('wed'), or 'YYYY-MM-DD'.
    """
    c = ctx.deps.c
    base = store.dt(c["now"]).replace(hour=0, minute=0)
    d = day.lower().strip()
    if d == "tomorrow":
        base += timedelta(days=1)
    elif re.match(r"\d{4}-\d{2}-\d{2}", d):
        base = store.dt(d[:10] + "T00:00")
    elif d[:3] in ("mon", "tue", "wed", "thu", "fri", "sat"):
        target = ["mon", "tue", "wed", "thu", "fri", "sat"].index(d[:3])
        while base.weekday() != target:
            base += timedelta(days=1)
    a, b = store.ts(base), store.ts(base + timedelta(days=1))
    rows = [appt_view(c, x) for x in store.appointments_between(c, a, b)]
    free = [store.nice(x) for x in store.free_slots(c, a, days=0, limit=12) if x[:10] == a[:10]]
    blocked = [x for x in c["blocked"] if x["start"][:10] == a[:10]]
    ctx.deps.log("get_agenda", f"{base.strftime('%a %b %d')}: {len(rows)} appointments")
    ctx.deps.s.mission("t_day")
    return {"day": base.strftime("%A %b %d"), "appointments": rows, "free_slots": free, "blocked": blocked,
            "waitlist": [c["patients"][w]["name"] for w in c["waitlist"]]}


def _notify(ctx: Ctx, pid: str, en: str, es: str) -> None:
    text = es if patient_lang(ctx.c, pid) == "es" else en
    send_to_patient(ctx.s, pid, text)


@ops_partner.tool
async def move_appointment(ctx: RunContext[Ctx], appointment_id: str, new_start: str, notify_patient: bool = True,
                     message_to_patient: str = "") -> dict:
    """Move an appointment (the therapist asked, so no approval needed) and tell the patient.

    Args:
        appointment_id: from get_agenda.
        new_start: 'YYYY-MM-DDTHH:MM' (minutes allowed, e.g. 17:40).
        notify_patient: send the patient a message.
        message_to_patient: optional custom message, written in the patient's language (patient_language
            from get_agenda); leave empty to send a polite default in the right language.
    """
    c = ctx.deps.c
    a = c["appointments"].get(appointment_id)
    if not a:
        return {"error": "Unknown appointment id."}
    slot = parse_slot(c, new_start) or new_start
    clash = store.busy_at(c, slot, ignore=a["id"])
    if clash and not clash.get("blocked"):
        return {"error": f"{store.nice(slot)} is taken by another patient.", "free": [store.nice(x) for x in store.free_slots(c, limit=4)]}
    old = a["start"]
    a["start"], a["end"] = slot, store.ts(store.dt(slot) + timedelta(hours=1))
    a["reminded"] = False
    p = c["patients"][a["patient_id"]]
    if notify_patient and "change_proposed" not in a["flags"]:
        a["flags"].append("change_proposed")
    if notify_patient:
        if message_to_patient:
            send_to_patient(ctx.deps.s, p["id"], message_to_patient)
        else:
            _notify(ctx.deps, p["id"],
                    f"Hello {p['name'].split()[0]}, the therapist needs to move your session from {store.nice(old)} to {store.nice(slot)}. Does that work for you? Sorry for the change.",
                    f"Hola {p['name'].split()[0]}, la terapeuta necesita mover su sesión del {store.nice(old)} al {store.nice(slot)}. ¿Le queda bien? Disculpe el cambio.")
    ctx.deps.log("move_appointment", f"{p['name']} {store.nice(old)} -> {store.nice(slot)}")
    ctx.deps.s.mission("t_move")
    if store.dt(slot) - store.dt(old) < timedelta(hours=3) and store.dt(slot) > store.dt(old):
        ctx.deps.s.mission("t_late")
    return {"ok": True, "patient": p["name"], "from": store.nice(old), "to": store.nice(slot), "notified": notify_patient}


@ops_partner.tool
async def book_appointment(ctx: RunContext[Ctx], patient: str, start: str,
                     service: Literal["evaluation", "conventional", "redcord", "shockwave"] = "conventional",
                     notify_patient: bool = True) -> dict:
    """Book directly (the therapist asked). Use for series after a plan is agreed, or family back to back.

    Args:
        patient: name or id.
        start: 'YYYY-MM-DDTHH:MM'.
        service: type of session.
        notify_patient: send a confirmation message.
    """
    c = ctx.deps.c
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    slot = parse_slot(c, start) or start
    if store.busy_at(c, slot):
        return {"error": f"{store.nice(slot)} is not free.", "free": [store.nice(x) for x in store.free_slots(c, limit=5)]}
    p["sessions_done"] = p.get("sessions_done", 0)
    n = len([a for a in c["appointments"].values() if a["patient_id"] == p["id"] and a["status"] in ("done", "booked", "confirmed")]) + 1
    a = store.add_appointment(c, p["id"], slot, service, "booked", session_number=n)
    if p["status"] in ("inquiry", "new"):
        p["status"] = "active"
    if notify_patient:
        _notify(ctx.deps, p["id"], f"Hello {p['name'].split()[0]}, you're booked for {store.nice(slot)} ({service}). See you then!",
                f"Hola {p['name'].split()[0]}, quedó agendado(a) el {store.nice(slot)} ({service}). ¡Nos vemos!")
    ctx.deps.log("book_appointment", f"{p['name']} {store.nice(slot)} {service}")
    hh = p.get("household_id")
    if hh and any(x["patient_id"] != p["id"] and c["patients"][x["patient_id"]].get("household_id") == hh
                  and abs((store.dt(x["start"]) - store.dt(slot)).total_seconds()) <= 3600 for x in c["appointments"].values()):
        ctx.deps.s.mission("t_household")
    return {"ok": True, "appointment_id": a["id"], "when": store.nice(slot)}


@ops_partner.tool
async def block_time(ctx: RunContext[Ctx], start: str, end: str, reason: str, notify_patients: bool = True) -> dict:
    """Block agenda time (holiday, personal). Lists affected appointments and offers to move them;
    affected appointments are cancelled without charge and patients are told.

    Args:
        start: 'YYYY-MM-DDTHH:MM'.
        end: 'YYYY-MM-DDTHH:MM'.
        reason: e.g. 'holiday'.
        notify_patients: message affected patients with free alternatives.
    """
    c = ctx.deps.c
    c["blocked"].append({"start": start, "end": end, "reason": reason})
    hit = [a for a in c["appointments"].values() if start <= a["start"] < end and a["status"] in ("booked", "confirmed", "pending_approval")]
    affected = []
    for a in hit:
        a["status"] = "cancelled"
        a["flags"].append("clinic_closed")
        p = c["patients"][a["patient_id"]]
        alts = [store.nice(x) for x in store.free_slots(c, end, limit=3)]
        if notify_patients:
            _notify(ctx.deps, p["id"],
                    f"Hello {p['name'].split()[0]}, the clinic will be closed on {store.nice(a['start'])} ({reason}). No charge for this change. Could one of these work instead: {', '.join(alts)}?",
                    f"Hola {p['name'].split()[0]}, la clínica estará cerrada el {store.nice(a['start'])} ({reason}). No tiene costo. ¿Le funciona alguno de estos horarios: {', '.join(alts)}?")
        affected.append({"patient": p["name"], "was": store.nice(a["start"]), "offered": alts})
    ctx.deps.log("block_time", f"{store.nice(start)} to {store.nice(end)}: {len(affected)} affected")
    ctx.deps.s.mission("t_block")
    return {"ok": True, "blocked": f"{store.nice(start)} to {store.nice(end)}", "affected": affected}


@ops_partner.tool
async def cancel_appointment(ctx: RunContext[Ctx], appointment_id: str, charge: bool = False, reason: str = "") -> dict:
    """Cancel an appointment on the therapist's instruction.

    Args:
        appointment_id: id.
        charge: True to charge it as a late cancellation.
        reason: note.
    """
    c = ctx.deps.c
    a = c["appointments"].get(appointment_id)
    if not a:
        return {"error": "Unknown appointment id."}
    a["status"] = "late_cancel" if charge else "cancelled"
    if charge:
        store.add_ledger(c, a["patient_id"], "charge", store.SERVICE_PRICE[a["service"]], f"Late cancellation {store.nice(a['start'])} {a['id']}")
    ctx.deps.log("cancel_appointment", f"{c['patients'][a['patient_id']]['name']} {store.nice(a['start'])}")
    _offer_waitlist(ctx.deps, a["start"])
    return {"ok": True}


def _offer_waitlist(ctx: Ctx, slot: str) -> list[str]:
    c = ctx.c
    offered = []
    for pid in c["waitlist"][:2]:
        p = c["patients"][pid]
        _notify(ctx, pid, f"Hello {p['name'].split()[0]}, a slot just opened on {store.nice(slot)}. Would you like it? Reply YES and I'll hold it for you.",
                f"Hola {p['name'].split()[0]}, se liberó un espacio el {store.nice(slot)}. ¿Lo quiere? Responda SÍ y se lo aparto.")
        offered.append(p["name"])
    if offered:
        c.setdefault("offers", []).append({"slot": slot, "to": list(c["waitlist"][:2]), "time": c["now"]})
        ctx.log("offer_slot_to_waitlist", f"{store.nice(slot)} offered to {', '.join(offered)}")
        ctx.s.mission("t_waitlist")
    return offered


@ops_partner.tool
async def offer_slot_to_waitlist(ctx: RunContext[Ctx], start: str) -> dict:
    """Offer a free slot to the patients on the waitlist (first to say yes gets it).

    Args:
        start: the free slot 'YYYY-MM-DDTHH:MM'.
    """
    return {"offered_to": _offer_waitlist(ctx.deps, parse_slot(ctx.deps.c, start) or start)}


@ops_partner.tool
async def message_patient(ctx: RunContext[Ctx], patient: str, instruction: str) -> dict:
    """Have Patient Success write to a patient on WhatsApp in the clinic's tone (e.g. win-back,
    payment reminder, reschedule). The therapist asked, so it is sent.

    Args:
        patient: name or id.
        instruction: what to say and why.
    """
    c = ctx.deps.c
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    sub = ctx.deps.child("patient_success")
    sub.patient_id = p["id"]
    sub.lang = patient_lang(c, p["id"])
    ctx.deps.s.emit("delegation", run_id=ctx.deps.run_id, **{"from": "ops_partner", "to": "patient_success", "task": instruction[:120]})
    text = await run("patient_success", patient_success, sub,
                     f"{now_line(c)}\nTHE THERAPIST (via Operations Partner) asks you to write ONE WhatsApp message to "
                     f"{p['name']} ({sub.lang}). Instruction: {instruction}\nReply with only the message text.",
                     history_key=None, lead=False)
    send_to_patient(ctx.deps.s, p["id"], text)
    ctx.deps.log("message_patient", f"to {p['name']}")
    if "at_risk" in p["status"] or "missed_2" in p["flags"]:
        ctx.deps.s.mission("t_winback")
    return {"sent": text}


@ops_partner.tool
async def ask_finance_ops(ctx: RunContext[Ctx], question: str) -> str:
    """Delegate money questions to Finance Ops: balances, payments, invoices, business pulse,
    profitability, price what-ifs, AI cost.

    Args:
        question: the specific question.
    """
    if ctx.deps.shared["delegations"] >= 4:
        return "Delegation limit reached for this request; answer with what you have."
    ctx.deps.shared["delegations"] += 1
    ctx.deps.s.emit("delegation", run_id=ctx.deps.run_id, **{"from": "ops_partner", "to": "finance_ops", "task": question[:120]})
    return await run("finance_ops", finance_ops, ctx.deps.child("finance_ops"), f"{now_line(ctx.deps.c)}\n{question}", lead=False)


@ops_partner.tool
async def handoff_to_health_advisor(ctx: RunContext[Ctx], request: str) -> str:
    """Hand a clinical part of the request to the Health Advisor (once per request).

    Args:
        request: what the Health Advisor should do or answer.
    """
    return await _handoff(ctx, "health_advisor", request)


@ops_partner.tool
async def pending_approvals(ctx: RunContext[Ctx]) -> dict:
    """Approvals waiting for the therapist."""
    rows = [{"title": a["title"], "kind": a["kind"]} for a in ctx.deps.c["approvals"].values() if a["status"] == "pending"]
    ctx.deps.log("pending_approvals", f"{len(rows)} pending")
    return {"pending": rows}


@ops_partner.tool
async def patients_at_risk(ctx: RunContext[Ctx]) -> dict:
    """Patients who may drop out: missed sessions, no upcoming booking, or flagged at risk."""
    return _at_risk(ctx)


def _at_risk(ctx: RunContext[Ctx]) -> dict:
    c = ctx.deps.c
    rows = []
    for p in c["patients"].values():
        if p["status"] not in ("active", "at_risk"):
            continue
        missed = len([a for a in c["appointments"].values() if a["patient_id"] == p["id"] and a["status"] in ("no_show", "late_cancel")])
        upcoming = store.upcoming_for(c, p["id"])
        if missed >= 2 or not upcoming or p["status"] == "at_risk":
            rows.append({"patient": p["name"], "missed": missed, "next": store.nice(upcoming[0]["start"]) if upcoming else None,
                         "sessions": f"{p['sessions_done']}/{p['plan_total']}"})
    ctx.deps.log("patients_at_risk", f"{len(rows)} at risk")
    ctx.deps.s.mission("t_risk")
    return {"at_risk": rows}


# ======================================================================================
# Health Advisor tools
# ======================================================================================
@health_advisor.tool
async def get_patient(ctx: RunContext[Ctx], patient: str) -> dict:
    """A patient's record: condition, plan, sessions, intake answers, restrictions, home program,
    upcoming appointments and the latest documents.

    Args:
        patient: name or id.
    """
    c = ctx.deps.c
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'.", "patients": [x["name"] for x in c["patients"].values()]}
    ctx.deps.log("get_patient", p["name"])
    b = patient_brief(c, p)
    docs = [d for d in c["documents"].values() if d["patient_id"] == p["id"]]
    b["documents"] = [{"doc_id": d["id"], "kind": d["kind"], "version": d["version"], "status": d["status"]} for d in docs]
    ev = store.find_doc(c, p["id"], "evaluation")
    if ev and ev["status"] == "draft":
        ctx.deps.s.mission("t_prefill")
        b["evaluation_draft_filled"] = [f["label"] for f in ev["versions"][-1]["fields"] if f["value"]]
    return b


ops_partner.tool(get_patient, name="get_patient")


@health_advisor.tool
async def complete_evaluation(ctx: RunContext[Ctx], patient: str, session_notes: str) -> dict:
    """Clinical Scribe turns the therapist's session notes (plus the intake chat) into the evaluation
    form draft. Nothing is invented: unstated fields stay empty. Creates a signature request.

    Args:
        patient: name or id.
        session_notes: the therapist's notes or dictation, verbatim.
    """
    c, s = ctx.deps.c, ctx.deps.s
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    s.emit("delegation", run_id=ctx.deps.run_id, **{"from": "health_advisor", "to": "clinical_scribe", "task": f"evaluation for {p['name']}"})
    draft: EvaluationDraft = await run("clinical_scribe", clinical_scribe_eval, ctx.deps.child("clinical_scribe"),
                                       f"FORM: initial evaluation.\nPATIENT: {p['name']}, {p['age']}, {p['condition']}\n"
                                       f"INTAKE CHAT ANSWERS (source intake_chat): {json.dumps(p.get('intake') or {}, ensure_ascii=False)}\n"
                                       f"THERAPIST SESSION NOTES (source session_notes): {session_notes}", lead=False)
    vals = draft.model_dump()
    from_notes = set(vals.pop("from_session_notes", []) or [])
    missing = vals.pop("missing_important", []) or []
    hist = {k: vals.get(src) for k, src in (("family", "family_history"), ("personal", "medical_history"), ("surgeries", "surgeries"),
                                             ("medications", "medications"), ("lifestyle", "lifestyle"))}
    data = {"pain": vals.pop("pain_detail", None) or {}, "history": hist,
            "rom": vals.pop("rom_table", []), "strength": vals.pop("strength_table", []),
            "special_tests": vals.pop("special_tests_table", []), "functional": vals.pop("functional_table", []),
            "problems": vals.pop("problem_list", []), "short_term_goals": vals.pop("short_term_goals", []),
            "long_term_goals": vals.pop("long_term_goals", []), "impression": vals.get("pt_impression")}
    # keep the flat form readable in the app when only tables were given
    if not vals.get("rom") and data["rom"]:
        vals["rom"] = "; ".join(f"{r['joint']} {r['movement']} R {r.get('right') or '-'} / L {r.get('left') or '-'}" for r in data["rom"])
    if not vals.get("strength") and data["strength"]:
        vals["strength"] = "; ".join(f"{r['muscle']} R {r.get('right') or '-'} / L {r.get('left') or '-'}" for r in data["strength"])
    if not vals.get("special_tests") and data["special_tests"]:
        vals["special_tests"] = "; ".join(f"{r['test']} R {r.get('right') or '-'} / L {r.get('left') or '-'}" for r in data["special_tests"])
    intake = p.get("intake") or {}
    fields = []
    for k, lbl in store.EVAL_FIELDS:
        v = vals.get(k)
        src = "empty" if not v else ("session_notes" if k in from_notes or k not in intake else "intake_chat")
        fields.append({"key": k, "label": lbl, "value": v, "source": src, "needs_review": not v})
    ev = store.find_doc(c, p["id"], "evaluation")
    d = store.add_document(c, p["id"], "evaluation", "Initial evaluation", fields, author="clinical_scribe", status="draft",
                           reason="Completed from session notes", doc_id=ev["id"] if ev else None, data=data)
    new_approval(ctx.deps, "sign_document", f"Sign evaluation: {p['name']}",
                 f"Evaluation v{d['version']} drafted from your notes. {sum(1 for f in fields if f['value'])} of {len(fields)} fields filled; "
                 f"still empty: {', '.join(missing) or 'none flagged'}.", [{"id": "approve", "label": "Sign", "primary": True}, {"id": "reject", "label": "Needs changes"}],
                 {"doc_id": d["id"]}, p["id"])
    s.emit("doc_updated", doc_id=d["id"], patient_id=p["id"], version=d["version"])
    ctx.deps.log("complete_evaluation", f"{p['name']} v{d['version']}")
    s.mission("t_notes")
    return {"doc_id": d["id"], "version": d["version"], "filled": [f["label"] for f in fields if f["value"]], "empty_important": missing}


@health_advisor.tool
async def write_soap_note(ctx: RunContext[Ctx], patient: str, session_notes: str) -> dict:
    """Clinical Scribe writes today's SOAP note from the therapist's notes (draft for signature).

    Args:
        patient: name or id.
        session_notes: the therapist's notes, verbatim.
    """
    c, s = ctx.deps.c, ctx.deps.s
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    s.emit("delegation", run_id=ctx.deps.run_id, **{"from": "health_advisor", "to": "clinical_scribe", "task": f"SOAP for {p['name']}"})
    note: SoapNote = await run("clinical_scribe", clinical_scribe_soap, ctx.deps.child("clinical_scribe"),
                               f"FORM: SOAP note for today's session.\nPATIENT: {p['name']}, {p['condition']}\nNOTES: {session_notes}", lead=False)
    vals = {"date": store.nice(c["now"]), **note.model_dump()}
    fields = [{"key": k, "label": lbl, "value": vals.get(k), "source": "session_notes" if vals.get(k) else "empty",
               "needs_review": not vals.get(k)} for k, lbl in store.SOAP_FIELDS]
    d = store.add_document(c, p["id"], "soap", f"SOAP {store.nice(c['now'])}", fields, author="clinical_scribe", status="draft",
                           reason="From session notes")
    s.emit("doc_updated", doc_id=d["id"], patient_id=p["id"], version=1)
    ctx.deps.log("write_soap_note", p["name"])
    s.mission("t_notes")
    return {"doc_id": d["id"], "soap": vals}


@health_advisor.tool
async def propose_treatment_plan(ctx: RunContext[Ctx], patient: str, conventional_sessions: int, redcord_sessions: int,
                           shockwave_sessions: int, frequency: str, focus: str, goals: str, next_session: str,
                           review_point: str, reason: str, payment_terms: str = "Per session or 10-session package",
                           phases: list[PlanPhase] | None = None, short_term_goals: list[str] | None = None,
                           long_term_goals: list[str] | None = None, precautions: list[str] | None = None,
                           home_program: list[str] | None = None, review_points: list[str] | None = None) -> dict:
    """Create or update the treatment plan (new version, needs the therapist's approval). The cost is
    computed in code from the clinic price list; never state prices yourself. Fill the structured
    parts (phases, goals, precautions, home program, review points) so the plan PDF is complete:
    2-3 phases with weeks, focus and interventions; SMART goals; precautions from restrictions,
    surgery protocol or red flags.

    Args:
        patient: name or id.
        conventional_sessions: number of conventional sessions.
        redcord_sessions: number of Redcord sessions.
        shockwave_sessions: number of shockwave sessions.
        frequency: e.g. '2x/week'.
        focus: clinical focus for the block.
        goals: measurable goals.
        next_session: what to do next session.
        review_point: when to re-assess.
        reason: why this plan or why it changed (cite the notes or progress).
        payment_terms: payment terms.
    """
    c, s = ctx.deps.c, ctx.deps.s
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    total = conventional_sessions + redcord_sessions + shockwave_sessions
    cost = (conventional_sessions * store.SERVICE_PRICE["conventional"] + redcord_sessions * store.SERVICE_PRICE["redcord"]
            + shockwave_sessions * store.SERVICE_PRICE["shockwave"])
    package_hint = ""
    if total == 10 and conventional_sessions == 5 and (redcord_sessions + shockwave_sessions) == 5:
        package_hint = " (10-session package available: MXN 5,000)"
    mix = ", ".join(f"{n} {k}" for n, k in ((conventional_sessions, "conventional"), (redcord_sessions, "Redcord"), (shockwave_sessions, "shockwave")) if n)
    vals = {"total_sessions": str(total), "frequency": frequency, "therapy_mix": mix, "focus": focus, "goals": goals,
            "next_session": next_session, "total_cost_mxn": f"{cost}{package_hint}", "payment_terms": payment_terms,
            "review_point": review_point}
    fields = [{"key": k, "label": lbl, "value": vals.get(k), "source": "agent_proposal", "needs_review": False} for k, lbl in store.PLAN_FIELDS]
    old = store.find_doc(c, p["id"], "treatment_plan")
    data = {"schedule": {"sessions": total, "frequency": frequency, "mix": mix},
            "phases": [ph.model_dump() for ph in (phases or [])],
            "short_term_goals": short_term_goals or [], "long_term_goals": long_term_goals or [],
            "precautions": precautions or ([p["restrictions"]] if p.get("restrictions") else []),
            "home_program": home_program or [], "review_points": review_points or [review_point],
            "cost": {"total_mxn": f"{cost:,}{package_hint}", "terms": payment_terms}}
    d = store.add_document(c, p["id"], "treatment_plan", "Treatment plan", fields, author="health_advisor", status="draft",
                           reason=reason, doc_id=old["id"] if old else None, data=data)
    new_approval(ctx.deps, "plan_change", f"Approve plan v{d['version']}: {p['name']}",
                 f"**{total} sessions** ({mix}), {frequency}. Total **MXN {cost:,}**.\n\nWhy: {reason}",
                 [{"id": "approve", "label": f"Approve v{d['version']}", "primary": True}, {"id": "reject", "label": "Keep current"}],
                 {"doc_id": d["id"], "patient_id": p["id"], "total": total}, p["id"])
    s.emit("doc_updated", doc_id=d["id"], patient_id=p["id"], version=d["version"])
    ctx.deps.log("propose_treatment_plan", f"{p['name']} v{d['version']}: {total} sessions, MXN {cost}")
    s.mission("t_plan" if d["version"] == 1 else "t_plan_v2")
    if d["version"] > 1:
        s.mission("t_plan")
    return {"doc_id": d["id"], "version": d["version"], "total_sessions": total, "total_cost_mxn": cost, "package_hint": package_hint}


@health_advisor.tool
async def update_home_program(ctx: RunContext[Ctx], patient: str, exercises_markdown: str, send_to_patient_now: bool = True) -> dict:
    """Save the home exercise program and (if asked) send it to the patient.

    Args:
        patient: name or id.
        exercises_markdown: numbered list: exercise, sets x reps, times per day, cues.
        send_to_patient_now: send it on WhatsApp.
    """
    c = ctx.deps.c
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    p["home_program"] = exercises_markdown
    store.add_document(c, p["id"], "home_program", "Home exercise program", body_md=exercises_markdown, author="health_advisor",
                       status="signed", doc_id=(store.find_doc(c, p["id"], "home_program") or {}).get("id"))
    if send_to_patient_now:
        intro = "Your exercises for home:" if patient_lang(c, p["id"]) == "en" else "Sus ejercicios para casa:"
        send_to_patient(ctx.deps.s, p["id"], f"{intro}\n{exercises_markdown}")
    ctx.deps.log("update_home_program", p["name"])
    ctx.deps.s.mission("t_home")
    return {"ok": True, "sent": send_to_patient_now}


@health_advisor.tool
async def progress_data(ctx: RunContext[Ctx], patient: str) -> dict:
    """Everything needed to write a grounded progress report: baseline evaluation values, every SOAP
    note, treatment plan versions with their reasons, attendance (done, missed, late cancels), home
    program and next appointments. Call this before writing a progress report.

    Args:
        patient: name or id.
    """
    c = ctx.deps.c
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    ev = store.find_doc(c, p["id"], "evaluation")
    baseline = {k: v for k, v in (store.fields_dict(ev) if ev else {}).items() if v}
    soaps = [{"date": store.nice(d["versions"][-1]["created"]), **{k: v for k, v in store.fields_dict(d).items() if v}}
             for d in c["documents"].values() if d["patient_id"] == p["id"] and d["kind"] == "soap"]
    plan = store.find_doc(c, p["id"], "treatment_plan")
    plans = [{"version": v["version"], "status": v["status"], "reason": v.get("reason"),
              **{f["key"]: f["value"] for f in v["fields"] if f["value"]}} for v in (plan["versions"] if plan else [])]
    appts = [a for a in c["appointments"].values() if a["patient_id"] == p["id"]]
    ctx.deps.log("progress_data", p["name"])
    return {"patient": p["name"], "age": p["age"], "condition": p["condition"],
            "sessions_done": p["sessions_done"], "plan_total": p["plan_total"],
            "attendance": {"done": len([a for a in appts if a["status"] == "done"]) + max(0, p["sessions_done"] - len([a for a in appts if a["status"] == "done"])),
                           "missed": len([a for a in appts if a["status"] == "no_show"]),
                           "late_cancellations": len([a for a in appts if a["status"] == "late_cancel"])},
            "baseline_evaluation": baseline, "soap_notes": soaps, "plan_versions": plans,
            "home_program": p.get("home_program"), "restrictions": p.get("restrictions"),
            "next_appointments": [store.nice(a["start"]) for a in store.upcoming_for(c, p["id"])[:3]],
            "referring_doctor": c["doctors"][p["referring_doctor_id"]]["name"] if p.get("referring_doctor_id") else None,
            "note": "Use only these facts. If objective re-measurements are missing, say so and recommend re-assessing at the next session."}


@health_advisor.tool
async def draft_progress_report(ctx: RunContext[Ctx], patient: str, summary: str, outcomes: list[OutcomeRow],
                                goals: list[GoalStatus], plan_changes: str, recommendation: str, next_review: str = "",
                                send_to_doctor: bool = False, to_doctor: str = "") -> dict:
    """Create a progress report document in the patient's folder (versioned, exportable to PDF and Word).
    By default it is only saved and waits for the therapist's signature. Set send_to_doctor=True when
    a doctor asked for it: then approving the card also sends it (the consent letter authorises sharing
    progress with the treating doctors). Call progress_data first and use ONLY those facts.

    Args:
        patient: name or id.
        summary: 2-4 sentences: where the patient started, where they are now, overall trend.
        outcomes: one row per measure with baseline (evaluation) and latest (most recent note) values and
            the change; use 'not re-measured' instead of guessing.
        goals: each goal from the plan with its status (met / progressing / not yet / not re-measured).
        plan_changes: what continues or changes in the plan, and why.
        recommendation: one clear recommendation (e.g. continue, re-assess, refer, discharge criteria).
        next_review: when the next re-assessment happens.
        send_to_doctor: True only if the report should be sent to a doctor after approval.
        to_doctor: doctor name; defaults to the referring doctor.
    """
    c = ctx.deps.c
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    did = p.get("referring_doctor_id")
    doc_name = to_doctor or (c["doctors"][did]["name"] if did else "the treating doctor")
    appts = [a for a in c["appointments"].values() if a["patient_id"] == p["id"]]
    attendance = {"done": p.get("sessions_done", 0), "total": p.get("plan_total"),
                  "missed": len([a for a in appts if a["status"] == "no_show"]),
                  "late": len([a for a in appts if a["status"] == "late_cancel"])}
    data = {"summary": summary, "attendance": attendance, "outcomes": [o.model_dump() for o in outcomes],
            "goals": [g.model_dump() for g in goals], "plan_changes": plan_changes, "recommendation": recommendation,
            "next_review": next_review}
    rows = "\n".join(f"| {o.measure} | {o.baseline or 'n/r'} | {o.latest or 'n/r'} | {o.change or ''} |" for o in outcomes)
    report_markdown = (f"## Summary\n{summary}\n\n## Sessions and attendance\n{attendance['done']} of {attendance['total']} sessions; "
                       f"{attendance['missed']} missed; {attendance['late']} late cancellations.\n\n## Objective outcomes\n"
                       f"| Measure | Baseline | Latest | Change |\n|---|---|---|---|\n{rows}\n\n## Goals\n"
                       + "\n".join(f"- {g.goal}: **{g.status}**" for g in goals)
                       + f"\n\n## Plan\n{plan_changes}\n\n## Recommendation\n{recommendation}"
                       + (f"\n\n## Next review\n{next_review}" if next_review else ""))
    old = store.find_doc(c, p["id"], "progress_report")
    title = f"Progress report ({store.nice(c['now'])[:10]})"
    d = store.add_document(c, p["id"], "progress_report", title, body_md=report_markdown, author="health_advisor",
                           status="draft", reason=f"Requested {'by ' + doc_name if send_to_doctor else 'by the therapist'}",
                           doc_id=old["id"] if old and old["status"] == "draft" else None, data=data)
    if send_to_doctor:
        new_approval(ctx.deps, "outbound_message", f"Send progress report to {doc_name}: {p['name']}",
                     report_markdown[:900], [{"id": "approve", "label": "Approve and send", "primary": True}, {"id": "reject", "label": "Hold"}],
                     {"doc_id": d["id"], "doctor_id": did, "patient_id": p["id"]}, p["id"])
    else:
        new_approval(ctx.deps, "sign_document", f"Sign progress report: {p['name']}",
                     f"Saved in {p['name']}'s folder (v{d['version']}). Sign it to file it; export to Word from the folder.",
                     [{"id": "approve", "label": "Sign", "primary": True}, {"id": "reject", "label": "Needs changes"}],
                     {"doc_id": d["id"]}, p["id"])
    ctx.deps.s.emit("doc_updated", doc_id=d["id"], patient_id=p["id"], version=d["version"])
    ctx.deps.log("draft_progress_report", f"{p['name']} saved" + (f", to send to {doc_name}" if send_to_doctor else ""))
    ctx.deps.s.mission("t_doctor_report" if send_to_doctor else "t_progress_report")
    return {"doc_id": d["id"], "version": d["version"], "saved_in_folder": True,
            "status": "waiting for approval to send" if send_to_doctor else "saved, waiting for signature"}


@health_advisor.tool
async def draft_discharge_summary(ctx: RunContext[Ctx], patient: str, summary_markdown: str) -> dict:
    """Discharge summary with results and advice (e.g. swimming, gym), plus the satisfaction survey.

    Args:
        patient: name or id.
        summary_markdown: the summary.
    """
    c = ctx.deps.c
    p = find_patient(c, patient)
    if not p:
        return {"error": f"No patient matches '{patient}'."}
    d = store.add_document(c, p["id"], "discharge_summary", "Discharge summary", body_md=summary_markdown,
                           author="health_advisor", status="draft", reason="End of treatment")
    new_approval(ctx.deps, "outbound_message", f"Send discharge message and survey: {p['name']}", summary_markdown[:900],
                 [{"id": "approve", "label": "Approve and send", "primary": True}, {"id": "reject", "label": "Hold"}],
                 {"doc_id": d["id"], "patient_id": p["id"], "survey": True}, p["id"])
    ctx.deps.log("draft_discharge_summary", p["name"])
    ctx.deps.s.mission("t_discharge")
    return {"doc_id": d["id"]}


@health_advisor.tool
async def read_study(ctx: RunContext[Ctx], attachment_id: str, patient: str) -> dict:
    """Imaging Reader (vision) reads a photo or PDF of a study or referral and files a structured
    summary. PDFs are scanned for hidden text first; hidden text is removed and logged.

    Args:
        attachment_id: id of the uploaded file.
        patient: name or id.
    """
    return await read_attachment(ctx.deps, attachment_id, patient)


async def read_attachment(deps: Ctx, attachment_id: str, patient: str) -> dict:
    c, s = deps.c, deps.s
    att = c["attachments"].get(attachment_id)
    p = find_patient(c, patient)
    if not att or not p:
        return {"error": "Unknown attachment or patient."}
    from pathlib import Path
    path = Path(att["path"])
    s.emit("delegation", run_id=deps.run_id, **{"from": "health_advisor", "to": "imaging_reader", "task": att["name"]})
    hidden_note = ""
    if att["kind"] == "pdf":
        scan = safety.scan_pdf(path)
        if scan["hidden_found"]:
            s.safety("injection_hidden", "blocked", f"Hidden text removed from '{att['name']}': \"{scan['hidden_text'][:160]}\"", p["id"])
            hidden_note = " Hidden text was found and removed before reading."
            s.mission("t_hidden_pdf")
        prompt: Any = f"Document text (visible layer only):\n{scan['visible_text'][:6000]}"
    else:
        data = path.read_bytes()
        media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        prompt = [f"Read this medical document photo for patient {p['name']}.", BinaryContent(data, media_type=media)]
    summary: ImagingSummary = await run("imaging_reader", imaging_reader, deps.child("imaging_reader"), prompt, lead=False)
    body = (f"**{summary.study_type or 'Document'}** {summary.date or ''} - {summary.body_region or ''}\n\n"
            f"Findings: {summary.findings or '-'}\n\nImpression: {summary.impression or '-'}"
            + (f"\n\nReferral request: {summary.referral_request}" if summary.referral_request else "")
            + (f"\n\nUrgent terms: {', '.join(summary.urgent_terms)}" if summary.urgent_terms else "")
            + "\n\n_Read by the Imaging Reader; the therapist must verify._" + hidden_note)
    store.add_document(c, p["id"], "imaging_summary", f"Study: {att['name']}", body_md=body, author="imaging_reader", status="draft",
                       reason="Read from uploaded file")
    ev = store.find_doc(c, p["id"], "evaluation")
    if ev and summary.legible:
        for f in ev["versions"][-1]["fields"]:
            if f["key"] == "imaging":
                f["value"] = f"{summary.study_type or ''} {summary.date or ''}: {summary.impression or summary.findings or ''}".strip()
                f["source"], f["needs_review"] = "imaging", True
    s.emit("doc_updated", patient_id=p["id"], doc_id=ev["id"] if ev else None, version=ev["version"] if ev else 1)
    deps.log("read_study", f"{att['name']} for {p['name']}")
    s.mission("t_imaging")
    return {"summary": summary.model_dump(), "hidden_text_removed": bool(hidden_note)}


@health_advisor.tool
async def patient_list(ctx: RunContext[Ctx], status: str = "active") -> dict:
    """Patients by status (active, at_risk, inquiry, new, discharged) with sessions and condition."""
    rows = [{"name": p["name"], "condition": p["condition"], "sessions": f"{p['sessions_done']}/{p['plan_total']}", "status": p["status"]}
            for p in ctx.deps.c["patients"].values() if status in ("all", p["status"])]
    ctx.deps.log("patient_list", f"{len(rows)} {status}")
    return {"patients": rows}


ops_partner.tool(patient_list, name="patient_list")


@health_advisor.tool
async def doctor_stats(ctx: RunContext[Ctx]) -> dict:
    """Referring doctors: referrals this month and their active patients."""
    c = ctx.deps.c
    rows = []
    for d in c["doctors"].values():
        act = [p["name"] for p in c["patients"].values() if p.get("referring_doctor_id") == d["id"] and p["status"] in ("active", "at_risk", "new")]
        rows.append({"doctor": d["name"], "specialty": d["specialty"], "referrals_this_month": d["referrals_this_month"], "active_patients": act})
    ctx.deps.log("doctor_stats", f"{len(rows)} doctors")
    ctx.deps.s.mission("t_referrals")
    return {"doctors": sorted(rows, key=lambda r: -r["referrals_this_month"])}


ops_partner.tool(doctor_stats, name="doctor_stats")


@health_advisor.tool
async def patients_at_risk_h(ctx: RunContext[Ctx]) -> dict:
    """Patients who may drop out (missed sessions, nothing booked)."""
    return _at_risk(ctx)


@health_advisor.tool
async def handoff_to_ops_partner(ctx: RunContext[Ctx], request: str) -> str:
    """Hand the operational part to the Operations Partner (once per request), e.g. 'book Sofia's 10
    sessions Tue/Thu 18:00' after a plan is approved.

    Args:
        request: what Operations should do.
    """
    return await _handoff(ctx, "ops_partner", request)


async def _handoff(ctx: RunContext[Ctx], to: str, request: str) -> str:
    sh = ctx.deps.shared
    if sh["handoffs"] >= 1 or ctx.deps.depth >= 2:
        ctx.deps.s.safety("loop_guard", "capped", f"Blocked a second hand-off ({ctx.deps.agent} -> {to}) in one request.")
        return "Hand-off limit reached for this request (one per request). Report back to the therapist with what you have."
    sh["handoffs"] += 1
    ctx.deps.s.emit("delegation", run_id=ctx.deps.run_id, **{"from": ctx.deps.agent, "to": to, "task": request[:120]})
    ag = ops_partner if to == "ops_partner" else health_advisor
    return await run(to, ag, ctx.deps.child(to), f"{now_line(ctx.deps.c)}\nHAND-OFF from {NAMES[ctx.deps.agent]}: {request}",
                     history_key=None, lead=False)


# ======================================================================================
# Entry points
# ======================================================================================
OPS_WORDS = re.compile(r"\b(agenda|schedule|day|tomorrow|today|move|book|block|holiday|cancel|late|waitlist|slot|owe|pay|paid|invoice|factura|revenue|profit|money|price|cost|budget|ai cost|utiliz|week|report|reminder|confirm|resched|calendar|cita|horario|cobr|pago)\b", re.I)
HEALTH_WORDS = re.compile(r"\b(notes?|session notes|evaluation|soap|plan|exercise|home program|progress|doctor|dr\.?|referral|imaging|x-?ray|mri|study|studies|pain|discharge|clinical|diagnos|rom|strength|red flag|valoraci|ejercicio|nota)\b", re.I)


async def route(s: Session, text: str, run_id: str) -> str:
    t = text.strip()
    if t.lower().startswith(("@ops", "@operations")):
        return "ops"
    if t.lower().startswith(("@health", "@health advisor")):
        return "health"
    o, h = bool(OPS_WORDS.search(t)), bool(HEALTH_WORDS.search(t))
    if o and not h:
        return "ops"
    if h and not o:
        return "health"
    ctx = Ctx(s=s, agent="router", run_id=run_id, thread="team")
    r: Route = await run("router", router, ctx, t, lead=False)
    return r.lead if r.lead != "both" else "ops"


async def therapist_turn(s: Session, thread: str, text: str, run_id: str, attachment_id: str | None = None) -> None:
    """The therapist writes in Team / Ops / Health. Replies are posted to the same thread."""
    c = s.c
    lead = {"ops": "ops", "health": "health"}.get(thread) or await route(s, text, run_id)
    agent_id = "ops_partner" if lead == "ops" else "health_advisor"
    ag = ops_partner if lead == "ops" else health_advisor
    ctx = Ctx(s=s, agent=agent_id, run_id=run_id, thread=thread)
    prompt = f"{now_line(c)}\nTHERAPIST ({thread} chat): {text}"
    if attachment_id and attachment_id in c["attachments"]:
        att = c["attachments"][attachment_id]
        prompt += f"\n[Attached file: '{att['name']}', attachment_id={attachment_id}. Use read_study with this id if it is a study or referral.]"
    out = await run(agent_id, ag, ctx, prompt, history_key=f"{thread}:{agent_id}")
    s.add_message(thread, "agent", NAMES[agent_id], out, agent=agent_id, tools=ctx.shared["tools"],
                  agents_involved=ctx.shared["agents"], cost_usd=round(ctx.shared.get("usd", 0.0), 5))


async def doctor_turn(s: Session, did: str, text: str, run_id: str) -> None:
    """A referring doctor writes to the clinic. The Health Advisor prepares the answer; the therapist
    only sees an approval card plus one line in the Health thread (nothing is sent without approval)."""
    c = s.c
    d = c["doctors"][did]
    clean, _ = safety.clean_text(text)
    if safety.injection(clean):
        s.safety("injection_direct", "blocked", f"{d['name']} channel: suspicious instructions blocked.")
        return
    ctx = Ctx(s=s, agent="health_advisor", run_id=run_id, thread=f"doc:{did}")
    prompt = (f"{now_line(c)}\nA REFERRING DOCTOR, {d['name']} ({d['specialty']}), wrote to the clinic: \"{clean}\"\n"
              f"If they ask about a patient, call progress_data and then draft_progress_report with send_to_doctor=True (it waits for the "
              f"therapist's approval before it is sent). Then reply with ONE short line for the therapist saying what the doctor "
              f"asked and what is ready for approval.")
    out = await run("health_advisor", health_advisor, ctx, prompt, history_key=None)
    s.add_message("health", "agent", "Health Advisor", f"🩺 **{d['name']}:** {out}", agent="health_advisor",
                  tools=ctx.shared["tools"], agents_involved=ctx.shared["agents"], cost_usd=round(ctx.shared.get("usd", 0.0), 5))


async def patient_turn(s: Session, pid: str, text: str, run_id: str, attachment_id: str | None = None) -> None:
    """A patient (human tester or bot) writes on WhatsApp. The safety layer runs first, in code."""
    c = s.c
    p = c["patients"][pid]
    lang = c.get("persona_lang", {}).get(pid) or safety.guess_lang(text)
    clean, removed = safety.clean_text(text)
    if removed:
        s.safety("injection_hidden", "blocked", f"Removed {removed} invisible characters from {p['name']}'s message.", pid)
    attack = safety.injection(clean)
    if attack:
        s.safety("injection_direct", "blocked", f"{p['name']}: {attack}. Message: \"{clean[:120]}\"", pid)
        for m in reversed(c["messages"]):
            if m["thread"] == f"wa:{pid}" and m["role"] == "patient":
                m["blocked"] = True
                s.emit("message", message=m)
                break
        send_to_patient(s, pid, safety.SAFE_REPLY[lang]["injection"], agent="safety", author="Movimiento Fisioterapia (AI assistant)")
        s.mission("t_injection")
        s.mission("s_trick")
        return
    flags = safety.red_flags(clean)
    if flags:
        if "red_flag" not in p["flags"]:
            p["flags"].append("red_flag")
        s.safety("red_flag", "escalated", f"{p['name']}: {'; '.join(flags)}. \"{clean[:140]}\"", pid)
        s.alert("red_flag", f"RED FLAG - {p['name']}: {flags[0]}. Call the patient.", pid)
        s.add_message("health", "agent", "Health Advisor", f"**Red flag from {p['name']}**: {'; '.join(flags)}.\n\n> {clean}\n\n"
                      f"Coaching stopped for this patient. Suggested action: call now; if signs are confirmed, refer to urgent care. "
                      f"Restrictions on file: {p.get('restrictions') or 'none'}.", agent="safety")
        send_to_patient(s, pid, safety.SAFE_REPLY[lang]["red_flag"], agent="safety")
        s.mission("t_redflag")
        s.mission("s_red_flag")
        return
    notes = []
    if safety.mentions_medication(clean):
        notes.append("The patient mentions medication: never advise on it; tell them their doctor decides dose or changes, and log it with escalate_to_therapist(kind='medication', urgency='routine') unless it sounds urgent.")
        s.safety("medication", "routed", f"{p['name']} asked about medication; routed to the therapist.", pid)
    if safety.links(clean):
        notes.append("The message contains a link you cannot open. Say so, remind them of their restrictions on file if any, and log it with escalate_to_therapist(kind='exercise_check', urgency='routine') so the therapist reviews it at the next session.")
        s.safety("link", "routed", f"{p['name']} sent a link; agent will not open it.", pid)
    att_note = ""
    if attachment_id and attachment_id in c["attachments"]:
        att = c["attachments"][attachment_id]
        att_note = f"\n[The patient attached '{att['name']}'. It was filed and sent to the Health Advisor's Imaging Reader.]"
        ctx_h = Ctx(s=s, agent="health_advisor", run_id=run_id, thread=f"wa:{pid}", patient_id=pid)
        try:
            res = await read_attachment(ctx_h, attachment_id, pid)
            att_note += f"\n[Imaging Reader result: {json.dumps(res.get('summary', {}), ensure_ascii=False)[:500]}]"
            s.mission("s_referral")
        except runtime.BudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001
            att_note += f"\n[Could not read the file: {exc}]"
    ctx = Ctx(s=s, agent="patient_success", run_id=run_id, thread=f"wa:{pid}", patient_id=pid, lang=lang)
    prompt = (f"{now_line(c)}\nYou are chatting with {p['name']} (contact id {pid}). Reply in "
              f"{'Spanish (usted)' if lang == 'es' else 'English'}.\n" + ("\n".join(notes) + "\n" if notes else "")
              + f"PATIENT MESSAGE: {clean}{att_note}")
    out = await run("patient_success", patient_success, ctx, prompt, history_key=f"wa:{pid}")
    send_to_patient(s, pid, out, tools=ctx.shared["tools"], agents_involved=ctx.shared["agents"],
                    cost_usd=round(ctx.shared.get("usd", 0.0), 5))
    if p["status"] == "inquiry" and any(t["tool"] == "clinic_info" for t in ctx.shared["tools"]):
        s.mission("s_first_contact")
