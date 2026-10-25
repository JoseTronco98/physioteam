import type { AgentId, Service } from "./types";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function parseSim(s: string): Date {
  return new Date(s.length <= 16 ? `${s}:00` : s);
}

export function fmtClock(s?: string): string {
  if (!s) return "";
  const d = parseSim(s);
  if (isNaN(d.getTime())) return s;
  return `${DAYS[d.getDay()]} ${MONTHS[d.getMonth()]} ${d.getDate()}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function fmtTime(s?: string): string {
  if (!s) return "";
  const d = parseSim(s);
  if (isNaN(d.getTime())) return s;
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function fmtDay(s?: string): string {
  if (!s) return "";
  const d = parseSim(s);
  if (isNaN(d.getTime())) return s;
  return `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

export function money(mxn: number, rate?: number): string {
  const m = `MXN ${Math.round(mxn).toLocaleString("en-US")}`;
  if (!rate) return m;
  return `${m} (~USD ${Math.round(mxn / rate).toLocaleString("en-US")})`;
}

export function usd(v: number, digits = 4): string {
  if (v >= 1) return `$${v.toFixed(2)}`;
  return `$${v.toFixed(digits)}`;
}

export function tokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `${Math.round(n / 1000)}k`;
  return n.toLocaleString("en-US");
}

export const AGENT_LABEL: Record<AgentId, string> = {
  ops_partner: "Operations Partner",
  health_advisor: "Health Advisor",
  patient_success: "Patient Success",
  finance_ops: "Finance Ops",
  clinical_scribe: "Clinical Scribe",
  imaging_reader: "Imaging Reader",
  router: "Router",
  safety: "Safety layer",
};

/** Muted iOS system colors for agent dots (the UI ignores any color the API sends). */
export const AGENT_COLOR: Record<AgentId, string> = {
  ops_partner: "#0071E3",
  health_advisor: "#5856D6",
  patient_success: "#30B0C7",
  finance_ops: "#FF9500",
  clinical_scribe: "#34C759",
  imaging_reader: "#5856D6",
  router: "#8E8E93",
  safety: "#34C759",
};

export const SERVICE_LABEL: Record<Service, string> = {
  evaluation: "Evaluation",
  conventional: "Conventional",
  redcord: "Redcord",
  shockwave: "Shockwave",
};

export const SOURCE_LABEL: Record<string, string> = {
  intake_chat: "intake chat",
  session_notes: "session notes",
  imaging: "read from study, verify",
  therapist: "therapist",
  agent_proposal: "agent proposal",
  empty: "empty, needs therapist",
};

export const cx = (...xs: (string | false | null | undefined)[]) => xs.filter(Boolean).join(" ");
