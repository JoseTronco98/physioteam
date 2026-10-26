"""Live WhatsApp channel (Meta WhatsApp Business Cloud API).

Real messages to the clinic number arrive at /webhook/whatsapp and go into one "live" clinic session:
the same agents, safety layer and approvals as the demo, but with the real clock and no simulator bots.
Everything the clinic sends to a patient who wrote from WhatsApp goes back through the Cloud API.
The therapist watches and approves in the web app (open it with ?session=live).

Environment (.env):
  WHATSAPP_TOKEN            access token (temporary from the Meta console, or a system-user token)
  WHATSAPP_PHONE_NUMBER_ID  the clinic number's id (Meta console > WhatsApp > API setup)
  WHATSAPP_VERIFY_TOKEN     any secret string; the same one goes in the Meta webhook settings
  WHATSAPP_APP_SECRET       app secret, to check Meta's signature on every webhook call (recommended)
  WHATSAPP_ALLOWED          comma-separated phone numbers allowed to talk to the bot (test phones only)
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta, timezone

import httpx

LIVE = "live"
GRAPH = "https://graph.facebook.com/v21.0"


def cfg(key: str) -> str:
    return os.environ.get(key, "").strip()


def enabled() -> bool:
    return bool(cfg("WHATSAPP_TOKEN") and cfg("WHATSAPP_PHONE_NUMBER_ID"))


def digits(n: str) -> str:
    return re.sub(r"\D", "", n or "")


def allowed(wa_id: str) -> bool:
    """Only the test phones may talk to the live bot (no real patients during the test)."""
    allow = [digits(x) for x in cfg("WHATSAPP_ALLOWED").split(",") if digits(x)]
    w = digits(wa_id)
    # Mexican numbers may arrive as 521XXXXXXXXXX or 52XXXXXXXXXX: compare the last 10 digits.
    return bool(allow) and any(w[-10:] == a[-10:] for a in allow)


def signature_ok(body: bytes, header: str | None) -> bool:
    secret = cfg("WHATSAPP_APP_SECRET")
    if not secret:
        return True  # not configured: accept (fine for a short test, set it for anything longer)
    if not header or not header.startswith("sha256="):
        return False
    mac = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, header[7:])


def clinic_now() -> str:
    """Real clinic time (Mexico, UTC-6 all year)."""
    return (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M")


def to_whatsapp_text(md: str) -> str:
    """Markdown from the agents -> WhatsApp formatting (*bold*, plain lists)."""
    t = re.sub(r"\*\*(.+?)\*\*", r"*\1*", md or "")
    t = re.sub(r"^#{1,4}\s*", "", t, flags=re.M)
    return t[:4000]


def recipient(wa_id: str) -> str:
    """Mexican mobiles arrive as 521 + 10 digits but must be addressed as 52 + 10 digits
    (otherwise Meta answers 'recipient not in allowed list')."""
    d = digits(wa_id)
    return "52" + d[3:] if d.startswith("521") and len(d) == 13 else d


async def send_text(to: str, text: str) -> dict:
    url = f"{GRAPH}/{cfg('WHATSAPP_PHONE_NUMBER_ID')}/messages"
    payload = {"messaging_product": "whatsapp", "to": recipient(to), "type": "text",
               "text": {"preview_url": False, "body": to_whatsapp_text(text)}}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, json=payload, headers={"Authorization": f"Bearer {cfg('WHATSAPP_TOKEN')}"})
    out = {"status": r.status_code, "body": r.text[:300]}
    if r.status_code >= 300:
        print("[whatsapp] send failed:", out)
    return out


async def mark_read(message_id: str) -> None:
    url = f"{GRAPH}/{cfg('WHATSAPP_PHONE_NUMBER_ID')}/messages"
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, json={"messaging_product": "whatsapp", "status": "read", "message_id": message_id},
                          headers={"Authorization": f"Bearer {cfg('WHATSAPP_TOKEN')}"})


def outbound(s, pid: str, text: str) -> None:
    """Called for every message the clinic sends to a patient: in the live clinic it goes out on WhatsApp."""
    if s.c.get("mode") != "live" or not enabled():
        return
    phone = s.c["patients"].get(pid, {}).get("phone")
    if not phone:
        return
    try:
        asyncio.get_running_loop().create_task(send_text(phone, text))
    except RuntimeError:  # no loop (unit tests): send synchronously
        asyncio.run(send_text(phone, text))


# --------------------------------------------------------------------------------------
# Inbound
# --------------------------------------------------------------------------------------
def live_session():
    from . import runtime, sim, store
    s = runtime.get_session(LIVE)
    c = s.c
    if c.get("mode") != "live":
        c["mode"] = "live"
        c["now"] = max(clinic_now(), store.WEEK_START)
        sim.ensure_demo_attachments(s)
        c["events"], c["fired"] = [], []   # no scripted week: only real messages
        c.setdefault("phones", {})
        s.save()
    return s


def patient_for(s, wa_id: str, name: str) -> str:
    from . import store
    c = s.c
    pid = c.setdefault("phones", {}).get(digits(wa_id))
    if pid and pid in c["patients"]:
        return pid
    pid = f"p_wa{digits(wa_id)[-6:]}"
    p = store._patient(pid, (name or f"WhatsApp {digits(wa_id)[-4:]}").strip()[:40], 0, "New WhatsApp contact", "inquiry")
    p["phone"] = digits(wa_id)
    c["patients"][pid] = p
    c["phones"][digits(wa_id)] = pid
    return pid


def parse(payload: dict) -> list[dict]:
    """Meta webhook payload -> [{id, from, name, text, kind}] (status updates are ignored)."""
    out = []
    for entry in payload.get("entry", []):
        for ch in entry.get("changes", []):
            v = ch.get("value", {})
            names = {x.get("wa_id"): x.get("profile", {}).get("name", "") for x in v.get("contacts", [])}
            for m in v.get("messages", []):
                kind = m.get("type")
                text = (m.get("text") or {}).get("body") if kind == "text" else \
                       (m.get("button") or {}).get("text") or ((m.get("interactive") or {}).get("button_reply") or {}).get("title")
                out.append({"id": m.get("id"), "from": m.get("from"), "name": names.get(m.get("from"), ""),
                            "text": text, "kind": kind})
    return out


async def handle(payload: dict, run_id: str) -> None:
    """Process one webhook call in the live clinic (runs in the background; Meta gets its 200 at once)."""
    from . import agents, sim
    s = live_session()
    c = s.c
    seen = c.setdefault("wa_seen", [])
    for m in parse(payload):
        if not m["id"] or m["id"] in seen:
            continue  # Meta retries: never answer twice
        seen.append(m["id"])
        del seen[:-500]
        if not allowed(m["from"]):
            print("[whatsapp] ignored message from a number not on WHATSAPP_ALLOWED:", m["from"][-4:])
            continue
        c["now"] = max(c["now"], clinic_now())
        pid = patient_for(s, m["from"], m["name"])
        if enabled():
            asyncio.get_running_loop().create_task(mark_read(m["id"]))
        if not m["text"]:
            s.add_message(f"wa:{pid}", "patient", c["patients"][pid]["name"], f"(sent a {m['kind']})")
            agents.send_to_patient(s, pid, "Thanks! For now I can only read text messages here. If it's a study or a referral, "
                                           "please bring it to your visit or tell me what it says.")
            continue
        await sim.patient_message(s, pid, m["text"], None, bot_turns=0, run_id=run_id)
        s.save()
