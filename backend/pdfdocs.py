"""Professional PDF deliverables: initial evaluation, treatment plan, progress report, SOAP note,
discharge summary. One clean, Apple-like layout on clinic letterhead. Values come only from the
document's fields and structured data; anything missing is printed as "not recorded"."""

from __future__ import annotations

import io
import re
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

from . import store

INK = colors.HexColor("#1D1D1F")
MUTED = colors.HexColor("#6E6E73")
LINE = colors.HexColor("#D2D2D7")
SOFT = colors.HexColor("#F5F5F7")
BLUE = colors.HexColor("#0071E3")
GREEN = colors.HexColor("#1D7A35")
ORANGE = colors.HexColor("#B25E00")

S = {
    "title": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK, spaceAfter=2),
    "kicker": ParagraphStyle("k", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=BLUE, spaceAfter=2),
    "h": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=MUTED, spaceBefore=12, spaceAfter=5, keepWithNext=1),
    "body": ParagraphStyle("b", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK),
    "small": ParagraphStyle("s", fontName="Helvetica", fontSize=8, leading=10.5, textColor=MUTED),
    "cell": ParagraphStyle("c", fontName="Helvetica", fontSize=8.8, leading=11.5, textColor=INK),
    "cellb": ParagraphStyle("cb", fontName="Helvetica-Bold", fontSize=8.8, leading=11.5, textColor=INK),
    "cellh": ParagraphStyle("ch", fontName="Helvetica-Bold", fontSize=7.8, leading=10, textColor=MUTED),
    "right": ParagraphStyle("r", fontName="Helvetica", fontSize=8.5, leading=11, textColor=MUTED, alignment=TA_RIGHT),
}
W = 7.0 * inch


def _esc(t: Any) -> str:
    t = "" if t is None else str(t)
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def _money(x: Any) -> str:
    try:
        return f"{int(str(x).split()[0].replace(',', '')):,}" + (" " + " ".join(str(x).split()[1:]) if len(str(x).split()) > 1 else "")
    except (ValueError, IndexError):
        return str(x)


def P(t: Any, st: str = "body") -> Paragraph:
    return Paragraph(_esc(t) if t not in (None, "") else "<font color='#6E6E73'>not recorded</font>", S[st])


def H(t: str) -> Paragraph:
    return Paragraph(t.upper(), S["h"])


def table(header: list[str], rows: list[list[Any]], widths: list[float], color_last: bool = False) -> Table:
    data = [[Paragraph(_esc(h).upper(), S["cellh"]) for h in header]]
    for r in rows:
        cells = []
        for i, v in enumerate(r):
            st = "cellb" if i == 0 else "cell"
            txt = _esc(v) if v not in (None, "") else "<font color='#6E6E73'>n/r</font>"
            if color_last and i == len(r) - 1 and v:
                low = str(v).lower()
                col = "#1D7A35" if any(k in low for k in ("met", "improv", "+", "better", "achieved")) else (
                    "#B25E00" if any(k in low for k in ("progress", "partial", "re-measure", "not re")) else "#1D1D1F")
                txt = f"<font color='{col}'><b>{txt}</b></font>"
            cells.append(Paragraph(txt, S[st]))
        data.append(cells)
    t = Table(data, colWidths=[w * W for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return t


def boxed(flow: list, bg=SOFT) -> Table:
    t = Table([[flow]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("ROUNDEDCORNERS", [8, 8, 8, 8])]))
    return t


def bullets(items: list[str]) -> list:
    return [Paragraph(f"•&nbsp;&nbsp;{_esc(i)}", S["body"]) for i in items if i] or [P(None)]


def kv(rows: list[tuple[str, Any]], widths=(0.28, 0.72)) -> Table:
    data = [[Paragraph(_esc(k), S["cellh"]), P(v, "cell")] for k, v in rows]
    t = Table(data, colWidths=[widths[0] * W, widths[1] * W])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                           ("LEFTPADDING", (0, 0), (-1, -1), 2)]))
    return t


