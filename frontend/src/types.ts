// Types mirror docs/api_contract.md exactly.

export type AgentId =
  | "ops_partner" | "health_advisor" | "patient_success" | "finance_ops"
  | "clinical_scribe" | "imaging_reader" | "router" | "safety";
export type ThreadId = "team" | "ops" | "health";
export type Lang = "en" | "es";
export type Mode = "therapist" | "patient" | "autopilot" | null;

export interface AgentInfo { id: AgentId; name: string; role: string; lead: boolean; reports_to: AgentId | null; color: string }

export interface ToolEvent { agent: AgentId; tool: string; summary: string }

export interface Attachment { id: string; name: string; kind: "image" | "pdf" | "other"; url: string }

export interface ChatMessage {
  id: string;
  thread: string;
  role: "user" | "agent" | "system" | "patient" | "therapist" | "doctor";
  author: string;
  agent?: AgentId;
  text: string;
  time: string;
  tools?: ToolEvent[];
  agents_involved?: AgentId[];
  cost_usd?: number;
  approval_id?: string;
  attachment?: Attachment;
  lang?: Lang;
  blocked?: boolean;
}

export type ApprovalKind =
  | "booking" | "late_cancel_charge" | "sign_document" | "plan_change" | "outbound_message"
  | "invoice_request" | "reschedule_batch" | "discount";

export interface Approval {
  id: string;
  kind: ApprovalKind;
  title: string;
  detail: string;
  patient_id?: string;
  created: string;
  status: "pending" | "approved" | "rejected" | "waived";
  options: { id: string; label: string; primary?: boolean }[];
  requested_by: AgentId;
  doc_id?: string | null;
  // optional plain-language decision support (backend may omit)
  if_approve?: string[];
  if_decline?: string[];
  preview?: { to: string; text: string } | null;
  context?: string;
}

export type Service = "evaluation" | "conventional" | "redcord" | "shockwave";

export interface Appointment {
  id: string; patient_id: string; patient_name: string; start: string; end: string;
  service: Service;
  status: "booked" | "pending_approval" | "confirmed" | "done" | "cancelled" | "no_show" | "late_cancel";
  session_number?: number; plan_total?: number; flags: string[];
}

export interface Patient {
  id: string; name: string; age: number; condition: string; status: "inquiry" | "active" | "discharged" | "at_risk";
  household_id?: string; referring_doctor_id?: string; sessions_done: number; plan_total?: number;
  balance_mxn: number; lang: Lang; flags: string[];
}

export interface DocVersion { version: number; created: string; author: AgentId | "therapist"; status: "draft" | "signed" | "superseded"; reason?: string }

export type FieldSource = "intake_chat" | "session_notes" | "imaging" | "therapist" | "agent_proposal" | "empty";

export interface DocField { key: string; label: string; value: string | null; source: FieldSource; needs_review?: boolean }

export type DocKind =
  | "evaluation" | "soap" | "treatment_plan" | "home_program" | "progress_report"
  | "discharge_summary" | "imaging_summary" | "invoice_request";

export interface ClinicalDoc {
  id: string; patient_id: string;
  kind: DocKind;
  title: string; version: number; status: "draft" | "signed" | "superseded"; versions: DocVersion[];
  fields: DocField[];
  body_md?: string;
  data?: Record<string, unknown>;   // structured tables (rom, strength, outcomes, phases, goals...)
}

export interface DocDiff { from: number; to: number; changes: { label: string; before: string | null; after: string | null }[]; reason: string }

export interface LedgerEntry { id: string; time: string; patient_id: string; kind: "charge" | "payment" | "waiver"; amount_mxn: number; note: string; method?: "cash" | "transfer" }

export interface PatientFolder { patient: Patient; documents: ClinicalDoc[]; ledger: LedgerEntry[]; appointments: Appointment[]; attachments: (Attachment | undefined)[] }

export interface Doctor { id: string; name: string; specialty: string; referrals_this_month: number; active_patients: number }

export interface Mission { id: string; group: string; title: string; try_prompt?: string; done: boolean; hint?: string }

export interface Persona {
  id: string; patient_id: string; title: string; blurb: string; starts_as: string;
  lang_default: "en"; missions: Mission[];
}

