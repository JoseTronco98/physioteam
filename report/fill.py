"""Fill the ⟦MARKERS⟧ in report.src.html / slides.src.html from the measured data.

Inputs (report/data/):  report_data.json  (tools/report_data.py)
                        eval_quality.json (tools/eval_quality.py)
                        user_test.json    (optional: the therapist's test; see user_test_guide.md)
Outputs: report/report.ready.html, report/slides.ready.html  → then build.py embeds the images.
Run: python report/fill.py
"""

import html
import json
import re
from pathlib import Path

R = Path(__file__).parent
D = json.loads((R / "data" / "report_data.json").read_text(encoding="utf-8"))
Q = json.loads((R / "data" / "eval_quality.json").read_text(encoding="utf-8"))
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


def before_after(rows, width=560):
    """rows: [(label, before_h, after_h)] -> paired bars."""
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
                   f'<text x="{lw + wb + 5:.1f}" y="{y + 11}" font-size="10" fill="#5F6368">{b:.1f} h</text>')
        out.append(f'<rect x="{lw}" y="{y + 15}" width="{max(wa, 1):.1f}" height="13" fill="{G}"/>'
                   f'<text x="{lw + wa + 5:.1f}" y="{y + 26}" font-size="10" font-weight="700" fill="{GDD}">{a:.1f} h</text>')
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
        basis = "the therapist's own timings from the user test"
    if UT.get("review_minutes"):
        review.update(UT["review_minutes"])
    msgs = wa["inbound"] - 2 * wa["feedback_ratings"]   # feedback replies only exist because of the system
    evals = wa["evaluations_done"]
    soaps = max(0, wa["sessions_done"] - evals)
    plans = evals
    reports = wa["agent_documents"].get("progress_report", 0)
    escal = wa["escalations_now"] + wa["batched_questions"]
    tasks = [("Patient WhatsApp messages", msgs, m["message"], 0, f"{escal} questions batched for her, ~3 min each"),
             ("Reminders and confirmations", wa["reminders"], m["reminder"], 0, "sent and confirmed in code"),
             ("Initial evaluations", evals, m["evaluation"], review["evaluation"], "read and sign the draft"),
             ("SOAP notes", soaps, m["soap"], review["soap"], "read and sign"),
             ("Treatment plans", plans, m["plan"], review["plan"], "approve; sessions book themselves"),
             ("Progress reports to doctors", reports, m["report"], review["report"], "approve and send")]
    trows = ['<table><tr><th>Task (per week)</th><th class="n">Volume</th><th class="n">Min. by hand</th><th class="n">Min. with PhysioTeam</th>'
             '<th class="n">Hours before</th><th class="n">Hours after</th><th>What she still does</th></tr>']
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
              f'<tr><td>… needing her attention now (urgent)</td><td class="n">{wa["escalations_now"]}</td></tr>'
              f'<tr><td>… routine clinical questions batched for the next session</td><td class="n">{wa["batched_questions"]}</td></tr>'
              f'<tr><td>Outgoing messages sent by code at zero tokens</td><td class="n">{wa["outbound_code"]} of {wa["outbound_code"] + wa["outbound_model"]}</td></tr>'
              f'<tr><td>Approval cards she tapped</td><td class="n">{sum(v for v in wa["approvals"].values())}</td></tr>'
              f'<tr><td>Freed slots refilled from the waitlist</td><td class="n">{len(rec)} (MXN {rec_mxn:,})</td></tr>'
              f'<tr><td>Session ratings collected · average</td><td class="n">{wa["feedback_ratings"]} · {wa["feedback_avg"]}/5</td></tr>'
              f'<tr><td>Red flags escalated · attacks blocked</td><td class="n">{ap["red_flags_escalated"]} · {ap["attacks_blocked"]}</td></tr>'
              f'<tr class="total"><td>AI cost of the week</td><td class="n">{usd(week_usd)}</td></tr></table>')

    # user test
    vis = UT.get("repo_visibility", "public")
    if UT.get("quote"):
        ut_rows = [("Admin hours a week today (her estimate)", UT.get("admin_hours_per_week")),
                   ("3 patient replies: by hand vs with PhysioTeam", f'{UT.get("time_by_hand_messages")} vs {UT.get("time_team_messages")}'),
                   ("Quality of the assistant's replies (1-5)", UT.get("rating_messages")),
                   ("Evaluation: her usual time vs reviewing the draft", f'{UT.get("time_by_hand_eval_min")} min vs {UT.get("time_review_eval")}'),
                   ("Evaluation draft usable with few corrections (1-5)", UT.get("rating_eval")),
                   ("Would send the doctor report as drafted", UT.get("doctor_report_ok")),
                   ("Hours a week she thinks it would save", UT.get("hours_saved_estimate")),
                   ("Willing to pay per month (MXN)", UT.get("willingness_to_pay_mxn"))]
        user_test = ('<div class="ex"><div class="et"><span class="n">Exhibit 18a</span>User test: a practicing physical therapist (solo clinic, Mexico), 40 minutes, screen shared</div>'
                     '<table><tr><th>Measure</th><th>Result</th></tr>' +
                     "".join(f"<tr><td>{a}</td><td><b>{html.escape(str(b))}</b></td></tr>" for a, b in ut_rows if b not in (None, "")) +
                     "</table>"
                     f'<div class="take"><b>"{html.escape(UT["quote"])}"</b> - the therapist who tested PhysioTeam</div>'
                     f'<p><b>What she would change:</b> {html.escape(UT.get("changes", ""))} <b>Liked most:</b> {html.escape(UT.get("liked_most", ""))} '
                     f'<b>Liked least:</b> {html.escape(UT.get("liked_least", ""))}</p></div>')
        one_line = f'A practicing therapist tested it: "{html.escape(UT["quote"])}"'
        slide_imp = (f'<div class="take"><b>"{html.escape(UT["quote"])}"</b><br>- the physical therapist who tested it</div>'
                     f'<ul style="font-size:.6em"><li>Evaluation: {UT.get("time_by_hand_eval_min")} min by hand vs {UT.get("time_review_eval")} reviewing the draft</li>'
                     f'<li>Reply quality {UT.get("rating_messages")}/5 · draft usability {UT.get("rating_eval")}/5</li>'
                     f'<li>Refilled slots: MXN {rec_mxn:,} in the measured week</li></ul>')
    else:
        user_test = ('<div class="pending"><b>User test (to be completed with the therapist):</b> 40-minute session, screen shared and recorded. '
                     'Tasks: (A) three patient replies by hand vs with the team, timed; (B) review of a drafted evaluation vs her usual time; '
                     '(C) would she send the doctor report as drafted; (D) her weekly results. Closing: hours saved, willingness to pay, one quote. '
                     'Protocol and data sheet: <code>report/user_test_guide.md</code>. Results replace the stated assumptions in Exhibit 18.</div>')
        one_line = "A practicing therapist is testing it (results in section 6)."
        slide_imp = (f'<div class="pending">User test with a practicing therapist: results go here (quote, timings, ratings).</div>'
                     f'<ul style="font-size:.6em"><li>Refilled slots: MXN {rec_mxn:,} in the measured week</li>'
                     f'<li>{wa["feedback_ratings"]} session ratings collected, average {wa["feedback_avg"]}/5</li></ul>')

    lat_p = sorted(x["seconds"] for x in st["steps"] if x["actor"] == "patient" and x["usd"] > 0)
    lat_t = sorted(x["seconds"] for x in st["steps"] if x["actor"] == "you" and x["usd"] > 0)
    code_share = round(100 * wa["outbound_code"] / max(1, wa["outbound_code"] + wa["outbound_model"]))
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
        "X_EXTRA_SESSIONS": f"{saved:.0f}", "X_EXTRA_MXN": f"{saved * 400:,.0f}",
        "X_FEEDBACK": str(wa["feedback_ratings"]), "X_FEEDBACK_AVG": str(wa["feedback_avg"]),
        "L_PATIENT": f"{lat_p[len(lat_p) // 2]:.1f}", "L_THERAPIST": f"{lat_t[len(lat_t) // 2]:.1f}",
        "T1_SLOT": t1_slot, "T1_USD": usd(t1_usd, 5), "T2_USD": usd(t2_usd, 4), "T2_SECONDS": f"{t2_secs:.0f}",
        "TRACE1_TABLE": tr1, "TRACE2_TABLE": tr2, "RUNS_TABLE": runs_table,
        "WEEK_TABLE": week_rows(), "WEEK_TABLE_SHORT": week_rows(short=True), "SCALE_TABLE": "\n".join(scale),
        "CACHE_CHART": cache_chart(), "IMPACT_TABLE": impact, "DIAGRAM": diagram(),
        "D_MEASURED": D["measured"], "S_LOG": ", ".join(f"{k} {v}" for k, v in D["safety_log"].items()),
        "F_EVAL": D["files"]["eval_javier"], "F_PLAN": D["files"]["plan_javier"],
        "USER_TEST": user_test, "USER_TEST_ONE_LINE": one_line, "SLIDE_IMPACT": slide_imp,
    }
    for name in ("report", "slides"):
        text = (R / f"{name}.src.html").read_text(encoding="utf-8")
        text = re.sub(r"⟦([A-Z0-9_]+)⟧", lambda mm: rep.get(mm.group(1), mm.group(0)), text)
        left = sorted(set(re.findall(r"⟦[A-Z0-9_]+⟧", text)))
        (R / f"{name}.ready.html").write_text(text, encoding="utf-8")
        print(name, "markers left:", left)
    print(f"time model: {before:.1f} h before, {after:.1f} h after, {saved:.1f} h saved ({basis}); grounded {grounded_all}%")


main()