def markdown_flow(md: str) -> list:
    """Small markdown renderer: headings, bullets, tables, paragraphs."""
    out: list = []
    lines = (md or "").splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        if ln.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                n = max(len(r) for r in rows)
                rows = [r + [""] * (n - len(r)) for r in rows]
                out.append(table(rows[0], rows[1:], [1 / n] * n, color_last=True))
                out.append(Spacer(1, 4))
            continue
        m = re.match(r"#{1,4}\s+(.*)", ln)
        if m:
            out.append(H(m.group(1).strip()))
        elif re.match(r"\s*[-*•]\s+", ln):
            out.append(Paragraph("•&nbsp;&nbsp;" + _esc(re.sub(r"^\s*[-*•]\s+", "", ln)), S["body"]))
        else:
            out.append(Paragraph(_esc(ln), S["body"]))
        i += 1
    return out


# ---------------------------------------------------------------------------------------
def _letterhead(c: dict, title: str, kicker: str, v: dict, patient: dict, recipient: str | None) -> list:
    cl = c["clinic"]
    left = [Paragraph(f"<b>{_esc(cl['name'])}</b>", ParagraphStyle("lh", fontName="Helvetica-Bold", fontSize=12.5, leading=15, textColor=INK)),
            Paragraph(_esc(cl["therapist"]) + "<br/>" + _esc(cl["address"].split(".")[0]), S["small"])]
    right = [Paragraph(f"{_esc(kicker)}<br/>{store.nice(v['created'])}<br/>Version {v['version']} · {v['status']}", S["right"])]
    head = Table([[left, right]], colWidths=[0.65 * W, 0.35 * W])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 1.4, INK),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    ref = c["doctors"].get(patient.get("referring_doctor_id") or "", {}).get("name")
    meta = Table([[
        [Paragraph("PATIENT", S["cellh"]), Paragraph(f"<b>{_esc(patient['name'])}</b>, {patient['age']}", S["cell"])],
        [Paragraph("CONDITION", S["cellh"]), Paragraph(_esc(patient["condition"]), S["cell"])],
        [Paragraph("FOR" if recipient else "REFERRED BY", S["cellh"]), Paragraph(_esc(recipient or ref or "Self-referred"), S["cell"])],
    ]], colWidths=[0.26 * W, 0.46 * W, 0.28 * W])
    meta.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 8)]))
    return [head, Spacer(1, 10), Paragraph(kicker.upper(), S["kicker"]), Paragraph(_esc(title), S["title"]), meta, Spacer(1, 4)]


def _signature(c: dict) -> list:
    t = Table([[Paragraph(_esc(c["clinic"]["therapist"]), S["small"]), Paragraph("Date", S["small"])]], colWidths=[0.55 * W, 0.45 * W])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (0, 0), 0.8, INK), ("LINEABOVE", (1, 0), (1, 0), 0.8, INK),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    return [Spacer(1, 30), KeepTogether([t])]


def _fields(v: dict) -> dict:
    return {f["key"]: f["value"] for f in v.get("fields") or []}


