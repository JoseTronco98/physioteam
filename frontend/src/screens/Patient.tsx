import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Attachment, Lang, Mission, Persona } from "../types";
import { Md, FilePicker } from "../components/common";
import { MissionsPanel } from "./Therapist";
import { BehindTheScenes } from "../components/behind";
import { ClinicImpact } from "../components/impact";
import { GuideSide, useGuide } from "../components/guide";
import { cx, fmtTime } from "../util";

function Phone({ thread, lang, prefill }: { thread: string; lang: Lang; prefill: { text: string; n: number } }) {
  const { threads, pending, send, state } = useStore();
  const [text, setText] = useState("");
  const [att, setAtt] = useState<Attachment | null>(null);
  const [pick, setPick] = useState(false);
  const list = threads[thread] ?? [];
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (prefill.text) setText(prefill.text); }, [prefill]);
  useEffect(() => { ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" }); }, [list.length, pending.has(thread)]);
  const submit = async () => {
    if (!text.trim() && !att) return;
    const t = text.trim(); setText(""); const a = att; setAtt(null);
    await send(thread, t || (lang === "es" ? "Le envío el archivo" : "Sending the file"), a?.id, lang);
  };
  return (
    <div className="phone">
      <div className="ptop">
        <div className="avatar">MF</div>
        <div style={{ lineHeight: 1.25 }}>
          <b>{state?.clinic.name ?? "Clinic"}</b>
          <div className="tiny" style={{ color: "#6E6E73" }}>{lang === "es" ? "Cuenta de empresa" : "Business account"}</div>
        </div>
      </div>
      <div className="wa-scroll" ref={ref}>
        <div className="wa sys">{lang === "es" ? "Los mensajes los responde el asistente de IA de la clínica. Lo clínico lo revisa la terapeuta." : "Messages are answered by the clinic's AI assistant. Anything clinical goes to the therapist."}</div>
        {list.map((m) => {
          if (m.role === "system") return <div key={m.id} className="wa sys"><Md>{m.text}</Md></div>;
          const out = m.role === "patient";
          return (
            <div key={m.id} className={cx("wa", out ? "out" : "in", m.blocked && "blocked")}>
              <Md>{m.text}</Md>
              {m.attachment && (m.attachment.kind === "image"
                ? <img src={api.fileUrl(m.attachment)} alt={m.attachment.name} />
                : <a href={api.fileUrl(m.attachment)} target="_blank" rel="noreferrer">📎 {m.attachment.name}</a>)}
              <div className="wt">{fmtTime(m.time)}{out ? " ✓✓" : ""}</div>
            </div>
          );
        })}
        {pending.has(thread) && <div className="wa in" style={{ color: "#6E6E73" }}>{lang === "es" ? "escribiendo…" : "typing…"}</div>}
      </div>
      {att && <div className="tiny" style={{ color: "#6E6E73", padding: "4px 8px" }}>📎 {att.name} <button className="btn sm ghost" onClick={() => setAtt(null)}>remove</button></div>}
      <div className="wa-compose" style={{ position: "relative" }}>
        <button className="round ghost" title="Attach" onClick={() => setPick((p) => !p)}>📎</button>
        <input value={text} placeholder={lang === "es" ? "Escribe un mensaje" : "Type a message"} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") void submit(); }} />
        <button className="round" onClick={() => void submit()} disabled={pending.has(thread)} title="Send">➤</button>
        {pick && <FilePicker onPick={setAtt} onClose={() => setPick(false)} />}
      </div>
    </div>
  );
}

function personaName(p: Persona): string {
  const m = p.blurb.match(/^([A-Z][a-zá-úñ]+)/);
  return m ? m[1] : p.title;
}

export function Patient() {
  const { run, loadThread, setState, toast } = useStore();
  const { on: guideOn } = useGuide();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [sel, setSel] = useState<Persona | null>(null);
  const [thread, setThread] = useState<string | null>(null);
  const [lang, setLang] = useState<Lang>("en");
  const [prefill, setPrefill] = useState({ text: "", n: 0 });

  useEffect(() => { void run(api.personas()).then((p) => p && setPersonas(p)); }, [run]);

  const start = async (p: Persona, l: Lang = lang) => {
    setSel(p);
    const r = await run(api.startPersona(p.id, l));
    if (r) { setThread(r.thread); await loadThread(r.thread); }
  };
  useEffect(() => { if (!sel && personas.length) void start(personas[0]); }, [personas]); // eslint-disable-line

  const onTry = (m: Mission) => {
    if (!m.try_prompt) return;
    setPrefill((p) => ({ text: m.try_prompt ?? "", n: p.n + 1 }));
  };

  const phone = sel && thread ? <Phone thread={thread} lang={lang} prefill={prefill} /> : <div className="card empty">Opening WhatsApp…</div>;
  if (!guideOn) return <div className="stage solo phone-solo">{phone}</div>;

  return (
    <div className="stage">
      <GuideSide side="left" label="Personas" minWidth={1180} width={290}>
        <h3 className="gh">Pick your story.</h3>
        {personas.map((p) => (
          <div key={p.id} className={cx("persona", sel?.id === p.id && "on")} onClick={() => void start(p)}>
            <div className="pt">{p.title}</div>
            <div className="small muted">{p.blurb}</div>
            <div className="tiny dim">{p.starts_as}</div>
          </div>
        ))}
        <div className="gcontrols">
          <div className="seg gseg">
            <button className={cx(lang === "en" && "on")} onClick={() => { setLang("en"); if (sel) void start(sel, "en"); }}>English</button>
            <button className={cx(lang === "es" && "on")} onClick={() => { setLang("es"); if (sel) void start(sel, "es"); }}>Español</button>
          </div>
          <button className="gbtn" disabled={!sel} title="Jump to 10:00 the day before your next session: the reminder arrives"
            onClick={async () => { if (sel) { const s = await run(api.dayBefore(sel.id)); if (s) setState(s); } }}>Jump to day before</button>
          <button className="gbtn" disabled={!sel} title="Simulate the therapy session: the therapist bot writes notes and the agents produce documents and your follow-up"
            onClick={async () => { if (sel) { const r = await run(api.sessionHappens(sel.id)); if (r) toast("Session simulated: watch the follow-up arrive"); } }}>Session happens</button>
        </div>
        {sel && <MissionsPanel missions={sel.missions} onTry={onTry} title="Things to try" />}
        <p className="gsub">Try it puts the words in the phone for you. Edit them, or just press Enter. Attach demo files with 📎. A bot plays the therapist here.</p>
      </GuideSide>
      <div className="phone-stage">
        {phone}
        {guideOn && <div className="tiny dim" style={{ textAlign: "center", marginTop: 10 }}>This is the real product: exactly what a patient sees on WhatsApp.</div>}
      </div>
      <GuideSide side="right" label="Clinic impact" minWidth={1320} width={340}>
        {sel ? <ClinicImpact patientId={sel.patient_id} name={personaName(sel)} /> : <div className="empty">Pick a story to begin.</div>}
        <details className="moredetails">
          <summary>Every step, behind the scenes</summary>
          <BehindTheScenes maxHeight={360} note="A bot plays the therapist here. Its cost is counted separately from the clinic's agents." />
        </details>
      </GuideSide>
    </div>
  );
}
