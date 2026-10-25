"""Cost-cut experiment: the same simulated clinic day with prompt caching ON vs OFF.
Also counts work done in code at zero tokens. Run: python -m tests.caching_ab"""

import asyncio
import json
import sys

from backend import runtime, sim

sys.stdout.reconfigure(encoding="utf-8")


async def one(caching: bool) -> dict:
    s = runtime.reset_session(f"ab_{'on' if caching else 'off'}")
    sim.ensure_demo_attachments(s)
    sim.schedule_week(s)
    s.c["mode"] = "autopilot"
    s.c["caching"] = caching
    await sim.run_autopilot(s, 1)
    prod = s.c["spend"]["product"].values()
    tin = sum(b["input_tokens"] for b in prod)
    out = {
        "caching": caching,
        "product_usd": round(sum(b["usd"] for b in prod), 5),
        "input_tokens": tin,
        "cached_tokens": sum(b["cached_tokens"] for b in prod),
        "cache_write_tokens": sum(b["cache_write_tokens"] for b in prod),
        "output_tokens": sum(b["output_tokens"] for b in prod),
        "model_calls": sum(b["calls"] for b in prod),
        # quality proxies: same work should get done either way
        "bookings_requested": len([a for a in s.c["approvals"].values() if a["kind"] == "booking"]),
        "documents": len([d for d in s.c["documents"].values() if d["versions"][-1]["author"] != "therapist"]),
        "safety_blocks": len([e for e in s.c["safety"] if e["action"] in ("blocked", "escalated")]),
        "patient_msgs": len([m for m in s.c["messages"] if m["thread"].startswith("wa:") and m["role"] == "patient"]),
        "automatic_msgs_zero_tokens": len([m for m in s.c["messages"] if "automatic" in m.get("author", "").lower()
                                            or (m["thread"].startswith("wa:") and m["role"] == "agent" and not m.get("tools") and m.get("agent") in ("ops_partner",))]),
        "errors": [m["text"][:120] for m in s.c["messages"] if m["author"] == "System"],
    }
    return out


async def main():
    on = await one(True)
    off = await one(False)
    print(json.dumps({"on": on, "off": off}, indent=1))
    if off["product_usd"]:
        print("saving_pct", round(100 * (1 - on["product_usd"] / off["product_usd"]), 1))


asyncio.run(main())
