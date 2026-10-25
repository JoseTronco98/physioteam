import { useEffect, useState } from "react";
import { useStore } from "../store";
import type { ActivityRow, AgentId } from "../types";
import { AGENT_COLOR, AGENT_LABEL, cx, fmtClock, usd } from "../util";

const FILTERS = ["All", "Agents", "Patients", "Safety", "Approvals"] as const;
type Filter = (typeof FILTERS)[number];

const TREE: { lead: AgentId; subs: AgentId[] }[] = [
  { lead: "ops_partner", subs: ["patient_success", "finance_ops"] },
  { lead: "health_advisor", subs: ["clinical_scribe", "imaging_reader"] },
];

/** The server log uses raw event names; the live stream uses short ones. Normalise both. */
const TYPE_ALIAS: Record<string, ActivityRow["type"]> = {
  agent_started: "agent", tool_called: "tool", run_finished: "run", alert: "safety",
};
function norm(r: ActivityRow): ActivityRow {
  const t = TYPE_ALIAS[r.type as string] ?? r.type;
  return t === r.type ? r : { ...r, type: t };
}

/** Drop bare "Run finished" rows; carry their cost onto the latest row of the same run (or the row just before). */
export function tidyFeed(rows: ActivityRow[]): ActivityRow[] {
  const xs = rows.map(norm);
  const out: ActivityRow[] = [];
  const carry: Record<string, number> = {};
  let loose = 0;
  for (const r of xs) {                       // newest first
    if (r.type === "run" && r.tone !== "bad") {
      if (r.cost_usd) { if (r.run_id) carry[r.run_id] = (carry[r.run_id] ?? 0) + r.cost_usd; else loose += r.cost_usd; }
      continue;
    }
    let row = r;
    const c = (r.run_id && carry[r.run_id]) || (!r.run_id && loose) || 0;
    if (c && !r.cost_usd) {
      row = { ...r, cost_usd: c };
      if (r.run_id) delete carry[r.run_id]; else loose = 0;
    }
    out.push(row);
  }
  return out;
}

function matches(r: ActivityRow, f: Filter): boolean {
  if (f === "All") return true;
  if (f === "Agents") return r.type === "agent" || r.type === "tool" || r.type === "delegation" || r.type === "run";
  if (f === "Patients") return r.type === "message" && (!r.thread || r.thread.startsWith("wa:"));
  if (f === "Safety") return r.type === "safety" || r.agent === "safety" || r.tone === "bad";
  return r.type === "approval";
}

function Node({ id, small }: { id: AgentId; small?: boolean }) {
  const { agents, live } = useStore();
  const info = agents.find((a) => a.id === id);
  const now = live[id];
  return (
    <div className={cx("bts-node", small && "sub", now && "live")} title={info?.role}>
      <div className="bn"><i style={{ background: AGENT_COLOR[id] ?? "#8E8E93" }} />{AGENT_LABEL[id]}</div>
      <div className="bnow">{now ? `now: ${now}` : <span className="dim">idle</span>}</div>
    </div>
  );
}

export function OrgChart() {
  return (
    <div className="bts-org">
      <div className="bts-tree">
        {TREE.map((t) => (
          <div key={t.lead} className="bts-branch">
            <Node id={t.lead} />
            <div className="bts-subs">{t.subs.map((s) => <Node key={s} id={s} small />)}</div>
          </div>
        ))}
      </div>
      <div className="bts-guards"><Node id="router" small /><Node id="safety" small /></div>
    </div>
  );
}

/** Live view of what the agent team is doing: org chart + filterable activity feed. */
export function BehindTheScenes({ title = "Behind the scenes", maxHeight = 420, collapsible, note }: {
  title?: string; maxHeight?: number; collapsible?: boolean; note?: string;
}) {
  const { feed, loadFeed } = useStore();
  const [filter, setFilter] = useState<Filter>("All");
  const [open, setOpen] = useState(true);
  useEffect(() => { void loadFeed(); }, [loadFeed]);
  const rows = tidyFeed(feed).filter((r) => matches(r, filter));

  return (
    <div className="card bts">
      <h3 style={{ display: "flex", alignItems: "center" }}>
        {title}<small style={{ marginLeft: 8 }}>live</small>
        <span className="spacer" />
        {collapsible && <button className="btn sm ghost" onClick={() => setOpen((o) => !o)}>{open ? "Hide" : "Show"}</button>}
      </h3>
      {open && (
        <>
          <OrgChart />
          <div className="chips">
            {FILTERS.map((f) => (
              <button key={f} className={cx("chip", filter === f && "on")} onClick={() => setFilter(f)}>{f}</button>
            ))}
          </div>
          <div className="bts-feed" style={{ maxHeight }}>
            {rows.length === 0 && <div className="empty">Nothing here yet. Send a message or move the clock and watch the agents work.</div>}
            {rows.map((r) => (
              <div key={r.id} className={cx("bts-row", r.tone)}>
                <span className="bt">{fmtClock(r.time).replace(/^(\w+) \w+ \d+, /, "$1 ")}</span>
                <i className="bdot" style={{ background: r.agent ? AGENT_COLOR[r.agent] ?? "#8E8E93" : r.type === "message" ? "#30B0C7" : "#C7C7CC" }}
                  title={r.agent ? AGENT_LABEL[r.agent] : r.type} />
                <span className="btx">{r.agent && r.type !== "message" && <b>{AGENT_LABEL[r.agent]} </b>}{r.text}</span>
                {r.cost_usd ? <span className="bc">{usd(r.cost_usd)}</span> : null}
              </div>
            ))}
          </div>
          {note && <p className="tiny dim" style={{ marginTop: 8, marginBottom: 0 }}>{note}</p>}
        </>
      )}
    </div>
  );
}
