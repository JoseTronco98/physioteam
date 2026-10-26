"""Fill the ⟦MARKERS⟧ in report.src.html / slides.src.html from the measured data.

Inputs (report/data/):  report_data.json  (tools/report_data.py)
                        eval_quality.json (tools/eval_quality.py)
                        user_test.json    (optional: the therapist's test; see user_test_guide.md)
                        demo_runs.json    (tools/demo_runs.py: the three user-test demos, rendered by demos.py)
Outputs: report/report.ready.html, report/slides.ready.html  → then build.py embeds the images.
Run: python report/fill.py
"""

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import demos  # noqa: E402

R = Path(__file__).parent
D = json.loads((R / "data" / "report_data.json").read_text(encoding="utf-8"))
Q = json.loads((R / "data" / "eval_quality.json").read_text(encoding="utf-8"))
C = json.loads((R / "data" / "costs.json").read_text(encoding="utf-8"))   # sourced prices: WhatsApp, hosting, FX, receptionist
UT = json.loads((R / "data" / "user_test.json").read_text(encoding="utf-8")) if (R / "data" / "user_test.json").is_file() else {}
LABEL = {"patient_success": "Patient Success", "ops_partner": "Operations Partner", "health_advisor": "Health Advisor",
         "finance_ops": "Finance Ops", "clinical_scribe": "Clinical Scribe", "imaging_reader": "Imaging Reader", "router": "Router"}
G, GD, GDD, GL = "#29BA74", "#197A56", "#03522D", "#DCF3E7"


def usd(x, d=4):
    return f"${x:,.{d}f}"


def tok(n):
    return f"{int(n):,}"


