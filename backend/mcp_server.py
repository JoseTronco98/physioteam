"""PhysioTeam clinic tools as an MCP server, so the therapist's own AI assistant (Claude, ChatGPT,
Cursor, any MCP client) can read the clinic: agenda, free slots, patients, balances, business pulse.

Read-only on purpose: changes go through PhysioTeam's approval cards, not through outside agents.

Run (stdio):  python -m backend.mcp_server
Session:      PHYSIOTEAM_SESSION=<id> picks which saved clinic to read (default: newest in data/sessions).
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

from . import agents, config, store

mcp = FastMCP("physioteam-clinic")


def _clinic() -> dict:
    sid = os.getenv("PHYSIOTEAM_SESSION")
    if sid:
        c = store.load(sid)
        if c:
            return c
    files = sorted(config.SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files:
        c = store.load(f.stem)
        if c:
            return c
    return store.new_clinic("mcp-demo")


@mcp.tool
def get_agenda(day: str = "") -> dict:
    """Appointments for a day ('YYYY-MM-DD'; default: the clinic's current simulated day)."""
    c = _clinic()
    d = day or c["now"][:10]
    rows = store.appointments_between(c, d + "T00:00", d + "T23:59")
    return {"day": d, "appointments": [agents.appt_view(c, a) for a in rows]}


@mcp.tool
def free_slots(limit: int = 8) -> dict:
    """Next free one-hour slots."""
    c = _clinic()
    return {"slots": [store.nice(s) for s in store.free_slots(c, limit=limit)]}


@mcp.tool
def patient_summary(name: str) -> dict:
    """Condition, sessions, plan, balance and upcoming appointments for one patient."""
    c = _clinic()
    p = agents.find_patient(c, name)
    return agents.patient_brief(c, p) if p else {"error": f"No patient matches '{name}'."}


@mcp.tool
def balances() -> dict:
    """Patients with a balance due (MXN)."""
    c = _clinic()
    rows = [{"patient": p["name"], "owes_mxn": store.balance(c, p["id"])} for p in c["patients"].values()]
    return {"balances": [r for r in rows if r["owes_mxn"] > 0]}


@mcp.tool
def business_pulse() -> dict:
    """Week-to-date revenue, collected, utilization, late-cancellation losses and AI cost."""
    return agents.pulse(_clinic())


@mcp.tool
def pending_approvals() -> dict:
    """What is waiting for the therapist's approval."""
    c = _clinic()
    return {"pending": [a["title"] for a in c["approvals"].values() if a["status"] == "pending"]}


@mcp.resource("clinic://profile")
def clinic_profile() -> dict:
    """Clinic services, prices, hours, address and policies."""
    return store.CLINIC


if __name__ == "__main__":
    mcp.run()
