"""Local check of the live WhatsApp path without Meta: a fake webhook call goes through the real
route; outgoing messages are captured instead of sent. Run: python -m tests.whatsapp_local"""

import asyncio
import json
import os
import sys

from fastapi.testclient import TestClient

sys.stdout.reconfigure(encoding="utf-8")
os.environ.update(WHATSAPP_TOKEN="test", WHATSAPP_PHONE_NUMBER_ID="123", WHATSAPP_VERIFY_TOKEN="verify-me",
                  WHATSAPP_ALLOWED="+52 55 1234 5678", WHATSAPP_APP_SECRET="")

from backend import main, runtime, whatsapp  # noqa: E402

SENT = []


async def fake_send(to, text):
    SENT.append((to, text))
    return {"status": 200}


async def fake_read(mid):
    return None

whatsapp.send_text = fake_send
whatsapp.mark_read = fake_read


def payload(frm: str, text: str, mid: str, name: str = "Jose Test") -> dict:
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": "123"},
        "contacts": [{"profile": {"name": name}, "wa_id": frm}],
        "messages": [{"from": frm, "id": mid, "timestamp": "1", "type": "text", "text": {"body": text}}]}}]}]}


def main_():
    runtime.reset_session("live")
    with TestClient(main.app) as client:
        r = client.get("/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
        print("verify:", r.status_code, r.text)
        print("wrong token:", client.get("/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1"}).status_code)
        r = client.post("/webhook/whatsapp", content=json.dumps(payload("5215512345678", "Hi! How much is a first visit, and do you have time tomorrow afternoon?", "wamid.1")))
        print("inbound:", r.status_code, r.json())
        client.post("/webhook/whatsapp", content=json.dumps(payload("5215512345678", "dup", "wamid.1")))  # Meta retry: ignored
        client.post("/webhook/whatsapp", content=json.dumps(payload("5219999999999", "I'm a stranger", "wamid.2", "Stranger")))
        s = runtime.get_session("live")
        import time
        for _ in range(240):
            time.sleep(0.5)
            if SENT and not s.running:
                break
        print("mode:", s.c["mode"], "clock:", s.c["now"], "phones:", s.c.get("phones"))
        for to, text in SENT:
            print(f"SENT to {to}: {text[:300]}")
        print("stranger answered?", any(t.endswith("9999") for t, _ in SENT))


main_()