# ------------------------------------------------------------------ charts (inline SVG)
def hbars(rows, unit="h", width=560, color=G, max_v=None, label_w=190):
    """rows: [(label, value, note)] -> horizontal bar chart."""
    h = 26 * len(rows) + 10
    mx = max_v or max(v for _, v, _ in rows) or 1
    out = [f'<svg viewBox="0 0 {width} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for i, (lab, v, note) in enumerate(rows):
        y = 6 + i * 26
        w = (width - label_w - 70) * v / mx
        out.append(f'<text x="{label_w - 8}" y="{y + 14}" text-anchor="end" font-size="11" fill="#212427">{html.escape(lab)}</text>')
        out.append(f'<rect x="{label_w}" y="{y}" width="{max(w, 1):.1f}" height="18" fill="{color}"/>')
        out.append(f'<text x="{label_w + w + 6:.1f}" y="{y + 14}" font-size="11" font-weight="700" fill="{GDD}">{v:.1f} {unit}</text>')
        if note:
            out.append(f'<text x="{label_w + w + 52:.1f}" y="{y + 14}" font-size="9.5" fill="#5F6368">{html.escape(note)}</text>')
    out.append("</svg>")
    return "".join(out)


def before_after(rows, width=560, unit="h"):
    """rows: [(label, before, after)] -> paired bars (unit "h" or "min")."""
    fmt = (lambda v: f"{v:.1f} h") if unit == "h" else (lambda v: f"{v:.0f} min")
    h = 34 * len(rows) + 34
    mx = max(b for _, b, _ in rows) or 1
    lw = 150
    out = [f'<svg viewBox="0 0 {width} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">',
           f'<rect x="{lw}" y="2" width="12" height="10" fill="#B9B9B9"/><text x="{lw + 16}" y="11" font-size="10" fill="#5F6368">By hand today</text>',
           f'<rect x="{lw + 110}" y="2" width="12" height="10" fill="{G}"/><text x="{lw + 126}" y="11" font-size="10" fill="#5F6368">With PhysioTeam</text>']
    for i, (lab, b, a) in enumerate(rows):
        y = 22 + i * 34
        wb, wa = (width - lw - 60) * b / mx, (width - lw - 60) * a / mx
        out.append(f'<text x="{lw - 8}" y="{y + 18}" text-anchor="end" font-size="11" fill="#212427">{html.escape(lab)}</text>')
        out.append(f'<rect x="{lw}" y="{y}" width="{max(wb, 1):.1f}" height="13" fill="#B9B9B9"/>'
                   f'<text x="{lw + wb + 5:.1f}" y="{y + 11}" font-size="10" fill="#5F6368">{fmt(b)}</text>')
        out.append(f'<rect x="{lw}" y="{y + 15}" width="{max(wa, 1):.1f}" height="13" fill="{G}"/>'
                   f'<text x="{lw + wa + 5:.1f}" y="{y + 26}" font-size="10" font-weight="700" fill="{GDD}">{fmt(a)}</text>')
    out.append("</svg>")
    return "".join(out)


def cache_chart():
    rows = [("No caching (same tokens)", 0.0087), ("Explicit breakpoints", 0.00358), ("Automatic caching (used)", 0.00336)]
    w, lw = 360, 150
    out = [f'<svg viewBox="0 0 {w} 96" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for i, (lab, v) in enumerate(rows):
        y = 6 + i * 30
        bw = (w - lw - 60) * v / 0.0087
        col = "#B9B9B9" if i == 0 else (GD if i == 2 else G)
        out.append(f'<text x="{lw - 6}" y="{y + 14}" text-anchor="end" font-size="10.5" fill="#212427">{lab}</text>'
                   f'<rect x="{lw}" y="{y}" width="{bw:.1f}" height="18" fill="{col}"/>'
                   f'<text x="{lw + bw + 5:.1f}" y="{y + 14}" font-size="10.5" font-weight="700" fill="{GDD}">${v:.4f}</text>')
    out.append("</svg>")
    return "".join(out)


def diagram():
    """Agent architecture in the report's greens."""
    box = lambda x, y, w, h, fill, stroke, t1, t2, c1="#212427", c2="#5F6368": (  # noqa: E731
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.3"/>'
        f'<text x="{x + w / 2}" y="{y + h / 2 - (3 if t2 else -5)}" text-anchor="middle" font-size="13.5" font-weight="700" fill="{c1}">{t1}</text>'
        + (f'<text x="{x + w / 2}" y="{y + h / 2 + 14}" text-anchor="middle" font-size="10.5" fill="{c2}">{t2}</text>' if t2 else ""))
    arrow = lambda x1, y1, x2, y2, c="#5F6368", d="": (  # noqa: E731
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="1.6" {d} marker-end="url(#ah)"/>')
    s = ['<svg viewBox="0 0 980 450" width="100%" xmlns="http://www.w3.org/2000/svg">',
         f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#5F6368"/></marker></defs>',
         '<rect x="0" y="0" width="980" height="450" fill="#FFFFFF"/>',
         box(20, 30, 165, 66, "#F2F2F2", "#B9B9B9", "Patients", "WhatsApp"),
         box(20, 200, 165, 66, "#F2F2F2", "#B9B9B9", "Referring doctors", "doctor channel"),
         box(215, 30, 140, 66, "#FFF8E6", "#B8860B", "Safety layer", "code, before any model", "#7A5A00", "#7A5A00"),
         box(385, 30, 165, 66, "#FFFFFF", G, "Patient Success", "only voice to patients"),
         box(385, 145, 165, 52, "#FFFFFF", G, "Finance Ops", ""),
         box(385, 280, 165, 52, "#FFFFFF", G, "Clinical Scribe", ""),
         box(385, 350, 165, 52, "#FFFFFF", G, "Imaging Reader", ""),
         box(585, 135, 190, 66, GD, GD, "Operations Partner", "lead · agenda, money", "#FFFFFF", "#DCF3E7"),
         box(585, 280, 190, 66, GD, GD, "Health Advisor", "lead · clinical, doctors", "#FFFFFF", "#DCF3E7"),
         box(805, 30, 155, 66, GDD, GDD, "The therapist", "chat · approvals", "#FFFFFF", "#DCF3E7"),
         arrow(185, 63, 213, 63), arrow(355, 63, 383, 63), arrow(550, 80, 610, 133),
         arrow(583, 171, 552, 171), arrow(583, 306, 552, 306), arrow(600, 346, 552, 372),
         arrow(185, 233, 583, 300), arrow(680, 203, 680, 278, "#5F6368", 'stroke-dasharray="4 4"'),
         '<text x="690" y="245" font-size="10.5" fill="#5F6368">one hand-off per request</text>',
         arrow(880, 98, 777, 160, GDD), arrow(880, 98, 777, 300, GDD),
         f'<rect x="20" y="415" width="940" height="30" rx="3" fill="{GL}" stroke="{G}"/>',
         f'<text x="490" y="435" text-anchor="middle" font-size="11.5" fill="{GDD}"><tspan font-weight="700">Code layer (no model):</tspan> approvals executed in code · 24 h policy · waitlist · reminders · 1-5 feedback · spend caps · audit trail · loop guard</text>',
         "</svg>"]
    return "".join(s)


# ------------------------------------------------------------------ tables
def trace_table(rows):
    out = ['<table><tr><th>#</th><th>Step</th><th>Agent</th><th>What happened</th><th class="n">Input (cached)</th><th class="n">Output</th><th class="n">Cost</th></tr>']
    i = 0
    for r in rows:
        if r["event"] not in ("agent_run", "tool"):
            continue
        i += 1
        u = r.get("usage") or {}
        what = r.get("summary") if r["event"] == "tool" else f"model run ({u.get('calls', '')} calls), reply composed"
        name = r.get("tool") if r["event"] == "tool" else "model"
        out.append(f'<tr><td>{i}</td><td><code>{html.escape(name or "")}</code></td><td>{LABEL.get(r.get("agent"), r.get("agent") or "")}</td>'
                   f'<td>{html.escape(str(what or ""))}</td><td class="n">{tok(u["input_tokens"]) + " (" + tok(u["cached_tokens"]) + ")" if u else "code"}</td>'
                   f'<td class="n">{tok(u["output_tokens"]) if u else ""}</td><td class="n">{usd(r["usd"], 5) if r.get("usd") else "$0"}</td></tr>')
    cost = sum(r.get("usd") or 0 for r in rows if r["event"] == "agent_run")
    secs = sum(r.get("seconds") or 0 for r in rows if r["event"] == "agent_run")
    out.append(f'<tr class="total"><td></td><td colspan="5">Total (tools are Python, run in code; cost is the model runs only) · {secs:.0f} s of model time</td>'
               f'<td class="n">{usd(cost, 5)}</td></tr></table>')
    return "\n".join(out), cost, secs


def main():
    st, ap, wa = D["stories"], D["autopilot"], D["week_activity"]
    steps = {(x["story"], x["step"]): x for x in st["steps"]}
    week_usd, cached, patients = ap["product_usd"], ap["cached_share_pct"], ap["patients"]
    month = week_usd * 4.3
    s_tot = st["total"]

    # traces
    tr1, t1_usd, _ = trace_table(D["trace_valentina_ask"])
    tr2, t2_usd, t2_secs = trace_table(D["trace_javier_notes"])
    t1_slot = re.search(r"come (.+?) for my", D["t1_text"]).group(1)

    # typical runs
    pick = [("booking", "ask", "A patient asks for a time → booking held for approval"),
            ("booking", "cancel", "A late cancellation → policy, fee card, waitlist check"),
            ("booking", "argue", "The patient disputes the fee → kind, firm answer"),
            ("results", "day", "\"What's my day?\" (Operations Partner)"),
            ("results", "ask", "\"How did the week go?\" (Ops + Finance Ops)"),
            ("doctor", "ask", "A doctor asks → progress report drafted"),
            ("newpatient", "notes", "First-visit notes → evaluation + plan + home program"),
            ("newpatient", "followup", "Follow-up notes → SOAP note"),
            ("safety", "inject", "Prompt injection → blocked in code")]
    rows = ['<table><tr><th>Run</th><th class="n">Input</th><th class="n">Cached</th><th class="n">Output</th><th class="n">Calls</th><th class="n">Seconds</th><th class="n">Cost</th></tr>']
    for sid, step, label in pick:
        x = steps[(sid, step)]
        rows.append(f'<tr><td>{label}</td><td class="n">{tok(x["input_tokens"])}</td><td class="n">{tok(x["cached_tokens"])}</td>'
                    f'<td class="n">{tok(x["output_tokens"])}</td><td class="n">{x["calls"]}</td><td class="n">{x["seconds"]}</td><td class="n">{usd(x["usd"], 5)}</td></tr>')
    rows.append(f'<tr class="total"><td>All five stories (51 steps)</td><td class="n">{tok(s_tot["input_tokens"])}</td><td class="n">{tok(s_tot["cached_tokens"])}</td>'
                f'<td class="n">{tok(s_tot["output_tokens"])}</td><td class="n">{s_tot["calls"]}</td><td class="n">{st["wall_seconds"]}</td><td class="n">{usd(s_tot["usd"])}</td></tr></table>')
    runs_table = "\n".join(rows)

    # week by agent
    def week_rows(short=False):
        r = ['<table><tr><th>Agent</th>' + ('' if short else '<th class="n">Input</th><th class="n">Cached</th>') +
             '<th class="n">Output</th><th class="n">Calls</th><th class="n">Cost</th></tr>']
        for k, b in sorted(ap["by_agent"].items(), key=lambda kv: -kv[1]["usd"]):
            r.append(f'<tr><td>{LABEL.get(k, k)}</td>' + ('' if short else f'<td class="n">{tok(b["input_tokens"])}</td><td class="n">{tok(b["cached_tokens"])}</td>') +
                     f'<td class="n">{tok(b["output_tokens"])}</td><td class="n">{b["calls"]}</td><td class="n">{usd(b["usd"], 5)}</td></tr>')
        w = ap["total"]
        r.append(f'<tr class="total"><td>Clinic week · {patients} patients · {ap["messages"]} msgs</td>' +
                 ('' if short else f'<td class="n">{tok(w["input_tokens"])}</td><td class="n">{tok(w["cached_tokens"])}</td>') +
                 f'<td class="n">{tok(w["output_tokens"])}</td><td class="n">{w["calls"]}</td><td class="n">{usd(week_usd)}</td></tr></table>')
        if not short:
            r.append(f'<div class="src">{ap["tokens_per_patient_week"]:,} tokens per patient per week · {cached}% of input from cache · '
                     f'simulator bots ${ap["simulator_usd"]:.4f} (excluded) · {ap["wall_seconds"]} s to simulate the week.</div>')
        return "\n".join(r)

    scale = ['<table><tr><th>Clinics</th><th class="n">Per month</th><th class="n">At 10× traffic</th><th class="n">Per year</th></tr>']
    for n in (1, 100, 10_000):
        scale.append(f'<tr><td>{n:,}</td><td class="n">{usd(month * n, 2)}</td><td class="n">{usd(month * n * 10, 2)}</td><td class="n">{usd(month * n * 12, 2)}</td></tr>')
    scale.append("</table>")

    # quality
    qs, qr = Q["summary"], Q["rows"]
    ev, so = qs["evaluation"], qs["soap"]
    nums = ev["numbers_checked"] + so["numbers_checked"]
    grounded_all = round(100 * (sum(r["grounded"] for r in qr)) / nums, 1)
    ungr = [u for r in qr for u in r["ungrounded"]]
    bmi_like = [r for r in qr if r["kind"] == "evaluation" and r["ungrounded"]]
    qtab = ('<table><tr><th>Document</th><th class="n">Notes</th><th class="n">Form complete</th><th class="n">Numbers grounded</th>'
            '<th class="n">Median time</th><th class="n">Cost each</th></tr>'
            f'<tr><td>Initial evaluation (38 fields + tables)</td><td class="n">{ev["documents"]}</td><td class="n">{ev["completeness_pct"]}%</td>'
            f'<td class="n">{ev["grounded_numbers_pct"]}% of {ev["numbers_checked"]}</td><td class="n">{ev["median_seconds"]} s</td><td class="n">{usd(ev["avg_usd"], 5)}</td></tr>'
            f'<tr><td>SOAP note (S, O, A, P)</td><td class="n">{so["documents"]}</td><td class="n">{so["completeness_pct"]}%</td>'
            f'<td class="n">{so["grounded_numbers_pct"]}% of {so["numbers_checked"]}</td><td class="n">{so["median_seconds"]} s</td><td class="n">{usd(so["avg_usd"], 5)}</td></tr>'
            f'<tr class="total"><td>All 30 notes</td><td class="n">30</td><td class="n">-</td><td class="n">{grounded_all}% of {nums}</td><td class="n"></td><td class="n"></td></tr></table>'
            f'<div class="src">Diagnosis captured in {ev["dx_captured"]}/10 evaluations, prognosis in {ev["prognosis_captured"]}/10. '
            f'The {len(ungr)} ungrounded numbers, reviewed by hand: in evaluations they are derived values (BMI computed from height and weight, '
            f'height converted from cm to m: {", ".join(sorted({u for r in bmi_like for u in r["ungrounded"]}, key=float))}); in SOAP notes, '
            f'session counts and set or repetition numbers restated from the plan. No invented clinical measurement was found.</div>')
    qtab_short = (f'<table><tr><th>Document</th><th class="n">Complete</th><th class="n">Grounded</th><th class="n">Time</th></tr>'
                  f'<tr><td>10 evaluations</td><td class="n">{ev["completeness_pct"]}%</td><td class="n">{ev["grounded_numbers_pct"]}%</td><td class="n">{ev["median_seconds"]} s</td></tr>'
                  f'<tr><td>20 SOAP notes</td><td class="n">{so["completeness_pct"]}%</td><td class="n">{so["grounded_numbers_pct"]}%</td><td class="n">{so["median_seconds"]} s</td></tr></table>')

    # time model: volumes measured, minutes stated (or the therapist's own, from user_test.json)
    m = {"message": 1.5, "reminder": 0.5, "evaluation": 20, "soap": 5, "plan": 10, "report": 15}
    review = {"evaluation": 5, "soap": 1, "plan": 2, "report": 3}
    basis = "stated assumptions"
    if UT.get("minutes"):
        m.update(UT["minutes"])
        basis = UT.get("minutes_basis", "the therapist's own timings from the user test")  # read as "minutes per task are <basis>"
    if UT.get("review_minutes"):
        review.update(UT["review_minutes"])
    msgs = wa["inbound"] - 2 * wa["feedback_ratings"]   # feedback replies only exist because of the system
    evals = wa["evaluations_done"]
    soaps = max(0, wa["sessions_done"] - evals)
    plans = evals
    reports = wa["agent_documents"].get("progress_report", 0)
    escal = wa["escalations_now"] + wa["batched_questions"]
    tasks = [("Patient WhatsApp messages", msgs, m["message"], 0, f"{escal} questions batched for the therapist, ~3 min each"),
             ("Reminders and confirmations", wa["reminders"], m["reminder"], 0, "sent and confirmed in code"),
             ("Initial evaluations", evals, m["evaluation"], review["evaluation"], "read and sign the draft"),
             ("SOAP notes", soaps, m["soap"], review["soap"], "read and sign"),
             ("Treatment plans", plans, m["plan"], review["plan"], "approve; sessions book themselves"),
             ("Progress reports to doctors", reports, m["report"], review["report"], "approve and send")]
    trows = ['<table><tr><th>Task (per week)</th><th class="n">Volume</th><th class="n">Min. by hand</th><th class="n">Min. with PhysioTeam</th>'
             '<th class="n">Hours before</th><th class="n">Hours after</th><th>What the therapist still does</th></tr>']
    before = after = 0.0
    chart_rows = []
    for name, vol, mb, ma, note in tasks:
        hb, ha = vol * mb / 60, (vol * ma + (escal * 3 if "WhatsApp" in name else 0)) / 60
        before += hb
        after += ha
        chart_rows.append((name, hb, ha))
        trows.append(f'<tr><td>{name}</td><td class="n">{vol}</td><td class="n">{mb:g}</td><td class="n">{ma:g}</td>'
                     f'<td class="n">{hb:.1f}</td><td class="n">{ha:.1f}</td><td>{note}</td></tr>')
    trows.append(f'<tr class="total"><td>Total</td><td></td><td></td><td></td><td class="n">{before:.1f}</td><td class="n">{after:.1f}</td>'
                 f'<td>{before - after:.1f} h saved a week</td></tr></table>')
    saved = before - after
    base_chart = hbars([(n, hb, "") for n, hb, _ in sorted(chart_rows, key=lambda x: -x[1])], "h")
    time_chart = before_after(chart_rows)

    rec = wa["recovered"]
    rec_mxn = sum(r["mxn"] for r in rec)
    impact = (f'<table><tr><th>In one measured week</th><th class="n">Value</th></tr>'
              f'<tr><td>Patient WhatsApp messages handled</td><td class="n">{wa["inbound"]}</td></tr>'
              f'<tr><td>… needing the therapist&#39;s attention now (urgent)</td><td class="n">{wa["escalations_now"]}</td></tr>'
              f'<tr><td>… routine clinical questions batched for the next session</td><td class="n">{wa["batched_questions"]}</td></tr>'
              f'<tr><td>Outgoing messages sent by code at zero tokens</td><td class="n">{wa["outbound_code"]} of {wa["outbound_code"] + wa["outbound_model"]}</td></tr>'
              f'<tr><td>Approval cards the therapist tapped</td><td class="n">{sum(v for v in wa["approvals"].values())}</td></tr>'
              f'<tr><td>Freed slots refilled from the waitlist</td><td class="n">{len(rec)} (MXN {rec_mxn:,})</td></tr>'
              f'<tr><td>Session ratings collected · average</td><td class="n">{wa["feedback_ratings"]} · {wa["feedback_avg"]}/5</td></tr>'
              f'<tr><td>Red flags escalated · attacks blocked</td><td class="n">{ap["red_flags_escalated"]} · {ap["attacks_blocked"]}</td></tr>'
              f'<tr class="total"><td>AI cost of the week</td><td class="n">{usd(week_usd)}</td></tr></table>')

    # user test
    vis = UT.get("repo_visibility", "public")
    if UT.get("quote"):
        # the recorded session with the therapist (the demo video is this session, edited)
        # case study (n = 1): the tester's best estimates of her operation, my assumptions labeled
        op = UT["operation"]
        docs = [r for r in chart_rows if r[0] not in ("Patient WhatsApp messages", "Reminders and confirmations")]
        review_ratio = sum(r[2] for r in docs) / sum(r[1] for r in docs)   # documents: after / before in the time model
        tasks = [dict(t) for t in op["tasks"]]
        tasks[1]["after_min"] = round(tasks[1]["before_min"] * review_ratio)
        tasks[1]["after_basis"] = f"assumed: review and sign drafts; the {100 * (1 - review_ratio):.0f}% cut on documents in Exhibit 20"
        cs_before = sum(t["before_min"] for t in tasks)
        cs_after = sum(t["after_min"] for t in tasks)
        cs_day = cs_before - cs_after
        cs_days, price = op["days_per_month"], op["price_mxn"]
        cs_h_month = cs_day * cs_days / 60
        cs_consults = cs_days if cs_day >= 60 else 0
        cs_rev = cs_consults * price
        trow = "".join(f'<tr><td>{html.escape(t["task"])}</td><td>{html.escape(t["when"])}</td><td class="n">{t["before_min"]}</td>'
                       f'<td class="n">{t["after_min"]}</td><td class="n"><b>{t["before_min"] - t["after_min"]}</b></td>'
                       f'<td>{html.escape(t["before_basis"])}; after: {html.escape(t["after_basis"]).replace("assumed: ", "(assumed) ", 1)}</td></tr>' for t in tasks)
        user_test = ('<div class="ex"><div class="et"><span class="n">Exhibit 18</span>'
                     f'Case study, {html.escape(UT["name"])}: about {cs_day} minutes a day back, {cs_before} today vs {cs_after} with PhysioTeam (initial estimate, n = 1)</div>'
                     '<table><tr><th>Task (per working day)</th><th>When</th><th class="n">Today, min</th><th class="n">With PhysioTeam, min</th>'
                     '<th class="n">Saved, min</th><th>Basis</th></tr>' + trow +
                     f'<tr class="total"><td>Total</td><td></td><td class="n">{cs_before}</td><td class="n">{cs_after}</td><td class="n">{cs_day}</td>'
                     f'<td>{cs_day / 60:.1f} h a day · {cs_day * 5 / 60:.1f} h a week · {cs_h_month:.0f} h a month ({cs_days} days)</td></tr></table>'
                     f'<div class="src"><b>Method:</b> {html.escape(op["source_note"])}, after running the three demos herself on a recorded '
                     f'26-minute call (the 5-minute demo video is cut from it). <b>Limits:</b> one practitioner (n = 1); the "today" minutes are her best estimates, the '
                     f'"with PhysioTeam" minutes are the author&#39;s assumptions; {html.escape(UT.get("not_measured", ""))}.</div>'
                     f'<div class="take"><b>"{html.escape(UT["quote_time"])}"</b><br><b>"{html.escape(UT["quote"])}"</b>'
                     f' - {html.escape(UT["name"])}</div></div>')
        one_line = (f'Case study with {html.escape(UT["name"])} (n = 1, initial estimate): about {cs_day} minutes a day back; the freed 8:00 hour '
                    f'becomes a paid consultation, about MXN {cs_rev:,} a month.')
        slide_imp = (f'<div class="take"><b>"{html.escape(UT["quote"])}"</b><br>- {html.escape(UT["name"])}</div>'
                     f'<ul style="font-size:.6em"><li>Booking {tasks[0]["before_min"]} → {tasks[0]["after_min"]} min a day · reports at 8:00 '
                     f'{tasks[1]["before_min"]} → {tasks[1]["after_min"]} · finances after hours {tasks[2]["before_min"]} → {tasks[2]["after_min"]}</li>'
                     f'<li><b>{cs_day} min a day</b> back ({cs_h_month:.0f} h a month) → the 8:00 hour becomes a consultation → '
                     f'<b>{cs_consults} a month → MXN {cs_rev:,}</b></li>'
                     f'<li>Her best estimates; review times assumed; one practitioner (n = 1)</li></ul>')
    else:
        user_test = ('<div class="pending"><b>User test (to be completed with the therapist):</b> 40-minute session, screen shared and recorded. '
                     'Tasks: (A) three patient replies by hand vs with the team, timed; (B) review of a drafted evaluation vs the usual time; '
                     '(C) would the therapist send the doctor report as drafted; (D) the weekly results. Closing: hours saved, willingness to pay, one quote. '
                     'Protocol and data sheet: <code>report/user_test_guide.md</code>. Results replace the stated assumptions in Exhibit 20.</div>')
        one_line = "A practicing therapist is testing it (results in section 6)."
        slide_imp = (f'<div class="pending">User test with a practicing therapist: results go here (quote, timings, ratings).</div>'
                     f'<ul style="font-size:.6em"><li>Refilled slots: MXN {rec_mxn:,} in the measured week</li>'
                     f'<li>{wa["feedback_ratings"]} session ratings collected, average {wa["feedback_avg"]}/5</li></ul>')

    lat_p = sorted(x["seconds"] for x in st["steps"] if x["actor"] == "patient" and x["usd"] > 0)
    lat_t = sorted(x["seconds"] for x in st["steps"] if x["actor"] == "you" and x["usd"] > 0)
    code_share = round(100 * wa["outbound_code"] / max(1, wa["outbound_code"] + wa["outbound_model"]))
    # organization-wide running cost per clinic (monthly): AI measured + WhatsApp templates + hosting, in USD and MXN
    fx = C["fx"]["mxn_per_usd"]
    link = lambda d, k="url", t="label": f'<a href="{d[k]}">{html.escape(d[t])}</a>'
    wa_msgs = (wa["reminders"] + wa["feedback_ratings"]) * 4.3
    wa_usd = wa_msgs * C["whatsapp"]["utility_usd"]
    hours_month = cs_h_month if UT.get("quote") else saved * 4.3
    cols = [(1, C["hosting"]["starter_usd"]), (100, C["hosting"]["scale_usd_per_clinic"]), (10_000, C["hosting"]["scale_usd_per_clinic"])]
    tot = {n: month + wa_usd + h for n, h in cols}
    org = ['<table><tr><th>Per clinic, per month</th><th>Basis</th>' + "".join(f'<th class="n">{n:,} clinic{"s" if n > 1 else ""}</th>' for n, _ in cols) + "</tr>",
           f'<tr><td>AI (all six agents)</td><td>measured week × 4.3</td>' + "".join(f'<td class="n">{usd(month, 2)}</td>' for _ in cols) + "</tr>",
           f'<tr><td>WhatsApp templates (reminders, rating requests)</td><td>{wa_msgs:,.0f} messages × US${C["whatsapp"]["utility_usd"]} (sourced); replies free</td>'
           + "".join(f'<td class="n">{usd(wa_usd, 2)}</td>' for _ in cols) + "</tr>",
           f'<tr><td>Hosting</td><td>Starter instance (sourced); shared at scale (assumed)</td>' + "".join(f'<td class="n">{usd(h, 2)}</td>' for _, h in cols) + "</tr>",
           f'<tr class="total"><td>Total per clinic</td><td>US$ · MXN at {fx:.2f}</td>' + "".join(f'<td class="n">{usd(tot[n], 2)} · MXN {tot[n] * fx:,.0f}</td>' for n, _ in cols) + "</tr>",
           f'<tr><td>All clinics, per month</td><td></td>' + "".join(f'<td class="n">{usd(tot[n] * n, 0)}</td>' for n, _ in cols) + "</tr>",
           f'<tr><td>Cost per hour of the therapist&#39;s time saved</td><td>total ÷ {hours_month:.0f} h saved a month</td>'
           + "".join(f'<td class="n">MXN {tot[n] * fx / hours_month:,.1f}</td>' for n, _ in cols) + "</tr></table>"]
    rec = C["receptionist"]
    org_src = (f'<b>Current method:</b> a part-time receptionist costs about MXN {rec["parttime_mxn"]:,} a month (half the average full-time wage, '
               f'{link(rec)}; {link(rec, "range_url", "range_label")}), about {rec["parttime_mxn"] / (tot[1] * fx):.0f}× PhysioTeam&#39;s running cost '
               f'for one clinic, and a receptionist does not draft clinical forms. <b>Sources:</b> {link(C["whatsapp"])}; {link(C["hosting"])}; '
               f'{link(C["fx"])}, {C["fx"]["date"]}. {html.escape(C["hosting"]["scale_note"])}; {html.escape(C["whatsapp"]["note"])}.')
    # Exhibit 19: the freed 8:00 hour becomes a paid consultation (rows labeled: best estimate / assumed / measured / sourced / calculated)
    run_mxn = tot[1] * fx
    net = cs_rev - run_mxn
    pt_price = C["price_mxn"]
    evenings = tasks[2]["before_min"] - tasks[2]["after_min"]
    th = C["therapists_mx"]
    L = lambda t: f'<span class="chip">{t}</span>'
    crow = lambda k, label, val, src: f'<tr><td>{k}</td><td>{label}</td><td class="n"><b>{val}</b></td><td>{src}</td></tr>'
    case_rows = [
        crow("a", "Minutes freed per working day", f"{cs_day} min", f'{L("best estimate")} {L("assumed")} Exhibit 18'),
        crow("b", "Report work today at 8:00-9:00", f'{tasks[1]["before_min"]} min', f'{L("best estimate")} her usual habit'),
        crow("c", "How the whole hour frees up", f'{tasks[1]["before_min"] - tasks[1]["after_min"]} + {tasks[1]["after_min"]} min',
             f'{L("assumed")} drafts are ready right after each session; the {tasks[1]["after_min"]} min of review fit into the '
             f'{tasks[0]["before_min"]} min that booking frees during clinic hours'),
        crow("d", "Working days a month", f"{cs_days}", f'{L("assumed")} Monday-Friday'),
        crow("e", "Price per consultation", f"MXN {price}", f'{L("sourced")} clinic price list'),
        crow("f", "Extra consultations a month", f"{cs_consults}", f'{L("calculated")} one a day, since a ≥ 60 min; {L("assumed")} demand fills the 8:00 slot'),
        crow("g", "Extra revenue a month", f"MXN {cs_rev:,}", f'{L("calculated")} f × e'),
        crow("h", "Running cost a month", f"MXN {run_mxn:,.0f}", f'{L("measured")} AI + {L("sourced")} WhatsApp, hosting (Exhibit 12)'),
        crow("i", "Net gain a month", f"MXN {net:,.0f}", f'{L("calculated")} g - h; MXN {cs_rev - pt_price:,} if bought at MXN {pt_price} a month'),
        crow("j", "Return on a MXN 500 price", f"{cs_rev / pt_price:.1f}×", f'{L("calculated")} g ÷ price ({L("assumed")} price, section 7)'),
        crow("k", "Cost per hour freed", f"MXN {run_mxn / cs_h_month:,.1f}", f'{L("calculated")} h ÷ {cs_h_month:.0f} h a month'),
        crow("l", "After-hours time back (finances)", f"{evenings * cs_days / 60:.0f} h a month", f'{L("best estimate")} {evenings} min a day, not counted as revenue'),
        crow("m", "Current method: part-time receptionist", f'MXN {C["receptionist"]["parttime_mxn"]:,}', f'{L("sourced")} {link(C["receptionist"])}; covers booking, not clinical reports'),
    ]
    org.insert(-1, f'<tr><td><i>Illustrative, if other clinics resemble the case study:</i> extra revenue, all clinics</td><td>MXN {cs_rev:,} per clinic (Exhibit 19)</td>'
               + "".join(f'<td class="n">MXN {cs_rev * n:,.0f}</td>' for n, _ in cols) + "</tr>")
    org.insert(-1, '<tr class="total"><td><i>Illustrative:</i> net a month, all clinics</td><td>extra revenue - running cost</td>'
               + "".join(f'<td class="n">MXN {(cs_rev - tot[n] * fx) * n:,.0f}</td>' for n, _ in cols) + "</tr>")
    scale_rows = "".join(f'<tr><td>{n:,}</td><td class="n">MXN {cs_rev * n:,.0f}</td><td class="n">MXN {tot[n] * fx * n:,.0f}</td>'
                         f'<td class="n">MXN {(cs_rev - tot[n] * fx) * n:,.0f}</td></tr>' for n in (1, 100, 10_000))
    case_table = ('<table><tr><th></th><th>Input</th><th class="n">Value</th><th>Source</th></tr>' + "".join(case_rows) + "</table>"
                  f'<div class="src"><b>Reach (illustrative):</b> at least {th["count"]:,} physical therapists and related professionals work in Mexico '
                  f'({link(th)}; {html.escape(th["note"])}); at {cs_h_month:.0f} h a month each, about {th["count"] * cs_h_month:,.0f} hours a month. '
                  f'<b>Clinic hours:</b> the app&#39;s simulated clinic opens at 11:00; the case rests on her 8:00 report hour, which PhysioTeam turns into a bookable slot.</div>')
    rep = {
        "REPO_VISIBILITY": "public repo" if vis == "public" else "private repo: zlisto added as collaborator",
        "K_WEEK_USD": usd(week_usd, 3), "K_WEEK_PATIENTS": str(patients), "K_MESSAGES": str(ap["messages"]),
        "K_CACHED": f"{cached:.0f}", "K_HANDLED": f"{ap['handled_without_therapist_pct']:.0f}", "K_MONTH_USD": usd(month, 2),
        "K_STORIES_USD": usd(s_tot["usd"], 3), "K_10K_MONTH": usd(month * 10_000, 0),
        "K_CODE_MSGS": f"{wa['outbound_code']} of {wa['outbound_code'] + wa['outbound_model']} outgoing patient messages ({code_share}%)",
        "K_CODE_MSGS_SHORT": f"{code_share}%",
        "Q_EVAL_COMPLETE": f"{ev['completeness_pct']:.0f}", "Q_SOAP_COMPLETE": f"{so['completeness_pct']:.0f}",
        "Q_GROUNDED": f"{grounded_all:.0f}", "Q_EVAL_SECONDS": f"{ev['median_seconds']:.0f}", "Q_MEASURED": Q["measured"],
        "QUALITY_TABLE": qtab, "QUALITY_TABLE_SHORT": qtab_short,
        "X_BASE_HOURS": f"{before:.0f}", "X_AFTER_HOURS": f"{after:.1f}", "X_SAVED_HOURS": f"{saved:.0f}",
        "X_BASE_CHART": base_chart, "TIME_TABLE": "\n".join(trows), "TIME_CHART": time_chart, "X_TIME_BASIS": basis,
        "X_INBOUND": str(wa["inbound"]), "X_SESSIONS": str(wa["sessions_done"]),
        "X_RECOVERED_MXN": f"{rec_mxn:,}", "X_RECOVERED_MONTH": f"{rec_mxn * 4.3:,.0f}",
        "X_EXTRA_SESSIONS": f"{saved:.0f}", "X_EXTRA_MXN": f"{round(saved) * 400:,}",
        "X_FEEDBACK": str(wa["feedback_ratings"]), "X_FEEDBACK_AVG": str(wa["feedback_avg"]),
        "L_PATIENT": f"{lat_p[len(lat_p) // 2]:.1f}", "L_THERAPIST": f"{lat_t[len(lat_t) // 2]:.1f}",
        "T1_SLOT": t1_slot, "T1_USD": usd(t1_usd, 5), "T2_USD": usd(steps[("newpatient", "notes")]["usd"], 4),
        "T2_HA_USD": usd(t2_usd, 5), "T2_SECONDS": f"{t2_secs:.0f}",
        "TRACE1_TABLE": tr1, "TRACE2_TABLE": tr2, "RUNS_TABLE": runs_table,
        "CS_CHART": before_after([("Booking (WhatsApp)", tasks[0]["before_min"], tasks[0]["after_min"]),
                                  ("Reports at 8:00", tasks[1]["before_min"], tasks[1]["after_min"]),
                                  ("Finances after hours", tasks[2]["before_min"], tasks[2]["after_min"])], unit="min"),
        "CASE_TABLE": case_table, "CS_NAME": html.escape(UT["name"]), "CS_MIN_DAY": str(cs_day), "CS_H_DAY": f"{cs_day / 60:.1f}",
        "CS_H_WEEK": f"{cs_day * 5 / 60:.0f}", "CS_H_MONTH": f"{cs_h_month:.0f}", "CS_CONSULTS": str(cs_consults), "CS_REV": f"{cs_rev:,}",
        "CS_NET": f"{net:,.0f}", "CS_RETURN": f"{cs_rev / pt_price:.0f}", "CS_COST_H": f"{run_mxn / cs_h_month:,.1f}",
        "CS_BEFORE": str(cs_before), "CS_AFTER": str(cs_after), "CS_REPORT_BEFORE": str(tasks[1]["before_min"]),
        "CS_REPORT_AFTER": str(tasks[1]["after_min"]),
        "ORG_TABLE": "".join(org), "ORG_SRC": org_src, "K_TOTAL_USD": usd(tot[1], 2), "K_TOTAL_MXN": f"{tot[1] * fx:,.0f}",
        "K_AI_SHARE": f"{100 * month / tot[1]:.0f}", "K_COST_PER_HOUR_MXN": f"{tot[1] * fx / hours_month:,.1f}",
        "K_WA_USD": usd(wa_usd, 2), "K_HOST_USD": usd(C["hosting"]["starter_usd"], 0), "K_RECEP_MXN": f"{rec['parttime_mxn']:,}",
        "WEEK_TABLE": week_rows(), "WEEK_TABLE_SHORT": week_rows(short=True), "SCALE_TABLE": "\n".join(scale),
        "CACHE_CHART": cache_chart(), "IMPACT_TABLE": impact, "DIAGRAM": diagram(),
        "D_MEASURED": D["measured"], "S_LOG": ", ".join(f"{k} {v}" for k, v in D["safety_log"].items()),
        "F_EVAL": D["files"]["eval_javier"], "F_PLAN": D["files"]["plan_javier"],
        "USER_TEST": user_test, "USER_TEST_ONE_LINE": one_line, "SLIDE_IMPACT": slide_imp,
        **demos.markers(),
    }
    for name in ("report", "slides"):
        text = (R / f"{name}.src.html").read_text(encoding="utf-8")
        text = re.sub(r"⟦([A-Z0-9_]+)⟧", lambda mm: rep.get(mm.group(1), mm.group(0)), text)
        left = sorted(set(re.findall(r"⟦[A-Z0-9_]+⟧", text)))
        (R / f"{name}.ready.html").write_text(text, encoding="utf-8")
        print(name, "markers left:", left)
    print(f"time model: {before:.1f} h before, {after:.1f} h after, {saved:.1f} h saved ({basis}); grounded {grounded_all}%")


main()
