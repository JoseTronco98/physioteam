# PhysioTeam: house rules for coding agents

- Model: `gpt-6-luna` through Portkey (`PORTKEY_API_KEY`), Responses API via PydanticAI `OpenAIResponsesModel`. No other model on the course key.
- `.env` is loaded from the repo folder, then each parent folder. Never commit `.env` or keys; only `.env.example`.
- Back end: FastAPI in `backend/` (`main.py` routes, `agents.py` agent team and tools, `safety.py` code guardrails, `sim.py` simulated clinic week, `store.py` records, `runtime.py` sessions, spend and audit). Front end: React + Vite + TypeScript in `frontend/`; the build in `frontend/dist` is committed so graders need only Python.
- API shapes live in `docs/api_contract.md`; change the contract and both sides together.
- All data is fictional. Never add real patient names, phone numbers, bank details or chat text.
- Clinical content is always a draft the therapist signs. Agents never give medication advice, never invent clinical values (empty beats guessed), never price anything outside `store.CLINIC`.
- Anything that changes the clinic on a patient's request (booking, late-cancel charge, invoice, sending a report) is an approval executed in `approvals.py`, in code.
- Safety rules run in code before any model sees a patient message (`safety.py`). Prompt-injection, red flags, hidden PDF text, medication and links are covered; extend the rules there.
- UI style: Apple / apple.com look, light mode. Palette #FFFFFF, #F5F5F7, #1D1D1F, #6E6E73, #D2D2D7, links #0066CC, buttons #0071E3; iOS system green/orange/red only for status. No pink. Keep text short and readable.
- Run: `python run.py` (no auto-reload). When stopping, kill the whole process tree.
