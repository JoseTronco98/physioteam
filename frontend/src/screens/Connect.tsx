import { useEffect, useState } from "react";
import { api, isMock } from "../api";
import { useStore } from "../store";
import type { Integration } from "../types";
import { Card } from "../components/common";
import { cx, money } from "../util";

const WA_TEXT = "Production: the clinic's number connects through Meta's WhatsApp Business API; Patient Success answers there and every conversation appears in Clinic Messages.";

const STATUS: Record<Integration["status"], { label: string; tone: string }> = {
  works: { label: "works today", tone: "ok" }, roadmap: { label: "roadmap", tone: "" }, stretch: { label: "stretch goal", tone: "warn" },
};

export function Connect() {
  const { run, state } = useStore();
  const [items, setItems] = useState<Integration[]>([]);
  useEffect(() => {
    void run(api.integrations()).then((x) => {
      if (!x) return;
      // One WhatsApp card that states the production setup; drop the separate API/bridge duplicates.
      const wa = x.filter((i) => /whatsapp/i.test(i.id) || /whatsapp/i.test(i.name));
      const rest = x.filter((i) => !wa.includes(i));
      setItems([{ id: "whatsapp", name: "WhatsApp (Clinic Messages)", status: "roadmap", detail: WA_TEXT }, ...rest]);
    });
  }, [run]);
  const c = state?.clinic;
  return (
    <div className="screen">
      <h2 className="ptitle">Settings</h2>
      <p className="psub" style={{ marginBottom: 18 }}>Clinic setup and the tools PhysioTeam connects to: WhatsApp, your calendar, Word forms, your accountant.</p>
      <div className="cards3">
        {items.map((i) => (
          <div key={i.id} className="card">
            <h3>{i.name}</h3>
            {i.id === "whatsapp" ? <span className="tag warn">simulated in this demo</span> : <span className={cx("tag", STATUS[i.status].tone)}>{STATUS[i.status].label}</span>}
            <p className="small muted" style={{ marginBottom: 0 }}>{i.detail}</p>
            {i.id === "calendar" && <a className="btn sm" style={{ marginTop: 8 }} href={api.icsUrl()} onClick={(e) => { if (isMock()) { e.preventDefault(); alert("Connect the backend to download the .ics file."); } }}>Download agenda (.ics)</a>}
          </div>
        ))}
      </div>
      {c && (
        <Card title="Clinic setup" sub="15-minute wizard, pre-filled for the demo">
          <table><tbody>
            <tr><td style={{ width: 160 }} className="muted">Clinic</td><td>{c.name} · {c.therapist}</td></tr>
            <tr><td className="muted">Address</td><td>{c.address}</td></tr>
            <tr><td className="muted">Hours</td><td>{c.hours}</td></tr>
            <tr><td className="muted">Services</td><td>{c.services.map((s) => `${s.name} ${s.minutes} min ${money(s.price_mxn, c.usd_rate)}`).join(" · ")}</td></tr>
            <tr><td className="muted">Policies</td><td>{c.policies.join(" · ")}</td></tr>
            <tr><td className="muted">Approvals</td><td>Bookings: ask me · Charges: ask me · Outgoing messages: ask me · Clinical documents: draft only · FAQs: automatic · Red flags: always to me</td></tr>
          </tbody></table>
        </Card>
      )}
    </div>
  );
}
