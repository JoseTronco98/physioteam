import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api";
import { useStore } from "../store";
import type { AgentId, Approval, ChatMessage, DemoFile, Attachment } from "../types";
import { AGENT_LABEL, cx, fmtClock, fmtTime, usd } from "../util";

export function Md({ children }: { children: string }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: (p) => <a {...p} target="_blank" rel="noreferrer" /> }}>
        {children}
      </ReactMarkdown>
    </div>
  );
}

export function Card({ title, sub, children, className, right }: { title?: ReactNode; sub?: ReactNode; children: ReactNode; className?: string; right?: ReactNode }) {
  return (
    <div className={cx("card", className)}>
      {title && (
        <h3>
          <span>{title}</span>
          {sub && <small>{sub}</small>}
          {right && <span style={{ marginLeft: "auto" }}>{right}</span>}
        </h3>
      )}
      {children}
    </div>
  );
}

export const KIND_LABEL: Record<Approval["kind"], string> = {
  booking: "Booking", late_cancel_charge: "Late cancellation", sign_document: "Signature", plan_change: "Plan change",
  outbound_message: "Message to send", invoice_request: "Invoice request", reschedule_batch: "Reschedule", discount: "Discount",
  waitlist_offer: "Freed slot", weekly_reports: "Doctor reports",
};

export function PreviewBubble({ p }: { p: NonNullable<Approval["preview"]> }) {
  return (
    <div className="apreview">
      <div className="tiny muted">What {p.to} will receive</div>
      <div className="abubble">{p.text}</div>
    </div>
  );
}

export function ApprovalCard({ a, compact }: { a: Approval; compact?: boolean }) {
  const { decide } = useStore();
  const [busy, setBusy] = useState(false);
  const resolved = a.status !== "pending";
  return (
    <div className={cx("approval", resolved && "resolved")}>
      <div className="row" style={{ gap: 6 }}>
        <span className="tag pk">{KIND_LABEL[a.kind] ?? a.kind}</span>
        <span className="at">{a.title}</span>
      </div>
      {!compact && a.context && <div className="small muted" style={{ marginTop: 4 }}>{a.context}</div>}
      {!compact && a.detail && !a.context && <div className="ad"><Md>{a.detail}</Md></div>}
      {!resolved && a.preview && <PreviewBubble p={a.preview} />}
      {resolved ? (
        <div className="small" style={{ marginTop: 4 }}>
          <span className={cx("tag", a.status === "approved" ? "ok" : a.status === "waived" ? "warn" : "bad")}>{a.status}</span>
        </div>
      ) : (
        <div className="row" style={{ gap: 6, marginTop: compact ? 6 : 0 }}>
          {a.options.map((o) => (
            <button key={o.id} className={cx("btn sm", o.primary ? "solid" : "ghost")} disabled={busy}
              onClick={async () => { setBusy(true); await decide(a.id, o.id); setBusy(false); }}>
              {o.label}
            </button>
          ))}
          <span className="tiny dim" style={{ marginLeft: "auto" }}>from {AGENT_LABEL[a.requested_by] ?? a.requested_by}</span>
        </div>
      )}
    </div>
  );
}

export function WhatJustHappened({ m }: { m: ChatMessage }) {
  if (!m.tools?.length && !m.agents_involved?.length && m.cost_usd === undefined) return null;
  return (
    <details className="wjh">
      <summary>
        ▸ What just happened
        {m.agents_involved?.length ? ` · ${m.agents_involved.length} agent${m.agents_involved.length > 1 ? "s" : ""}` : ""}
        {m.tools?.length ? ` · ${m.tools.length} tool${m.tools.length > 1 ? "s" : ""}` : ""}
        {m.cost_usd !== undefined ? ` · ${usd(m.cost_usd)}` : ""}
      </summary>
      {m.agents_involved?.length ? (
        <div style={{ marginTop: 4 }}>
          {m.agents_involved.map((a) => <span key={a} className="node" style={{ marginRight: 4 }}>{AGENT_LABEL[a] ?? a}</span>)}
        </div>
      ) : null}
      {m.tools?.length ? (
        <ul>
          {m.tools.map((t, i) => (
            <li key={i}><span className="pk">{AGENT_LABEL[t.agent] ?? t.agent}</span> used <code>{t.tool}</code>{t.summary ? `: ${t.summary}` : ""}</li>
          ))}
        </ul>
      ) : null}
    </details>
  );
}

export function AttachmentView({ a }: { a: Attachment }) {
  const url = api.fileUrl(a);
  if (a.kind === "image") return <a href={url} target="_blank" rel="noreferrer"><img src={url} alt={a.name} style={{ maxWidth: 260, borderRadius: 8, display: "block", marginTop: 6 }} /></a>;
  return <a className="chip" href={url} target="_blank" rel="noreferrer" style={{ marginTop: 6 }}>📎 {a.name}</a>;
}

