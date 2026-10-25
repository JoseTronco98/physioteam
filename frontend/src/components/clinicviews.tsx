import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Appointment, BlockedRange, ChatMessage, Conversation } from "../types";
import { Md } from "./common";
import { useGuide } from "./guide";
import { cx, fmtClock, fmtTime, parseSim, SERVICE_LABEL } from "../util";

/* ======================================================================================
   Patient chats: WhatsApp-style inbox of every patient conversation, as the therapist sees it
   ====================================================================================== */

function bubbleAuthor(m: ChatMessage, name: string): { label: string; tone: string } {
  if (m.role === "patient" || m.role === "doctor") return { label: name || m.author, tone: "pat" };
  if (m.role === "therapist") return { label: m.author || "Lic. Ana Rivera, PT", tone: "ther" };
  if (m.agent === "safety") return { label: "Safety layer", tone: "safe" };
  if (/automatic/i.test(m.author)) return { label: "Automatic reminder", tone: "auto" };
  if (m.role === "system") return { label: "System", tone: "auto" };
  return { label: "Patient Success (AI)", tone: "ps" };
}

export function PatientChats({ initial, onOpened }: { initial?: string | null; onOpened?: () => void }) {
  const { run, loadThread, threads, lastMessage, send, pending, toast } = useStore();
  const { on: guideOn } = useGuide();
  const [mode, setMode] = useState<"direct" | "ps">("direct");
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [sel, setSel] = useState<string | null>(initial ?? null);
  const [unread, setUnread] = useState<Set<string>>(new Set());
  const [text, setText] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const refetch = useRef<number | undefined>(undefined);

  const load = useMemo(() => async () => {
    const c = await run(api.conversations());
    if (c) setConvs(c);
  }, [run]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (initial) { setSel(initial); onOpened?.(); } }, [initial]); // eslint-disable-line
  useEffect(() => { if (!sel && convs.length) setSel(convs[0].thread); }, [convs, sel]);
  useEffect(() => {
    if (!sel) return;
    void loadThread(sel);
    setUnread((u) => { if (!u.has(sel)) return u; const c = new Set(u); c.delete(sel); return c; });
  }, [sel, loadThread]);

  // live: bump the conversation, mark unread, refresh the list a moment later
  useEffect(() => {
    const m = lastMessage;
    if (!m || !(m.thread.startsWith("wa:") || m.thread.startsWith("doc:"))) return;
    setConvs((cs) => {
      const i = cs.findIndex((c) => c.thread === m.thread);
      const prev = i >= 0 ? cs[i] : { thread: m.thread, patient_id: m.thread.split(":")[1], name: m.role === "patient" || m.role === "doctor" ? m.author : m.thread.split(":")[1], count: 0, flags: [] };
      const upd: Conversation = { ...prev, last_text: m.text, last_time: m.time, last_role: m.role, count: (prev.count ?? 0) + 1,
        flags: m.blocked ? [...new Set([...(prev.flags ?? []), "blocked"])] : prev.flags ?? [] };
      return [upd, ...cs.filter((c) => c.thread !== m.thread)];
    });
    if (m.thread !== sel && (m.role === "patient" || m.role === "doctor")) setUnread((u) => new Set(u).add(m.thread));
    window.clearTimeout(refetch.current);
    refetch.current = window.setTimeout(() => void load(), 1500);
  }, [lastMessage]); // eslint-disable-line

  const list = sel ? threads[sel] ?? [] : [];
  const conv = convs.find((c) => c.thread === sel);
  const name = conv?.name ?? "";
  useEffect(() => { ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" }); }, [list.length, sel]);

  const ask = async () => {
    const t = text.trim();
    if (!t || !conv) return;
    setText("");
    const isDoc = conv.thread.startsWith("doc:");
    if (!isDoc && mode === "direct") {
      await run(api.sendAsTherapist(conv.thread, t));
      return;
    }
    await send(isDoc ? "health" : "ops", isDoc ? `Reply to ${conv.name}: ${t}` : `Message ${conv.name}: ${t}`);
    toast(isDoc ? `Asked the Health Advisor to draft a reply to ${conv.name}` : `Asked Patient Success to message ${conv.name.split(" ")[0]}`);
  };

  return (
    <div className="cm">
    <div className="cm-head">
      <div>
        <h2 className="ptitle">Clinic Messages</h2>
        <div className="psub">powered by WhatsApp · Patient Success (AI) answers; you see every conversation and can reply yourself</div>
      </div>
      {guideOn && <span className="gchip">simulated in this demo</span>}
    </div>
    <div className="inbox">
      <div className="inbox-list">
        {convs.length === 0 && <div className="empty" style={{ padding: 12 }}>No patient conversations yet. Press <b>Next event</b> in the top bar.</div>}
        {convs.map((c) => (
          <div key={c.thread} className={cx("conv", c.thread === sel && "on")} onClick={() => setSel(c.thread)}>
            <div className={cx("cav", c.thread.startsWith("doc:") && "doc")}>{c.name.replace(/^(Dr\.|Dra\.)\s*/, "").split(" ").map((x) => x[0]).slice(0, 2).join("")}</div>
            <div className="cbody">
              <div className="ctop">
                <b>{c.name}</b>
                <span className="tiny dim">{fmtTime(c.last_time)}</span>
              </div>
              <div className="cl">
                {c.last_role === "patient" ? "" : "AI: "}{c.last_text?.replace(/\s+/g, " ").slice(0, 60)}
              </div>
              <div className="cflags">
                {c.thread.startsWith("doc:") && <span className="tag blue">Doctor</span>}
                {c.flags.includes("red_flag") && <span className="tag bad">red flag</span>}
                {c.flags.includes("blocked") && <span className="tag bad">blocked</span>}
                {(c.flags.includes("pending") || c.flags.includes("pending_approval")) && <span className="tag pk">pending</span>}
                {c.flags.includes("owes") && <span className="tag warn">owes</span>}
                {c.flags.includes("new") && <span className="tag blue">new</span>}
              </div>
            </div>
            {unread.has(c.thread) && <span className="udot" title="New message" />}
          </div>
        ))}
      </div>
      <div className="inbox-thread">
        {!sel ? <div className="empty" style={{ padding: 20 }}>Pick a conversation.</div> : (
          <>
            <div className="ihead">
              <b>{name}</b>
              <span className="tiny dim">{conv?.thread.startsWith("doc:") ? "Referring doctor · replies are drafted by the Health Advisor and sent only after your approval" : "WhatsApp · answered by Patient Success (AI)"}</span>
            </div>
            <div className="ithread" ref={ref}>
              {list.length === 0 && <div className="empty">No messages yet.</div>}
              {list.map((m) => {
                const a = bubbleAuthor(m, name);
                const incoming = m.role === "patient" || m.role === "doctor";
                return (
                  <div key={m.id} className={cx("ib", incoming ? "in" : "out", a.tone, m.blocked && "blocked")}>
                    <div className="ia">{a.label}<span className="t">{fmtClock(m.time).replace(/^(\w+) \w+ \d+, /, "$1 ")}</span>
                      {m.blocked && <span className="tag bad" style={{ marginLeft: 6 }}>blocked by safety</span>}</div>
                    <div className="itx"><Md>{m.text}</Md></div>
                    {m.attachment && <div className="tiny pk">📎 {m.attachment.name}</div>}
                  </div>
                );
              })}
              {pending.has("ops") && <div className="tiny dim" style={{ padding: "4px 8px" }}>Patient Success is writing…</div>}
            </div>
            {!conv?.thread.startsWith("doc:") && (
              <div className="seg cm-mode">
                <button className={cx(mode === "direct" && "on")} onClick={() => setMode("direct")}>Reply as Lic. Ana</button>
                <button className={cx(mode === "ps" && "on")} onClick={() => setMode("ps")}>Ask Patient Success</button>
              </div>
            )}
            <div className="icompose">
              <input value={text} placeholder={conv?.thread.startsWith("doc:") ? `Ask the Health Advisor to reply to ${name}…` : mode === "direct" ? `Message ${name || "this patient"} as Lic. Ana…` : `Ask Patient Success to message ${name || "this patient"}…`}
                onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void ask(); }} />
              <button className="btn solid sm" onClick={() => void ask()} disabled={!text.trim()}>Send</button>
            </div>
            <div className="tiny dim" style={{ padding: "4px 2px 0" }}>
              {conv?.thread.startsWith("doc:") ? "The Health Advisor drafts the reply; it waits in Approvals until you approve it."
                : mode === "direct" ? "Sent straight to the patient on WhatsApp from you, Lic. Ana."
                : "Your Operations Partner has Patient Success write it in the clinic's tone. The reply appears here."}
            </div>
          </>
        )}
      </div>
    </div>
    </div>
  );
}

