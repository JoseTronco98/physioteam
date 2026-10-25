import type { Mode } from "../components/shell";

const RISKS: [string, string][] = [
  ["Clinical advice", "Never. Agents draft, the therapist signs. Patients asking about symptoms or exercises are routed to the therapist."],
  ["Red flags", "Calf swelling, new numbness, bladder changes, chest pain: escalated by code to the therapist in seconds, never coached."],
  ["Prompt injection", "\"Ignore your rules\" in chat and invisible text inside PDFs are caught in code before any model reads them."],
  ["Privacy", "Health data is sensitive personal data under Mexico's data-protection law. Patients opt in to WhatsApp; this demo uses synthetic data only."],
  ["Errors and hallucination", "Empty beats guessed. Every form value shows its source: intake chat, session notes, a study, or the therapist."],
  ["Overspending", "A budget per visitor and a daily budget for everyone. When it's reached, the agents pause."],
  ["Over-automation", "Anything that touches money, the agenda or leaves the clinic waits for the therapist's approval."],
];

export function Deploy({ go }: { go: (m: Mode) => void }) {
  return (
    <div className="screen gpage">
      <div className="cp-hero">
        <span className="glabel">Demo guide · deployment and next steps</span>
        <h1>From demo<br />to clinic.</h1>
        <p>Everything that runs here can run for a real practice. Here's the path, the price and the guardrails.</p>
      </div>

      <h2 className="cp-section">Take it live on WhatsApp.</h2>
      <p className="cp-sub">One official connection. Then every conversation lives in one place.</p>
      <div className="cp-grid">
        <div className="glass cp-card">
          <span className="glabel">Go-live, step by step</span>
          <ol className="steps-num">
            <li><b>Verify the business</b> with Meta (WhatsApp Business Platform).</li>
            <li><b>Connect the clinic's number</b> to the Cloud API.</li>
            <li><b>Host the backend</b> with a public webhook, for example on Render.</li>
            <li><b>Approve message templates</b> for reminders and confirmations.</li>
            <li><b>Ask patients to opt in</b> and publish a privacy notice.</li>
            <li><b>Pilot on Meta's test number</b>, then roll out to the clinic.</li>
          </ol>
        </div>
        <div className="glass cp-card">
          <span className="glabel">What changes for the therapist</span>
          <h3>One inbox. Every chat.</h3>
          <p>With the API connected, Patient Success answers on WhatsApp in the clinic's name. Every conversation appears in Clinic Messages, where the therapist can read along and reply at any moment.</p>
          <p>Nothing else changes for patients. They keep writing to the same number they already know.</p>
        </div>
      </div>

      <h2 className="cp-section">What it costs.</h2>
      <p className="cp-sub">Measured, not estimated.</p>
      <div className="cp-grid three">
        <div className="glass cp-card"><div className="big">$0.013</div><p>AI cost of a full simulated clinic week with 15 active patients.</p></div>
        <div className="glass cp-card"><div className="big">~$0.06</div><p>AI cost per clinic per month.</p></div>
        <div className="glass cp-card"><div className="big">~$7</div><p>Hosting per month, plus Meta's per-message fees, which depend on the country and the message type.</p></div>
      </div>

      <h2 className="cp-section">Risks, handled.</h2>
      <p className="cp-sub">The things that could go wrong, and what's built to stop them.</p>
      <div className="glass gpanel">
        {RISKS.map(([k, v]) => <div key={k} className="risk"><b>{k}</b><span className="muted">{v}</span></div>)}
      </div>

      <h2 className="cp-section">What's next.</h2>
      <p className="cp-sub">The pipeline after the pilot.</p>
      <div className="cp-grid three">
        <div className="glass cp-card"><h3>Voice notes.</h3><p>Dictate after a session; the evaluation and SOAP note write themselves.</p></div>
        <div className="glass cp-card"><h3>Real calendar sync.</h3><p>Two-way with Google, Apple or Outlook calendars.</p></div>
        <div className="glass cp-card"><h3>E-invoicing.</h3><p>CFDI invoices through the clinic's accountant, without the back and forth.</p></div>
        <div className="glass cp-card"><h3>Your own templates.</h3><p>Upload the clinic's Word forms and keep using them.</p></div>
        <div className="glass cp-card"><h3>Outcome tracking.</h3><p>See which treatments work best, across every patient.</p></div>
        <div className="glass cp-card"><h3>Bigger clinics.</h3><p>Several therapists, shared agenda, one team of agents.</p></div>
      </div>

      <div className="cp-cta">
        <button className="gbtn solid lg" onClick={() => go("therapist")}>Run the clinic</button>
        <button className="gbtn lg" onClick={() => go("start")}>Back to home</button>
      </div>
    </div>
  );
}