def _evaluation(c, d, v, p) -> list:
    f, data = _fields(v), v.get("data") or {}
    pain = data.get("pain") or {}
    hist = data.get("history") or {}
    out = _letterhead(c, "Initial physiotherapy evaluation", "Evaluation", v, p, None)
    out += [H("Reason for consultation"),
            kv([("Chief complaint", f.get("chief_complaint")), ("Medical diagnosis", f.get("medical_diagnosis")),
                ("Mechanism and date", f.get("mechanism_and_date")), ("Patient goals", f.get("patient_goals")),
                ("Occupation", f.get("occupation"))])]
    out += [H("History"),
            kv([("Family history", hist.get("family") or f.get("family_history")),
                ("Medical history", hist.get("personal") or f.get("medical_history")),
                ("Surgeries", hist.get("surgeries") or f.get("surgeries")), ("Medications", hist.get("medications") or f.get("medications")),
                ("Allergies", f.get("allergies")), ("Lifestyle", hist.get("lifestyle") or f.get("lifestyle"))])]
    out += [H("Pain"),
            table(["Best", "Worst", "Now", "Location", "Pattern"],
                  [[pain.get("best"), pain.get("worst"), pain.get("now"), pain.get("location") or f.get("pain_location"),
                    pain.get("pattern") or f.get("pain_pattern")]] if pain else [[None, None, None, f.get("pain_location"), f.get("pain_vas")]],
                  [0.09, 0.09, 0.09, 0.33, 0.40]),
            Spacer(1, 3), kv([("Aggravating", f.get("aggravating_factors")), ("Relieving", f.get("relieving_factors"))])]
    out += [H("Physical examination"),
            kv([("Posture", f.get("posture")), ("Palpation", f.get("palpation")), ("Sensation", f.get("sensation")),
                ("Imaging", f.get("imaging"))])]
    if data.get("rom"):
        out += [H("Range of motion"), table(["Joint", "Movement", "Right", "Left", "Normal"],
                                            [[r.get("joint"), r.get("movement"), r.get("right"), r.get("left"), r.get("normal")] for r in data["rom"]],
                                            [0.2, 0.25, 0.2, 0.17, 0.18])]
    elif f.get("rom"):
        out += [H("Range of motion"), P(f.get("rom"))]
    if data.get("strength"):
        out += [H("Muscle strength (0-5)"), table(["Muscle", "Right", "Left"],
                                                  [[r.get("muscle"), r.get("right"), r.get("left")] for r in data["strength"]], [0.4, 0.3, 0.3])]
    elif f.get("strength"):
        out += [H("Muscle strength"), P(f.get("strength"))]
    if data.get("special_tests"):
        out += [H("Special tests"), table(["Test", "Right", "Left", "Notes"],
                                          [[r.get("test"), r.get("right"), r.get("left"), r.get("notes")] for r in data["special_tests"]],
                                          [0.3, 0.14, 0.14, 0.42])]
    elif f.get("special_tests"):
        out += [H("Special tests"), P(f.get("special_tests"))]
    if data.get("functional"):
        out += [H("Functional tests"), table(["Test", "Result"], [[r.get("test"), r.get("result")] for r in data["functional"]], [0.35, 0.65])]
    out += [H("Physiotherapy impression"), boxed([P(data.get("impression") or f.get("pt_impression"))])]
    out += [H("Problem list")] + bullets(data.get("problems") or ([f["pt_problems"]] if f.get("pt_problems") else []))
    goals_rows = [["Short term", g] for g in data.get("short_term_goals", [])] + [["Long term", g] for g in data.get("long_term_goals", [])]
    out += [H("Goals"), table(["Horizon", "Goal"], goals_rows, [0.2, 0.8]) if goals_rows else P(f.get("pt_goals"))]
    out += _signature(c)
    return out


def _plan(c, d, v, p) -> list:
    f, data = _fields(v), v.get("data") or {}
    sch = data.get("schedule") or {}
    cost = data.get("cost") or {}
    out = _letterhead(c, "Treatment plan", "Plan of care", v, p, None)
    stats = Table([[
        [Paragraph("SESSIONS", S["cellh"]), Paragraph(f"<b>{_esc(sch.get('sessions') or f.get('total_sessions'))}</b>", S["title"])],
        [Paragraph("FREQUENCY", S["cellh"]), Paragraph(_esc(sch.get("frequency") or f.get("frequency")), S["body"])],
        [Paragraph("THERAPY MIX", S["cellh"]), Paragraph(_esc(sch.get("mix") or f.get("therapy_mix")), S["body"])],
        [Paragraph("TOTAL", S["cellh"]), Paragraph(f"<b>MXN {_esc(_money(cost.get('total_mxn') or f.get('total_cost_mxn')))}</b>", S["body"])],
    ]], colWidths=[0.2 * W, 0.26 * W, 0.3 * W, 0.24 * W])
    stats.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    out += [Spacer(1, 6), stats]
    if v.get("reason"):
        out += [H("Why this plan"), P(v["reason"])]
    out += [H("Focus"), P(f.get("focus"))]
    if data.get("phases"):
        out += [H("Phases"), table(["Phase", "Weeks", "Focus", "Interventions"],
                                   [[ph.get("name"), ph.get("weeks"), ph.get("focus"), ph.get("interventions")] for ph in data["phases"]],
                                   [0.24, 0.1, 0.3, 0.36])]
    goals_rows = [["Short term", g] for g in data.get("short_term_goals", [])] + [["Long term", g] for g in data.get("long_term_goals", [])]
    out += [H("Goals"), table(["Horizon", "Goal"], goals_rows, [0.2, 0.8]) if goals_rows else P(f.get("goals"))]
    out += [H("Home program")] + bullets(data.get("home_program") or ([p.get("home_program")] if p.get("home_program") else []))
    out += [H("Precautions")] + bullets(data.get("precautions") or [])
    out += [H("Next session and review"), kv([("Next session", f.get("next_session")),
                                              ("Review points", "; ".join(data.get("review_points") or []) or f.get("review_point")),
                                              ("Payment", cost.get("terms") or f.get("payment_terms"))])]
    out += [Spacer(1, 10), P("Plan explained to the patient, who agrees with the number of sessions, cost and payment terms.", "small")]
    out += _signature(c)
    return out


