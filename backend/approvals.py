"""Approval cards are executed here, in code, never by a model (so a confused or attacked agent
cannot approve its own request)."""

from __future__ import annotations

from . import store
from .agents import patient_lang, public_approval, send_to_patient
from .runtime import Session


def _say(s: Session, pid: str, en: str, es: str) -> None:
    send_to_patient(s, pid, es if patient_lang(s.c, pid) == "es" else en, author="Movimiento Fisioterapia (AI assistant)")


def resolve(s: Session, approval_id: str, option: str, by: str = "therapist") -> dict:
    c = s.c
    a = c["approvals"].get(approval_id)
    if not a:
        raise KeyError(approval_id)
    if a["status"] != "pending":
        return public_approval(a)
    pl = a["payload"]
    kind = a["kind"]
    pid = a.get("patient_id")
    p = c["patients"].get(pid) if pid else None
    first = p["name"].split()[0] if p else ""

    if kind == "booking":
        ap = c["appointments"].get(pl["appointment_id"])
        if option == "approve" and ap:
            ap["status"] = "booked"
            _say(s, pid, f"Confirmed, {first}: {store.nice(ap['start'])} ({ap['service']}). Address: {c['clinic']['address']} See you then!",
                 f"Confirmado, {first}: {store.nice(ap['start'])} ({ap['service']}). Dirección: {c['clinic']['address']} ¡Nos vemos!")
            if p and p["status"] in ("inquiry", "new"):
                p["status"] = "new"
            s.mission("t_approve_booking")
            s.mission("s_confirmed")
        elif ap:
            ap["status"] = "cancelled"
            alts = [store.nice(x) for x in store.free_slots(c, limit=3)]
            _say(s, pid, f"Sorry {first}, that time is no longer available. Could one of these work: {', '.join(alts)}?",
                 f"Disculpe {first}, ese horario ya no está disponible. ¿Le funciona alguno de estos: {', '.join(alts)}?")
        a["status"] = "approved" if option == "approve" else "rejected"

    elif kind == "late_cancel_charge":
        amount = pl["amount"]
        if option == "charge":
            store.add_ledger(c, pid, "charge", amount, f"Late cancellation {pl['appointment_id']}")
            _say(s, pid, f"Thanks for letting us know, {first}. As agreed at the start, cancellations under 24 h are charged (MXN {amount}). We'll see you at your next session.",
                 f"Gracias por avisar, {first}. Como acordamos al inicio, las cancelaciones con menos de 24 h se cobran (MXN {amount}). Nos vemos en su próxima sesión.")
            a["status"] = "approved"
        else:
            store.add_ledger(c, pid, "waiver", 0, f"Late cancellation waived once {pl['appointment_id']}")
            if p and "waived_once" not in p["flags"]:
                p["flags"].append("waived_once")
            _say(s, pid, f"No problem this time, {first}. Please try to let us know 24 h ahead next time. Get well!",
                 f"Por esta ocasión no hay problema, {first}. La próxima vez avísenos con 24 h de anticipación, por favor. ¡Que se mejore!")
            a["status"] = "waived"
        s.mission("t_late_cancel")

    elif kind in ("sign_document", "plan_change"):
        d = c["documents"].get(pl["doc_id"])
        if d and option == "approve":
            for v in d["versions"][:-1]:
                if v["status"] == "signed":
                    v["status"] = "superseded"
            d["versions"][-1]["status"] = "signed"
            d["status"] = "signed"
            if kind == "plan_change" and p:
                p["plan_total"] = pl.get("total") or p["plan_total"]
                for ap in c["appointments"].values():
                    if ap["patient_id"] == pid:
                        ap["plan_total"] = p["plan_total"]
            s.emit("doc_updated", doc_id=d["id"], patient_id=d["patient_id"], version=d["version"])
            s.mission("t_sign")
        a["status"] = "approved" if option == "approve" else "rejected"

    elif kind == "outbound_message":
        d = c["documents"].get(pl.get("doc_id", ""))
        if option == "approve" and d:
            d["versions"][-1]["status"] = "signed"
            d["status"] = "signed"
            body = d["versions"][-1].get("body_md") or ""
            did = pl.get("doctor_id")
            if did:
                s.add_message(f"doc:{did}", "agent", "Movimiento Fisioterapia", body, agent="health_advisor")
                c["outbox"].append({"to": c["doctors"][did]["name"], "subject": d["title"], "time": c["now"]})
            elif pid:
                _say(s, pid, body, body)
                if pl.get("survey"):
                    _say(s, pid, f"One last favour: this 1-minute anonymous survey helps us improve: {c['clinic']['survey_url']}",
                         f"Un último favor: esta encuesta anónima de 1 minuto nos ayuda a mejorar: {c['clinic']['survey_url']}")
                    s.mission("t_discharge")
        a["status"] = "approved" if option == "approve" else "rejected"

    elif kind == "invoice_request":
        if option == "approve":
            c["outbox"].append({"to": "Accountant", "subject": f"{pl.get('kind', 'invoice')} for {p['name'] if p else ''}",
                                "detail": pl, "time": c["now"]})
            _say(s, pid, f"Done, {first}: your {pl.get('kind', 'invoice')} request went to our accountant. You'll get it by email.",
                 f"Listo, {first}: su solicitud de {'factura' if pl.get('kind') == 'invoice' else 'recibo'} ya está con la contadora. Le llegará por correo.")
            s.mission("t_invoice")
        a["status"] = "approved" if option == "approve" else "rejected"
    else:
        a["status"] = "approved" if option == "approve" else "rejected"

    a["resolved_by"] = by
    a["resolved_at"] = c["now"]
    s.emit("approval", approval=public_approval(a))
    return public_approval(a)


def auto_therapist(s: Session) -> int:
    """Simulator therapist (patient mode / autopilot): approves what a sensible therapist would."""
    n = 0
    for a in list(s.c["approvals"].values()):
        if a["status"] != "pending":
            continue
        option = "approve"
        if a["kind"] == "late_cancel_charge":
            p = s.c["patients"].get(a.get("patient_id"), {})
            option = "charge" if "waived_once" in p.get("flags", []) else "waive"
        resolve(s, a["id"], option, by="therapist_bot")
        n += 1
    return n

