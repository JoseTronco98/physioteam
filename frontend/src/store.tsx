import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AccessError, api, health as fetchHealth, subscribe } from "./api";
import type {
  ActivityRow, AgentId, AgentInfo, Approval, AutopilotStats, ChatMessage, ClinicState, Health, Lang, SafetyEvent, ServerEvent,
} from "./types";
import { AGENT_LABEL } from "./util";

export interface Activity { id: string; time: number; run_id?: string; agent?: AgentId; kind: "start" | "tool" | "delegation" | "done" | "finished" | "error"; text: string }
export interface Alert { id: string; level: "red_flag" | "info"; text: string; patient_id?: string }
export interface Toast { id: string; text: string; tone: "ok" | "warn" | "bad" }

interface Store {
  health: Health | null;
  needCode: boolean;
  state: ClinicState | null;
  agents: AgentInfo[];
  live: Partial<Record<AgentId, string>>;          // agent -> current tool/task text while active
  activity: Activity[];
  threads: Record<string, ChatMessage[]>;
  approvals: Approval[];
  alerts: Alert[];
  safety: SafetyEvent[];
  missionsDone: Set<string>;
  autopilot: AutopilotStats | null;
  docVersion: number;
  pending: Set<string>;                              // threads waiting for a reply
  toasts: Toast[];
  connected: boolean;
  refresh: () => Promise<void>;
  loadThread: (thread: string) => Promise<void>;
  send: (thread: string, text: string, attachment_id?: string, lang?: Lang) => Promise<void>;
  decide: (id: string, option: string) => Promise<void>;
  setState: (s: ClinicState) => void;
  dismissAlert: (id: string) => void;
  toast: (text: string, tone?: Toast["tone"]) => void;
  run: <T>(p: Promise<T>) => Promise<T | undefined>;
  codeAccepted: () => void;
  feed: ActivityRow[];                               // behind-the-scenes feed, newest first
  loadFeed: () => Promise<void>;
  eventTick: number;                                 // bumps on events that change the agenda / chats
  lastMessage: ChatMessage | null;
  focusPatient: string | null;                       // patient to open in Patient folders
  setFocusPatient: (id: string | null) => void;
}

const Ctx = createContext<Store | null>(null);
export const useStore = () => {
  const s = useContext(Ctx);
  if (!s) throw new Error("useStore outside provider");
  return s;
};

let n = 0;
const nid = () => `c${Date.now().toString(36)}${n++}`;

