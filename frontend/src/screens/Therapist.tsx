import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Appointment, Mission, ThreadId } from "../types";
import { ApprovalCard, Composer, MessageList } from "../components/common";
import { AlertBar, AskDrawer } from "../components/shell";
import { BehindTheScenes } from "../components/behind";
import { TeamRoom } from "../components/teamroom";
import { ApprovalsView } from "../components/approvals";
import { AgendaWeek, PatientChats } from "../components/clinicviews";
import { GuideSide, useGuide } from "../components/guide";
import { cx, fmtDay, fmtTime, SERVICE_LABEL } from "../util";
import { Folder } from "./Folder";
import { Report } from "./Report";
import { Costs } from "./Costs";
import { Connect } from "./Connect";

export type Section = "chat" | "messages" | "agenda" | "approvals" | "folders" | "report" | "costs" | "settings";
export const SECTIONS: { id: Section; label: string; icon: string }[] = [
  { id: "chat", label: "Team chat", icon: "💬" },
  { id: "messages", label: "Clinic Messages", icon: "🟢" },
  { id: "agenda", label: "Agenda", icon: "📅" },
  { id: "approvals", label: "Approvals", icon: "✅" },
  { id: "folders", label: "Patient folders", icon: "📁" },
  { id: "report", label: "Daily report", icon: "📊" },
  { id: "costs", label: "Costs and safety", icon: "🛡️" },
  { id: "settings", label: "Settings", icon: "⚙️" },
];

const THREADS: { id: ThreadId; label: string; hint: string }[] = [
  { id: "team", label: "Team", hint: "Both leads. The router picks who answers; start with @Ops or @Health to choose." },
  { id: "ops", label: "Operations Partner", hint: "1:1 with the Operations Partner: agenda, policies, money, reports." },
  { id: "health", label: "Health Advisor", hint: "1:1 with the Health Advisor: evaluations, plans, progress, doctors." },
];

