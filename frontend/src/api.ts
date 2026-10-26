import type {
  AgentInfo, Approval, Appointment, AutopilotStats, BusinessPulse, ChatMessage, ClinicState, ClinicalDoc,
  DailyReport, DemoFile, DocDiff, Doctor, Health, Integration, Lang, Mission, Mode, Patient, PatientFolder,
  Persona, SafetyEvent, ServerEvent, Spend, Attachment, Conversation, BlockedRange, ActivityRow, StoriesPayload,
} from "./types";
import { mock } from "./mock";

const SESSION_KEY = "physioteam.session";
const CODE_KEY = "physioteam.access_code";

export class AccessError extends Error {}

function newId(): string {
  const c = globalThis.crypto;
  if (c && "randomUUID" in c) return c.randomUUID().replace(/-/g, "").slice(0, 16);
  return Math.random().toString(36).slice(2, 18);
}

export function sessionId(): string {
  // ?session=live opens the live WhatsApp clinic in this tab (the demo sandbox stays untouched).
  const fromUrl = new URLSearchParams(location.search).get("session");
  if (fromUrl) sessionStorage.setItem(SESSION_KEY, fromUrl);
  const tab = sessionStorage.getItem(SESSION_KEY);
  if (tab) return tab;
  let s = localStorage.getItem(SESSION_KEY);
  if (!s) { s = newId(); localStorage.setItem(SESSION_KEY, s); }
  return s;
}
export function accessCode(): string { return localStorage.getItem(CODE_KEY) ?? ""; }
export function setAccessCode(code: string) { localStorage.setItem(CODE_KEY, code.trim()); }

let mockMode = import.meta.env.VITE_MOCK === "1";
export function isMock() { return mockMode; }