export function StoreProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [needCode, setNeedCode] = useState(false);
  const [state, setState] = useState<ClinicState | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [live, setLive] = useState<Partial<Record<AgentId, string>>>({});
  const [activity, setActivity] = useState<Activity[]>([]);
  const [threads, setThreads] = useState<Record<string, ChatMessage[]>>({});
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [safety, setSafety] = useState<SafetyEvent[]>([]);
  const [missionsDone, setMissionsDone] = useState<Set<string>>(new Set());
  const [autopilot, setAutopilot] = useState<AutopilotStats | null>(null);
  const [docVersion, setDocVersion] = useState(0);
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [connected, setConnected] = useState(false);
  const [ready, setReady] = useState(0);
  const runThread = useRef<Record<string, string>>({});
  const [feed, setFeed] = useState<ActivityRow[]>([]);
  const [eventTick, setEventTick] = useState(0);
  const [lastMessage, setLastMessage] = useState<ChatMessage | null>(null);
  const [focusPatient, setFocusPatient] = useState<string | null>(null);
  const names = useRef<Record<string, string>>({});   // wa thread -> patient name
  const nowRef = useRef<string>("");
  useEffect(() => { if (state?.now) nowRef.current = state.now; }, [state?.now]);

  const pushFeed = useCallback((r: Omit<ActivityRow, "id" | "time"> & { time?: string }) =>
    setFeed((xs) => [{ ...r, id: nid(), time: r.time ?? nowRef.current }, ...xs].slice(0, 400)), []);

  const loadFeed = useCallback(async () => {
    try {
      const rows = await api.activity(150);
      setFeed(rows);  // the server log already contains everything streamed so far
    } catch { /* feed is optional */ }
  }, []);

  const toast = useCallback((text: string, tone: Toast["tone"] = "ok") => {
    const id = nid();
    setToasts((t) => [...t, { id, text, tone }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);

  const handleError = useCallback((e: unknown) => {
    if (e instanceof AccessError) { setNeedCode(true); return; }
    toast(e instanceof Error ? e.message : String(e), "bad");
  }, [toast]);

  const run = useCallback(async <T,>(p: Promise<T>) => {
    try { return await p; } catch (e) { handleError(e); return undefined; }
  }, [handleError]);

  const addActivity = useCallback((a: Omit<Activity, "id" | "time">) =>
    setActivity((xs) => [{ ...a, id: nid(), time: Date.now() }, ...xs].slice(0, 120)), []);

  const upsertMessage = useCallback((m: ChatMessage) => {
    setThreads((t) => {
      const list = t[m.thread] ?? [];
      if (list.some((x) => x.id === m.id)) return t;
      return { ...t, [m.thread]: [...list, m] };
    });
    if (m.role === "agent" || m.role === "system") {
      setPending((p) => { if (!p.has(m.thread)) return p; const c = new Set(p); c.delete(m.thread); return c; });
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [s, ap, sf, ag] = await Promise.all([api.state(), api.approvals(), api.safetyLog(), api.agents()]);
      setState(s); setApprovals(ap); setSafety(sf); setAgents(ag);
    } catch (e) { handleError(e); }
  }, [handleError]);

  // boot
  useEffect(() => {
    (async () => {
      const h = await fetchHealth();
      setHealth(h);
      try {
        const [s, ag] = await Promise.all([api.state(), api.agents()]);
        setState(s); setAgents(ag);
        const [ap, sf] = await Promise.all([api.approvals(), api.safetyLog()]);
        setApprovals(ap); setSafety(sf);
        setReady((r) => r + 1);
        api.conversations().then((cs) => cs.forEach((c) => { names.current[c.thread] = c.name; })).catch(() => undefined);
      } catch (e) { handleError(e); }
    })();
  }, [handleError]);

  const feedFrom = useCallback((e: ServerEvent) => {
    const name = (a?: string) => (a ? AGENT_LABEL[a as AgentId] ?? a : "");
    switch (e.type) {
      case "agent_started": pushFeed({ type: "agent", agent: e.agent, run_id: e.run_id, text: `started: ${e.task}` }); break;
      case "tool_called": pushFeed({ type: "tool", agent: e.agent, run_id: e.run_id, text: `${e.tool}: ${e.summary}` }); break;
      case "delegation": pushFeed({ type: "delegation", agent: e.from, run_id: e.run_id, text: `→ ${name(e.to)}: ${e.task}` }); break;
      case "run_finished":
        pushFeed({ type: "run", run_id: e.run_id, text: e.error ? `Run failed: ${e.error}` : "Run finished", cost_usd: e.cost_usd, tone: e.error ? "bad" : "ok" });
        break;
      case "safety":
        pushFeed({ type: "safety", agent: "safety", time: e.event.time, text: `${e.event.action}: ${e.event.detail}`,
          tone: e.event.action === "blocked" || e.event.kind === "red_flag" ? "bad" : "warn" });
        break;
      case "approval":
        pushFeed({ type: "approval", agent: e.approval.requested_by, time: e.approval.created,
          text: e.approval.status === "pending" ? `asks your approval: ${e.approval.title}` : `${e.approval.status}: ${e.approval.title}`,
          tone: e.approval.status === "pending" ? "warn" : "ok" });
        break;
      case "message": {
        const m = e.message;
        const short = m.text.replace(/[*_>`#]+/g, "").replace(/\s+/g, " ").trim().slice(0, 140);
        let text: string;
        if (m.thread.startsWith("wa:")) {
          if (m.role === "patient") { names.current[m.thread] = m.author; text = `${m.author} → clinic: ${short}`; }
          else {
            const who = m.agent === "safety" ? "Safety layer" : /automatic/i.test(m.author) ? "Automatic reminder" : m.agent ? name(m.agent) : "Patient Success";
            text = `${who} → ${names.current[m.thread] ?? "patient"}: ${short}`;
          }
        } else if (m.thread.startsWith("doc:")) text = `${m.author} → doctor: ${short}`;
        else if (m.role === "therapist" || m.role === "user") text = `You → ${m.thread}: ${short}`;
        else if (m.role === "doctor") text = `${m.author} → you: ${short}`;
        else text = `${m.author} → you: ${short}`;
        pushFeed({ type: "message", agent: m.agent, time: m.time, text, cost_usd: m.cost_usd, thread: m.thread, tone: m.blocked ? "bad" : undefined });
        break;
      }
      case "reset": setFeed([]); break;
    }
  }, [pushFeed]);

  const onEvent = useCallback((e: ServerEvent) => {
    feedFrom(e);
    if (["message", "approval", "clock", "state", "reset", "run_finished"].includes(e.type)) setEventTick((t) => t + 1);
    switch (e.type) {
      case "agent_started":
        setLive((l) => ({ ...l, [e.agent]: e.task || "working" }));
        addActivity({ run_id: e.run_id, agent: e.agent, kind: "start", text: e.task });
        break;
      case "tool_called":
        setLive((l) => ({ ...l, [e.agent]: e.tool }));
        addActivity({ run_id: e.run_id, agent: e.agent, kind: "tool", text: `${e.tool}: ${e.summary}` });
        break;
      case "delegation":
        setLive((l) => ({ ...l, [e.to]: "delegated" }));
        addActivity({ run_id: e.run_id, agent: e.from, kind: "delegation", text: `→ ${e.to}: ${e.task}` });
        break;
      case "agent_done":
        setLive((l) => { const c = { ...l }; delete c[e.agent]; return c; });
        break;
      case "message": upsertMessage(e.message); setLastMessage(e.message); break;
      case "approval":
        setApprovals((xs) => {
          const i = xs.findIndex((x) => x.id === e.approval.id);
          if (i < 0) return [e.approval, ...xs];
          const c = [...xs]; c[i] = e.approval; return c;
        });
        break;
      case "alert":
        setAlerts((xs) => [{ id: nid(), level: e.level, text: e.text, patient_id: e.patient_id }, ...xs].slice(0, 6));
        break;
      case "safety":
        setSafety((xs) => [e.event, ...xs.filter((x) => x.id !== e.event.id)]);
        toast(`Safety: ${e.event.action} · ${e.event.detail}`, e.event.kind === "red_flag" ? "bad" : "warn");
        break;
      case "spend": setState((s) => (s ? { ...s, spend: e.spend } : s)); break;
      case "clock": setState((s) => (s ? { ...s, now: e.now } : s)); break;
      case "mission":
        if (e.done) setMissionsDone((m) => { const c = new Set(m); c.add(e.mission_id); return c; });
        break;
      case "doc_updated": setDocVersion((v) => v + 1); break;
      case "run_finished":
        setLive({});
        addActivity({ run_id: e.run_id, kind: e.error ? "error" : "finished", text: e.error ? `Error: ${e.error}` : `Done · $${(e.cost_usd ?? 0).toFixed(4)}` });
        if (e.error) toast(e.error, "bad");
        {
          const th = runThread.current[e.run_id];
          if (th) setPending((p) => { const c = new Set(p); c.delete(th); return c; });
          if (e.error) setPending(new Set());
        }
        break;
      case "autopilot": setAutopilot(e.stats); break;
      case "state": setState(e.state); break;
      case "reset":
        setThreads({}); setApprovals([]); setSafety([]); setAlerts([]); setMissionsDone(new Set()); setFeed([]);
        setState(e.state); setDocVersion((v) => v + 1);
        break;
    }
  }, [addActivity, toast, upsertMessage, feedFrom]);

  const lastEventAt = useRef(Date.now());
  const threadsRef = useRef<string[]>([]);
  useEffect(() => { threadsRef.current = Object.keys(threads); }, [threads]);

  useEffect(() => {
    if (!ready) return;
    return subscribe((e) => { lastEventAt.current = Date.now(); onEvent(e); }, setConnected);
  }, [ready, onEvent]);

  // Safety net for proxies that hold back the live stream (e.g. some tunnels): when no event has
  // arrived for a while, poll the same data the stream would have pushed.
  useEffect(() => {
    if (!ready) return;
    const id = window.setInterval(async () => {
      if (document.hidden || Date.now() - lastEventAt.current < 8000) return;
      try {
        const [s, ap] = await Promise.all([api.state(), api.approvals()]);
        setState(s); setApprovals(ap);
        // the three team chats always (their messages arrive unasked, e.g. "You're with Javier now"), plus any chat open
        const want = Array.from(new Set(["team", "ops", "health", ...threadsRef.current]));
        const lists = await Promise.all(want.map((t) => api.messages(t).then((m) => [t, m] as const)));
        setThreads((cur) => {
          const next = { ...cur };
          let newest: ChatMessage | null = null;
          for (const [t, msgs] of lists) {
            if ((cur[t]?.length ?? 0) !== msgs.length) {
              next[t] = msgs;
              const last = msgs[msgs.length - 1];
              if (last && (!newest || last.id > newest.id)) newest = last;
              if (last && (last.role === "agent" || last.role === "system"))
                setPending((p) => { if (!p.has(t)) return p; const c = new Set(p); c.delete(t); return c; });
            }
          }
          if (newest) { setLastMessage(newest); setEventTick((n) => n + 1); setDocVersion((v) => v + 1); }
          return next;
        });
        void loadFeed();
      } catch { /* next tick */ }
    }, 4000);
    return () => window.clearInterval(id);
  }, [ready, loadFeed]);

  const loadThread = useCallback(async (thread: string) => {
    try {
      const msgs = await api.messages(thread);
      const pm = msgs.find((m) => m.role === "patient");
      if (pm) names.current[thread] = pm.author;
      setThreads((t) => {
        const prev = t[thread] ?? [];
        const ids = new Set(msgs.map((m) => m.id));
        return { ...t, [thread]: [...msgs, ...prev.filter((m) => !ids.has(m.id))] };
      });
    } catch (e) { handleError(e); }
  }, [handleError]);

  const send = useCallback(async (thread: string, text: string, attachment_id?: string, lang?: Lang) => {
    setPending((p) => new Set(p).add(thread));
    try {
      const r = await api.send(thread, text, attachment_id, lang);
      runThread.current[r.run_id] = thread;
      window.setTimeout(() => setPending((p) => { const c = new Set(p); c.delete(thread); return c; }), 90000);
    } catch (e) {
      setPending((p) => { const c = new Set(p); c.delete(thread); return c; });
      handleError(e);
    }
  }, [handleError]);

  const decide = useCallback(async (id: string, option: string) => {
    try {
      const a = await api.decide(id, option);
      setApprovals((xs) => xs.map((x) => (x.id === a.id ? a : x)));
      toast(`${a.title}: ${a.status}`);
      const s = await api.state(); setState(s);
    } catch (e) { handleError(e); }
  }, [handleError, toast]);

  const value = useMemo<Store>(() => ({
    health, needCode, state, agents, live, activity, threads, approvals, alerts, safety, missionsDone, autopilot,
    docVersion, pending, toasts, connected, refresh, loadThread, send, decide, setState, toast, run,
    feed, loadFeed, eventTick, lastMessage, focusPatient, setFocusPatient,
    dismissAlert: (id: string) => setAlerts((xs) => xs.filter((x) => x.id !== id)),
    codeAccepted: () => { setNeedCode(false); void refresh(); setReady((r) => r + 1); },
  }), [health, needCode, state, agents, live, activity, threads, approvals, alerts, safety, missionsDone, autopilot,
    docVersion, pending, toasts, connected, refresh, loadThread, send, decide, toast, run,
    feed, loadFeed, eventTick, lastMessage, focusPatient]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
