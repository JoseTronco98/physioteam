# PhysioTeam

**A six-agent AI team that runs the back office of a solo physical therapy clinic on WhatsApp.** Patients write to the
clinic; the therapist talks to two lead agents, an **Operations Partner** (agenda, money, patients) and a **Health
Advisor** (evaluations, SOAP notes, treatment plans, doctors), each with specialists. Every booking, charge, document and
message to a doctor waits for her approval. A full clinic week is simulated so anyone can try it in minutes.

- **Repo:** https://github.com/JoseTronco98/physioteam (public)
- **Run it:** locally, in about 3 minutes (below). It is not hosted, so the course API key is never exposed online.
- **Model:** `gpt-6-luna` through Portkey (PydanticAI agents, OpenAI Responses API). No other model or key is used.
- **Report and slides:** `report/out/report.html` and `report/out/slides.html` (open with a double-click).
- All patients, doctors, chats and notes are fictional.

## Run it locally (about 3 minutes)

Requirements: **Python 3.11 or newer** (tested on 3.12). No Node.js: the React front end is prebuilt in `frontend/dist`.

1. Clone and enter the folder:
   ```bash
   git clone https://github.com/JoseTronco98/physioteam
   cd physioteam
   ```
2. Create a virtual environment and install:
   ```bash
   python -m venv .venv
   ```
   Windows: `.venv\Scripts\activate` · Mac/Linux: `source .venv/bin/activate`
   ```bash
   pip install -r requirements.txt
   ```
3. API key: the app reads `.env` **first in this folder, then in the folder above it**, so a `.env` one level up with
   `PORTKEY_API_KEY` (or `OPENAI_API_KEY`) works as is. Otherwise copy `.env.example` to `.env` and fill in one of them.
4. Start it:
   ```bash
   python run.py
   ```
   The browser opens at http://127.0.0.1:8000 (open it yourself if it doesn't). Stop with Ctrl+C.

## How to test it (10 minutes)

The app opens on a home page with a short tour. There are two roles:

1. **Be the therapist** (recommended): **Therapist → Stories**. Five short stories, one click per step; patients' and
   doctors' lines are scripted so a story never derails, and everything the clinic does in reply is live AI. Skip ahead
   any time: earlier steps play first. Decisions are yours: approve the card in **Approvals**, or press "Decide for me".
   1. *The hard-to-book patient*: booking, a late cancellation, the fee argument, "move me if something earlier opens", the waitlist, her next weeks.
   2. *The referring doctor*: a doctor asks, an X-ray is read, reports for all his patients, an edit, a longer plan, plan v2, the reply.
   3. *A new patient's month*: first message, intake, first visit and notes, evaluation and plan, a follow-up SOAP, a 1-5 rating, the review point, discharge.
   4. *Safety and edge cases*: prompt injection, hidden PDF text, medication, links, privacy, Spanish, a red flag you answer yourself.
   5. *Running the clinic, and the results*: your day, running late, a day off, family bookings, payments, the results of a day and a week.

   "All 45 features, and where to see them" maps every capability to a story step. All five stories cost about $0.03 of AI.
   **Free play** lets the week run with the clock at the top (patients and doctors write in on their own).
2. **Be the patient**: pick a persona and chat in the WhatsApp-style phone; **Things to try** writes the message for you.

Then open **Patient folders** (evaluation, treatment plan, one SOAP note per session, progress reports, feedback file;
named `yymmdd_PatientName_Type`, exportable as PDF in the clinic's form layout or as Word), the 5-week **Agenda**,
**Daily report** and **Costs and safety** (live token and dollar meters).

Every browser gets its own sandbox clinic; **Reset** in the top bar starts over.

## What's inside

```
backend/
  main.py           FastAPI routes, live event stream (SSE), serves the React build
  agents.py         the six PydanticAI agents and their tools
  safety.py         code guardrails: prompt injection, red flags, hidden PDF text, medication, links
  approvals.py      approval cards executed in code (bookings, charges, signatures, reports, waitlist offers)
  stories.py        the five one-click stories and the feature coverage map
  sim.py            the simulated clinic week, personas, bots (metered separately), reports, autopilot
  store.py          clinic data (fictional), 5-week agenda, ledger, versioned documents, file names
  pdfdocs.py        PDF documents in the clinic's form layout; exports.py: Word and calendar export
  runtime.py        per-browser sessions, spend meter and caps, audit trail
  whatsapp.py       WhatsApp Cloud API channel (webhook + sender; off unless WHATSAPP_* keys are set)
  mcp_server.py     read-only clinic tools as an MCP server
  prompts/          one prompt file per agent
  clinical_history.json, demo_files/notes/   fictional clinical history and 30 sample therapist notes
frontend/           React + Vite + TypeScript (prebuilt in frontend/dist)
report/             report and slides: sources, measured data, screenshots, build scripts (report/README.md)
tools/              data generators and the measurement scripts behind every number in the report
tests/              end-to-end scripts (live model): stories, waitlist, 5-week agenda, quality, WhatsApp webhook
docs/               API contract, live WhatsApp setup
```

## The agent team

| Agent | Reports to | What it does |
|---|---|---|
| Operations Partner (lead) | therapist | Agenda, bookings, waitlist, policy, money, weekly results; delegates to Patient Success and Finance Ops |
| Health Advisor (lead) | therapist | Evaluations, SOAP notes, treatment plans and versions, home exercises, progress reports, doctors, discharge |
| Patient Success | Operations Partner | The only agent that talks to patients (WhatsApp); always says it is an AI |
| Finance Ops | Operations Partner | Balances, payments, invoice requests, business pulse, price what-ifs, AI cost |
| Clinical Scribe | Health Advisor | Notes → the clinic's evaluation form and SOAP notes (structured output; never invents values) |
| Imaging Reader | Health Advisor | Reads photos or PDFs of studies and referrals (vision), after the hidden-text scan |

A code-level **safety layer** checks every patient message before any model sees it.

## Spend limits

Each browser session has an AI budget (default $0.75) and the app a daily cap (default $8), set in `.env`
(`SESSION_CAP_USD`, `GLOBAL_DAILY_CAP_USD`). Optional `ACCESS_CODE` asks visitors for a code (useful if you expose it).

## Reproduce the report's numbers

```bash
python -m tools.report_data report/data/report_data.json     # ~$0.07, ~7 min: 51 story steps + a simulated week
python -m tools.eval_quality report/data/eval_quality.json   # ~$0.06, ~6 min: Clinical Scribe on 30 notes
python -m tests.stories_run                                  # all five stories end to end
python report/fill.py && python report/build.py              # rebuild report.html and slides.html
```
Details in `report/README.md`.

## Development

Front end: `cd frontend && npm install && npm run dev` (proxies `/api` to port 8000). Rebuild with `npm run build` and
commit `frontend/dist`. MCP server: `python -m backend.mcp_server`.