/** Decide between the real backend and the in-browser mock. */
export async function health(): Promise<Health> {
  if (mockMode) return mock.health();
  try {
    const r = await fetch("/api/health", { headers: { "X-Session": sessionId() } });
    if (!r.ok) throw new Error(String(r.status));
    const ct = r.headers.get("content-type") ?? "";
    if (!ct.includes("json")) throw new Error("not json");
    return (await r.json()) as Health;
  } catch {
    mockMode = true;
    return mock.health();
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  if (mockMode) return mock.handle(method, path, body) as Promise<T>;
  const r = await fetch(`/api${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Session": sessionId(),
      "X-Access-Code": accessCode(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (r.status === 401) throw new AccessError("Access code required");
  if (!r.ok) {
    let msg = `${r.status}`;
    try { const j = await r.json(); msg = j.detail ?? j.error ?? msg; } catch { /* keep status */ }
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return (await r.json()) as T;
}

const get = <T,>(p: string) => call<T>("GET", p);
const post = <T,>(p: string, b: unknown = {}) => call<T>("POST", p, b);
const q = (s: string) => encodeURIComponent(s);

export const api = {
  state: () => get<ClinicState>("/state"),
  reset: () => post<ClinicState>("/session/reset"),
  setMode: (mode: Mode) => post<ClinicState>("/session/mode", { mode }),
  tourDone: () => post<{ ok: boolean }>("/session/tour_done"),
  agents: () => get<AgentInfo[]>("/agents"),

  advance: (minutes: number) => post<ClinicState>("/sim/advance", { minutes }),
  nextEvent: () => post<ClinicState>("/sim/next_event"),
  endOfDay: () => post<ClinicState>("/sim/end_of_day"),
  autoplay: (on: boolean) => post<ClinicState>("/sim/autoplay", { on }),

  messages: (thread: string) => get<ChatMessage[]>(`/threads/${q(thread)}/messages`),
  send: (thread: string, text: string, attachment_id?: string, lang?: Lang) =>
    post<{ accepted: boolean; run_id: string }>(`/threads/${q(thread)}/send`, { text, attachment_id, lang }),

  sendAsTherapist: (thread: string, text: string) =>
    post<{ accepted: boolean; run_id: string }>(`/threads/${q(thread)}/send`, { text, as_therapist: true }),
  dayBefore: (id: string) => post<ClinicState>(`/personas/${q(id)}/day_before`),
  personas: () => get<Persona[]>("/personas"),
  startPersona: (id: string, lang: Lang) => post<{ thread: string; patient_id: string }>(`/personas/${q(id)}/start`, { lang }),
  stories: () => get<StoriesPayload>("/stories"),
  runStory: (sid: string, step: string) => post<{ accepted: boolean; go: string | null; thread: string | null; note: string }>(`/stories/${q(sid)}/${q(step)}/run`),
  tryMission: (id: string) => post<{ accepted: boolean; go: string | null; thread: string | null; note: string }>(`/missions/${q(id)}/try`),
  sessionHappens: (id: string) => post<{ accepted: boolean }>(`/personas/${q(id)}/session_happens`),
  missions: (mode: "therapist" | "patient") => get<Mission[]>(`/missions?mode=${mode}`),

  approvals: () => get<Approval[]>("/approvals"),
  decide: (id: string, option_id: string, note?: string) => post<Approval>(`/approvals/${q(id)}`, { option_id, note }),

  agenda: (from?: string, to?: string) =>
    get<Appointment[]>(`/agenda${from || to ? `?from=${q(from ?? "")}&to=${q(to ?? "")}` : ""}`),
  patients: () => get<Patient[]>("/patients"),
  conversations: () => get<Conversation[]>("/conversations"),
  blocked: () => get<BlockedRange[]>("/blocked"),
  activity: (limit = 150) => get<ActivityRow[]>(`/activity?limit=${limit}`),
  folder: (id: string) => get<PatientFolder>(`/patients/${q(id)}`),
  document: (id: string, version?: number) => get<ClinicalDoc>(`/documents/${q(id)}${version ? `?version=${version}` : ""}`),
  diff: (id: string, from: number, to: number) => get<DocDiff>(`/documents/${q(id)}/diff?from=${from}&to=${to}`),
  exportUrl: (id: string, format: "docx" | "html" | "pdf" = "docx") =>
    mockMode ? "#" : `/api/documents/${q(id)}/export?format=${format}&session=${q(sessionId())}&code=${q(accessCode())}`,
  doctors: () => get<Doctor[]>("/doctors"),

  daily: (date?: string) => get<DailyReport>(`/report/daily${date ? `?date=${q(date)}` : ""}`),
  pulse: (period = "week") => get<BusinessPulse>(`/business/pulse?period=${q(period)}`),

  spend: () => get<Spend>("/spend"),
  caching: (on: boolean) => post<Spend>("/spend/caching", { on }),
  safetyLog: () => get<SafetyEvent[]>("/safety/log"),
  safetyTest: (kind: "injection" | "hidden_pdf" | "red_flag" | "budget") =>
    post<{ accepted: boolean; run_id: string }>(`/safety/test/${kind}`),

  demoFiles: () => get<DemoFile[]>("/demo_files"),
  fileUrl: (a: Attachment) =>
    mockMode ? a.url : `${a.url}${a.url.includes("?") ? "&" : "?"}session=${q(sessionId())}&code=${q(accessCode())}`,

  autopilotStart: (days = 5, patients = 20) => post<AutopilotStats>("/autopilot/start", { days, patients }),
  autopilotStop: () => post<AutopilotStats>("/autopilot/stop"),
  autopilotStats: () => get<AutopilotStats>("/autopilot/stats"),

  integrations: () => get<Integration[]>("/integrations"),
  icsUrl: () => (mockMode ? "#" : `/api/agenda.ics?session=${q(sessionId())}&code=${q(accessCode())}`),

  async upload(file: File): Promise<Attachment> {
    if (mockMode) return mock.upload(file);
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch("/api/uploads", {
      method: "POST", body: fd,
      headers: { "X-Session": sessionId(), "X-Access-Code": accessCode() },
    });
    if (r.status === 401) throw new AccessError("Access code required");
    if (!r.ok) throw new Error(`Upload failed (${r.status})`);
    return (await r.json()) as Attachment;
  },
};

/** Subscribe to live server events. Returns an unsubscribe function. */
export function subscribe(onEvent: (e: ServerEvent) => void, onStatus?: (live: boolean) => void): () => void {
  if (mockMode) { onStatus?.(true); return mock.subscribe(onEvent); }
  let es: EventSource | null = null;
  let closed = false;
  let retry: number | undefined;
  const open = () => {
    es = new EventSource(`/api/events?session=${q(sessionId())}&code=${q(accessCode())}`);
    es.onopen = () => onStatus?.(true);
    es.onmessage = (m) => {
      try { onEvent(JSON.parse(m.data) as ServerEvent); } catch { /* ignore malformed */ }
    };
    es.onerror = () => {
      onStatus?.(false);
      es?.close();
      if (!closed) retry = window.setTimeout(open, 2500);
    };
  };
  open();
  return () => { closed = true; window.clearTimeout(retry); es?.close(); };
}
