"""Safety layer: deterministic rules that run BEFORE any model sees a message (Lecture 4:
"deterministic rules beat hoping the model behaves"; Lecture 12: direct and indirect injection).

- clean_text: strips zero-width and control characters used to smuggle instructions
- injection: direct prompt-injection patterns (EN/ES)
- red_flags: symptoms that must go to the therapist immediately, never to coaching
- medication / links: routed, never answered by the model
- scan_pdf: finds hidden text in PDFs (white text, microscopic fonts, off-page text)
- check_outbound: last check on what an agent is about to send to a patient
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

ZERO_WIDTH = re.compile("[​-‏ - ⁠-⁯﻿]")

INJECTION = [
    (r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|your|all|the|system)\b.{0,25}\b(instructions?|rules?|prompts?|polic(y|ies)|guidelines?)", "asks the agent to ignore its rules"),
    (r"\b(ignora|olvida|omite|desobedece)\b.{0,40}\b(instrucciones|reglas|indicaciones|pol[ií]ticas?)", "pide ignorar las reglas"),
    (r"\bsystem\s*(override|prompt|message)\b|\bdeveloper\s*mode\b|\bjailbreak\b|\bDAN\b", "system override / jailbreak wording"),
    (r"\b(you are now|from now on you are|act as|pretend to be)\b.{0,30}\b(admin|administrator|therapist|owner|developer|manager|unrestricted)", "role-play to gain authority"),
    (r"\b(eres ahora|act[uú]a como|finge ser)\b.{0,30}\b(administrador|terapeuta|due[nñ]a?o|desarrollador)", "juego de rol para ganar autoridad"),
    (r"\b(reveal|show|print|repeat)\b.{0,20}\b(your|the|system)\b.{0,15}\b(prompt|instructions|rules)", "asks for the hidden instructions"),
    (r"\b([3-9]\d|100)\s?%\s?(off|discount|descuento)|\b(free|gratis)\b.{0,15}\b(sessions?|sesiones?|treatment|tratamiento)", "demands an unauthorised discount"),
    (r"\b(send|give|list|export|dame|env[ií]a|lista)\b.{0,30}\b(all|every|todos?|todas?)\b.{0,20}\b(patients?|pacientes?|records?|expedientes?|phone numbers?|tel[eé]fonos?)", "tries to extract other patients' data"),
    (r"\b(approve|aprueba|autoriza)\b.{0,20}\b(all|every|todas?|todos?)\b", "tries to auto-approve actions"),
]

RED_FLAGS = [
    (r"(calf|pantorrilla|leg|pierna).{0,60}(swollen|swelling|hinchad|inflamad|red|roja|hot|caliente|hard|dura)|(swollen|swelling|hinchad|inflamad).{0,60}(calf|pantorrilla)",
     "Possible deep vein thrombosis signs (calf swelling, redness or heat)"),
    (r"(numb|numbness|entumid|entumec|adormec|hormigueo|tingling).{0,80}(both legs|ambas piernas|groin|entrepierna|saddle|genital|foot|pie|leg|pierna)|(foot|pie|leg|pierna).{0,40}(numb|entumid|adormec|dormid)",
     "New numbness (possible nerve or vascular compromise)"),
    (r"(can'?t|cannot|no puedo|unable to).{0,30}(control|contener|aguantar).{0,30}(urine|bladder|bowel|orina|vejiga|evacuar)",
     "Loss of bladder or bowel control (possible cauda equina)"),
    (r"chest pain|dolor (de|en el) pecho|short(ness)? of breath|falta de aire|no puedo respirar|me cuesta respirar",
     "Chest pain or breathing difficulty"),
    (r"(fever|fiebre|calentura).{0,80}(surgery|cirug|wound|herida|incision|incisi[oó]n|operaci)|(wound|herida|incision).{0,60}(pus|supur|abierta|opening|red|roja)",
     "Possible post-surgical infection"),
    (r"sudden(ly)? (weak|weakness)|debilidad (repentina|s[uú]bita)|can'?t move my (leg|arm)|no puedo mover (la|el|mi) (pierna|brazo)|face (droop|drooping)|cara (ca[ií]da|chueca)",
     "Sudden weakness (possible neurological emergency)"),
    (r"(fell|fall|ca[ií]|me ca[ií]|ca[ií]da).{0,60}(head|cabeza|golpe en la cabeza)",
     "Fall with head impact"),
]

MEDICATION = re.compile(
    r"\b(gabapentin\w*|pregabalin\w*|ibuprofen\w*|naproxen\w*|paracetamol|acetaminophen|tramadol|diclofenac\w*|ketorolac\w*|"
    r"medication|medicine|pills?|dose|dosage|pastillas?|medicamentos?|medicinas?|analg[eé]sicos?|dosis|n[uú]cleo|antiinflamatorio)\b", re.I)
LINK = re.compile(r"https?://\S+|www\.\S+", re.I)


def clean_text(text: str) -> tuple[str, int]:
    """Remove invisible characters. Returns (clean text, number of characters removed)."""
    text = unicodedata.normalize("NFKC", text or "")
    cleaned = ZERO_WIDTH.sub("", text)
    cleaned = "".join(ch for ch in cleaned if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    return cleaned.strip(), len(text) - len(cleaned)


def injection(text: str) -> str | None:
    t = text.lower()
    for pattern, reason in INJECTION:
        if re.search(pattern, t, re.I | re.S):
            return reason
    return None


def red_flags(text: str) -> list[str]:
    t = text.lower()
    return [label for pattern, label in RED_FLAGS if re.search(pattern, t, re.I | re.S)]


def mentions_medication(text: str) -> bool:
    return bool(MEDICATION.search(text or ""))


def links(text: str) -> list[str]:
    return LINK.findall(text or "")


def scan_pdf(path: Path) -> dict:
    """Split a PDF into what a person sees and what is hidden (white, tiny, or off-page text)."""
    import pdfplumber

    visible, hidden = [], []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            vis_chars, hid_chars = [], []
            for ch in page.chars:
                color = ch.get("non_stroking_color")
                white = False
                if isinstance(color, (list, tuple)) and color:
                    vals = [float(x) for x in color if isinstance(x, (int, float))]
                    if len(vals) == 1:
                        white = vals[0] >= 0.95
                    elif len(vals) == 3:
                        white = min(vals) >= 0.95
                    elif len(vals) == 4:  # CMYK white
                        white = max(vals) <= 0.05
                tiny = (ch.get("size") or 10) < 3
                off = ch["x0"] < 0 or ch["top"] < 0 or ch["x1"] > page.width or ch["bottom"] > page.height
                (hid_chars if (white or tiny or off) else vis_chars).append(ch["text"])
            visible.append("".join(vis_chars))
            hidden.append("".join(hid_chars))
    vis = page_text = "\n".join(v for v in visible if v.strip())
    hid = "\n".join(h for h in hidden if h.strip())
    # pdfplumber's extract_text keeps spacing nicer for the visible layer
    try:
        with pdfplumber.open(str(path)) as pdf:
            page_text = "\n".join(
                (p.filter(lambda o: o.get("object_type") != "char" or _is_visible(o, p)).extract_text() or "")
                for p in pdf.pages)
    except Exception:  # noqa: BLE001
        page_text = vis
    return {"visible_text": page_text.strip() or vis, "hidden_text": hid.strip(), "hidden_found": bool(hid.strip())}


def _is_visible(ch: dict, page) -> bool:
    color = ch.get("non_stroking_color")
    if isinstance(color, (list, tuple)) and color:
        vals = [float(x) for x in color if isinstance(x, (int, float))]
        if (len(vals) == 1 and vals[0] >= 0.95) or (len(vals) == 3 and min(vals) >= 0.95) or (len(vals) == 4 and max(vals) <= 0.05):
            return False
    if (ch.get("size") or 10) < 3:
        return False
    return not (ch["x0"] < 0 or ch["top"] < 0 or ch["x1"] > page.width or ch["bottom"] > page.height)


DISCOUNT_OUT = re.compile(r"\b([1-9]\d?|100)\s?%\s?(off|discount|descuento)|\bfree (session|treatment)s?\b|\bsesi[oó]n(es)? gratis\b", re.I)


def check_outbound(text: str) -> str | None:
    """Return a reason to hold the message, or None if it can go out."""
    if DISCOUNT_OUT.search(text or ""):
        return "Outgoing message offers a discount or free sessions, which only the therapist can approve."
    return None


SAFE_REPLY = {
    "en": {
        "injection": "I can only help with appointments, prices, directions and your treatment at Movimiento Fisioterapia. I can't change clinic rules or prices. Is there something about your sessions I can help with?",
        "red_flag": "Thank you for telling us. Lic. Ana has been notified and will contact you personally as soon as possible. If it's an emergency, call 911.",
        "budget": "Our assistant is paused right now. The therapist will reply to you personally as soon as possible.",
    },
    "es": {
        "injection": "Solo puedo ayudarle con citas, precios, ubicación y su tratamiento en Movimiento Fisioterapia. No puedo cambiar las reglas ni los precios de la clínica. ¿Le ayudo con algo de sus sesiones?",
        "red_flag": "Gracias por avisarnos. Lo que describe debe revisarlo un profesional de inmediato, así que ya avisé a la terapeuta. Si empeora, o tiene dolor de pecho o le falta el aire, llame al 911 o acuda a urgencias.",
        "budget": "Nuestro asistente está en pausa en este momento. La terapeuta le responderá personalmente lo antes posible.",
    },
}


def guess_lang(text: str) -> str:
    t = (text or "").lower()
    es_words = (" el ", " la ", " de ", " que ", "hola", "gracias", "por favor", "cita", "sesión", "sesion",
                "mañana", "dolor", "puedo", "usted", "buen día", "buenas", "¿", "cuánto", "cuanto")
    score = sum(w in f" {t} " for w in es_words)
    return "es" if score >= 2 else "en"
