# PhysioTeam API contract (v1)

Backend: FastAPI at the same origin as the UI. All routes are under `/api`. JSON everywhere.
Every request carries the visitor's sandbox id in the `X-Session` header (the UI creates a random
id on first load, stores it in `localStorage["physioteam.session"]`, and sends it on every call,
including the SSE URL as `?session=`). Each session id gets its own simulated clinic.

If the server has an access code set, `GET /api/health` returns `access_required: true` and every
other route needs header `X-Access-Code`. A 401 means "show the access code screen".

Times: simulated clinic time as ISO strings without timezone, e.g. `"2026-10-26T09:00"`.
Money: integers in MXN pesos. The UI shows USD alongside using `state.clinic.usd_rate` (MXN per USD).
Language: `"en"` or `"es"`; patient personas default to `"en"`.

## Types (TypeScript)

```ts
type AgentId = "ops_partner" | "health_advisor" | "patient_success" | "finance_ops"
             | "clinical_scribe" | "imaging_reader" | "router" | "safety";
type ThreadId = "team" | "ops" | "health";        // therapist chats

interface AgentInfo { id: AgentId; name: string; role: string; lead: boolean; reports_to: AgentId | null; color: string }

interface ToolEvent { agent: AgentId; tool: string; summary: string }

interface ChatMessage {
  id: string;
  thread: string;                 // "team" | "ops" | "health" | `wa:${patient_id}` | `doc:${doctor_id}`
  role: "user" | "agent" | "system" | "patient" | "therapist" | "doctor";
  author: string;                 // display name, e.g. "Operations Partner", "Sam Ortega"
  agent?: AgentId;
  text: string;                   // markdown
  time: string;                   // sim time
  tools?: ToolEvent[];            // what ran to produce this reply
  agents_involved?: AgentId[];
  cost_usd?: number;              // cost of the turn that produced it
  approval_id?: string;           // render an inline approval card
  attachment?: { id: string; name: string; kind: "image" | "pdf" | "other"; url: string };
  lang?: "en" | "es";
  blocked?: boolean;              // safety layer blocked this inbound message
}

interface Approval {
  id: string;
  kind: "booking" | "late_cancel_charge" | "sign_document" | "plan_change" | "outbound_message"
      | "invoice_request" | "reschedule_batch" | "discount" | "waitlist_offer";
  title: string;                  // "Book Sam Ortega, Wed 17:00"
  detail: string;                 // markdown
  patient_id?: string;            // waitlist_offer: the person who would be offered the slot
  related_patient_ids?: string[]; // waitlist_offer: who cancelled + waitlist candidates
                                  // waitlist_offer options: offer / offer_next / keep
  created: string;                // sim time
  status: "pending" | "approved" | "rejected" | "waived";
  options: { id: string; label: string; primary?: boolean }[];   // e.g. approve / reject / waive once
  requested_by: AgentId;
}

interface Appointment {
  id: string; patient_id: string; patient_name: string; start: string; end: string;
  service: "evaluation" | "conventional" | "redcord" | "shockwave";
  status: "booked" | "pending_approval" | "confirmed" | "done" | "cancelled" | "no_show" | "late_cancel";
  session_number?: number; plan_total?: number; flags: string[];   // "owes", "red_flag", "new"
}

interface Patient {
  id: string; name: string; age: number; condition: string; status: "inquiry" | "active" | "discharged" | "at_risk";
  household_id?: string; referring_doctor_id?: string; sessions_done: number; plan_total?: number;
  balance_mxn: number; lang: "en" | "es"; flags: string[];
}

interface DocVersion { version: number; created: string; author: AgentId | "therapist"; status: "draft" | "signed" | "superseded"; reason?: string }
interface ClinicalDoc {
  id: string; patient_id: string;
  kind: "evaluation" | "soap" | "treatment_plan" | "home_program" | "progress_report" | "discharge_summary" | "imaging_summary" | "invoice_request";
  title: string; version: number; status: "draft" | "signed" | "superseded"; versions: DocVersion[];
  fields: { key: string; label: string; value: string | null; source: "intake_chat" | "session_notes" | "imaging" | "therapist" | "agent_proposal" | "empty"; needs_review?: boolean }[];
  body_md?: string;               // for free-text docs
}

interface DocDiff { from: number; to: number; changes: { label: string; before: string | null; after: string | null }[]; reason: string }

interface LedgerEntry { id: string; time: string; patient_id: string; kind: "charge" | "payment" | "waiver"; amount_mxn: number; note: string; method?: "cash" | "transfer" }

interface PatientFolder { patient: Patient; documents: ClinicalDoc[]; ledger: LedgerEntry[]; appointments: Appointment[]; attachments: ChatMessage["attachment"][] }

interface Doctor { id: string; name: string; specialty: string; referrals_this_month: number; active_patients: number }

interface Persona {
  id: string; patient_id: string; title: string; blurb: string; starts_as: string;
  lang_default: "en"; missions: Mission[];
}
interface Mission { id: string; group: string; title: string; try_prompt?: string; done: boolean; hint?: string }

interface SpendBucket { agent: AgentId | "simulator"; usd: number; input_tokens: number; cached_tokens: number; cache_write_tokens: number; output_tokens: number; calls: number }
interface Spend { session_usd: number; session_cap_usd: number; global_usd_today: number; global_cap_usd: number; product: SpendBucket[]; simulator: SpendBucket; caching: boolean }

interface SafetyEvent { id: string; time: string; kind: "injection_direct" | "injection_hidden" | "red_flag" | "medication" | "link" | "budget" | "loop_guard" | "missing_data"; action: "blocked" | "escalated" | "held" | "capped" | "routed"; detail: string; patient_id?: string }

interface ClinicState {
  session: string;
  clinic: { name: string; therapist: string; address: string; usd_rate: number; hours: string; services: { id: string; name: string; minutes: number; price_mxn: number }[]; policies: string[] };
  now: string;                    // sim clock
  week_start: string; week_end: string;
  autoplay: boolean;
  mode: "therapist" | "patient" | "autopilot" | null;
  counts: { approvals: number; alerts: number; unread: Record<string, number> };
  spend: Spend;
  busy: boolean;                  // an agent run is in progress
  tour_done: boolean;
}

interface DailyReport {
  date: string;
  tomorrow: Appointment[];
  balances_due: { patient_id: string; name: string; amount_mxn: number }[];
  to_review: { doc_id: string; patient_name: string; title: string; action: string }[];
  plan_per_patient: { patient_name: string; focus: string; watch_for: string }[];
  patients: { at_risk: string[]; red_flags: string[]; satisfaction: string };
  business: BusinessPulse;
  narrative_md: string;           // short written summary from the two leads
}

interface BusinessPulse {
  period: string; revenue_mxn: number; collected_mxn: number; outstanding_mxn: number;
  sessions_done: number; utilization_pct: number; revenue_per_hour_mxn: number;
  late_cancel_lost_mxn: number; by_service: { service: string; sessions: number; revenue_mxn: number }[];
  ai_cost_usd: number;
}

interface AutopilotStats {
  running: boolean; progress_pct: number; day: string;
  patients: number; messages: number; handled_without_therapist_pct: number;
  red_flags_escalated: string; attacks_blocked: string; bookings: number; cancellations: number;
  product_usd: number; simulator_usd: number; tokens_per_patient_week: number; cached_share_pct: number;
  cost_per_patient_week_usd: number; cost_per_clinic_month_usd: number;
  log: { time: string; who: string; what: string; outcome: string; tone?: "ok" | "warn" | "bad" }[];
}
```

