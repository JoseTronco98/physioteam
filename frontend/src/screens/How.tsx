import type { Mode } from "../components/shell";

export function How({ go }: { go: (m: Mode) => void }) {
  return (
    <div className="screen gpage">
      <div className="cp-hero">
        <span className="glabel">Demo guide · how it works</span>
        <h1>One therapist.<br />A whole back office.</h1>
        <p>A solo physical therapist spends hours a week on WhatsApp, the agenda, paperwork and payments. PhysioTeam hands that work to a small team of AI agents, and keeps the therapist in charge.</p>
      </div>

      <h2 className="cp-section">Meet the team.</h2>
      <p className="cp-sub">Two leads you talk to. Four specialists who do the detail work.</p>
      <div className="glass gpanel">
        <div className="orgmini">
          <div className="lead"><b>🗂️ Operations Partner</b><span className="small muted">Your chief of staff. Agenda, policies, money and the daily ops report.</span>
            <div className="subs2"><span>💬 Patient Success: talks to patients on WhatsApp</span><span>💰 Finance Ops: balances and invoices</span></div></div>
          <div className="lead"><b>🩺 Health Advisor</b><span className="small muted">Your clinical co-pilot. Evaluations, plans, progress reports and doctors.</span>
            <div className="subs2"><span>📝 Clinical Scribe: forms and SOAP notes</span><span>🔬 Imaging Reader: reads studies</span></div></div>
        </div>
        <p className="small muted" style={{ margin: "12px 0 0" }}>A router picks the right lead in your team chat. A safety layer, written in code, checks every message before any agent sees it.</p>
      </div>

      <div className="cp-grid">
        <div className="glass cp-card">
          <span className="glabel">Approvals</span>
          <h3>You approve what matters.</h3>
          <p>Bookings, late-cancellation charges, signatures and anything that leaves the clinic wait for one tap. Approving runs the action in code, so an agent can never approve itself.</p>
        </div>
        <div className="glass cp-card">
          <span className="glabel">Safety</span>
          <h3>Safe by design.</h3>
          <ul>
            <li>Red flags like a swollen calf or new numbness go straight to you.</li>
            <li>"Ignore your rules" and hidden text in PDFs are blocked before any agent reads them.</li>
            <li>No medication advice. No invented values: empty beats guessed.</li>
            <li>Spending caps per visitor and per day.</li>
          </ul>
        </div>
      </div>

      <h2 className="cp-section">Real, or simulated?</h2>
      <p className="cp-sub">So you know exactly what you're looking at.</p>
      <div className="glass gpanel">
        <div className="realsim">
          <div><h4>Real</h4><p className="small muted" style={{ margin: 0 }}>The agents and their tools. The clinic records, documents and agenda. The approvals. Every token and every cent, measured live on gpt-6-luna.</p></div>
          <div><h4>Simulated</h4><p className="small muted" style={{ margin: 0 }}>The patients and doctors (you, or bots). WhatsApp itself. The clock, so a whole week fits in a few minutes.</p></div>
        </div>
      </div>

      <div className="cp-cta">
        <button className="gbtn solid lg" onClick={() => go("patient")}>Be the patient</button>
        <button className="gbtn lg" onClick={() => go("therapist")}>Run the clinic</button>
      </div>
    </div>
  );
}
