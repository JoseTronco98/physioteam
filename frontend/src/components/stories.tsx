import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Story, StoriesPayload } from "../types";
import { cx } from "../util";

const ACTOR: Record<string, { icon: string; label: string }> = {
  patient: { icon: "💬", label: "Patient" },
  doctor: { icon: "🩺", label: "Doctor" },
  you: { icon: "👩‍⚕️", label: "You" },
  clinic: { icon: "⏱", label: "Time passes" },
};

/** Story mode: five short stories, one step per click. Patients' and doctors' lines are scripted;
 *  everything the clinic does in reply is live. */
export function StoriesPanel({ onGo }: { onGo: (go: string | null, thread: string | null) => void }) {
  const { run, toast, lastMessage, approvals, state } = useStore();
  const [data, setData] = useState<StoriesPayload | null>(null);
  const [open, setOpen] = useState<string | null>("booking");
  const [busy, setBusy] = useState<string | null>(null);
  const [showCov, setShowCov] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => void run(api.stories()).then((d) => d && setData(d)), 400);
    return () => window.clearTimeout(t);
  }, [run, lastMessage, approvals, state?.now]);

  const go = async (s: Story, stepId: string) => {
    setBusy(`${s.id}/${stepId}`);
    const r = await run(api.runStory(s.id, stepId));
    setBusy(null);
    if (!r) return;
    toast(r.note);
    onGo(r.go, r.thread);
  };

  if (!data) return <div className="card"><div className="empty">Loading stories…</div></div>;
  return (
    <div className="card stories">
      <h3>Five stories<small>everything it does</small></h3>
      <p className="tiny muted" style={{ marginTop: 0 }}>
        Each step is one click. Patients and doctors follow a script; everything the clinic does is live AI.
        Skip ahead any time: earlier steps play first.
      </p>
      {data.stories.map((s, si) => (
        <div key={s.id} className={cx("story", open === s.id && "on")}>
          <div className="sh" onClick={() => setOpen(open === s.id ? null : s.id)}>
            <span className="sn">{si + 1}</span>
            <div style={{ flex: 1 }}>
              <b>{s.title}</b>
              <div className="tiny muted">{s.who}</div>
            </div>
            <span className="tiny dim">{s.done}/{s.steps.length}</span>
          </div>
          <div className="progress" style={{ margin: "6px 0 2px" }}><i style={{ width: `${(s.done / s.steps.length) * 100}%` }} /></div>
          {open === s.id && (
            <>
              <p className="tiny" style={{ margin: "6px 0 8px" }}>{s.blurb}</p>
              {s.steps.map((st, i) => {
                const next = !st.done && s.steps.slice(0, i).every((x) => x.done);
                const label = st.done ? "Again" : st.decide ? "Decide for me" : next ? "Run" : "Play to here";
                return (
                  <div key={st.id} className={cx("sstep", st.done && "done", next && "next")}>
                    <span className="sa" title={ACTOR[st.actor]?.label}>{st.done ? "✓" : ACTOR[st.actor]?.icon}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="st">{st.title}</div>
                      <div className="tiny muted">{st.watch}</div>
                      {st.decide && !st.done && next && <div className="tiny" style={{ color: "#0066CC" }}>Your call: decide in Approvals, or let the demo do it.</div>}
                      {!st.done && (
                        <button className={cx("btn try", next && "solid")} disabled={!!busy || (state?.busy ?? false)}
                          onClick={() => void go(s, st.id)}>{busy === `${s.id}/${st.id}` ? "Working…" : label}</button>
                      )}
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </div>
      ))}
      <button className="btn ghost sm" style={{ marginTop: 10, width: "100%" }} onClick={() => setShowCov((v) => !v)}>
        {showCov ? "Hide the feature list" : `All ${data.coverage.length} features, and where to see them`}
      </button>
      {showCov && (
        <div className="coverage">
          {data.coverage.map((c) => (
            <div key={c.feature} className="cov" onClick={() => { setOpen(c.story); setShowCov(false); }}>
              <span>{c.feature}</span><span className="tiny dim">{c.story_title} · {c.step_title}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