export interface SpendBucket { agent: AgentId | "simulator"; usd: number; input_tokens: number; cached_tokens: number; cache_write_tokens: number; output_tokens: number; calls: number }
export interface Spend { session_usd: number; session_cap_usd: number; global_usd_today: number; global_cap_usd: number; product: SpendBucket[]; simulator: SpendBucket; caching: boolean }

export type SafetyKind = "injection_direct" | "injection_hidden" | "red_flag" | "medication" | "link" | "budget" | "loop_guard" | "missing_data";
export interface SafetyEvent { id: string; time: string; kind: SafetyKind; action: "blocked" | "escalated" | "held" | "capped" | "routed"; detail: string; patient_id?: string }

export interface ClinicInfo {
  name: string; therapist: string; address: string; usd_rate: number; hours: string;
  services: { id: string; name: string; minutes: number; price_mxn: number }[];
  policies: string[];
}

export interface ClinicState {
  session: string;
  clinic: ClinicInfo;
  now: string;
  week_start: string; week_end: string;
  autoplay: boolean;
  mode: Mode;
  counts: { approvals: number; alerts: number; unread: Record<string, number> };
  spend: Spend;
  busy: boolean;
  tour_done: boolean;
}

export interface BusinessPulse {
  period: string; revenue_mxn: number; collected_mxn: number; outstanding_mxn: number;
  sessions_done: number; utilization_pct: number; revenue_per_hour_mxn: number;
  late_cancel_lost_mxn: number; by_service: { service: string; sessions: number; revenue_mxn: number }[];
  ai_cost_usd: number;
}

export interface DailyReport {
  date: string;
  tomorrow: Appointment[];
  balances_due: { patient_id: string; name: string; amount_mxn: number }[];
  to_review: { doc_id: string; patient_name: string; title: string; action: string }[];
  plan_per_patient: { patient_name: string; focus: string; watch_for: string }[];
  patients: { at_risk: string[]; red_flags: string[]; satisfaction: string };
  business: BusinessPulse;
  narrative_md: string;
}

export interface AutopilotStats {
  running: boolean; progress_pct: number; day: string;
  patients: number; messages: number; handled_without_therapist_pct: number;
  red_flags_escalated: string; attacks_blocked: string; bookings: number; cancellations: number;
  product_usd: number; simulator_usd: number; tokens_per_patient_week: number; cached_share_pct: number;
  cost_per_patient_week_usd: number; cost_per_clinic_month_usd: number;
  log: { time: string; who: string; what: string; outcome: string; tone?: "ok" | "warn" | "bad" }[];
}

export interface Integration { id: string; name: string; status: "works" | "roadmap" | "stretch"; detail: string }

export interface DemoFile extends Attachment { description: string }

export interface Conversation {
  thread: string; patient_id: string; name: string; last_text: string; last_time: string;
  last_role: ChatMessage["role"]; count: number; flags: string[];
}

export interface BlockedRange { start: string; end: string; reason: string }

export type ActivityType = "agent" | "tool" | "delegation" | "run" | "safety" | "approval" | "message" | "system";
export interface ActivityRow {
  id: string; time: string; type: ActivityType; agent?: AgentId; run_id?: string; text: string;
  cost_usd?: number; tone?: "ok" | "warn" | "bad"; thread?: string;
}

export interface Health { ok: boolean; model: string; access_required: boolean; version: string }

export type ServerEvent =
  | { type: "agent_started"; run_id: string; agent: AgentId; task: string }
  | { type: "tool_called"; run_id: string; agent: AgentId; tool: string; summary: string }
  | { type: "delegation"; run_id: string; from: AgentId; to: AgentId; task: string }
  | { type: "agent_done"; run_id: string; agent: AgentId }
  | { type: "message"; message: ChatMessage }
  | { type: "approval"; approval: Approval }
  | { type: "alert"; level: "red_flag" | "info"; text: string; patient_id?: string }
  | { type: "safety"; event: SafetyEvent }
  | { type: "spend"; spend: Spend }
  | { type: "clock"; now: string }
  | { type: "mission"; mission_id: string; done: boolean }
  | { type: "doc_updated"; doc_id: string; patient_id: string; version: number }
  | { type: "run_finished"; run_id: string; cost_usd: number; error?: string }
  | { type: "autopilot"; stats: AutopilotStats }
  | { type: "state"; state: ClinicState }
  | { type: "reset"; state: ClinicState };
