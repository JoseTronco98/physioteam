import { useEffect, useMemo, useState } from "react";
import { useStore } from "../store";
import type { AgentId } from "../types";
import { AGENT_LABEL, cx, usd } from "../util";

const ROLE: Record<AgentId, string> = {
  ops_partner: "Lead · agenda, money, ops",
  health_advisor: "Lead · plans, reports, doctors",
  patient_success: "WhatsApp with patients",
  finance_ops: "Balances and invoices",
  clinical_scribe: "Forms and SOAP notes",
  imaging_reader: "Reads studies",
  router: "Picks the right lead",
  safety: "Checks every message",
};
const AVA: Record<AgentId, [string, string]> = {
  ops_partner: ["🗂️", "#E8F2FF"], health_advisor: ["🩺", "#EFEEFF"], patient_success: ["💬", "#E6F7FB"], finance_ops: ["💰", "#FFF4E5"],
  clinical_scribe: ["📝", "#E8F7EC"], imaging_reader: ["🔬", "#EFEEFF"], router: ["🧭", "#F2F2F7"], safety: ["🛡️", "#E8F7EC"],
};
// x in % of the floor width, y in px
const POS: Record<AgentId, [number, number]> = {
  router: [50, 34], ops_partner: [24, 210], health_advisor: [76, 210],
  patient_success: [12, 420], finance_ops: [36, 420], clinical_scribe: [64, 420], imaging_reader: [88, 420], safety: [50, 420],
};
const EDGES: [AgentId, AgentId][] = [
  ["router", "ops_partner"], ["router", "health_advisor"], ["ops_partner", "health_advisor"],
  ["ops_partner", "patient_success"], ["ops_partner", "finance_ops"], ["health_advisor", "clinical_scribe"], ["health_advisor", "imaging_reader"],
];
const ORDER: AgentId[] = ["ops_partner", "health_advisor", "patient_success", "finance_ops", "clinical_scribe", "imaging_reader", "router", "safety"];

function useNow() {
  const { activity } = useStore();
  const [tick, setTick] = useState(0);
  useEffect(() => { const t = window.setInterval(() => setTick((x) => x + 1), 1000); return () => window.clearInterval(t); }, []);
  return useMemo(() => {
    void tick;
    const runId = activity.find((a) => a.run_id)?.run_id;
    if (!runId) return null;
    const rows = activity.filter((a) => a.run_id === runId);
    const start = [...rows].reverse().find((r) => r.kind === "start");
    const end = rows.find((r) => r.kind === "finished" || r.kind === "error");
    const agents: AgentId[] = [];
    [...rows].reverse().forEach((r) => { if (r.agent && !agents.includes(r.agent)) agents.push(r.agent); });
    const t0 = [...rows].reverse()[0]?.time ?? Date.now();
    const t1 = end?.time ?? Date.now();
    const tools = rows.filter((r) => r.kind === "tool").length;
    return { task: start?.text ?? "Working", agents, secs: Math.max(0, Math.round((t1 - t0) / 1000)), done: Boolean(end), endText: end?.text, tools };
  }, [activity, tick]);
}

function Desk({ id, compact }: { id: AgentId; compact?: boolean }) {
  const { live, state } = useStore();
  const b = state?.spend.product.find((x) => x.agent === id);
  const now = live[id];
  const [emoji, bg] = AVA[id];
  const isLead = id === "ops_partner" || id === "health_advisor";
  const style = compact ? undefined : { left: `${POS[id][0]}%`, top: POS[id][1] };
  return (
    <div className={cx("desk", isLead && "lead", now && "active", compact && "mini")} style={style}>
      <div className="ava" style={{ background: bg }}>{emoji}</div>
      <div className="n">{AGENT_LABEL[id]}</div>
      <div className="r">{ROLE[id]}</div>
      <div className="say">{now ? `“${now}”` : "idle"}</div>
      <div className="meter2"><span>{b ? `${b.calls} calls` : id === "safety" ? "code, no AI" : "0 calls"}</span><span>{b ? usd(b.usd) : "$0"}</span></div>
    </div>
  );
}

/** The team room: one desk per agent, lit while working, with live speech bubbles, hand-off lines and cost meters. */
export function TeamRoom({ compact }: { compact?: boolean }) {
  const { live } = useStore();
  const now = useNow();
  const hot = (a: AgentId, b: AgentId) => Boolean(live[a] && live[b]);

  const nowCard = (
    <div className="room-now">
      <div className="glabel">Now</div>
      {now ? (
        <>
          <div className="tl">{now.task}</div>
          <div className="flow">{now.agents.map((a, i) => <span key={a} style={{ display: "contents" }}>{i > 0 && <span className="a">→</span>}<span className="s">{AGENT_LABEL[a]}</span></span>)}</div>
          <div className="tiny muted" style={{ marginTop: 8 }}>
            {now.tools} tool{now.tools === 1 ? "" : "s"} · {now.secs} s{now.done ? ` · ${now.endText?.replace(/^Done · /, "") ?? ""}` : " · working…"}
          </div>
        </>
      ) : <div className="tiny muted" style={{ marginTop: 6 }}>Quiet for now. Send a message or move the clock and watch the desks light up.</div>}
    </div>
  );

  if (compact) {
    return (
      <div>
        <div className="room-floor compact" style={{ padding: "34px 8px 8px", display: "grid", gap: "34px 10px", gridTemplateColumns: "1fr 1fr" }}>
          {ORDER.map((id) => <div key={id} style={{ position: "relative" }}><Desk id={id} compact /></div>)}
        </div>
        {nowCard}
      </div>
    );
  }
  return (
    <div>
      <div className="room-floor">
        <svg className="room-links" viewBox="0 0 100 590" preserveAspectRatio="none">
          {EDGES.map(([a, b]) => {
            const [x1, y1] = POS[a]; const [x2, y2] = POS[b];
            const fromY = y1 + (a === "router" ? 128 : 148);
            const toY = b === "health_advisor" && a === "ops_partner" ? y2 + 70 : y2;
            const d = a === "ops_partner" && b === "health_advisor"
              ? `M ${x1 + 11} ${y1 + 70} L ${x2 - 11} ${y2 + 70}`
              : `M ${x1} ${fromY} C ${x1} ${(fromY + toY) / 2}, ${x2} ${(fromY + toY) / 2}, ${x2} ${toY}`;
            return <path key={`${a}-${b}`} d={d} className={cx(hot(a, b) && "hot")} vectorEffect="non-scaling-stroke" />;
          })}
        </svg>
        {ORDER.filter((id) => id !== "safety").map((id) => <Desk key={id} id={id} />)}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 260px", gap: 12, alignItems: "start" }}>
        {nowCard}
        <div className="room-now"><Desk id="safety" compact /></div>
      </div>
      <div className="room-legend"><span>Lit desk: working now</span><span>Blue dashed line: hand-off in progress</span><span>Meters: calls and cost in this demo session</span></div>
    </div>
  );
}
