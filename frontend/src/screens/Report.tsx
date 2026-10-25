import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { BusinessPulse, DailyReport } from "../types";
import { Card, Md } from "../components/common";
import { fmtDay, fmtTime, money, SERVICE_LABEL, usd } from "../util";

export function PulseCards({ p, rate }: { p: BusinessPulse; rate: number }) {
  const max = Math.max(1, ...p.by_service.map((s) => s.revenue_mxn));
  return (
    <>
      <div className="kpis">
        <div className="kpi"><div className="v">{money(p.revenue_mxn)}</div><div className="l">Billed</div><div className="s">~USD {Math.round(p.revenue_mxn / rate)}</div></div>
        <div className="kpi"><div className="v">{money(p.collected_mxn)}</div><div className="l">Collected</div><div className="s">{money(p.outstanding_mxn)} outstanding</div></div>
        <div className="kpi"><div className="v">{p.utilization_pct}%</div><div className="l">Agenda utilization</div><div className="s">{p.sessions_done} sessions</div></div>
        <div className="kpi"><div className="v">{money(p.revenue_per_hour_mxn)}</div><div className="l">Revenue per open hour</div><div className="s">~USD {Math.round(p.revenue_per_hour_mxn / rate)}</div></div>
        <div className="kpi"><div className="v warn">{money(p.late_cancel_lost_mxn)}</div><div className="l">Lost to late cancellations</div><div className="s">not charged or not refilled</div></div>
        <div className="kpi"><div className="v pk">{usd(p.ai_cost_usd, 2)}</div><div className="l">AI cost for the period</div><div className="s">clinic agents only</div></div>
      </div>
      <div className="bars" style={{ marginTop: 12 }}>
        {p.by_service.map((s) => (
          <div key={s.service} className="b">
            <span>{s.service}</span>
            <span className="track"><i style={{ width: `${(s.revenue_mxn / max) * 100}%` }} /></span>
            <span className="muted small">{s.sessions} · {money(s.revenue_mxn)}</span>
          </div>
        ))}
      </div>
    </>
  );
}

export function Report() {
  const { run, state, docVersion } = useStore();
  const [r, setR] = useState<DailyReport | null>(null);
  const rate = state?.clinic.usd_rate ?? 18.5;
  const day = state?.now.slice(0, 10);
  useEffect(() => { void run(api.daily(day)).then((x) => x && setR(x)); }, [run, day, docVersion]);
  if (!r) return <div className="screen"><div className="empty">Loading the daily report…</div></div>;
  return (
    <div className="screen">
      <div className="row" style={{ marginBottom: 6 }}>
        <h1 className="page">Daily report · {fmtDay(`${r.date}T09:00`)}</h1>
        <span className="spacer" />
        <span className="tiny dim">Written by the Operations Partner and the Health Advisor. Use “End of day” in the top bar to generate today's.</span>
      </div>
      {r.narrative_md && <div className="card" style={{ marginBottom: 14 }}><Md>{r.narrative_md}</Md></div>}
      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
        <Card title="Tomorrow" sub="from Operations">
          {r.tomorrow.length === 0 && <div className="empty">No sessions tomorrow.</div>}
          <table><tbody>{r.tomorrow.map((a) => (
            <tr key={a.id}><td style={{ width: 52 }}>{fmtTime(a.start)}</td><td>{a.patient_name}<div className="tiny muted">{SERVICE_LABEL[a.service]}{a.session_number ? ` · session ${a.session_number}` : ""}</div></td>
              <td style={{ textAlign: "right" }}>{a.flags.map((f) => <span key={f} className={`tag ${f === "owes" ? "warn" : f === "red_flag" ? "bad" : f === "new" ? "pk" : ""}`} style={{ marginLeft: 3 }}>{f.replace("_", " ")}</span>)}</td></tr>
          ))}</tbody></table>
        </Card>
        <Card title="Balances to remind" sub="from Finance Ops">
          {r.balances_due.length === 0 && <div className="empty">Nobody owes anything.</div>}
          <table><tbody>{r.balances_due.map((b) => <tr key={b.patient_id}><td>{b.name}</td><td className="warn" style={{ textAlign: "right" }}>{money(b.amount_mxn, rate)}</td></tr>)}</tbody></table>
        </Card>
        <Card title="To review" sub="from Health Advisor">
          {r.to_review.length === 0 && <div className="empty">All documents signed.</div>}
          <table><tbody>{r.to_review.map((x) => <tr key={x.doc_id}><td>{x.patient_name}<div className="tiny muted">{x.title}</div></td><td style={{ textAlign: "right" }}><span className="tag pk">{x.action}</span></td></tr>)}</tbody></table>
        </Card>
        <Card title="Patients" sub="from Patient Success">
          <div className="small"><b>Satisfaction:</b> {r.patients.satisfaction}</div>
          <div className="small" style={{ marginTop: 6 }}><b>At risk:</b> {r.patients.at_risk.length ? r.patients.at_risk.join(", ") : "none"}</div>
          <div className="small" style={{ marginTop: 6 }}><b className="bad">Red flags:</b> {r.patients.red_flags.length ? r.patients.red_flags.join("; ") : "none"}</div>
        </Card>
      </div>
      <Card title="Plan for tomorrow, per patient" className="" >
        <table><thead><tr><th>Patient</th><th>Session focus (from the plan)</th><th>Watch for</th></tr></thead>
          <tbody>{r.plan_per_patient.map((p) => <tr key={p.patient_name}><td>{p.patient_name}</td><td>{p.focus}</td><td className="warn">{p.watch_for}</td></tr>)}</tbody></table>
      </Card>
      <div style={{ height: 14 }} />
      <Card title="Business pulse" sub={r.business.period}>
        <PulseCards p={r.business} rate={rate} />
      </Card>
    </div>
  );
}
