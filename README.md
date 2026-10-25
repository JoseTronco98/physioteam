# PhysioTeam

**An AI agent team that runs the back office of a solo physical therapy clinic.** Patients talk to the clinic on WhatsApp; the therapist talks to two lead agents, an **Operations Partner** (agenda, money, patients) and a **Health Advisor** (evaluations, treatment plans, doctors), each with their own sub-agents. A full clinic week is simulated so anyone can test it in minutes.

- **Live app:** _link added after deployment_
- **Model:** `gpt-6-luna` via Portkey (PydanticAI agents on the OpenAI Responses API)
- All patients, the therapist and the clinic are fictional.

## Run it locally (about 3 minutes)

Requirements: Python 3.11 or newer. No Node.js needed (the React front end is prebuilt in `frontend/dist`).

1. Clone and enter the folder:
   ```bash
   git clone <this repo url> physioteam
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
3. API key: the app reads `.env` from **this folder or the folder above it**. Either keep your existing `.env` one level up, or copy `.env.example` to `.env` and fill in `PORTKEY_API_KEY` (or `OPENAI_API_KEY`).
4. Start it:
   ```bash
   python run.py
   ```
   Your browser opens at http://127.0.0.1:8000. If it doesn't, open that address.

## How to test it (10 minutes)

The app opens with a 5-step tour. Then:

1. **Patient demo**: pick a persona (for example *Busy worker with chronic pain*), press **Try it** on a mission, and chat in the WhatsApp-style phone. Try asking prices, cancelling late, sending a gym video link, or "my calf is swollen and my foot is numb".
2. **Therapist console**: ask "What's my day?", approve the booking card that appears, press **Next event** in the top bar to let the next patient or doctor write in, and dictate session notes (mic button or paste) with the **Try it** buttons in the missions panel.
3. **Patient folders**: open a patient to see where each evaluation value came from (intake chat, session notes, imaging, or empty), and the treatment plan **v1 to v2 diff**.
4. **Daily report**: press **End of day**.
5. **Costs + safety**: live token and dollar meters per agent, and the **exploit lab** (prompt injection, hidden text in a PDF, red flag, budget cap).
6. **Autopilot** (optional, about 3 minutes): bots play both sides for a simulated week and report cost per patient.

Every visitor gets a private sandbox clinic; **Reset demo** starts over.

## What's inside

```
backend/
  main.py        FastAPI routes + live event stream (SSE) + serves the React build
  agents.py      the PydanticAI agent team and their tools
  safety.py      code-level guardrails: injection, red flags, hidden PDF text, medication, links
  approvals.py   approval cards executed in code (bookings, charges, signatures, reports)
  sim.py         the simulated clinic week, personas, missions, bots, reports, autopilot
  store.py       clinic records (fictional demo data), agenda, ledger, versioned documents
  runtime.py     per-visitor sessions, spend meter and caps, audit trail
  exports.py     Word (.docx) documents and calendar (.ics) export
  mcp_server.py  the clinic tools as an MCP server for your own AI assistant
  prompts/       one prompt file per agent
frontend/        React + Vite + TypeScript (prebuilt in frontend/dist)
docs/            API contract
tests/           live smoke test and an end-to-end API journey
```

## The agent team

| Agent | Reports to | What it does |
|---|---|---|
| Operations Partner (lead) | therapist | Agenda, rescheduling, blocking time, waitlist, daily ops; hands money to Finance Ops and clinical work to the Health Advisor |
| Health Advisor (lead) | therapist | Evaluations, SOAP notes, treatment plans and their versions, home exercises, doctor reports, discharge |
| Patient Success | Operations Partner | The only agent that talks to patients (WhatsApp): prices, booking, intake, cancellations, payments, receipts |
| Finance Ops | Operations Partner | Balances, payments, invoice requests, business pulse, price what-ifs, AI cost |
| Clinical Scribe | Health Advisor | Turns session notes into the evaluation form and SOAP note (structured output, never invents values) |
| Imaging Reader | Health Advisor | Vision: reads photos or PDFs of studies and referrals |

A code-level **safety layer** checks every patient message before any model sees it. Bookings, charges, clinical signatures and messages to doctors only happen from **approval cards** executed in code.

## Spend limits

Each visitor has an AI budget (default $0.75) and there is a global daily cap (default $8). Both are set in `.env` (`SESSION_CAP_USD`, `GLOBAL_DAILY_CAP_USD`). Live meters are on the **Costs + safety** screen.

## MCP server (connect your own AI assistant)

```bash
python -m backend.mcp_server
```
Exposes read-only clinic tools (agenda, free slots, patient summary, balances, business pulse, pending approvals) to any MCP client.

## Development

Front end: `cd frontend && npm install && npm run dev` (proxies `/api` to port 8000; `npm run dev:mock` runs without the back end). Rebuild with `npm run build` and commit `frontend/dist`.
