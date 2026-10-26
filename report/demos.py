"""The three user-test demos, rendered for the report and the slides from data/demo_runs.json (tools/demo_runs.py)."""

import html
import json
from pathlib import Path

R = Path(__file__).parent
DR = json.loads((R / "data" / "demo_runs.json").read_text(encoding="utf-8"))
G, GD, GDD, GL, GREY = "#29BA74", "#197A56", "#03522D", "#DCF3E7", "#E8EAED"
WHO = {"patient": "Patient", "doctor": "Doctor", "you": "Therapist", "clinic": "Clock"}
META = {
    "demo1": {"n": 5, "shot": "demo1_combo.png", "w": "70%",
              "lead": "Valentina is hard to book: she asks for a time, cancels four hours before, argues about the fee, "
                      "wants to be moved earlier if anything opens, and finally needs her next weeks booked. "
                      "Patient Success handles every message; the therapist taps three decisions and asks for one thing; code does the rest."},
    "demo2": {"n": 6, "shot": "demo2_combo.png", "w": "80%",
              "lead": "Javier writes for the first time, answers the intake, comes for his first visit; the therapist sends "
                      "the session notes and the Health Advisor, with the Clinical Scribe, drafts the evaluation in the clinic's "
                      "form and a treatment plan (Exhibits 8 and 9). The therapist signs and approves; the sessions book themselves."},
    "demo3": {"n": 7, "shot": "demo3_combo.png", "w": "78%",
              "lead": "A normal day (late start, a blocked hour, a family booking, a payment) runs to closing; the therapist "
                      "asks who owes money, the week runs to Saturday, and the therapist asks how the "
                      "week went. Finance Ops and the Operations Partner answer from the ledger and the agenda."},
}


def esc(x):
    return html.escape(str(x or ""))


def short(t, n):
    t = " ".join(str(t or "").replace("**", "").split())
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0] + "…"


def agents_of(st):
    out = []
    for r in st["runs"]:
        if r["agent"] not in out:
            out.append(r["agent"])
    return out


def what(st):
    """One line on what happened in a step, from its messages, cards and decisions."""
    ms = st["messages"]
    parts = []
    first_in = None if st["actor"] == "clinic" else next((m for m in ms if m["role"] in ("patient", "therapist")), None)
    if first_in:
        who = "Therapist" if first_in["role"] == "therapist" else first_in["author"].split()[0]
        parts.append(f'{who}: "{esc(short(first_in["text"], 75))}"')
    for a in st["decided"]:
        parts.append(f'Therapist taps <b>{esc(a["status"])}</b>: {esc(short(a["title"], 60))}')
    if st["actor"] == "clinic":
        auto = sum(1 for m in ms if "automatic" in m["author"] or m["role"] == "patient")
        if auto > 4:
            parts.append(f"The clock runs: {len(ms)} messages (reminders, confirmations, ratings), almost all sent by code")
    reply = next((m for m in ms if m["role"] in ("agent", "system") and m is not first_in
                  and "automatic" not in m["author"]), None)
    if reply:
        text = reply["text"]
        if text.startswith("Hi! I'm the AI assistant"):   # skip the AI disclosure line on first contact
            text = text.split("Lic. Ana.", 1)[-1]
        parts.append(f'{esc(reply["author"].replace("Movimiento Fisioterapia (AI assistant)", "AI"))}: '
                     f'"{esc(short(text, 85))}"')
    for a in st["approvals"]:
        parts.append(f'<span class="chip">card</span> {esc(short(a["title"], 70))}')
    return "<br>".join(parts) or "-"


def tools_of(st):
    if not st["runs"] and not st["tools"]:
        return "<i>code only</i> (approvals.py, policy, booking)" if st["actor"] != "clinic" else "<i>code only</i> (simulated clock, reminders)"
    by = {}
    for t in st["tools"]:
        if t["tool"] not in by.setdefault(t["agent"], []):
            by[t["agent"]].append(t["tool"])
    lines = []
    for a in agents_of(st) or list(by):
        tl = by.get(a, [])
        lines.append(f"<b>{esc(a)}</b>" + (": <code>" + "</code>, <code>".join(esc(x) for x in tl) + "</code>" if tl else ": reply only"))
    return "<br>".join(lines)


