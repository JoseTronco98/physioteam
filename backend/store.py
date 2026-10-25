"""The clinic records: one simulated clinic per visitor session.

Plain dicts (JSON-serialisable) so the whole clinic can be snapshotted to data/sessions/<id>.json
and read by the MCP server. Every agent reads and writes through the tool layer, never directly.
All data is fictional.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from . import config
from .clinical_seed import EVAL_DATA, PLAN_DATA

FMT = "%Y-%m-%dT%H:%M"
WEEK_START = "2026-10-26T08:30"      # Monday
WEEK_END = "2026-10-31T13:00"        # Saturday noon close


def dt(s: str) -> datetime:
    return datetime.strptime(s[:16], FMT)


def ts(d: datetime) -> str:
    return d.strftime(FMT)


def nice(s: str) -> str:
    """'2026-10-27T18:00' -> 'Tue Oct 27, 18:00'."""
    d = dt(s)
    return d.strftime("%a %b %d, %H:%M").replace(" 0", " ")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------------------
# Static clinic profile (fictional, modelled on a real solo practice)
# --------------------------------------------------------------------------------------
CLINIC = {
    "name": "Movimiento Fisioterapia",
    "therapist": "Lic. Ana Rivera, PT",
    "address": "Calle Norte 12 #140, between Oriente 3 and Oriente 5, Centro. White house with a blue gate, no sign: ring the square doorbell.",
    "landmarks": "Half a block from the corner pharmacy; taxis know it as 'the blue gate by Farmacia del Centro'.",
    "map_url": "https://maps.google.com/?q=19.0000,-97.0000",
    "usd_rate": config.USD_RATE,
    "hours": "Mon-Fri 11:00-20:00, Sat 09:00-13:00",
    "services": [
        {"id": "evaluation", "name": "Initial evaluation (first visit)", "minutes": 60, "price_mxn": 400,
         "detail": "Full assessment, posture, tests, and a treatment proposal."},
        {"id": "conventional", "name": "Conventional session", "minutes": 50, "price_mxn": 400,
         "detail": "Manual therapy, therapeutic exercise, electrotherapy and heat or cold as needed."},
        {"id": "redcord", "name": "Redcord session", "minutes": 50, "price_mxn": 600,
         "detail": "Suspension system that loads or unloads body weight for neuromuscular activation and strength."},
        {"id": "shockwave", "name": "Shockwave session", "minutes": 50, "price_mxn": 600,
         "detail": "Radial shockwave for chronic tendon and fascia pain (e.g. plantar fasciitis, tennis elbow)."},
    ],
    "packages": [
        {"id": "pack10", "name": "10-session package (5 conventional + 5 Redcord or shockwave)", "price_mxn": 5000},
    ],
    "payment": "Cash or bank transfer at each session, or the full package in advance. Bank details are shared by the therapist on request (demo placeholder: Demo Bank, CLABE 000 000 0000 0000 00).",
    "policies": [
        "Cancellations or changes with less than 24 hours notice are charged as a session. The therapist may waive it once.",
        "If you are running late, sessions can start up to 15 minutes late when the next slot is free.",
        "Invoices (factura) are issued by the clinic's accountant; send your tax details within the same month as the session.",
        "Please bring or send your studies (X-ray, MRI, ultrasound reports) and the doctor's referral before the first visit.",
    ],
    "survey_url": "https://forms.example.com/movimiento-satisfaction",
}

SERVICE_PRICE = {s["id"]: s["price_mxn"] for s in CLINIC["services"]}

DOCTORS = [
    {"id": "d_ortiz", "name": "Dr. Alberto Ortiz", "specialty": "Orthopedic surgery", "referrals_this_month": 4},
    {"id": "d_salinas", "name": "Dra. Carmen Salinas", "specialty": "Neurology", "referrals_this_month": 1},
    {"id": "d_medina", "name": "Dr. Luis Medina", "specialty": "Sports medicine", "referrals_this_month": 3},
]

# id, name, age, condition, status, service, sessions_done, plan_total, doctor, weekly slots (weekday, hour), balance, flags
_PATIENTS = [
    ("p_lucia", "Lucia Mendez", 52, "Right shoulder, 8 weeks after rotator cuff repair", "active", "conventional", 4, 10, "d_ortiz", [(0, 11), (3, 11)], 0, []),
    ("p_daniel", "Daniel Ochoa", 38, "Low back pain with L5-S1 disc bulge", "active", "conventional", 6, 8, "d_medina", [(0, 12), (2, 12)], 400, ["owes"]),
    ("p_marisol", "Marisol Pena", 27, "Left ankle sprain grade II (runner)", "active", "conventional", 2, 6, "d_medina", [(0, 13), (3, 13)], 0, []),
    ("p_ana", "Ana Paula Torres", 45, "Neck pain, desk worker", "active", "conventional", 3, 8, None, [(0, 18), (3, 19)], 0, []),
    ("p_ricardo", "Ricardo Fuentes", 33, "Left ACL reconstruction, week 10", "active", "redcord", 9, 16, "d_ortiz", [(0, 19), (2, 19)], 0, []),
    ("p_jorge", "Jorge Salas", 55, "Frozen shoulder, right", "active", "conventional", 7, 10, None, [(1, 11), (4, 11)], 0, []),
    ("p_carmen", "Carmen Vidal", 70, "Hip osteoarthritis, left", "at_risk", "conventional", 2, 10, "d_ortiz", [(1, 12), (3, 12)], 400, ["missed_2", "owes"]),
    ("p_paola", "Paola Ibarra", 31, "Plantar fasciitis, right", "active", "shockwave", 1, 6, "d_medina", [(1, 13)], 0, ["waitlist_thu_pm"]),
    ("p_hector", "Hector Ruiz", 63, "Total knee replacement, right, week 4", "active", "conventional", 5, 12, "d_ortiz", [(1, 17), (4, 17)], 0, []),
    ("p_diego", "Diego Herrera", 41, "Chronic low back pain and bilateral plantar fasciitis", "active", "redcord", 14, 24, None, [(1, 19), (3, 18)], 600, ["owes", "needs_invoice", "frequent_canceller"]),
    ("p_luis", "Luis Mora", 47, "Tennis elbow (lateral epicondylalgia), right", "active", "shockwave", 4, 6, "d_medina", [(2, 11), (4, 12)], 0, ["waitlist_earlier"]),
    ("p_ernesto", "Ernesto Gomez", 88, "Lumbar spondylolisthesis with leg pain", "active", "conventional", 6, 12, "d_salinas", [(2, 16), (4, 16)], 0, ["household_gomez"]),
    ("p_marta", "Marta Gomez", 79, "Knee osteoarthritis, both", "active", "conventional", 3, 8, "d_ortiz", [(2, 17)], 0, ["household_gomez"]),
    ("p_elena", "Elena Rios", 66, "Osteoporosis, balance and fall prevention", "active", "conventional", 5, 10, None, [(3, 16), (5, 10)], 0, []),
]

# Contacts who write on WhatsApp but are not (yet) patients: personas and simulator bots.
_CONTACTS = [
    ("p_sofia", "Sofia Navarro", 34, "Referred for rehab after right humerus fracture (surgery 6 weeks ago)", "inquiry", "d_ortiz"),
    ("p_teresa", "Teresa Gomez", 54, "Caregiver for her parents Ernesto and Marta Gomez", "contact", None),
    ("p_valeria", "Valeria Cruz", 29, "Former patient (shoulder, discharged last year)", "discharged", None),
    ("p_alex", "Alex Kim", 30, "New contact (free play)", "inquiry", None),
    ("p_mariana", "Mariana Lopez", 24, "New inquiry: ankle pain after a fall", "inquiry", None),
    ("p_tom", "Tom Becker", 36, "New inquiry: shoulder", "inquiry", None),
    ("p_rosa", "Rosa Cruz", 61, "Facial palsy, left side, started 3 days ago", "inquiry", "d_salinas"),
]

EVAL_FIELDS = [
    ("occupation", "Occupation"), ("medical_diagnosis", "Medical diagnosis"), ("referring_doctor", "Referring doctor"),
    ("chief_complaint", "Chief complaint"), ("mechanism_and_date", "Mechanism and date of injury"),
    ("family_history", "Family history"), ("medical_history", "Medical history (diabetes, hypertension, heart, other)"),
    ("previous_injuries", "Previous injuries"), ("surgeries", "Surgeries"), ("allergies", "Allergies"),
    ("medications", "Medications"), ("lifestyle", "Lifestyle (smoking, alcohol, exercise hrs/week, stress, sleep)"),
    ("height_weight", "Height / weight"), ("can_climb_stairs", "Can climb stairs"),
    ("pain_location", "Pain location and irradiation"), ("pain_vas", "Pain VAS best / worst / now (0-10)"),
    ("pain_pattern", "Pain pattern (constant, intermittent; increasing, decreasing)"),
    ("aggravating_factors", "Aggravating factors"), ("relieving_factors", "Relieving factors"),
    ("posture", "Posture observation"), ("palpation", "Palpation (inflammation, scar, joint play)"),
    ("rom", "Range of motion"), ("strength", "Muscle strength (0-5)"), ("sensation", "Sensation"),
    ("special_tests", "Special tests"), ("functional_tests", "Functional tests"), ("imaging", "Imaging"),
    ("patient_goals", "Patient goals"), ("pt_impression", "Physiotherapy impression (therapist)"),
    ("pt_problems", "Physiotherapy problems"), ("pt_goals", "Physiotherapy goals"), ("treatment", "Treatment"),
]
PLAN_FIELDS = [
    ("total_sessions", "Total sessions"), ("frequency", "Frequency"), ("therapy_mix", "Therapy mix"),
    ("focus", "Focus"), ("goals", "Goals"), ("next_session", "Next session"), ("total_cost_mxn", "Total cost (MXN)"),
    ("payment_terms", "Payment terms"), ("review_point", "Review point"),
]
SOAP_FIELDS = [("date", "Date"), ("subjective", "S: Subjective"), ("objective", "O: Objective"),
               ("assessment", "A: Assessment"), ("plan", "P: Plan")]

_PLAN_SEEDS = {
    "p_lucia": {"total_sessions": "10", "frequency": "2x/week", "therapy_mix": "10 conventional",
                "focus": "Pain control, passive to active-assisted shoulder flexion, scapular control",
                "goals": "Flexion 150 degrees, sleep without night pain, return to hairdressing work",
                "next_session": "Active-assisted flexion with wand, rotator cuff isometrics",
                "total_cost_mxn": "4000", "payment_terms": "Per session", "review_point": "Session 5"},
    "p_hector": {"total_sessions": "12", "frequency": "2x/week", "therapy_mix": "12 conventional",
                 "focus": "Knee extension, quadriceps activation, gait without walker",
                 "goals": "0-110 degrees, walk 30 min, stairs reciprocal", "next_session": "Patellar mobilisation, step-ups",
                 "total_cost_mxn": "4800", "payment_terms": "Per session", "review_point": "Session 6"},
    "p_diego": {"total_sessions": "24", "frequency": "2x/week", "therapy_mix": "Redcord + shockwave alternating",
                "focus": "Core stability without loading, plantar fascia, breathing (avoid Valsalva)",
                "goals": "Walk without heel pain in the morning; gym with light machines only",
                "next_session": "Redcord pelvic bridge progressions; shockwave both heels",
                "total_cost_mxn": "14400", "payment_terms": "Per session, monthly invoice", "review_point": "Session 16"},
}


def _week_dt(weekday: int, hour: int) -> str:
    base = dt("2026-10-26T00:00") + timedelta(days=weekday)
    return ts(base.replace(hour=hour, minute=0))


def _patient(pid, name, age, condition, status, service="conventional", done=0, total=None, doctor=None,
             balance=0, flags=None, lang="en"):
    return {"id": pid, "name": name, "age": age, "condition": condition, "status": status,
            "service": service, "sessions_done": done, "plan_total": total, "referring_doctor_id": doctor,
            "balance_mxn": balance, "flags": list(flags or []), "lang": lang,
            "household_id": "h_gomez" if pid in ("p_ernesto", "p_marta", "p_teresa") else None,
            "intake": {}, "restrictions": "", "home_program": ""}


def new_clinic(session: str) -> dict:
    """A fresh demo clinic for one visitor."""
    c: dict[str, Any] = {
        "session": session, "version": config.VERSION, "now": WEEK_START, "mode": None,
        "tour_done": False, "autoplay": False, "caching": True,
        "clinic": copy.deepcopy(CLINIC), "patients": {}, "doctors": {d["id"]: dict(d) for d in DOCTORS},
        "appointments": {}, "blocked": [], "waitlist": ["p_paola", "p_luis"], "documents": {},
        "ledger": [], "approvals": {}, "messages": [], "safety": [], "alerts": [], "outbox": [],
        "attachments": {}, "missions_done": [], "events": [], "fired": [], "seq": 0,
        "spend": {"product": {}, "simulator": {}, "usd": 0.0},
        "persona_lang": {}, "autopilot": None, "notes_needed": [],
    }
    for (pid, name, age, cond, status, service, done, total, doc, slots, bal, flags) in _PATIENTS:
        p = _patient(pid, name, age, cond, status, service, done, total, doc, bal, flags)
        c["patients"][pid] = p
        n = done
        for (wd, hr) in slots:
            n += 1
            start = _week_dt(wd, hr)
            add_appointment(c, pid, start, service, status="booked", session_number=n if n <= (total or 99) else None)
        if bal:
            c["ledger"].append({"id": new_id("l"), "time": "2026-10-23T18:00", "patient_id": pid, "kind": "charge",
                                "amount_mxn": bal, "note": "Unpaid session(s) from last week", "method": None})
        _seed_docs(c, p)
    for (pid, name, age, cond, status, doc) in _CONTACTS:
        c["patients"][pid] = _patient(pid, name, age, cond, status, doctor=doc)
    c["patients"]["p_diego"]["restrictions"] = "No loaded squats or deadlifts; light machines only; always breathe (no Valsalva); swimming preferred."
    c["patients"]["p_ernesto"]["restrictions"] = "Spondylolisthesis: avoid lumbar extension under load; watch for leg weakness."
    # Last week's missed sessions for the at-risk patient
    for back in (3, 5):
        a = add_appointment(c, "p_carmen", ts(dt("2026-10-26T12:00") - timedelta(days=back)), "conventional", status="no_show")
        a["flags"] = ["missed"]
    _seed_chats(c)
    return c


AUTO = "Movimiento Fisioterapia (automatic)"
AI = "Movimiento Fisioterapia (AI assistant)"

# Made-up WhatsApp history from last week, modelled on real clinic patterns (all fictional).
_PAST_CHATS = {
    "p_lucia": [("2026-10-21T10:00", "agent", AUTO, "Hello Lucia! Reminder: see you tomorrow Thu Oct 22, 11:00 for your conventional session. Reply C to confirm."),
                ("2026-10-21T10:12", "patient", None, "C, thank you!"),
                ("2026-10-22T13:05", "agent", AI, "Your exercises for home:\n1. Pendulum swings 2x10\n2. Wand-assisted flexion 3x10\n3. Scapular squeezes 3x10, 3 times a day"),
                ("2026-10-22T19:40", "patient", None, "Thanks! The wand one hurts a bit at the top, is that ok?"),
                ("2026-10-22T19:41", "agent", AI, "Thanks for telling us. I've passed it to Lic. Ana, she'll reply personally. Until then, stay in the range that doesn't hurt.")],
    "p_diego": [("2026-10-20T09:30", "patient", None, "Oye una pregunta, ¿cuánto te debo?"),
                ("2026-10-20T09:31", "agent", AI, "Hola Diego, su saldo pendiente es de MXN 600 por la sesión del jueves pasado. ¿Le comparto los datos para transferencia?"),
                ("2026-10-20T09:40", "patient", None, "Sí porfa, y la factura de este mes"),
                ("2026-10-20T09:41", "agent", AI, "Con gusto. La terapeuta le comparte los datos bancarios. Para la factura necesito su RFC y correo; la contadora la emite dentro del mismo mes."),
                ("2026-10-22T17:55", "patient", None, "No voy a poder llegar hoy, no me dejan salir de la oficina 😞"),
                ("2026-10-22T17:56", "agent", AI, "Gracias por avisar, Diego. Como faltan menos de 24 h, la terapeuta decide si se cobra. ¿Le funciona mañana viernes a las 14:00 para reponerla?"),
                ("2026-10-22T18:10", "patient", None, "Mañana no puedo, nos vemos el martes")],
    "p_daniel": [("2026-10-23T10:00", "agent", AUTO, "¡Hola Daniel! Le recordamos su sesión el lunes 26 a las 12:00. Responda C para confirmar."),
                 ("2026-10-23T10:30", "patient", None, "Confirmo. ¿Me puede mandar recibo de la última sesión para el seguro?"),
                 ("2026-10-23T10:31", "agent", AI, "Claro, Daniel. Ya pedí el recibo a la terapeuta; le llegará por correo. Tiene un saldo de MXN 400 pendiente.")],
    "p_carmen": [("2026-10-21T11:00", "agent", AUTO, "Hello Carmen, we missed you today at 12:00. Is everything ok? Would you like to rebook?"),
                 ("2026-10-23T11:00", "agent", AUTO, "Hello Carmen, we missed you again today. Your hip program works best with regular sessions. Reply here when you'd like a new time.")],
    "p_teresa": [("2026-10-21T16:20", "patient", None, "Good afternoon! Dad is coming today at 4, mom is staying home with a cold"),
                 ("2026-10-21T16:21", "agent", AI, "Thank you for letting us know, Teresa. Get well soon to your mom! We'll see your dad at 16:00."),
                 ("2026-10-23T18:30", "patient", None, "I forgot dad's second exercise 🙈"),
                 ("2026-10-23T18:31", "agent", AI, "No problem! Ernesto's exercises:\n1. Diaphragmatic breathing 2x10\n2. Seated pelvic tilts 2x10\n3. Short walks with walker, 10 min")],
    "p_marisol": [("2026-10-22T08:15", "patient", None, "Hi! Can I run on the treadmill yet? 🏃‍♀️"),
                  ("2026-10-22T08:16", "agent", AI, "I'll pass your question to Lic. Ana so she can answer personally, Marisol. She'll check it at your next session on Monday too.")],
}


def _seed_chats(c: dict) -> None:
    for pid, rows in _PAST_CHATS.items():
        p = c["patients"][pid]
        for (t, role, author, text) in rows:
            c["seq"] += 1
            c["messages"].append({"id": f"m{c['seq']}", "thread": f"wa:{pid}", "role": role,
                                  "author": author or p["name"], "text": text, "time": t,
                                  **({"agent": "ops_partner" if author == AUTO else "patient_success"} if role == "agent" else {})})
    c["persona_lang"] = {"p_diego": "es", "p_daniel": "es"}


_BASELINES = {
    "p_lucia": {"chief_complaint": "Shoulder pain at night and cannot lift the arm to work",
                "aggravating_factors": "Lying on the right side, reaching overhead, carrying bags",
                "relieving_factors": "Sling at night the first weeks, ice, pendulum exercises",
                "posture": "Right shoulder elevated and protracted; guarded arm position",
                "palpation": "Tender over the anterolateral acromion; portal scars healed",
                "sensation": "Normal",
                "imaging": "Post-op MRI not required; surgical report: full-thickness supraspinatus tear repaired",
                "occupation": "Hairdresser", "mechanism_and_date": "Fall on outstretched arm; rotator cuff repair 2026-08-28",
                "pain_vas": "Best 3 / worst 7 / now 5", "rom": "Shoulder flexion 85 deg active, 110 passive; ER 15 deg",
                "strength": "Shoulder flexors 3/5, ER 3-/5", "special_tests": "Not tested (post-op protocol)",
                "patient_goals": "Sleep without pain, return to work", "pt_goals": "Flexion 150, ER 45, strength 4+/5"},
    "p_hector": {"chief_complaint": "Stiff, painful right knee; cannot walk far without the walker",
                 "aggravating_factors": "Walking more than 5 minutes, stairs, sitting for long",
                 "relieving_factors": "Ice, rest with the leg elevated, paracetamol",
                 "posture": "Knee held in slight flexion when standing; weight shifted to the left",
                 "palpation": "Mild warmth and swelling around the patella; scar healed, mobile; no calf tenderness",
                 "sensation": "Normal light touch; mild numbness lateral to the scar (expected after surgery)",
                 "imaging": "X-ray 2026-10-20: components in good position, no loosening, small effusion",
                 "occupation": "Retired accountant", "mechanism_and_date": "Osteoarthritis; total knee replacement right 2026-09-28",
                 "pain_vas": "Best 3 / worst 8 / now 5", "rom": "Knee 10-75 deg", "strength": "Quadriceps right 3-/5 (lag 10 deg)",
                 "functional_tests": "Walks 5 min with walker; stairs one step at a time", "patient_goals": "Walk to the market without walker",
                 "pt_goals": "0-110 deg, independent gait, reciprocal stairs"},
    "p_diego": {"occupation": "Office supervisor", "mechanism_and_date": "Chronic low back pain 2 years; plantar fasciitis 6 months",
                "pain_vas": "Back: best 3 / worst 8; heels 7 in the morning", "rom": "Lumbar flexion fingertips to mid-shin, painful",
                "strength": "Core endurance poor (plank 15 s)", "special_tests": "Windlass test positive bilateral",
                "patient_goals": "Go to the gym without pain, walk in the morning without heel pain"},
    "p_daniel": {"occupation": "Delivery driver", "pain_vas": "Best 2 / worst 7 / now 6", "rom": "Lumbar flexion limited 50%, painful",
                 "special_tests": "SLR negative bilateral", "strength": "Normal lower limbs", "patient_goals": "Drive full shifts without pain"},
    "p_ricardo": {"occupation": "Amateur soccer player", "mechanism_and_date": "ACL reconstruction left 2026-08-17",
                  "rom": "Knee 0-125 deg", "strength": "Quadriceps left 4-/5", "functional_tests": "Single-leg squat poor control",
                  "patient_goals": "Return to soccer by month 9"},
}
_SOAPS = {
    "p_lucia": [("2026-10-19T11:00", "Night pain 4/10, sleeping better", "Flexion 110 active / 130 passive; ER 30", "Improving as expected", "Start active-assisted wand, cuff isometrics"),
                ("2026-10-22T11:00", "Pain 3/10, wand exercise uncomfortable at end range", "Flexion 118 active; ER 35; flexors 3+/5", "Good progress, ahead of protocol", "Progress isometrics; scapular control")],
    "p_hector": [("2026-10-20T17:00", "Pain 5/10 after walking", "Knee 5-90 deg; quad lag 5 deg", "Extension improving", "Patellar mobilisation, quad sets, heel slides"),
                 ("2026-10-23T17:00", "Walked 10 min with cane", "Knee 3-98 deg; quadriceps 3+/5; walks with cane", "Good progress", "Step-ups, gait without walker indoors")],
    "p_diego": [("2026-10-20T19:00", "Back 5/10, heels 6/10 mornings", "Plank 30 s; Redcord pelvic bridge level 2", "Slow improvement, adherence irregular", "Redcord core, shockwave both heels"),
                ("2026-10-22T18:00", "Missed (late cancellation)", None, None, None)],
}


def _seed_docs(c: dict, p: dict) -> None:
    pid = p["id"]
    fields = {k: None for k, _ in EVAL_FIELDS}
    fields.update({"chief_complaint": p["condition"], "medical_diagnosis": p["condition"],
                   "referring_doctor": c["doctors"].get(p["referring_doctor_id"] or "", {}).get("name"),
                   "pt_impression": f"{p['condition']} (therapist's impression)", "treatment": "See treatment plan"})
    fields.update(_BASELINES.get(pid, {}))
    add_document(c, pid, "evaluation", "Initial evaluation", _fields(EVAL_FIELDS, fields, "therapist"),
                 author="therapist", status="signed", created="2026-10-05T12:00", data=EVAL_DATA.get(pid))
    for (t, s_, o, a, pl) in _SOAPS.get(pid, []):
        if o is None:
            continue
        add_document(c, pid, "soap", f"SOAP {nice(t)}", _fields(SOAP_FIELDS, {"date": nice(t), "subjective": s_, "objective": o,
                                                                       "assessment": a, "plan": pl}, "therapist"),
                     author="therapist", status="signed", created=t)
    plan = _PLAN_SEEDS.get(pid) or {
        "total_sessions": str(p["plan_total"]), "frequency": "2x/week", "therapy_mix": f"{p['plan_total']} {p['service']}",
        "focus": "See evaluation", "goals": "Return to daily activities without pain",
        "next_session": "Continue program", "total_cost_mxn": str((p["plan_total"] or 0) * SERVICE_PRICE[p["service"]]),
        "payment_terms": "Per session", "review_point": f"Session {max(1, (p['plan_total'] or 2) // 2)}"}
    add_document(c, pid, "treatment_plan", "Treatment plan", _fields(PLAN_FIELDS, plan, "therapist"),
                 author="therapist", status="signed", created="2026-10-05T12:30", data=PLAN_DATA.get(pid))
    p["home_program"] = {
        "p_lucia": "1. Pendulum swings 2x10\n2. Wand-assisted flexion 3x10\n3. Scapular squeezes 3x10, 3 times a day",
        "p_diego": "1. Diaphragmatic breathing 2x10\n2. Pelvic tilts with breathing 2x10\n3. Plantar fascia stretch with towel 3x30 s\n4. Ice on heels 10 min after walking",
        "p_ernesto": "1. Diaphragmatic breathing 2x10\n2. Seated pelvic tilts 2x10\n3. Short walks with walker, 10 min",
    }.get(pid, "1. Exercises as shown in the last session, 2 sets of 10, once a day")


def _fields(spec, values: dict, source: str) -> list[dict]:
    out = []
    for key, label in spec:
        v = values.get(key)
        out.append({"key": key, "label": label, "value": v if v not in ("", None) else None,
                    "source": source if v not in ("", None) else "empty", "needs_review": v in ("", None)})
    return out


# --------------------------------------------------------------------------------------
# Agenda
# --------------------------------------------------------------------------------------
def add_appointment(c, pid, start, service, status="booked", session_number=None) -> dict:
    a = {"id": new_id("a"), "patient_id": pid, "start": start, "end": ts(dt(start) + timedelta(hours=1)),
         "service": service, "status": status, "session_number": session_number,
         "plan_total": c["patients"].get(pid, {}).get("plan_total"), "flags": [], "reminded": False}
    c["appointments"][a["id"]] = a
    return a


def open_hours(day: datetime) -> list[int]:
    wd = day.weekday()
    if wd < 5:
        return list(range(11, 20))
    if wd == 5:
        return list(range(9, 13))
    return []


def busy_at(c, start: str, ignore: str | None = None) -> dict | None:
    for a in c["appointments"].values():
        if a["id"] != ignore and a["start"] == start and a["status"] in ("booked", "confirmed", "pending_approval"):
            return a
    for b in c["blocked"]:
        if b["start"] <= start < b["end"]:
            return {"blocked": True, **b}
    return None


def free_slots(c, from_time: str | None = None, days: int = 6, limit: int = 8, weekday: int | None = None,
               after_hour: int | None = None, before_hour: int | None = None) -> list[str]:
    start = dt(from_time or c["now"])
    out = []
    for d in range(days + 1):
        day = (start + timedelta(days=d)).replace(hour=0, minute=0)
        if weekday is not None and day.weekday() != weekday:
            continue
        for h in open_hours(day):
            if after_hour is not None and h < after_hour:
                continue
            if before_hour is not None and h >= before_hour:
                continue
            slot = ts(day.replace(hour=h))
            if slot <= ts(start + timedelta(hours=1)):
                continue
            if not busy_at(c, slot):
                out.append(slot)
                if len(out) >= limit:
                    return out
    return out


def appointments_between(c, a: str, b: str, pid: str | None = None) -> list[dict]:
    rows = [x for x in c["appointments"].values() if a <= x["start"] < b and (pid is None or x["patient_id"] == pid)]
    return sorted(rows, key=lambda x: x["start"])


def upcoming_for(c, pid: str) -> list[dict]:
    return [a for a in appointments_between(c, c["now"], "2099", pid) if a["status"] in ("booked", "confirmed", "pending_approval")]


def hours_until(c, start: str) -> float:
    return (dt(start) - dt(c["now"])).total_seconds() / 3600


# --------------------------------------------------------------------------------------
# Money
# --------------------------------------------------------------------------------------
def balance(c, pid: str) -> int:
    total = 0
    for e in c["ledger"]:
        if e["patient_id"] != pid:
            continue
        total += e["amount_mxn"] if e["kind"] == "charge" else -e["amount_mxn"]
    return total


def add_ledger(c, pid, kind, amount, note, method=None) -> dict:
    e = {"id": new_id("l"), "time": c["now"], "patient_id": pid, "kind": kind, "amount_mxn": int(amount),
         "note": note, "method": method}
    c["ledger"].append(e)
    c["patients"][pid]["balance_mxn"] = balance(c, pid)
    p = c["patients"][pid]
    if p["balance_mxn"] > 0 and "owes" not in p["flags"]:
        p["flags"].append("owes")
    if p["balance_mxn"] <= 0 and "owes" in p["flags"]:
        p["flags"].remove("owes")
    return e


# --------------------------------------------------------------------------------------
# Documents (versioned)
# --------------------------------------------------------------------------------------
def add_document(c, pid, kind, title, fields=None, body_md=None, author="therapist", status="draft",
                 reason=None, created=None, doc_id=None, data=None) -> dict:
    created = created or c["now"]
    if doc_id and doc_id in c["documents"]:
        d = c["documents"][doc_id]
        for v in d["versions"]:
            if v["status"] != "superseded" and status == "signed":
                v["status"] = "superseded"
        ver = len(d["versions"]) + 1
        d["versions"].append({"version": ver, "created": created, "author": author, "status": status,
                              "reason": reason, "fields": fields or [], "body_md": body_md, "data": data or {}})
        d["version"], d["status"] = ver, status
        return d
    d = {"id": doc_id or new_id("doc"), "patient_id": pid, "kind": kind, "title": title, "version": 1,
         "status": status, "versions": [{"version": 1, "created": created, "author": author, "status": status,
                                         "reason": reason, "fields": fields or [], "body_md": body_md, "data": data or {}}]}
    c["documents"][d["id"]] = d
    return d


def find_doc(c, pid: str, kind: str) -> dict | None:
    docs = [d for d in c["documents"].values() if d["patient_id"] == pid and d["kind"] == kind]
    return docs[-1] if docs else None


def doc_view(d: dict, version: int | None = None) -> dict:
    v = d["versions"][(version or d["version"]) - 1]
    return {"id": d["id"], "patient_id": d["patient_id"], "kind": d["kind"], "title": d["title"],
            "version": v["version"], "status": v["status"],
            "versions": [{k: x[k] for k in ("version", "created", "author", "status", "reason")} for x in d["versions"]],
            "fields": v["fields"], "body_md": v.get("body_md"), "data": v.get("data") or {}}


def doc_diff(d: dict, a: int, b: int) -> dict:
    va, vb = d["versions"][a - 1], d["versions"][b - 1]
    fa = {f["key"]: f for f in va["fields"]}
    changes = []
    for f in vb["fields"]:
        before = fa.get(f["key"], {}).get("value")
        if before != f["value"]:
            changes.append({"label": f["label"], "before": before, "after": f["value"]})
    if (va.get("body_md") or "") != (vb.get("body_md") or ""):
        changes.append({"label": "Text", "before": va.get("body_md"), "after": vb.get("body_md")})
    return {"from": a, "to": b, "changes": changes, "reason": vb.get("reason") or ""}


def fields_dict(d: dict) -> dict:
    return {f["key"]: f["value"] for f in d["versions"][d["version"] - 1]["fields"]}


# --------------------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------------------
def save(c: dict) -> None:
    path = config.SESSIONS_DIR / f"{safe(c['session'])}.json"
    data = {k: v for k, v in c.items() if not k.startswith("_")}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load(session: str) -> dict | None:
    path = config.SESSIONS_DIR / f"{safe(session)}.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("version") == config.VERSION:
                return data
        except (OSError, json.JSONDecodeError):
            return None
    return None


def safe(session: str) -> str:
    return "".join(ch for ch in session if ch.isalnum() or ch in "-_")[:64] or "anon"
