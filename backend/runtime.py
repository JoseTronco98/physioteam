"""Per-visitor sessions, the live event bus (SSE), spend metering, and the audit trail."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from . import config, store


class BudgetExceeded(RuntimeError):
    pass


AGENT_NAMES = {"ops_partner": "Operations Partner", "health_advisor": "Health Advisor", "patient_success": "Patient Success",
               "finance_ops": "Finance Ops", "clinical_scribe": "Clinical Scribe", "imaging_reader": "Imaging Reader",
               "router": "Router", "safety": "Safety layer", "simulator": "Simulator"}


@dataclass
class Session:
    id: str
    c: dict
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    histories: dict[str, list] = field(default_factory=dict)   # thread -> PydanticAI message history
    running: int = 0
    tasks: set = field(default_factory=set)
    last_seen: float = field(default_factory=time.time)

    # ---- events -------------------------------------------------------------------
    def emit(self, type_: str, **payload: Any) -> None:
        msg = {"type": type_, **payload}
        self._log_activity(msg)
        for q in list(self.subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def _log_activity(self, m: dict) -> None:
        """Behind-the-scenes feed that survives page reloads (GET /api/activity)."""
        t = m["type"]
        row: dict[str, Any] | None = None
        if t == "agent_started":
            row = {"agent": m["agent"], "run_id": m.get("run_id"), "text": f"{AGENT_NAMES.get(m['agent'], m['agent'])} started: {m.get('task', '')[:120]}"}
        elif t == "tool_called":
            row = {"agent": m["agent"], "run_id": m.get("run_id"), "text": f"{m['tool']}: {m.get('summary', '')}"}
        elif t == "delegation":
            row = {"agent": m["from"], "run_id": m.get("run_id"),
                   "text": f"{AGENT_NAMES.get(m['from'], m['from'])} → {AGENT_NAMES.get(m['to'], m['to'])}: {m.get('task', '')[:120]}"}
        elif t == "run_finished":
            row = {"run_id": m.get("run_id"), "text": f"Error: {m['error']}" if m.get("error") else "Run finished",
                   "cost_usd": m.get("cost_usd"), "tone": "bad" if m.get("error") else "ok"}
        elif t == "safety":
            e = m["event"]
            row = {"agent": "safety", "text": f"{e['action'].upper()} · {e['detail']}", "tone": "bad" if e["kind"] in ("red_flag", "injection_direct", "injection_hidden", "budget") else "warn"}
        elif t == "approval":
            a = m["approval"]
            row = {"agent": a.get("requested_by"), "text": f"Approval {a['status']}: {a['title']}", "tone": "warn" if a["status"] == "pending" else "ok"}
        elif t == "message":
            msg = m["message"]
            th = msg["thread"]
            if th.startswith("wa:"):
                pname = self.c["patients"].get(th[3:], {}).get("name", "patient")
                if msg["role"] == "patient":
                    row = {"thread": th, "text": f"{pname} → clinic: {msg['text'][:140]}", "tone": "bad" if msg.get("blocked") else None}
                elif msg["role"] == "therapist":
                    row = {"thread": th, "text": f"{msg['author']} (therapist) → {pname}: {msg['text'][:140]}"}
                else:
                    who = "Safety layer" if msg.get("agent") == "safety" else ("Automatic" if "automatic" in msg["author"].lower() else AGENT_NAMES.get(msg.get("agent", ""), "Patient Success"))
                    row = {"thread": th, "agent": msg.get("agent") or "patient_success", "text": f"{who} → {pname}: {msg['text'][:140]}"}
            elif th.startswith("doc:") or msg["role"] == "doctor":
                if msg["role"] == "doctor" and th.startswith("doc:"):
                    row = {"text": f"{msg['author']} → clinic: {msg['text'][:140]}"}
        elif t == "alert":
            row = {"agent": "safety", "text": m["text"], "tone": "bad" if m["level"] == "red_flag" else "warn"}
        if row is None:
            return
        self.c["seq"] += 1
        row = {"id": f"act{self.c['seq']}", "time": self.c["now"], "type": t, **{k: v for k, v in row.items() if v is not None}}
        act = self.c.setdefault("activity", [])
        act.append(row)
        if len(act) > 600:
            del act[: len(act) - 600]

    def add_message(self, thread: str, role: str, author: str, text: str, **extra: Any) -> dict:
        self.c["seq"] += 1
        m = {"id": f"m{self.c['seq']}", "thread": thread, "role": role, "author": author, "text": text,
             "time": self.c["now"], **{k: v for k, v in extra.items() if v is not None}}
        self.c["messages"].append(m)
        self.emit("message", message=m)
        return m

    def alert(self, level: str, text: str, patient_id: str | None = None) -> None:
        a = {"level": level, "text": text, "patient_id": patient_id, "time": self.c["now"]}
        self.c["alerts"].append(a)
        self.emit("alert", **a)

    def safety(self, kind: str, action: str, detail: str, patient_id: str | None = None) -> dict:
        e = {"id": store.new_id("s"), "time": self.c["now"], "kind": kind, "action": action,
             "detail": detail, "patient_id": patient_id}
        self.c["safety"].append(e)
        self.emit("safety", event=e)
        audit(self, "safety", **e)
        return e

    def mission(self, mission_id: str) -> None:
        # Patient missions belong to the persona being played (Sofia's booking is not Valeria's).
        if mission_id.startswith("s_") and self.c.get("persona_pid") and self.c.get("mode") == "patient":
            mission_id = f"{self.c['persona_pid']}:{mission_id}"
        if mission_id not in self.c["missions_done"]:
            self.c["missions_done"].append(mission_id)
            self.emit("mission", mission_id=mission_id, done=True)

    def save(self) -> None:
        store.save(self.c)

    @property
    def busy(self) -> bool:
        return self.running > 0


SESSIONS: dict[str, Session] = {}


def get_session(sid: str) -> Session:
    sid = store.safe(sid or "anon")
    s = SESSIONS.get(sid)
    if s is None:
        if len(SESSIONS) >= config.MAX_SESSIONS:
            oldest = min(SESSIONS.values(), key=lambda x: x.last_seen)
            SESSIONS.pop(oldest.id, None)
        c = store.load(sid) or store.new_clinic(sid)
        s = Session(id=sid, c=c)
        SESSIONS[sid] = s
    s.last_seen = time.time()
    return s


def reset_session(sid: str) -> Session:
    sid = store.safe(sid)
    old = SESSIONS.pop(sid, None)
    if old:
        for t in list(old.tasks):
            t.cancel()
    s = Session(id=sid, c=store.new_clinic(sid))
    if old:
        s.subscribers = old.subscribers
        # keep the visitor's spend so Reset cannot be used to dodge the session cap
        s.c["spend"] = old.c["spend"]
    SESSIONS[sid] = s
    s.save()
    return s


def spawn(s: Session, coro) -> None:
    """Run an agent job in the background and keep a handle so Reset can cancel it."""
    task = asyncio.create_task(coro)
    s.tasks.add(task)
    task.add_done_callback(s.tasks.discard)


# ---- spend -----------------------------------------------------------------------------
_GLOBAL = {"day": date.today().isoformat(), "usd": 0.0}
_GLOBAL_FILE = config.DATA / "global_spend.json"
try:
    _saved = json.loads(_GLOBAL_FILE.read_text(encoding="utf-8"))
    if _saved.get("day") == _GLOBAL["day"]:
        _GLOBAL.update(_saved)
except (OSError, json.JSONDecodeError):
    pass


def global_usd() -> float:
    if _GLOBAL["day"] != date.today().isoformat():
        _GLOBAL.update(day=date.today().isoformat(), usd=0.0)
    return _GLOBAL["usd"]


def usage_dict(u: Any) -> dict:
    return {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "cached_tokens": getattr(u, "cache_read_tokens", 0) or 0,
        "cache_write_tokens": getattr(u, "cache_write_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "calls": getattr(u, "requests", 0) or 0,
    }


def cost_usd(u: dict, model: str = config.MODEL_NAME) -> float:
    p = config.PRICES.get(model, config.PRICES["gpt-6-luna"])
    fresh = max(u["input_tokens"] - u["cached_tokens"] - u["cache_write_tokens"], 0)
    return (fresh * p["input"] + u["cached_tokens"] * p["cached_input"]
            + u["cache_write_tokens"] * p["cache_write"] + u["output_tokens"] * p["output"]) / 1_000_000


def record_spend(s: Session, agent: str, usage: Any, simulator: bool = False) -> float:
    u = usage_dict(usage)
    usd = cost_usd(u)
    bucket = s.c["spend"]["simulator" if simulator else "product"]
    key = "simulator" if simulator else agent
    b = bucket.setdefault(key, {"agent": key, "usd": 0.0, "input_tokens": 0, "cached_tokens": 0,
                                "cache_write_tokens": 0, "output_tokens": 0, "calls": 0})
    for k in ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "calls"):
        b[k] += u[k]
    b["usd"] += usd
    s.c["spend"]["usd"] += usd
    global_usd()
    _GLOBAL["usd"] += usd
    try:
        _GLOBAL_FILE.write_text(json.dumps(_GLOBAL), encoding="utf-8")
    except OSError:
        pass
    s.emit("spend", spend=spend_view(s))
    return usd


def check_budget(s: Session) -> None:
    cap = s.c.get("cap_override", config.SESSION_CAP_USD)
    if s.c["spend"]["usd"] >= cap:
        s.safety("budget", "capped", f"Visitor budget of ${config.SESSION_CAP_USD:.2f} reached{' (budget test)' if 'cap_override' in s.c else ''}. Agents paused for this session.")
        raise BudgetExceeded(f"This demo session reached its AI budget (${config.SESSION_CAP_USD:.2f}), so the agents are paused. This cap protects the shared API key.")
    if global_usd() >= config.GLOBAL_DAILY_CAP_USD:
        s.safety("budget", "capped", f"Global daily budget of ${config.GLOBAL_DAILY_CAP_USD:.2f} reached across all visitors.")
        raise BudgetExceeded("The demo reached today's global AI budget. Please try again tomorrow.")


def spend_view(s: Session) -> dict:
    prod = s.c["spend"]["product"]
    sim = s.c["spend"]["simulator"].get("simulator") or {"agent": "simulator", "usd": 0.0, "input_tokens": 0,
                                                         "cached_tokens": 0, "cache_write_tokens": 0,
                                                         "output_tokens": 0, "calls": 0}
    return {"session_usd": round(s.c["spend"]["usd"], 5), "session_cap_usd": config.SESSION_CAP_USD,
            "global_usd_today": round(global_usd(), 4), "global_cap_usd": config.GLOBAL_DAILY_CAP_USD,
            "product": [dict(v, usd=round(v["usd"], 6)) for v in prod.values()],
            "simulator": dict(sim, usd=round(sim["usd"], 6)), "caching": s.c.get("caching", True)}


# ---- audit trail (Lecture 4 harness: forensic log) --------------------------------------
def audit(s: Session, event: str, **data: Any) -> None:
    row = {"wall": time.strftime("%Y-%m-%dT%H:%M:%S"), "session": s.id, "sim_time": s.c["now"], "event": event, **data}
    try:
        with config.AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str)[:6000] + "\n")
    except OSError:
        pass
