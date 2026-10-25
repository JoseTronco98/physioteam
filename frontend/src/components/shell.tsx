import { useState } from "react";
import { api, isMock, setAccessCode } from "../api";
import { useStore } from "../store";
import { cx, usd } from "../util";
import { Clock } from "./common";
import { GuideLabel, GuideSwitch } from "./guide";

export type Mode = "start" | "how" | "deploy" | "therapist" | "patient" | "autopilot";
export const SIM_MODES: Mode[] = ["therapist", "patient", "autopilot"];

export const MODES: { id: Mode; label: string }[] = [
  { id: "patient", label: "Patient" },
  { id: "therapist", label: "Therapist" },
  { id: "autopilot", label: "Autopilot" },
];

/** Slim frosted top bar. Everything in it only exists to test the app. */
export function GuideBar({ mode, setMode, onTour }: { mode: Mode; setMode: (m: Mode) => void; onTour: () => void }) {
  const { state, setState, run, toast, refresh } = useStore();
  const [busy, setBusy] = useState(false);
  const s = state;
  const sim = SIM_MODES.includes(mode);
  const act = async (p: Promise<typeof state>, msg?: string) => {
    setBusy(true);
    const r = await run(p);
    if (r) { setState(r); if (msg) toast(msg); }
    setBusy(false);
  };
  const sp = s?.spend;
  const near = sp ? sp.session_usd / Math.max(sp.session_cap_usd, 1e-9) > 0.8 : false;
  return (
    <header className="gbar g">
      <span className="logo" onClick={() => setMode("start")}>Physio<b>Team</b></span>
      <button className="home" onClick={() => setMode("start")}>Home</button>
      <span className="sep" />
      <div className="gmodes">
        {MODES.map((m) => <button key={m.id} className={cx(mode === m.id && "on")} onClick={() => setMode(m.id)}>{m.label}</button>)}
      </div>
      {sim && (
        <>
          <Clock />
          <button className="gbtn" disabled={busy || !s} onClick={() => act(api.advance(60), "An hour later.")} title="Move the simulated clock one hour">+1 hour</button>
          <button className="gbtn" disabled={busy || !s} onClick={() => act(api.nextEvent())} title="Jump to the next thing that happens in the clinic week">Next event</button>
          <button className="gbtn" disabled={busy || !s} onClick={() => act(api.endOfDay(), "Day done. Your report is ready.")} title="Jump to the end of the clinic day">End of day</button>
          <button className={cx("gbtn", s?.autoplay && "solid")} disabled={!s} onClick={() => act(api.autoplay(!s?.autoplay))} title="Let the clock run on its own">
            {s?.autoplay ? "❚❚ Pause" : "▶ Autoplay"}
          </button>
        </>
      )}
      <span className="spacer" />
      {sp && sim && (
        <span className={cx("gtxt", near && "warn")} title={`All visitors today: ${usd(sp.global_usd_today, 2)} of ${usd(sp.global_cap_usd, 2)}`}>
          Budget <b>{usd(sp.session_usd)}</b> / {usd(sp.session_cap_usd, 2)}
        </span>
      )}
      <button className="gbtn" onClick={onTour}>Tour</button>
      {sim && <button className="gbtn" disabled={busy} onClick={async () => {
        if (!window.confirm("Start the demo week over from Monday morning? Your chats and changes in this sandbox are cleared.")) return;
        await act(api.reset(), "Fresh start. It's Monday morning."); await refresh();
      }}>Reset</button>}
      <GuideSwitch />
    </header>
  );
}

export function AlertBar() {
  const { alerts, dismissAlert } = useStore();
  const a = alerts[0];
  if (!a) return null;
  return (
    <div className={cx("alertbar", a.level === "info" && "info")}>
      <b>{a.level === "red_flag" ? "⚠ Red flag" : "ℹ"}</b>
      <span style={{ flex: 1 }}>{a.text}</span>
      {alerts.length > 1 && <span className="tiny muted">+{alerts.length - 1} more</span>}
      <button className="btn sm ghost" onClick={() => dismissAlert(a.id)}>Dismiss</button>
    </div>
  );
}

export function Toasts() {
  const { toasts } = useStore();
  return <div className="toasts">{toasts.map((t) => <div key={t.id} className={cx("toast", t.tone)}>{t.text}</div>)}</div>;
}

export function MockBanner() {
  if (!isMock()) return null;
  return <div className="mockbanner">Demo mode: the backend isn't connected, so you're seeing sample data and scripted agent replies.</div>;
}

const TOUR = [
  { t: "Welcome to PhysioTeam.", b: "A small team of AI agents that runs the back office of a solo physical therapy clinic. Everything here is a fictional clinic week, so try anything. Your sandbox is yours alone." },
  { t: "Glass is the guide. White is the product.", b: "Frosted glass panels, like this one, only exist to help you explore. The white window and the iPhone are the real product a clinic would use. Turn off Show guide to see just the product." },
  { t: "Two seats.", b: "Be the patient on WhatsApp and watch the clinic react. Or run the clinic as the therapist, with your Operations Partner and Health Advisor. Bots play the other side." },
  { t: "The clock runs the week.", b: "Use +1 hour, Next event or End of day. Patients and doctors write in, reminders go out, sessions happen. Anything important waits for the therapist's approval." },
  { t: "Every cent, in plain sight.", b: "Behind the scenes and the team room show each agent at work and what it costs. Costs and safety lets you attack the agents and watch the defences hold." },
];

