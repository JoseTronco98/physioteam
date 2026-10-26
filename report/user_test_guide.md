# User test with the therapist (about 40 minutes) + the 3-minute video

Goal for the report (Tier 3 evidence): **a real user tried it, time or quality measured against her current
method, and her own words.** Do it on a video call with her screen shared; record the call (the video can be
cut from it). In the report and slides she is "a practicing physical therapist who owns a solo clinic in Mexico":
no name, no clinic name.

Run the app (README) and share your screen, or expose it with a tunnel and an access code (`ACCESS_CODE` in `.env`).

---

## Before the call (2 minutes)
- Ask her two baseline questions and write the answers in the sheet:
  1. "¿Cuántas horas a la semana te llevan los mensajes de WhatsApp y el papeleo (evaluaciones, SOAP, planes, reportes)?"
  2. "¿Cuánto te tardas normalmente en llenar una evaluación inicial completa? ¿Y una nota SOAP?"

## Task A · Patient messages: by hand vs with the team (8 minutes)
1. **By hand (timer on):** show her these 3 messages and ask her to type the replies she'd send today, in a note:
   - "Hola, ¿cuánto cuesta la primera sesión y tienen espacio mañana en la tarde?"
   - "Me surgió algo en el trabajo, no voy a poder ir hoy a las 7, perdón."
   - "¿Cuánto les debo?"
   Stop the timer when the third reply is written. → **time_by_hand_messages**
2. **With PhysioTeam:** Stories → *The hard-to-book patient* → run steps 1, 3 and 4 (the request, the late cancel,
   the fee argument). Time from first click to the third reply. → **time_team_messages**
3. Ask: "Del 1 al 5, ¿qué tan bien contestó el asistente comparado con como contestarías tú?" → **rating_messages**

## Task B · First-visit paperwork (10 minutes)
1. Stories → *A new patient's month* → run to step 5 ("You send your notes"). Open **Patient folders → Javier
   Ortega → Evaluation** and the **Treatment plan**; open the PDF.
2. Ask her to read it as if it were her patient and mark anything wrong or missing. Time how long the review takes.
   → **time_review_eval**
3. Compare with her answer to baseline question 2 (time to fill an evaluation by hand). → **time_by_hand_eval**
4. "Del 1 al 5, ¿qué tan utilizable es esta evaluación con pocas correcciones?" → **rating_eval**
   "¿Qué le cambiarías?" (write it down: it's honest evidence for the report)

## Task C · The referring doctor (5 minutes)
Stories → *The referring doctor* → run to step 5 (send the three reports). Open Hector's progress report.
"¿Se lo mandarías así a un ortopedista?" (sí / con cambios / no) → **doctor_report_ok**

## Task D · Her week (3 minutes)
Stories → *Running the clinic, and the results* → "The day runs to closing", then "How did the week go?".
"¿Esto te sirve para saber cómo va tu consultorio?" → note her answer.

## Closing questions (5 minutes)
1. "¿Cuántas horas a la semana crees que te ahorraría?" → **hours_saved_estimate**
2. "¿Qué es lo que más te gustó? ¿Y lo que menos?"
3. "¿Lo usarías en tu consultorio? ¿Qué le falta para que sí?"
4. "¿Cuánto pagarías al mes por algo así?" → **willingness_to_pay_mxn**
5. Ask for **one sentence** you can quote (anonymous): "Si se lo tuvieras que describir a otra fisio en una frase…"

---

## Sheet (send me these values, I'll put them in the report)

```
admin_hours_per_week (baseline):
time_by_hand_eval (her usual, minutes):
time_by_hand_soap (her usual, minutes):
time_by_hand_messages (3 replies, mm:ss):
time_team_messages (3 replies, mm:ss):
rating_messages (1-5):
time_review_eval (mm:ss):
rating_eval (1-5):
what she would change:
doctor_report_ok (yes / with changes / no):
hours_saved_estimate (per week):
willingness_to_pay_mxn (per month):
liked most:
liked least:
would use it? what's missing:
quote:
```

## The 3-minute video (cut from the call, or recorded after)
- 0:00-0:20 · Hub page: "PhysioTeam runs the back office of a solo PT clinic on WhatsApp."
- 0:20-1:10 · Story 1: Valentina asks, cancels late, argues the fee, gets moved from the waitlist (show the approval tap).
- 1:10-1:50 · Story 3: the notes become the evaluation and plan; open the PDF in the clinic's form layout.
- 1:50-2:20 · Safety: the injection blocked and the red flag ("the therapist was notified").
- 2:20-3:00 · Her reaction: the quote and the time comparison.
