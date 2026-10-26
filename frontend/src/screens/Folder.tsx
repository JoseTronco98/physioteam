import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { ClinicalDoc, DocDiff, Doctor, Patient, PatientFolder } from "../types";
import { ApprovalCard, AttachmentView, Card, Md } from "../components/common";
import { useGuide } from "../components/guide";
import { AGENT_LABEL, cx, fmtClock, fmtDay, fmtTime, money, SERVICE_LABEL, SOURCE_LABEL } from "../util";

const SOURCE_TONE: Record<string, string> = { intake_chat: "", session_notes: "pk", imaging: "warn", therapist: "ok", agent_proposal: "blue", empty: "bad" };
const STATUS_TONE: Record<string, string> = { active: "ok", inquiry: "pk", discharged: "", at_risk: "warn" };

const OUT_ORDER = ["measure", "metric", "test", "baseline", "previous", "latest", "current", "now", "change", "goal"];

function OutcomeTable({ rows }: { rows: Record<string, unknown>[] }) {
  const keys = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  keys.sort((a, b) => {
    const ia = OUT_ORDER.indexOf(a.toLowerCase()); const ib = OUT_ORDER.indexOf(b.toLowerCase());
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  const label = (k: string) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
  const show = (v: unknown) => (v === null || v === undefined || v === "" ? "n/m" : String(v));
  return (
    <table>
      <thead><tr>{keys.map((k) => <th key={k}>{label(k)}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i}>{keys.map((k) => {
          const v = show(r[k]);
          const up = /change|delta/i.test(k) && /^\+|improv|better/i.test(v);
          return <td key={k} className={up ? "up" : undefined}>{v}</td>;
        })}</tr>
      ))}</tbody>
    </table>
  );
}

