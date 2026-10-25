import type { Mode } from "../components/shell";

const TILES: { mode: Mode; icon: string; bg: string; title: string; text: string; points: string[]; go: string }[] = [
  { mode: "how", icon: "💡", bg: "#E8F2FF", title: "How it works.", text: "The problem, the team, and what's real in two minutes.",
    points: ["Two leads, four specialists", "You approve what matters", "Safe and on budget by design"], go: "Take a look" },
  { mode: "patient", icon: "💬", bg: "#E8F7EC", title: "Be the patient.", text: "Chat on WhatsApp. Watch the clinic move with every message.",
    points: ["Book, cancel late, report pain", "See the therapist's phone light up", "Five patient stories to try"], go: "Open the phone" },
  { mode: "therapist", icon: "🩺", bg: "#EFEEFF", title: "Run the clinic.", text: "A full week, simulated. Patients and doctors write in as the clock moves.",
    points: ["24 things to try, from agenda to money", "Approvals, reports, profitability", "See the team room at work"], go: "Open the clinic" },
  { mode: "deploy", icon: "🚀", bg: "#FFF4E5", title: "Take it live.", text: "What it takes to run this in a real clinic. And what it costs.",
    points: ["WhatsApp Business, step by step", "Risks, and how they're handled", "What comes next"], go: "Read more" },
];

export function Start({ go }: { go: (m: Mode) => void; onTour?: () => void }) {
  return (
    <div className="screen gpage hub">
      <span className="glabel">Demo guide</span>
      <h1>Your clinic's back office.<br />Handled.</h1>
      <p className="sub">PhysioTeam answers patients on WhatsApp, keeps your agenda, writes the paperwork and minds the money. You stay with your patients.</p>
      <div className="hub-tiles">
        {TILES.map((t) => (
          <div key={t.mode} className="glass hub-tile" onClick={() => go(t.mode)} role="button" tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && go(t.mode)}>
            <div className="ic" style={{ background: t.bg }}>{t.icon}</div>
            <h3>{t.title}</h3>
            <p>{t.text}</p>
            <ul>{t.points.map((p) => <li key={p}>{p}</li>)}</ul>
            <span className="go">{t.go} ›</span>
          </div>
        ))}
      </div>
      <div className="glass hub-strip">
        <div><b>$0.013</b>for a full simulated clinic week</div>
        <div><b>86%</b>of input tokens from cache</div>
        <div><b>2 of 2</b>attacks blocked</div>
        <div><b>1 of 1</b>red flag escalated</div>
        <div><b>0</b>interruptions for non-urgent questions</div>
      </div>
      <p className="hub-foot">Every patient, doctor and message here is fictional. Measured on gpt-6-luna over a simulated week with 15 active patients.</p>
    </div>
  );
}
