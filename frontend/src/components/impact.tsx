import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { AgentId, Appointment, PatientFolder } from "../types";
import { AGENT_LABEL, cx, fmtDay, fmtTime, usd } from "../util";
import { tidyFeed } from "./behind";

/** Patient mode: what one WhatsApp conversation sets in motion inside the clinic. */
export function ClinicImpact({ patientId, name }: { patientId: string; name: string }) {
  const { run, state, approvals, alerts, eventTick, docVersion, feed } = useStore();
  const [day, setDay] = useState<Appointment[]>([]);
  const [folder, setFolder] = useState<PatientFolder | null>(null);
  const [mine, setMine] = useState<Appointment | null>(null);
  const first = (folder?.patient.name ?? name).split(" ")[0];

  // Re-read the agenda and the folder whenever something happens (debounced).
  useEffect(() => {
    const t = window.setTimeout(async () => {
      const f = await run(api.folder(patientId));
      if (f) setFolder(f);
      const now = state?.now.slice(0, 10) ?? "";
      const appt = f?.appointments.filter((a) => ["booked", "confirmed", "pending_approval"].includes(a.status) && a.start.slice(0, 10) >= now)
        .sort((a, b) => a.start.localeCompare(b.start))[0]
        ?? f?.appointments.slice().sort((a, b) => b.start.localeCompare(a.start))[0] ?? null;
      setMine(appt ?? null);
      const d = (appt?.start ?? state?.now ?? "").slice(0, 10);
      if (d) {
        const ag = await run(api.agenda(`${d}T00:00`, `${d}T23:59`));
        if (ag) setDay(ag.filter((a) => a.start.startsWith(d)).sort((a, b) => a.start.localeCompare(b.start)));
      }
    }, 500);
    return () => window.clearTimeout(t);
  }, [patientId, eventTick, docVersion, run, state?.now]);

  const myApprovals = approvals.filter((a) => a.patient_id === patientId || a.related_patient_ids?.includes(patientId)).slice(0, 4);
  const myAlerts = alerts.filter((a) => a.patient_id === patientId);
  const evalDoc = folder?.documents.find((d) => d.kind === "evaluation");
  const filled = evalDoc?.fields.filter((f) => f.value) ?? [];
  const total = evalDoc?.fields.length ?? 0;
  const otherDocs = (folder?.documents ?? []).filter((d) => d.kind !== "evaluation");

  // Last run that touched this patient's chat
  const last = useMemo(() => {
    const rows = tidyFeed(feed);
    const anchor = rows.find((r) => r.thread === `wa:${patientId}` && r.agent);
    if (!anchor) return null;
    const runId = rows.find((r) => r.run_id && (r.agent === "patient_success" || r.type === "tool"))?.run_id ?? anchor.run_id;
    const runRows = runId ? rows.filter((r) => r.run_id === runId) : [anchor];
    const steps: string[] = [];
    [...runRows].reverse().forEach((r) => {
      if (r.type === "agent" && r.agent && !steps.includes(AGENT_LABEL[r.agent])) steps.push(AGENT_LABEL[r.agent]);
      if (r.type === "tool") { const t = r.text.split(":")[0]; if (!steps.includes(t)) steps.push(t); }
    });
    const cost = runRows.reduce((s, r) => s + (r.cost_usd ?? 0), 0) || anchor.cost_usd || 0;
    if (!steps.length && anchor.agent) steps.push(AGENT_LABEL[anchor.agent as AgentId]);
    return { steps, cost };
  }, [feed, patientId]);

  const hours = day.length ? Array.from(new Set(day.map((a) => a.start.slice(11, 13)))) : [];
  const slotClass = (a: Appointment) => cx(
    a.patient_id === patientId ? cx("me", a.status === "confirmed" || a.status === "booked" ? "ok" : "") : "busy",
    ["cancelled", "late_cancel", "no_show"].includes(a.status) && "gone");

  return (
    <div className="impact">
      <h3>What just happened in the clinic</h3>
      <div className="tiny muted">Every message {first} sends moves something real inside the clinic.</div>

      <div className="icard">
        <div className="t"><span>Agenda · {fmtDay(mine?.start ?? state?.now)}</span>
          {mine && <span className={cx("tag", mine.status === "pending_approval" ? "warn" : mine.status === "confirmed" || mine.status === "booked" ? "ok" : "")}>
            {mine.status === "pending_approval" ? "pending" : mine.status.replace("_", " ")}</span>}
        </div>
        {day.length === 0 ? <div className="tiny muted">Nothing booked that day yet.</div> : (
          <div className="daystrip">
            {day.filter((a) => hours.includes(a.start.slice(11, 13))).slice(0, 7).map((a) => (
              <div key={a.id} className={slotClass(a)} title={`${a.patient_name} ${fmtTime(a.start)}`}>
                <b>{fmtTime(a.start).slice(0, 2)}</b>{a.patient_id === patientId ? first : a.patient_name.split(" ")[0]}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="icard">
        <div className="t"><span>Therapist's phone</span><span>{myApprovals.filter((a) => a.status === "pending").length + myAlerts.length} new</span></div>
        {myApprovals.length === 0 && myAlerts.length === 0 && <div className="tiny muted">No notifications yet. Book something and one appears here.</div>}
        {myAlerts.map((a) => (
          <div key={a.id} className="notif red"><div className="app">!</div><div className="nt"><b>Red flag</b><br />{a.text}</div></div>
        ))}
        {myApprovals.map((a) => (
          <div key={a.id} className="notif"><div className="app">P</div>
            <div className="nt"><b>{a.status === "pending" ? "Needs approval" : `Done: ${a.status}`}</b><br />{a.title}</div>
          </div>
        ))}
      </div>

      <div className="icard">
        <div className="t"><span>{first}'s folder</span><span>{total ? `${filled.length} / ${total} fields` : ""}</span></div>
        {evalDoc ? (
          <>
            <div className="ibar"><i style={{ width: `${total ? (filled.length / total) * 100 : 0}%` }} /></div>
            <div className="tiny muted" style={{ marginTop: 8 }}>{filled.slice(0, 8).map((f) => f.label.split(" (")[0]).join(" · ") || "Empty so far"}</div>
          </>
        ) : <div className="tiny muted">The evaluation form starts filling as {first} answers the intake questions.</div>}
        {otherDocs.length > 0 && <div className="tiny" style={{ marginTop: 8 }}>{otherDocs.slice(0, 4).map((d) => <span key={d.id} className="tag" style={{ marginRight: 4 }}>{d.title}</span>)}</div>}
      </div>

      <div className="icard">
        <div className="t"><span>Who did it</span><span>{last?.cost ? usd(last.cost) : ""}</span></div>
        {last ? <div className="flow">{["Safety layer", ...last.steps].map((s, i) => <span key={s + i} style={{ display: "contents" }}>{i > 0 && <span className="a">→</span>}<span className="s">{s}</span></span>)}</div>
          : <div className="tiny muted">Send a message to see the agents at work.</div>}
      </div>
    </div>
  );
}