## Routes

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | | `{ok, model, access_required, version}` |
| GET | `/api/state` | | `ClinicState` |
| POST | `/api/session/reset` | | `ClinicState` (fresh demo clinic) |
| POST | `/api/session/mode` | `{mode}` | `ClinicState` |
| POST | `/api/session/tour_done` | | `{ok}` |
| GET | `/api/agents` | | `AgentInfo[]` |
| POST | `/api/sim/advance` | `{minutes}` | `ClinicState` (runs events due in that window) |
| POST | `/api/sim/next_event` | | `ClinicState` |
| POST | `/api/sim/end_of_day` | | `ClinicState` |
| POST | `/api/sim/autoplay` | `{on: boolean}` | `ClinicState` |
| GET | `/api/threads/{thread}/messages` | | `ChatMessage[]` (thread = team / ops / health / wa:{pid} / doc:{did}) |
| POST | `/api/threads/{thread}/send` | `{text, attachment_id?, lang?}` | `{accepted: true, run_id}`; replies arrive by SSE |
| GET | `/api/personas` | | `Persona[]` |
| POST | `/api/personas/{id}/start` | `{lang}` | `{thread: "wa:{pid}", patient_id}` |
| POST | `/api/personas/{id}/session_happens` | | `{accepted}` (therapist bot writes notes, agents produce documents) |
| GET | `/api/missions?mode=therapist` | | `Mission[]` (grouped by `group`: Agenda, Health, Doctors, Money, Retention, Safety) |
| GET | `/api/approvals` | | `Approval[]` |
| POST | `/api/approvals/{id}` | `{option_id, note?}` | `Approval` |
| GET | `/api/agenda?from=&to=` | | `Appointment[]` |
| GET | `/api/patients` | | `Patient[]` |
| GET | `/api/patients/{id}` | | `PatientFolder` |
| GET | `/api/documents/{id}` | `?version=` | `ClinicalDoc` |
| GET | `/api/documents/{id}/diff?from=&to=` | | `DocDiff` |
| GET | `/api/documents/{id}/export?format=docx` | | file download (docx or html for print-to-PDF) |
| GET | `/api/doctors` | | `Doctor[]` |
| GET | `/api/report/daily?date=` | | `DailyReport` |
| GET | `/api/business/pulse?period=week` | | `BusinessPulse` |
| GET | `/api/spend` | | `Spend` |
| POST | `/api/spend/caching` | `{on}` | `Spend` |
| GET | `/api/safety/log` | | `SafetyEvent[]` |
| POST | `/api/safety/test/{kind}` | kind = `injection` / `hidden_pdf` / `red_flag` / `budget` | `{accepted, run_id}` |
| POST | `/api/uploads` | multipart `file` (png, jpg, webp, pdf; or session notes as docx, txt, md → `kind: "notes"`) | `{id, name, kind, url}` |
| GET | `/api/files/{id}` | | the uploaded or demo file |
| GET | `/api/demo_files` | | `{id, name, kind, url, description}[]` (referral photo, X-ray report, booby-trapped PDF) |
| POST | `/api/autopilot/start` | `{days: 5, patients: 20}` | `AutopilotStats` |
| POST | `/api/autopilot/stop` | | `AutopilotStats` |
| GET | `/api/autopilot/stats` | | `AutopilotStats` |
| GET | `/api/integrations` | | `{id, name, status: "works" \| "roadmap" \| "stretch", detail}[]` |
| GET | `/api/agenda.ics` | | iCalendar file |
| GET | `/api/activity?limit=150` | | `{id, time, type, agent?, run_id?, text, cost_usd?, tone?}[]` newest first (behind-the-scenes feed) |
| GET | `/api/conversations` | | `{thread, patient_id, name, last_text, last_time, last_role, count, flags}[]` newest first |
| GET | `/api/blocked` | | `{start, end, reason}[]` blocked agenda time |
| POST | `/api/personas/{id}/day_before` | | `ClinicState` (jump to 10:00 the day before the persona's next session; reminder sent) |

## Live events: `GET /api/events?session=...` (Server-Sent Events)

Each SSE message is `data: {"type": ..., ...}`. Types:

| type | payload | UI reaction |
|---|---|---|
| `agent_started` | `{run_id, agent, task}` | light up that agent node |
| `tool_called` | `{run_id, agent, tool, summary}` | add a live "Using: tool" line under the agent |
| `delegation` | `{run_id, from, to, task}` | draw/flash the edge between agents |
| `agent_done` | `{run_id, agent}` | dim the node |
| `message` | `{message: ChatMessage}` | append to its thread |
| `approval` | `{approval: Approval}` | add/update the approvals queue, badge count |
| `alert` | `{level: "red_flag" \| "info", text, patient_id?}` | banner at the top |
| `safety` | `{event: SafetyEvent}` | safety log + toast |
| `spend` | `{spend: Spend}` | update meters |
| `clock` | `{now}` | update top bar |
| `mission` | `{mission_id, done: true}` | tick the mission |
| `doc_updated` | `{doc_id, patient_id, version}` | refresh folder if open |
| `run_finished` | `{run_id, cost_usd, error?}` | stop spinner; show error text if any |
| `autopilot` | `{stats: AutopilotStats}` | refresh autopilot screen |
| `state` | `{state: ClinicState}` | replace state |