/* ======================================================================================
   Agenda: week grid Mon Oct 26 to Sat Oct 31, 09:00 to 20:00
   ====================================================================================== */

const DAYS = ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"];
const H0 = 9, H1 = 20, ROW = 42;
const mins = (s: string) => { const d = parseSim(s); return d.getHours() * 60 + d.getMinutes(); };
const top = (s: string) => ((mins(s) - H0 * 60) / 60) * ROW;

function statusClass(a: Appointment) {
  if (a.flags.includes("clinic_closed")) return "closed";
  return a.status;
}

export function AgendaWeek({ onOpenFolder, onMessage }: { onOpenFolder: (pid: string) => void; onMessage: (thread: string) => void }) {
  const { run, state, eventTick } = useStore();
  const [appts, setAppts] = useState<Appointment[]>([]);
  const [blocked, setBlocked] = useState<BlockedRange[]>([]);
  const [pick, setPick] = useState<Appointment | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const load = useMemo(() => async () => {
    const [a, b] = await Promise.all([
      run(api.agenda("2026-10-26T00:00", "2026-11-01T00:00")),
      run(api.blocked()),
    ]);
    if (a) setAppts(a);
    if (b) setBlocked(b);
  }, [run]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void load(), 800);
    return () => window.clearTimeout(timer.current);
  }, [eventTick, load]);

  const byDay = useMemo(() => {
    const m: Record<string, Appointment[]> = {};
    DAYS.forEach((d) => (m[d] = []));
    appts.forEach((a) => { const d = a.start.slice(0, 10); if (m[d]) m[d].push(a); });
    return m;
  }, [appts]);

  const now = state?.now ?? "";
  const nowDay = now.slice(0, 10);
  const nowTop = now ? top(now) : -1;
  const counts = {
    booked: appts.filter((a) => a.status === "booked" || a.status === "confirmed").length,
    pending: appts.filter((a) => a.status === "pending_approval").length,
    done: appts.filter((a) => a.status === "done").length,
    cancelled: appts.filter((a) => ["cancelled", "late_cancel", "no_show"].includes(a.status)).length,
  };

  return (
    <div className="agenda">
      <div className="row small" style={{ gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        <span className="muted">Week of Oct 26 · {counts.booked} booked · {counts.pending} pending · {counts.done} done · {counts.cancelled} cancelled</span>
        <span className="spacer" />
        <span className="lg-key"><i className="k booked" />booked</span>
        <span className="lg-key"><i className="k confirmed" />confirmed</span>
        <span className="lg-key"><i className="k pending_approval" />pending</span>
        <span className="lg-key"><i className="k done" />done</span>
        <span className="lg-key"><i className="k cancelled" />cancelled</span>
      </div>
      <div className="ag-grid" onClick={() => setPick(null)}>
        <div className="ag-hours">
          <div className="ag-dh" />
          {Array.from({ length: H1 - H0 }, (_, i) => <div key={i} className="ag-h" style={{ height: ROW }}>{String(H0 + i).padStart(2, "0")}:00</div>)}
        </div>
        {DAYS.map((d) => {
          const list = byDay[d] ?? [];
          const slots: Record<string, Appointment[]> = {};
          list.forEach((a) => { (slots[a.start] ??= []).push(a); });
          return (
            <div key={d} className={cx("ag-day", d === nowDay && "today")}>
              <div className="ag-dh">{fmtClock(`${d}T09:00`).split(",")[0]}</div>
              <div className="ag-body" style={{ height: (H1 - H0) * ROW }}>
                {Array.from({ length: H1 - H0 }, (_, i) => <div key={i} className="ag-line" style={{ top: i * ROW }} />)}
                {blocked.filter((b) => b.start.slice(0, 10) <= d && b.end.slice(0, 10) >= d).map((b, i) => {
                  const s = b.start.slice(0, 10) === d ? Math.max(0, top(b.start)) : 0;
                  const e = b.end.slice(0, 10) === d ? Math.min((H1 - H0) * ROW, top(b.end)) : (H1 - H0) * ROW;
                  return <div key={`b${i}`} className="ag-block" style={{ top: s, height: Math.max(12, e - s) }} title={b.reason}><span>{b.reason}</span></div>;
                })}
                {list.map((a) => {
                  const group = slots[a.start] ?? [a];
                  const idx = group.indexOf(a);
                  const t = Math.max(0, top(a.start));
                  const h = Math.max(18, top(a.end) - t - 2);
                  const w = 100 / group.length;
                  return (
                    <div key={a.id} className={cx("ag-appt", statusClass(a))}
                      style={{ top: t, height: h, left: `calc(${idx * w}% + 2px)`, width: `calc(${w}% - 4px)` }}
                      onClick={(e) => { e.stopPropagation(); setPick(a); }}
                      title={`${a.patient_name} · ${fmtTime(a.start)} · ${a.status}`}>
                      <div className="an">{a.patient_name}</div>
                      <div className="as">{fmtTime(a.start)} {SERVICE_LABEL[a.service]}{a.status === "pending_approval" ? " · pending" : ""}</div>
                      {a.flags.length > 0 && <div className="af">{a.flags.filter((f) => ["owes", "red_flag", "new"].includes(f)).map((f) => <i key={f} className={cx("fl", f)}>{f === "red_flag" ? "red flag" : f}</i>)}</div>}
                    </div>
                  );
                })}
                {d === nowDay && nowTop >= 0 && nowTop <= (H1 - H0) * ROW && <div className="ag-now" style={{ top: nowTop }}><span>{fmtTime(now)}</span></div>}
                {pick && pick.start.slice(0, 10) === d && (
                  <div className="ag-pop" style={{ top: Math.min(Math.max(0, top(pick.start)) + 30, (H1 - H0) * ROW - 150) }} onClick={(e) => e.stopPropagation()}>
                    <div className="row" style={{ justifyContent: "space-between" }}><b>{pick.patient_name}</b><button className="btn sm ghost" onClick={() => setPick(null)}>✕</button></div>
                    <div className="small muted">{fmtClock(pick.start)} · {SERVICE_LABEL[pick.service]}</div>
                    <div className="small">Session {pick.session_number ? `${pick.session_number}/${pick.plan_total ?? "?"}` : "n/a"} · <span className="pk">{pick.status.replace("_", " ")}</span></div>
                    {pick.flags.length > 0 && <div style={{ margin: "4px 0" }}>{pick.flags.map((f) => <span key={f} className={cx("tag", f === "red_flag" ? "bad" : f === "owes" ? "warn" : "")} style={{ marginRight: 3 }}>{f.replace("_", " ")}</span>)}</div>}
                    <div className="row" style={{ gap: 6, marginTop: 6 }}>
                      <button className="btn sm" onClick={() => onOpenFolder(pick.patient_id)}>Open folder</button>
                      <button className="btn sm ghost" onClick={() => onMessage(`wa:${pick.patient_id}`)}>Message patient</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
