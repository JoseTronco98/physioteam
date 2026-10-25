import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { AutopilotStats } from "../types";
import { Card } from "../components/common";
import { BehindTheScenes } from "../components/behind";
import { cx, tokens, usd } from "../util";
import { GuideLabel } from "../components/guide";
import { TeamRoom } from "../components/teamroom";

export function Autopilot() {
  const { run, autopilot } = useStore();
  const [stats, setStats] = useState<AutopilotStats | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { void run(api.autopilotStats()).then((s) => s && setStats(s)); }, [run]);
  useEffect(() => { if (autopilot) setStats(autopilot); }, [autopilot]);
  const s = stats;
  return (
    <div className="screen gpage">
      <div className="cp-hero" style={{ paddingTop: 16 }}>
        <GuideLabel>Demo guide · autopilot</GuideLabel>
        <h1>A whole week.<br />Three minutes.</h1>
        <p>Bots play the patients, the doctors and the therapist. The clinic's agents do the real work, and every cent is counted.</p>
      </div>
      <div className="row" style={{ marginBottom: 4, justifyContent: "center" }}>
        {s?.running
          ? <button className="btn danger" disabled={busy} onClick={async () => { setBusy(true); const r = await run(api.autopilotStop()); if (r) setStats(r); setBusy(false); }}>Stop</button>
          : <button className="gbtn solid lg" disabled={busy} onClick={async () => { setBusy(true); const r = await run(api.autopilotStart(5, 20)); if (r) setStats(r); setBusy(false); }}>▶ Run the week</button>}
      </div>
      <p className="tiny muted" style={{ textAlign: "center", margin: "6px 0 16px" }}>Starts a fresh sandbox. Bot costs are counted separately, so cost per patient reflects only the product.</p>
      <div className="glass gpanel" style={{ marginBottom: 16 }}>
        <h3 style={{ margin: "0 0 10px", fontSize: 22, letterSpacing: "-.02em" }}>The team room.</h3>
        <TeamRoom />
      </div>
      {s && (
        <div className="glass gpanel">
          <div className="row" style={{ marginBottom: 12 }}>
            <span className={cx("tag", s.running ? "pk" : "")}>{s.running ? `running · ${s.day}` : s.progress_pct >= 100 ? "finished" : "idle"}</span>
            <div className="progress" style={{ flex: 1 }}><i style={{ width: `${s.progress_pct}%` }} /></div>
            <span className="small muted">{Math.round(s.progress_pct)}%</span>
          </div>
          <div className="kpis">
            <div className="kpi"><div className="v">{s.patients}</div><div className="l">patients simulated</div></div>
            <div className="kpi"><div className="v">{s.messages}</div><div className="l">messages handled</div></div>
            <div className="kpi"><div className="v">{s.handled_without_therapist_pct}%</div><div className="l">without the therapist</div></div>
            <div className="kpi"><div className="v bad">{s.red_flags_escalated}</div><div className="l">red flags escalated</div></div>
            <div className="kpi"><div className="v ok">{s.attacks_blocked}</div><div className="l">attacks blocked</div></div>
            <div className="kpi"><div className="v">{s.bookings} / {s.cancellations}</div><div className="l">bookings / cancellations</div></div>
          </div>
          <div className="grid" style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1fr)", marginTop: 14 }}>
            <Card title="Event log" sub="live">
              {s.log.length === 0 && <div className="empty">Start the week to see events.</div>}
              <div style={{ maxHeight: 460, overflowY: "auto" }}>
                <table><tbody>{s.log.map((l, i) => (
                  <tr key={i}><td className="muted small" style={{ whiteSpace: "nowrap" }}>{l.time}</td><td className="small">{l.who}</td><td className="small">{l.what}</td>
                    <td className={cx("small", l.tone === "bad" ? "bad" : l.tone === "warn" ? "warn" : "ok")}>{l.outcome}</td></tr>
                ))}</tbody></table>
              </div>
            </Card>
            <Card title="Unit economics" sub="measured from this run">
              <table><tbody>
                <tr><td>Tokens per patient per week</td><td>{tokens(s.tokens_per_patient_week)}</td></tr>
                <tr><td>Share served from cache</td><td>{s.cached_share_pct}%</td></tr>
                <tr><td>Cost per patient per week</td><td>{usd(s.cost_per_patient_week_usd)}</td></tr>
                <tr><td>Cost per clinic per month</td><td className="pk"><b>{usd(s.cost_per_clinic_month_usd, 2)}</b></td></tr>
                <tr><td>Clinic agents (this run)</td><td>{usd(s.product_usd)}</td></tr>
                <tr><td className="muted">Simulator bots (excluded)</td><td className="muted">{usd(s.simulator_usd)}</td></tr>
              </tbody></table>
              <p className="tiny dim" style={{ marginTop: 8 }}>At scale: multiply the cost per clinic per month by 100 or 10,000 clinics (see the report's tokenomics section).</p>
            </Card>
          </div>
        </div>
      )}
      <div className="glass gpanel" style={{ marginTop: 16 }}>
        <BehindTheScenes title="Behind the scenes: the clinic agents during the simulated week" maxHeight={420}
          note="Bots play the patients, doctors and the therapist; everything in this feed is the clinic's real agents at work." />
      </div>
    </div>
  );
}