function SampleNotesButton({ thread, s }: { thread: string; s: NonNullable<ChatMessage["suggest_attachment"]> }) {
  const { send, pending } = useStore();
  const [sent, setSent] = useState(false);
  return (
    <div className="samplenotes">
      <button className="btn sm solid" disabled={sent || pending.has(thread)}
        onClick={async () => { setSent(true); await send(thread, "Here are my notes from the session.", s.id); }}>
        {sent ? "Notes sent" : `📎 ${s.label}`}
      </button>
      <span className="tiny dim">Demo shortcut: sends a sample note file ({s.name}). In real use the therapist types, dictates or attaches her own.</span>
    </div>
  );
}

const seq = (m: ChatMessage) => Number(m.id.replace(/\D/g, "")) || 0;
const LEAD_TAG: Record<string, string> = { ops: "Operations Partner", health: "Health Advisor" };

export function MessageList({ thread, me, merge }: { thread: string; me: ChatMessage["role"][]; merge?: string[] }) {
  const { threads, approvals, pending } = useStore();
  const list = useMemo(() => {
    const own = threads[thread] ?? [];
    if (!merge?.length) return own;
    return [...own, ...merge.flatMap((t) => threads[t] ?? [])].sort((a, b) => seq(a) - seq(b));
  }, [threads, thread, merge]);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" }); }, [list.length, pending.has(thread)]);
  return (
    <div className="scroll" ref={ref}>
      {list.length === 0 && <div className="empty">No messages yet. Run a story step on the left, or type below.</div>}
      {list.map((m) => {
        const mine = me.includes(m.role);
        const appr = m.approval_id ? approvals.find((a) => a.id === m.approval_id) : undefined;
        return (
          <div key={m.id} className={cx("msg", mine && "me", m.role === "system" && "system", m.role === "doctor" && "doctor", m.blocked && "blocked")}>
            {m.role !== "system" && (
              <div className="who">
                <span className={mine ? "" : m.role === "doctor" ? "" : "pk"} style={m.role === "doctor" ? { color: "var(--indigo)" } : undefined}>
                  {m.role === "doctor" ? `🩺 ${m.author}` : m.author}
                </span>
                <span className="t">{fmtTime(m.time)}</span>
                {merge && m.thread !== thread && LEAD_TAG[m.thread] && <span className="tag">in {LEAD_TAG[m.thread]} chat</span>}
                {m.blocked && <span className="tag ok">blocked by safety</span>}
              </div>
            )}
            <div className="body"><Md>{m.text}</Md></div>
            {m.attachment && <AttachmentView a={m.attachment} />}
            {appr && <ApprovalCard a={appr} />}
            {m.suggest_attachment && <SampleNotesButton thread={m.thread} s={m.suggest_attachment} />}
            {!mine && <WhatJustHappened m={m} />}
          </div>
        );
      })}
      {[thread, ...(merge ?? [])].some((t) => pending.has(t)) && <div className="thinking">Agents are working</div>}
    </div>
  );
}

// --------- dictation (Web Speech API) ---------
interface SpeechRec { lang: string; interimResults: boolean; continuous: boolean; start(): void; stop(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null; onerror: (() => void) | null }
type SpeechCtor = new () => SpeechRec;

export function useDictation(onText: (t: string) => void) {
  const [on, setOn] = useState(false);
  const rec = useRef<SpeechRec | null>(null);
  const w = window as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor };
  const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  const supported = Boolean(Ctor);
  const toggle = (lang: string) => {
    if (!Ctor) return;
    if (on) { rec.current?.stop(); return; }
    const r = new Ctor();
    r.lang = lang; r.interimResults = false; r.continuous = true;
    r.onresult = (e) => {
      let txt = "";
      for (let i = 0; i < e.results.length; i++) if (e.results[i].isFinal) txt += e.results[i][0].transcript;
      if (txt) onText(txt.trim());
    };
    r.onend = () => setOn(false);
    r.onerror = () => setOn(false);
    rec.current = r;
    r.start();
    setOn(true);
  };
  return { on, supported, toggle };
}