export function Tour({ onClose }: { onClose: () => void }) {
  const [i, setI] = useState(0);
  const { run } = useStore();
  const done = async () => { await run(api.tourDone()); onClose(); };
  const step = TOUR[i];
  return (
    <div className="overlay" onClick={done}>
      <div className="modal gmodal" onClick={(e) => e.stopPropagation()}>
        <div className="row" style={{ marginBottom: 6 }}><GuideLabel /><span className="tiny" style={{ opacity: .85 }}>Step {i + 1} of {TOUR.length}</span></div>
        <h2>{step.t}</h2>
        <p style={{ fontSize: 15, opacity: .92 }}>{step.b}</p>
        <div className="stepdots">{TOUR.map((_, k) => <i key={k} className={cx(k <= i && "on")} />)}</div>
        <div className="row">
          <button className="gbtn" onClick={done}>Skip</button>
          <span className="spacer" />
          {i > 0 && <button className="gbtn" onClick={() => setI(i - 1)}>Back</button>}
          {i < TOUR.length - 1 ? <button className="gbtn solid" onClick={() => setI(i + 1)}>Next</button> : <button className="gbtn solid" onClick={done}>Let's go</button>}
        </div>
      </div>
    </div>
  );
}

export const ASK: Record<"ops" | "health", { title: string; intro: string; groups: { g: string; qs: string[] }[] }> = {
  ops: {
    title: "Ask the Operations Partner",
    intro: "Runs the agenda, policies, money and the daily ops report. Manages Patient Success (WhatsApp) and Finance Ops.",
    groups: [
      { g: "Agenda", qs: ["What's my day?", "I'm running 40 minutes late, move my 17:00 and tell the patient.", "Block Thursday, it's a holiday. Tell affected patients.", "Fill tomorrow's cancelled 16:00 from the waitlist.", "Book Don Arturo and Carmen back to back on Wednesday."] },
      { g: "Money", qs: ["Who owes me money?", "How much did I make this week, and how full was my agenda?", "How much revenue did late cancellations cost me this month?", "What if Redcord goes from 600 to 650?", "Send pending invoice requests to the accountant."] },
      { g: "Patients", qs: ["Who is at risk of dropping out?", "Send Marta a friendly check-in with two slot options.", "What did patients say in this week's satisfaction surveys?"] },
    ],
  },
  health: {
    title: "Ask the Health Advisor",
    intro: "Owns evaluations, treatment plans, progress and doctor relations. Manages the Clinical Scribe and the Imaging Reader.",
    groups: [
      { g: "During the session", qs: ["Show Lucía's pre-filled evaluation. What's still missing?", "Notes for Sam: anterior knee pain 3/10 on stairs, step-down now negative, quad 4+/5. Update the plan.", "Read the X-ray report I attached for Lucía."] },
      { g: "Plans and progress", qs: ["Update Sam's plan: he improved, add hip strength and walk-run intervals.", "Write Don Arturo's home program and send it to his daughter.", "Draft Rosa's discharge summary and the survey message."] },
      { g: "Doctors", qs: ["Dr. Ortiz asks how Daniel is doing. Draft a progress report.", "Which doctor sent me the most patients this month?", "Draft a thank-you note to Dr. Ortiz with an update on his patients."] },
    ],
  },
};

export function AskDrawer({ which, onPick, onClose }: { which: "ops" | "health"; onPick: (q: string) => void; onClose: () => void }) {
  const d = ASK[which];
  return (
    <>
      <div className="overlay" style={{ background: "rgba(0,0,0,.35)", zIndex: 54 }} onClick={onClose} />
      <aside className="drawer">
        <div className="row"><h2 style={{ margin: 0, fontSize: 20 }}>{d.title}</h2><span className="spacer" /><button className="btn sm ghost" onClick={onClose}>Close</button></div>
        <p className="muted small">{d.intro} Click a question to put it in the chat box.</p>
        {d.groups.map((g) => (
          <div key={g.g}>
            <div className="section-title">{g.g}</div>
            {g.qs.map((q) => <button key={q} className="q" onClick={() => { onPick(q); onClose(); }}>{q}</button>)}
          </div>
        ))}
      </aside>
    </>
  );
}

export function AccessScreen() {
  const { codeAccepted } = useStore();
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  return (
    <div className="access gcard g">
      <GuideLabel />
      <h2>Physio<b>Team</b> demo</h2>
      <p className="gsub">This demo is protected so its AI budget stays put. Enter the access code from the README or the report.</p>
      <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Access code" onKeyDown={(e) => e.key === "Enter" && (e.currentTarget.nextElementSibling as HTMLButtonElement)?.click()} />
      <button className="gbtn solid" onClick={async () => {
        setAccessCode(code);
        try { await api.state(); codeAccepted(); } catch { setErr("That code didn't work. Check the README."); }
      }}>Enter</button>
      {err && <p className="small bad">{err}</p>}
    </div>
  );
}
