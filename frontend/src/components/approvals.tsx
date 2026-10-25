import { useEffect, useMemo, useState } from "react";
import { useStore } from "../store";
import type { Approval } from "../types";
import { AGENT_LABEL, cx, fmtClock } from "../util";
import { KIND_LABEL, Md, PreviewBubble } from "./common";

/** Plain-language question for the decision title. */
function question(a: Approval): string {
  const t = a.title;
  switch (a.kind) {
    case "booking": return `${t.replace(/^Book /, "Book ")}?`;
    case "late_cancel_charge": return `${t.replace(/^Late cancellation: /, "Charge the late cancellation for ")}?`;
    case "sign_document": return `${t.replace(/^Sign /, "Sign ")}?`;
    case "plan_change": return `${t.replace(/^Approve /, "Approve ")}?`;
    case "outbound_message": return `${t}?`;
    case "invoice_request": return `Send to the accountant: ${t.replace(/^Invoice request: /, "")}?`;
    default: return `${t}?`;
  }
}

/** Fallback consequences when the backend does not provide them. */
function consequences(a: Approval): { yes: string[]; no: string[] } {
  if (a.if_approve?.length || a.if_decline?.length) return { yes: a.if_approve ?? [], no: a.if_decline ?? [] };
  switch (a.kind) {
    case "booking": return { yes: ["The slot is confirmed in your agenda", "The patient gets a confirmation on WhatsApp"], no: ["The patient is offered other times", "Nothing is charged"] };
    case "late_cancel_charge": return { yes: ["The session is added to the patient's balance", "The patient gets a kind note about the policy"], no: ["Nothing is charged this time"] };
    case "sign_document":
    case "plan_change": return { yes: ["The document becomes the signed version in the folder"], no: ["It stays a draft for your edits"] };
    case "outbound_message": return { yes: ["It is sent exactly as written"], no: ["Nothing is sent"] };
    case "invoice_request": return { yes: ["The request goes to the accountant's outbox", "The patient is told it is on its way"], no: ["Nothing is sent"] };
    default: return { yes: ["The action runs"], no: ["Nothing happens"] };
  }
}

export function ApprovalsView() {
  const { approvals, decide } = useStore();
  const pend = useMemo(() => approvals.filter((a) => a.status === "pending"), [approvals]);
  const decided = useMemo(() => approvals.filter((a) => a.status !== "pending").slice(0, 20), [approvals]);
  const [sel, setSel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const cur = approvals.find((a) => a.id === sel) ?? pend[0] ?? null;

  useEffect(() => { if (sel && !approvals.some((a) => a.id === sel && a.status === "pending")) setSel(null); }, [approvals, sel]);

  const act = async (a: Approval, option: string) => {
    setBusy(true);
    const i = pend.findIndex((x) => x.id === a.id);
    await decide(a.id, option);
    setSel(pend[i + 1]?.id ?? pend[i - 1]?.id ?? null);
    setBusy(false);
  };
  const routine = pend.filter((a) => a.kind === "booking");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || !cur || cur.status !== "pending" || busy) return;
      const i = pend.findIndex((x) => x.id === cur.id);
      if (e.key === "a" || e.key === "A") { const p = cur.options.find((o) => o.primary) ?? cur.options[0]; if (p) void act(cur, p.id); }
      if (e.key === "ArrowDown") { e.preventDefault(); setSel(pend[Math.min(i + 1, pend.length - 1)]?.id ?? null); }
      if (e.key === "ArrowUp") { e.preventDefault(); setSel(pend[Math.max(i - 1, 0)]?.id ?? null); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }); // eslint-disable-line

  return (
    <div className="apv">
      <div className="apv-list">
        <div className="row" style={{ justifyContent: "space-between", padding: "4px 4px 10px" }}>
          <b style={{ fontSize: 16 }}>Waiting for you</b><span className="tag pk">{pend.length}</span>
        </div>
        {pend.map((a) => (
          <div key={a.id} className={cx("apv-row", cur?.id === a.id && "on")} onClick={() => setSel(a.id)}>
            <div className="k">{KIND_LABEL[a.kind] ?? a.kind}</div>
            <div className="tt">{a.title}</div>
          </div>
        ))}
        {routine.length > 0 && (
          <button className="btn ghost" style={{ width: "100%", marginTop: 4 }} disabled={busy}
            onClick={async () => { setBusy(true); for (const a of routine) { const p = a.options.find((o) => o.primary) ?? a.options[0]; if (p) await decide(a.id, p.id); } setBusy(false); }}>
            Approve all bookings ({routine.length})
          </button>
        )}
        {decided.length > 0 && <div className="section-title" style={{ marginTop: 16 }}>Decided</div>}
        {decided.map((a) => (
          <div key={a.id} className="apv-row done" onClick={() => setSel(a.id)}>
            <div className="k">{a.status}</div>
            <div className="tt" style={{ fontWeight: 500 }}>{a.title}</div>
          </div>
        ))}
      </div>
      <div className="apv-detail">
        {!cur ? (
          <div className="apv-empty"><b>All clear.</b>Nothing needs you right now. Bookings, charges, signatures and reports will wait here.</div>
        ) : (() => {
          const c = consequences(cur);
          const resolved = cur.status !== "pending";
          return (
            <>
              <span className={cx("tag", resolved ? (cur.status === "approved" ? "ok" : "warn") : "warn")}>{resolved ? cur.status : "Needs you · 1 tap"}</span>
              <h2>{question(cur)}</h2>
              {cur.context ? <p className="muted" style={{ margin: 0 }}>{cur.context}</p> : cur.detail ? <div className="muted small"><Md>{cur.detail}</Md></div> : null}
              <div className="apv-what">
                <div className="box yes"><h5>If you approve</h5><ul>{c.yes.map((x) => <li key={x}>{x}</li>)}</ul></div>
                <div className="box no"><h5>If you decline</h5><ul>{c.no.map((x) => <li key={x}>{x}</li>)}</ul></div>
              </div>
              {cur.preview && <PreviewBubble p={cur.preview} />}
              {!resolved && (
                <div className="apv-actions">
                  {[...cur.options].sort((a, b) => Number(Boolean(b.primary)) - Number(Boolean(a.primary))).map((o) => (
                    <button key={o.id} className={cx("btn", o.primary ? "solid" : "ghost")} disabled={busy} onClick={() => void act(cur, o.id)}>{o.label}</button>
                  ))}
                  <span className="tiny muted" style={{ marginLeft: "auto" }}>
                    Prepared by {AGENT_LABEL[cur.requested_by] ?? cur.requested_by} · {fmtClock(cur.created)} · <span className="kbd">A</span> approve <span className="kbd">↓</span> next
                  </span>
                </div>
              )}
            </>
          );
        })()}
      </div>
    </div>
  );
}