def flow(dm):
    """Swimlane-free flow: one chip per step, coloured by who acts; the agents under each chip."""
    steps = [s for s in dm["steps"] if s["focus"]]
    per_row, w, h, gap, row_h = 5, 142, 60, 12, 104
    rows = (len(steps) + per_row - 1) // per_row
    W, H = per_row * (w + gap), rows * row_h + 6
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" style="max-height:{rows * 1.05:.2f}in">']
    for i, st in enumerate(steps):
        x, y = (i % per_row) * (w + gap), (i // per_row) * row_h + 4
        fill, ink = {"you": (GDD, "#fff"), "clinic": (GL, GDD)}.get(st["actor"], (GREY, "#212427"))
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}"/>')
        out.append(f'<text x="{x + 8}" y="{y + 15}" font-size="10" font-weight="700" fill="{G if st["actor"] == "you" else GD}">'
                   f'{i + 1} · {WHO.get(st["actor"], st["actor"]).upper()}</text>')
        words, line, lines = short(st["title"].strip('"'), 64).split(), "", []
        for wd in words:
            if len(line + " " + wd) > 24:
                lines.append(line)
                line = wd
            else:
                line = (line + " " + wd).strip()
        lines.append(line)
        for k, ln in enumerate(lines[:3]):
            out.append(f'<text x="{x + 8}" y="{y + 30 + k * 12}" font-size="10.5" fill="{ink}">{esc(ln)}</text>')
        ag = ", ".join(agents_of(st)) or "code only"
        out.append(f'<text x="{x + 4}" y="{y + h + 13}" font-size="9.5" fill="{GD}" font-weight="700">{esc(short(ag, 30))}</text>')
        cost = f"${st['usd']:.4f}" if st["usd"] else "$0"
        out.append(f'<text x="{x + 4}" y="{y + h + 25}" font-size="9" fill="#5F6368">{cost}</text>')
        if i % per_row != per_row - 1 and i < len(steps) - 1:
            out.append(f'<path d="M{x + w + 1},{y + h / 2} l{gap - 3},0" stroke="{GD}" stroke-width="1.6" marker-end="url(#ar)"/>')
    out.insert(1, f'<defs><marker id="ar" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">'
                  f'<path d="M0,0 L6,3 L0,6 z" fill="{GD}"/></marker></defs>')
    out.append("</svg>")
    return "".join(out)


def table(dm):
    steps = [s for s in dm["steps"] if s["focus"]]
    rows = ['<table class="demo"><tr><th>#</th><th>Who</th><th>What happened</th><th>Agent · tools called</th>'
            '<th class="n">Tokens in (cached) / out</th><th class="n">Cost</th></tr>']
    for i, st in enumerate(steps, 1):
        tk = (f'{st["input_tokens"]:,} ({st["cached_tokens"]:,}) / {st["output_tokens"]:,}' if st["input_tokens"] else "-")
        rows.append(f'<tr><td>{i}</td><td>{WHO.get(st["actor"], st["actor"])}</td><td>{what(st)}</td><td>{tools_of(st)}</td>'
                    f'<td class="n">{tk}</td><td class="n">{"$%.5f" % st["usd"] if st["usd"] else "$0"}</td></tr>')
    t = {k: sum(s[k] for s in steps) for k in ("input_tokens", "cached_tokens", "output_tokens", "usd", "seconds")}
    runs = sum(len(s["runs"]) for s in steps)
    taps = sum(len(s["decided"]) for s in steps)
    rows.append(f'<tr class="total"><td></td><td colspan="3">{len(steps)} steps · {runs} agent runs · {taps} approval taps by the therapist · '
                f'{t["seconds"]:.0f} s end to end</td><td class="n">{t["input_tokens"]:,} ({t["cached_tokens"]:,}) / {t["output_tokens"]:,}</td>'
                f'<td class="n">${t["usd"]:.4f}</td></tr></table>')
    return "\n".join(rows), t, runs, taps, len(steps)


def exhibit(dm):
    m = META[dm["id"]]
    tab, t, runs, taps, n = table(dm)
    return (f'<div class="ex demo-ex"><div class="et"><span class="n">Exhibit {m["n"]}</span>Demo {dm["id"][-1]} · {esc(dm["title"])}: '
            f'{n} steps, {runs} agent runs, {taps} taps by the therapist, ${t["usd"]:.4f} of AI</div>'
            f'<p>{m["lead"]}</p>{flow(dm)}{tab}'
            f'<img src="shots/{m["shot"]}" alt="Demo {dm["id"][-1]} on screen" style="width:{m["w"]}">'
            f'<div class="src"><b>Read:</b> chips are steps (dark = the therapist, grey = a patient or doctor, mint = the clock); '
            f'under each, the agents that ran and the step\'s cost. Screenshots: the conversations at the end of the demo. '
            f'<b>Source:</b> replay of the user-test demos with <code>tools/demo_runs.py</code> and <code>tools/demo_shots.py</code>, '
            f'{esc(DR["measured"])}, {esc(DR["model"])}; same scripted patient lines, live agents.</div></div>')


def slide():
    cols = []
    for dm in DR["demos"]:
        m = META[dm["id"]]
        _, t, runs, taps, n = table(dm)
        steps = [s for s in dm["steps"] if s["focus"]]
        li = "".join(f'<li><b>{WHO.get(s["actor"], "")[:1]}</b> {esc(short(s["title"].strip(chr(34)), 40))}</li>' for s in steps)
        cols.append(f'<div class="dcol"><p class="q">Demo {dm["id"][-1]} · {esc(dm["title"].split(":")[0])}</p>'
                    f'<img class="shot" src="shots/{m["shot"]}" alt="Demo" style="max-height:150px;width:auto;max-width:100%">'
                    f'<ol class="dsteps">{li}</ol>'
                    f'<div class="dkpi"><b>${t["usd"]:.4f}</b> · {runs} agent runs · {taps} taps</div></div>')
    return '<div class="dgrid">' + "".join(cols) + "</div>"


def markers() -> dict:
    out = {f"DEMO_{dm['id'][-1]}": exhibit(dm) for dm in DR["demos"]}
    out["SLIDE_DEMOS"] = slide()
    out["DEMOS_USD"] = f'${sum(table(dm)[1]["usd"] for dm in DR["demos"]):.4f}'   # the demo steps shown (Demo 3's setup steps excluded)
    out["DEMOS_MEASURED"] = esc(DR["measured"])
    return out