def _progress(c, d, v, p) -> list:
    data = v.get("data") or {}
    did = p.get("referring_doctor_id")
    out = _letterhead(c, "Progress report", "Progress report", v, p, c["doctors"][did]["name"] if did else None)
    if data:
        att = data.get("attendance") or {}
        out += [H("Summary"), P(data.get("summary"))]
        out += [H("Sessions and attendance"),
                table(["Completed", "Planned", "Missed", "Late cancellations"],
                      [[att.get("done"), att.get("total"), att.get("missed"), att.get("late")]], [0.25] * 4)]
        if data.get("outcomes"):
            out += [H("Objective outcomes"), table(["Measure", "Baseline", "Latest", "Change"],
                                                    [[o.get("measure"), o.get("baseline"), o.get("latest"), o.get("change")] for o in data["outcomes"]],
                                                    [0.34, 0.22, 0.22, 0.22], color_last=True),
                    Paragraph("n/r = not recorded. Values come only from the signed evaluation and session notes.", S["small"])]
        if data.get("goals"):
            out += [H("Goals"), table(["Goal", "Status"], [[g.get("goal"), g.get("status")] for g in data["goals"]], [0.72, 0.28], color_last=True)]
        out += [H("Plan"), P(data.get("plan_changes")), H("Recommendation"), boxed([P(data.get("recommendation"))])]
        if data.get("next_review"):
            out += [H("Next review"), P(data["next_review"])]
    else:
        out += markdown_flow(v.get("body_md") or "")
    out += _signature(c)
    return out


def _soap(c, d, v, p) -> list:
    f = _fields(v)
    out = _letterhead(c, d["title"], "Session note (SOAP)", v, p, None)
    for k, lbl in (("subjective", "Subjective"), ("objective", "Objective"), ("assessment", "Assessment"), ("plan", "Plan")):
        out += [H(lbl), P(f.get(k))]
    out += _signature(c)
    return out


def _generic(c, d, v, p) -> list:
    out = _letterhead(c, d["title"], d["kind"].replace("_", " ").title(), v, p, None)
    if v.get("fields"):
        out.append(kv([(f["label"], f["value"]) for f in v["fields"]]))
    out += markdown_flow(v.get("body_md") or "")
    out += _signature(c)
    return out


def render(c: dict, doc: dict, version: int | None = None) -> bytes:
    v = doc["versions"][(version or doc["version"]) - 1]
    p = c["patients"][doc["patient_id"]]
    build = {"evaluation": _evaluation, "treatment_plan": _plan, "progress_report": _progress,
             "soap": _soap}.get(doc["kind"], _generic)
    story = build(c, doc, v, p)
    buf = io.BytesIO()

    def footer(canvas, docx):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(0.75 * inch, 0.5 * inch, f"{c['clinic']['name']} · Confidential health information · Draft prepared with PhysioTeam AI, reviewed and signed by the therapist")
        canvas.drawRightString(7.75 * inch, 0.5 * inch, f"Page {docx.page}")
        if v["status"] == "draft":
            canvas.setFont("Helvetica-Bold", 60)
            canvas.setFillColor(colors.Color(0, 0, 0, alpha=0.04))
            canvas.translate(4.25 * inch, 5.5 * inch)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "DRAFT")
        canvas.restoreState()

    tpl = BaseDocTemplate(buf, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.7 * inch,
                          bottomMargin=0.8 * inch, title=f"{doc['title']} - {p['name']}", author=c["clinic"]["therapist"])
    tpl.addPageTemplates([PageTemplate(id="p", frames=[Frame(tpl.leftMargin, tpl.bottomMargin, tpl.width, tpl.height, id="f")], onPage=footer)])
    tpl.build(story)
    return buf.getvalue()