export function MissionsPanel({ missions, onTry, title = "Missions" }: { missions: Mission[]; onTry: (m: Mission) => void; title?: string }) {
  const { missionsDone } = useStore();
  const groups = useMemo(() => {
    const g: Record<string, Mission[]> = {};
    missions.forEach((m) => (g[m.group] ??= []).push(m));
    return g;
  }, [missions]);
  const done = missions.filter((m) => m.done || missionsDone.has(m.id)).length;
  return (
    <div className="card missions">
      <h3>{title}<small>{done}/{missions.length} done</small></h3>
      <div className="progress" style={{ marginBottom: 10 }}><i style={{ width: `${missions.length ? (done / missions.length) * 100 : 0}%` }} /></div>
      {Object.entries(groups).map(([g, ms]) => (
        <div className="group" key={g}>
          <div className="section-title">{g}</div>
          {ms.map((m) => {
            const isDone = m.done || missionsDone.has(m.id);
            return (
              <div key={m.id} className={cx("mission", isDone && "done")}>
                <span className="chk">{isDone ? "✓" : ""}</span>
                <span className="mt">{m.title}{m.hint && <div className="tiny dim">{m.hint}</div>}</span>
                {m.try_prompt ? <button className="btn try" onClick={() => onTry(m)}>Try it</button> : null}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function TodayList({ agenda, now }: { agenda: Appointment[]; now?: string }) {
  return (
    <div className="pblock">
      <div className="pblock-h">Today <span>{fmtDay(now)}</span></div>
      {agenda.length === 0 && <div className="empty">No sessions today.</div>}
      {agenda.map((a) => (
        <div key={a.id} className="prow">
          <span className="pt">{fmtTime(a.start)}</span>
          <span className="pn">{a.patient_name}<small>{SERVICE_LABEL[a.service]}{a.session_number ? ` · ${a.session_number}/${a.plan_total ?? "?"}` : ""}</small></span>
          <span className="pf">
            {a.status === "pending_approval" && <span className="tag warn">pending</span>}
            {a.status === "confirmed" && <span className="tag ok">confirmed</span>}
            {(a.status === "cancelled" || a.status === "late_cancel" || a.status === "no_show") && <span className="tag">{a.status.replace("_", " ")}</span>}
            {a.flags.filter((f) => f !== "change_proposed").map((f) => <span key={f} className={cx("tag", f === "red_flag" ? "bad" : f === "owes" ? "warn" : f === "new" ? "blue" : "")}>{f.replace("_", " ")}</span>)}
          </span>
        </div>
      ))}
    </div>
  );
}

/** The real product: a Mac-style window with the clinic's own navigation. */
export function TherapistProduct({ section, go, draftReq }: {
  section: Section; go: (s: Section) => void; draftReq: { thread: ThreadId; text: string; n: number } | null;
}) {
  const { loadThread, threads, approvals, state, run, docVersion, setFocusPatient, lastMessage } = useStore();
  const { on: guideOn } = useGuide();
  const [thread, setThread] = useState<ThreadId>("team");
  const [openThread, setOpenThread] = useState<string | null>(null);
  const [msgUnread, setMsgUnread] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [agenda, setAgenda] = useState<Appointment[]>([]);
  const [ask, setAsk] = useState<"ops" | "health" | null>(null);
  const [seen, setSeen] = useState<Record<string, number>>({});

  useEffect(() => { THREADS.forEach((t) => void loadThread(t.id)); }, [loadThread]);
  const day = state?.now.slice(0, 10);
  useEffect(() => {
    if (!day) return;
    void run(api.agenda(`${day}T00:00`, `${day}T23:59`)).then((a) => a && setAgenda(a.filter((x) => x.start.startsWith(day))));
  }, [day, run, approvals, docVersion, lastMessage]);
  useEffect(() => {
    setSeen((s) => {
      const c = { ...s, [thread]: threads[thread]?.length ?? 0 };
      THREADS.forEach((t) => { if (c[t.id] === undefined && threads[t.id]) c[t.id] = threads[t.id].length; });
      return c;
    });
  }, [thread, threads]);
  useEffect(() => {
    if (lastMessage && (lastMessage.thread.startsWith("wa:") || lastMessage.thread.startsWith("doc:"))
      && (lastMessage.role === "patient" || lastMessage.role === "doctor") && section !== "messages") setMsgUnread((n) => n + 1);
  }, [lastMessage]); // eslint-disable-line
  useEffect(() => { if (section === "messages") setMsgUnread(0); }, [section]);
  useEffect(() => {
    if (!draftReq) return;
    setThread(draftReq.thread);
    setDrafts((d) => ({ ...d, [draftReq.thread]: draftReq.text }));
  }, [draftReq]);

  const openFolder = (pid: string) => { setFocusPatient(pid); go("folders"); };
  const messagePatient = (th: string) => { setOpenThread(th); go("messages"); };
  const pend = approvals.filter((a) => a.status === "pending");
  const current = THREADS.find((t) => t.id === thread)!;
  const showRight = section === "chat" || section === "messages";

  return (
    <div className="pwin">
      <div className="pchrome"><i className="tl-r" /><i className="tl-y" /><i className="tl-g" /><span>PhysioTeam</span></div>
      <div className={cx("papp", showRight && "withright")}>
        <nav className="pside">
          <div className="pbrand">Physio<b>Team</b><small>{state?.clinic.name}</small></div>
          {SECTIONS.map((s) => (
            <button key={s.id} className={cx("pitem", section === s.id && "on")} onClick={() => go(s.id)}>
              <span className="pi">{s.icon}</span>
              <span className="pl">{s.label}{s.id === "messages" && <small>powered by WhatsApp</small>}</span>
              {s.id === "approvals" && pend.length > 0 && <span className="badge">{pend.length}</span>}
              {s.id === "messages" && msgUnread > 0 && <span className="badge">{msgUnread}</span>}
            </button>
          ))}
          <span className="spacer" />
          <div className="pstatus"><i />WhatsApp · simulated in this demo</div>
        </nav>

        <main className="pmain">
          <AlertBar />
          {section === "chat" && (
            <div className="pchat">
              <div className="phead">
                <div>
                  <h2 className="ptitle">Team chat</h2>
                  <div className="psub">Your two leads and their team. Nothing important happens without you.</div>
                </div>
                {guideOn && (
                  <div className="row" style={{ gap: 6 }}>
                    <button className="gpill" onClick={() => setAsk("ops")}>What can I ask Ops?</button>
                    <button className="gpill" onClick={() => setAsk("health")}>What can I ask Health?</button>
                  </div>
                )}
              </div>
              <div className="tabs">
                {THREADS.map((t) => {
                  const unread = seen[t.id] === undefined ? 0 : Math.max(0, (threads[t.id]?.length ?? 0) - seen[t.id]);
                  return (
                    <button key={t.id} className={cx(thread === t.id && "on")} onClick={() => setThread(t.id)}>
                      {t.label}{thread !== t.id && unread > 0 && <span className="badge">{unread}</span>}
                    </button>
                  );
                })}
              </div>
              <div className="chat">
                <MessageList thread={thread} me={["therapist", "user"]} />
                <Composer thread={thread} draft={drafts[thread] ?? ""} setDraft={(v) => setDrafts((d) => ({ ...d, [thread]: v }))}
                  placeholder={thread === "team" ? "Message your team… e.g. What's my day?  (Enter to send, Shift+Enter for a new line)" : `Message the ${current.label}…`}
                  hint={current.hint} />
              </div>
            </div>
          )}
          {section === "messages" && <PatientChats initial={openThread} onOpened={() => setOpenThread(null)} />}
          {section === "agenda" && (
            <>
              <h2 className="ptitle">Agenda</h2>
              <div className="psub" style={{ marginBottom: 12 }}>Your week at a glance. Tap an appointment to open the folder or message the patient.</div>
              <AgendaWeek onOpenFolder={openFolder} onMessage={messagePatient} />
            </>
          )}
          {section === "approvals" && (
            <>
              <h2 className="ptitle">Approvals</h2>
              <div className="psub" style={{ marginBottom: 12 }}>One decision at a time. See exactly what happens before you tap.</div>
              <ApprovalsView />
            </>
          )}
          {section === "folders" && (
            <>
              <h2 className="ptitle">Patient folders</h2>
              <div className="psub" style={{ marginBottom: 12 }}>Every evaluation, note, plan and report. Ready to sign, print or send.</div>
              <Folder />
            </>
          )}
          {section === "report" && <Report />}
          {section === "costs" && <Costs />}
          {section === "settings" && <Connect />}
        </main>

        {showRight && (
          <aside className="pright">
            <div className="pblock">
              <div className="pblock-h">Approvals {pend.length > 0 && <span className="badge">{pend.length}</span>}</div>
              {pend.length === 0 && <div className="empty">Nothing waiting for you.</div>}
              {pend.slice(0, 4).map((a) => <ApprovalCard key={a.id} a={a} compact />)}
              {pend.length > 4 && <button className="btn sm ghost" style={{ marginTop: 8 }} onClick={() => go("approvals")}>See all {pend.length}</button>}
            </div>
            <TodayList agenda={agenda} now={state?.now} />
          </aside>
        )}
      </div>
      {ask && <AskDrawer which={ask} onClose={() => setAsk(null)} onPick={(q) => { const t: ThreadId = ask === "ops" ? "ops" : "health"; setThread(t); setDrafts((d) => ({ ...d, [t]: q })); go("chat"); }} />}
    </div>
  );
}

function RightGuide() {
  const [view, setView] = useState<"feed" | "room">("feed");
  return (
    <>
      <div className="seg gtoggle" style={{ width: "100%" }}>
        <button className={cx(view === "feed" && "on")} onClick={() => setView("feed")}>Behind the scenes</button>
        <button className={cx(view === "room" && "on")} onClick={() => setView("room")}>Team room</button>
      </div>
      {view === "feed"
        ? <BehindTheScenes maxHeight={520} note="An x-ray of the agents and tools at work. A real therapist doesn't see this." />
        : <TeamRoom compact />}
    </>
  );
}

/** Therapist mode: guide missions · product window · guide behind-the-scenes. */
export function Therapist({ section, go }: { section: Section; go: (s: Section) => void }) {
  const { run } = useStore();
  const { on: guideOn } = useGuide();
  const [missions, setMissions] = useState<Mission[]>([]);
  const [draftReq, setDraftReq] = useState<{ thread: ThreadId; text: string; n: number } | null>(null);
  useEffect(() => { void run(api.missions("therapist")).then((m) => m && setMissions(m)); }, [run]);

  const onTry = (m: Mission) => {
    const p = m.try_prompt ?? "";
    const target: ThreadId = p.startsWith("@Health") ? "health" : p.startsWith("@Ops") ? "ops" : "team";
    const clean = target !== "team" ? p.replace(/^@(Health|Ops)\s*/, "") : p;
    setDraftReq((d) => ({ thread: target, text: clean, n: (d?.n ?? 0) + 1 }));
    go("chat");
  };

  if (!guideOn) return <div className="stage solo"><TherapistProduct section={section} go={go} draftReq={draftReq} /></div>;
  return (
    <div className="stage">
      <GuideSide side="left" label="Missions" minWidth={1400} width={262}>
        <MissionsPanel missions={missions} onTry={onTry} title="Things to try this week" />
      </GuideSide>
      <TherapistProduct section={section} go={go} draftReq={draftReq} />
      <GuideSide side="right" label="Behind the scenes" minWidth={1560} width={316}>
        <RightGuide />
      </GuideSide>
    </div>
  );
}