export function FilePicker({ onPick, onClose }: { onPick: (a: Attachment) => void; onClose: () => void }) {
  const [files, setFiles] = useState<DemoFile[]>([]);
  const { run } = useStore();
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { void run(api.demoFiles()).then((f) => f && setFiles(f)); }, [run]);
  return (
    <div className="filepick" onMouseLeave={onClose}>
      <div className="section-title">Demo files (fictional)</div>
      {files.map((f) => (
        <div key={f.id} className="f" onClick={() => { onPick(f); onClose(); }}>
          <span>📎 {f.name}</span><span className="tiny muted">{f.description}</span>
        </div>
      ))}
      <div className="section-title" style={{ marginTop: 8 }}>Or upload</div>
      <button className="btn sm ghost" onClick={() => input.current?.click()}>Choose a file…</button>
      <input ref={input} type="file" hidden accept="image/*,application/pdf,.docx,.txt,.md" onChange={async (e) => {
        const f = e.target.files?.[0];
        if (!f) return;
        const a = await run(api.upload(f));
        if (a) { onPick(a); onClose(); }
      }} />
    </div>
  );
}

export function Composer({ thread, draft, setDraft, placeholder, lang = "en", hint }: {
  thread: string; draft: string; setDraft: (s: string) => void; placeholder: string; lang?: "en" | "es"; hint?: ReactNode;
}) {
  const { send, pending } = useStore();
  const [att, setAtt] = useState<Attachment | null>(null);
  const [pick, setPick] = useState(false);
  const dict = useDictation((t) => setDraft(draft ? `${draft} ${t}` : t));
  const busy = pending.has(thread);
  const submit = async () => {
    const text = draft.trim();
    if (!text && !att) return;
    setDraft(""); const a = att; setAtt(null);
    await send(thread, text || "(attachment)", a?.id, lang);
  };
  return (
    <div className="composer" style={{ position: "relative" }}>
      <textarea value={draft} placeholder={placeholder} onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void submit(); } }} />
      <div className="bar">
        <button className="iconbtn" title="Attach a file (demo files or upload)" onClick={() => setPick((p) => !p)}>📎</button>
        <button className={cx("iconbtn", dict.on && "on")} title={dict.supported ? "Dictate (browser speech recognition)" : "Dictation needs Chrome or Edge"}
          disabled={!dict.supported} onClick={() => dict.toggle(lang === "es" ? "es-MX" : "en-US")}>🎙</button>
        {att && <span className="chip">📎 {att.name}<button onClick={() => setAtt(null)}>✕</button></span>}
        {dict.on && <span className="tag pk">listening… click 🎙 to stop</span>}
        <span className="tiny dim" style={{ flex: 1 }}>{hint}</span>
        <button className="btn solid" disabled={busy || (!draft.trim() && !att)} onClick={() => void submit()}>{busy ? "Working…" : "Send"}</button>
      </div>
      {pick && <FilePicker onPick={setAtt} onClose={() => setPick(false)} />}
    </div>
  );
}

export function AgentStrip() {
  const { agents, live } = useStore();
  const leads = agents.filter((a) => a.lead);
  const shown: AgentId[] = ["router", "safety"];
  return (
    <div>
      <div className="agentstrip">
        {leads.map((l) => {
          const subs = agents.filter((a) => a.reports_to === l.id);
          const isLive = Boolean(live[l.id]) || subs.some((s) => live[s.id]);
          const liveText = live[l.id] ?? subs.map((s) => live[s.id] && `${s.name}: ${live[s.id]}`).find(Boolean) ?? "";
          return (
            <div key={l.id} className={cx("leadbox", isLive && "live")}>
              <div className="lname"><span className="pulse" />{l.name}<span className="tag" style={{ marginLeft: "auto" }}>lead</span></div>
              <div className="subs">
                {subs.map((s) => <span key={s.id} className={cx("node", live[s.id] && "live")} title={s.role}>{s.name}</span>)}
              </div>
              <div className="livetxt">{isLive ? liveText || "working…" : <span className="dim">idle</span>}</div>
            </div>
          );
        })}
      </div>
      <div className="row tiny" style={{ marginTop: -4, marginBottom: 8, gap: 6 }}>
        {shown.map((id) => <span key={id} className={cx("node", live[id] && "live")}>{AGENT_LABEL[id]}</span>)}
        <span className="dim">Every message passes the safety layer; the router picks a lead in the Team chat.</span>
      </div>
    </div>
  );
}

export function Meter({ label, value, max, right, variant }: { label: ReactNode; value: number; max: number; right?: ReactNode; variant?: "sim" | "cap" }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="meter">
      <div className="mh"><span>{label}</span><span className="muted">{right}</span></div>
      <div className={cx("therm", variant)}><i style={{ width: `${Math.max(pct, value > 0 ? 1.5 : 0)}%` }} /></div>
    </div>
  );
}

export function Clock() {
  const { state, connected } = useStore();
  return <span className="clock" title={connected ? "Live updates connected" : "Reconnecting to live updates"}><span className={cx("dot", !connected && "off")} />Sim clock: {fmtClock(state?.now)}</span>;
}