function DocView({ doc, rate, patient, doctor }: { doc: ClinicalDoc; rate: number; patient?: Patient; doctor?: Doctor }) {
  const { approvals } = useStore();
  const [version, setVersion] = useState(doc.version);
  const [shown, setShown] = useState<ClinicalDoc>(doc);
  const [diff, setDiff] = useState<DocDiff | null>(null);
  const { run } = useStore();
  void rate;
  useEffect(() => { setVersion(doc.version); setShown(doc); setDiff(null); }, [doc]);
  useEffect(() => {
    if (version === doc.version) { setShown(doc); return; }
    void run(api.document(doc.id, version)).then((d) => d && setShown(d));
  }, [version, doc, run]);
  useEffect(() => {
    if (doc.versions.length > 1) void run(api.diff(doc.id, doc.version - 1, doc.version)).then((d) => d && setDiff(d));
  }, [doc, run]);
  // Approvals have no doc_id in the contract, so match on the document title (or plan changes on the plan).
  const base = doc.title.toLowerCase().split(" (")[0];
  const appr = approvals.filter((a) => a.patient_id === doc.patient_id && a.status === "pending"
    && ((a.kind === "plan_change" && doc.kind === "treatment_plan") || (a.kind === "sign_document" && a.title.toLowerCase().includes(base))));
  const { state, decide } = useStore();
  const { on: guideOn } = useGuide();
  const ver = shown.versions.find((v) => v.version === shown.version);
  const author = ver ? (AGENT_LABEL[ver.author as keyof typeof AGENT_LABEL] ?? "Therapist") : "";
  const signAppr = appr.find((a) => a.kind === "sign_document" || a.kind === "plan_change");
  const sendAppr = approvals.find((a) => a.patient_id === doc.patient_id && a.status === "pending" && a.kind === "outbound_message"
    && (a.doc_id === doc.id || (doc.kind === "progress_report" && /progress report/i.test(a.title))));
  const outcomes = Array.isArray(shown.data?.outcomes) ? (shown.data!.outcomes as Record<string, unknown>[]) : null;
  const clinic = state?.clinic;
  return (
    <>
      <div className="doc-actions" style={{ marginBottom: 10 }}>
        {doc.versions.length > 1 && (
          <div className="seg">
            {doc.versions.map((v) => (
              <button key={v.version} className={cx(v.version === version && "on")} onClick={() => setVersion(v.version)} title={v.reason ?? ""}>v{v.version}</button>
            ))}
          </div>
        )}
        <span className="spacer" />
        {signAppr && <button className="btn solid" onClick={() => void decide(signAppr.id, (signAppr.options.find((o) => o.primary) ?? signAppr.options[0]).id)}>
          {signAppr.kind === "plan_change" ? "Approve" : "Sign"}</button>}
        <button className="btn ghost" disabled title="Editing arrives in the next version">Edit</button>
        <a className={cx("btn", signAppr ? "ghost" : "solid")} href={api.exportUrl(doc.id, "pdf")} target="_blank" rel="noreferrer">Export PDF</a>
        <a className="btn ghost" href={api.exportUrl(doc.id, "docx")} target="_blank" rel="noreferrer">Export Word</a>
        {doc.kind === "progress_report" && sendAppr && <button className="btn ghost" onClick={() => void decide(sendAppr.id, (sendAppr.options.find((o) => o.primary) ?? sendAppr.options[0]).id)}>Send to doctor</button>}
      </div>

      <div className="paper">
        <div className="letter">
          <div><div className="clinic">{clinic?.name ?? "Clinic"}</div><div className="tiny muted">{clinic?.therapist} · {clinic?.address?.split(".")[0]}</div></div>
          <div className="meta">{shown.title}<br />{fmtDay(ver?.created)}<br />
            <span className={cx("stamp", shown.status === "signed" ? "signed" : "draft")}>v{shown.version} · {shown.status}</span></div>
        </div>
        <div className="who">
          <div><span>Patient</span><b>{patient?.name ?? "—"}{patient ? `, ${patient.age}` : ""}</b></div>
          <div><span>Diagnosis</span><b>{patient?.condition ?? "—"}</b></div>
          {doctor && <div><span>{doc.kind === "progress_report" ? "For" : "Referred by"}</span><b>{doctor.name}</b></div>}
        </div>
        {shown.fields.length > 0 && (
          <>
            <h4 className="sec">{shown.kind === "soap" ? "Session note" : shown.kind === "treatment_plan" ? "Plan" : "Assessment"}</h4>
            <div className="form">
              {shown.fields.map((f) => (
                <div key={f.key} style={{ display: "contents" }}>
                  <div className="fk">{f.label}</div>
                  <div>
                    <span className={cx(!f.value && "empty-v")}>{f.value ?? "Not stated"}</span>
                    {guideOn || f.source === "empty"
                      ? <span className={cx("tag src", SOURCE_TONE[f.source])}>{SOURCE_LABEL[f.source] ?? f.source}</span> : null}
                    {f.needs_review && f.source !== "empty" && <span className="tag warn src">review</span>}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
        {outcomes && outcomes.length > 0 && (
          <>
            <h4 className="sec">Objective changes</h4>
            <div className="md"><OutcomeTable rows={outcomes} /></div>
          </>
        )}
        {shown.body_md && <Md>{shown.body_md}</Md>}
        <div className="sig"><div>{clinic?.therapist ?? "Therapist"}</div><div>Date</div></div>
        <div className="tiny muted" style={{ marginTop: 10 }}>Prepared by {author} · {fmtClock(ver?.created)}{ver?.reason ? ` · ${ver.reason}` : ""}</div>
      </div>
      {guideOn && (
        <div className="glass doc-guide">
          <span className="glabel">Demo guide</span>
          <b style={{ display: "block", marginTop: 4 }}>Why you can trust this document.</b>
          <p>Built only from {patient?.name.split(" ")[0] ?? "the patient"}'s folder: the intake chat, signed notes, studies and plan versions. Every value shows where it came from. Missing values stay empty, never guessed. Nothing leaves the clinic until you sign or approve it.</p>
        </div>
      )}
      {appr.filter((a) => a !== signAppr).map((a) => <ApprovalCard key={a.id} a={a} />)}
      {diff && (
        <Card title={`What changed: v${diff.from} → v${diff.to}`}>
          <div className="diff">
            {diff.changes.map((c) => (
              <div key={c.label} className="diffrow">
                <b>{c.label}:</b> {c.before && <del>{c.before}</del>} {c.before && c.after && "→ "}{c.after && <ins>{c.after}</ins>}
              </div>
            ))}
          </div>
          <div className="why"><b>Why it changed</b><div className="muted">{diff.reason}</div></div>
        </Card>
      )}
    </>
  );
}

const GROUP_LABEL: Record<string, string> = {
  evaluation: "Evaluation (first visit)", treatment_plan: "Treatment plan", soap: "Session notes (SOAP)",
  progress_report: "Progress reports", discharge_summary: "Discharge", home_program: "Home program",
  imaging_summary: "Studies", feedback: "Patient feedback",
};

export function Folder() {
  const { run, state, docVersion, focusPatient, setFocusPatient } = useStore();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [pid, setPid] = useState<string | null>(null);
  const [folder, setFolder] = useState<PatientFolder | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const rate = state?.clinic.usd_rate ?? 18.5;

  useEffect(() => {
    void run(api.patients()).then((p) => {
      if (!p) return;
      setPatients(p);
      if (focusPatient && p.some((x) => x.id === focusPatient)) { setPid(focusPatient); setFocusPatient(null); }
      else if (!pid && p.length) setPid(p[0].id);
    });
    void run(api.doctors()).then((d) => d && setDoctors(d));
  }, [run, docVersion]); // eslint-disable-line
  // A folder asked for from elsewhere (agenda, a story step, a deep link) wins, even after the list has loaded.
  useEffect(() => {
    if (focusPatient && patients.some((x) => x.id === focusPatient)) { setPid(focusPatient); setFocusPatient(null); }
  }, [focusPatient, patients]); // eslint-disable-line
  useEffect(() => {
    if (!pid) return;
    void run(api.folder(pid)).then((f) => {
      if (!f) return;
      setFolder(f);
      setDocId((cur) => (cur && f.documents.some((d) => d.id === cur) ? cur : f.documents[0]?.id ?? null));
    });
  }, [pid, run, docVersion]);

  const doc = folder?.documents.find((d) => d.id === docId) ?? null;
  const doctor = doctors.find((d) => d.id === folder?.patient.referring_doctor_id);
  const balance = folder?.patient.balance_mxn ?? 0;

  return (
    <div className="screen">
      <div className="folder-layout">
        <div className="col">
          <Card title="Patients" sub={`${patients.length}`}>
            <div className="plist">
              {patients.map((p) => (
                <div key={p.id} className={cx("p", p.id === pid && "on")} onClick={() => setPid(p.id)}>
                  <div className="row" style={{ justifyContent: "space-between", gap: 4 }}>
                    <b className={p.id === pid ? "pk" : ""}>{p.name}</b>
                    <span className={cx("tag", STATUS_TONE[p.status])}>{p.status.replace("_", " ")}</span>
                  </div>
                  <div className="tiny muted">{p.condition}{p.plan_total ? ` · ${p.sessions_done}/${p.plan_total}` : ""}</div>
                </div>
              ))}
            </div>
          </Card>
          <Card title="Referring doctors">
            <table><tbody>{doctors.map((d) => <tr key={d.id}><td>{d.name}<div className="tiny muted">{d.specialty}</div></td><td className="small">{d.referrals_this_month} this month</td></tr>)}</tbody></table>
          </Card>
        </div>

        <div className="col">
          {folder && (
            <Card title={folder.patient.name} sub={`${folder.patient.age} y · ${folder.patient.condition}`}>
              <div className="row small" style={{ gap: 6 }}>
                {doctor && <span className="tag blue">Referred by {doctor.name}</span>}
                {folder.patient.household_id && <span className="tag">household</span>}
                {folder.patient.flags.map((f) => <span key={f} className={cx("tag", f === "red_flag" ? "bad" : f === "owes" ? "warn" : "")}>{f.replace("_", " ")}</span>)}
                <span className={cx("tag", balance > 0 ? "warn" : "ok")}>balance {money(balance, rate)}</span>
              </div>
              <div className="section-title" style={{ marginTop: 10 }}>Folder</div>
              <div className="doclist">
                {folder.documents.length === 0 && <div className="empty">No documents yet. They appear as the agents work.</div>}
                {folder.documents.map((d, i) => (
                  <div key={d.id} style={{ display: "contents" }}>
                  {(i === 0 || folder.documents[i - 1].kind !== d.kind) && (
                    <div className="tiny dim" style={{ margin: "8px 2px 2px", textTransform: "uppercase", letterSpacing: ".04em" }}>
                      {GROUP_LABEL[d.kind] ?? d.kind.replace("_", " ")}
                      {d.kind === "soap" ? ` · ${folder.documents.filter((x) => x.kind === "soap").length} sessions` : ""}
                    </div>
                  )}
                  <div className={cx("d", d.id === docId && "on")} onClick={() => setDocId(d.id)}>
                    <span>{d.filename ?? d.title}</span>
                    <span className="row" style={{ gap: 4 }}>
                      {d.versions.length > 1 && <span className="tag pk">v{d.version}</span>}
                      <span className={cx("tag", d.status === "signed" ? "ok" : "warn")}>{d.status}</span>
                    </span>
                  </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
          {doc && <DocView doc={doc} rate={rate} patient={folder?.patient} doctor={doctor} />}
        </div>

        <div className="col rightcol">
          {folder && (
            <>
              <Card title="Appointments">
                {folder.appointments.length === 0 && <div className="empty">None scheduled.</div>}
                <table><tbody>{folder.appointments.map((a) => (
                  <tr key={a.id}><td>{fmtDay(a.start)} {fmtTime(a.start)}</td><td>{SERVICE_LABEL[a.service]}</td><td><span className="tag">{a.status.replace("_", " ")}</span></td></tr>
                ))}</tbody></table>
              </Card>
              <Card title="Ledger" sub="MXN with USD">
                {folder.ledger.length === 0 && <div className="empty">No charges yet.</div>}
                <table><tbody>{folder.ledger.map((l) => (
                  <tr key={l.id}>
                    <td className="small">{fmtDay(l.time)}</td>
                    <td className="small">{l.note}{l.method ? <span className="tiny muted"> · {l.method}</span> : null}</td>
                    <td className={cx("small", l.kind === "payment" ? "ok" : l.kind === "waiver" ? "warn" : "")} style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      {l.kind === "charge" ? "" : "−"}{money(l.amount_mxn, rate)}
                    </td>
                  </tr>
                ))}</tbody></table>
                <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }}><b>Balance due</b><b className={balance > 0 ? "warn" : "ok"}>{money(balance, rate)}</b></div>
              </Card>
              <Card title="Studies and files">
                {folder.attachments.filter(Boolean).length === 0 && <div className="empty">No files yet.</div>}
                {folder.attachments.filter(Boolean).map((a) => <div key={a!.id}><AttachmentView a={a!} /></div>)}
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
