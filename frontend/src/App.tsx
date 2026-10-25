import { useEffect, useState } from "react";
import { api } from "./api";
import { StoreProvider, useStore } from "./store";
import { AccessScreen, GuideBar, MockBanner, Toasts, Tour } from "./components/shell";
import type { Mode } from "./components/shell";
import { SIM_MODES } from "./components/shell";
import { How } from "./screens/How";
import { Deploy } from "./screens/Deploy";
import { GuideContext, GuideFloat, useGuideState } from "./components/guide";
import { Start } from "./screens/Start";
import { SECTIONS, Therapist } from "./screens/Therapist";
import type { Section } from "./screens/Therapist";
import { Patient } from "./screens/Patient";
import { Autopilot } from "./screens/Autopilot";

const LEGACY: Record<string, [Mode, Section?]> = {
  folder: ["therapist", "folders"], report: ["therapist", "report"], costs: ["therapist", "costs"], connect: ["therapist", "settings"],
};

function readHash(): { mode: Mode; section: Section } {
  const [m, s] = window.location.hash.replace("#", "").split("/");
  if (LEGACY[m]) return { mode: LEGACY[m][0], section: LEGACY[m][1] ?? "chat" };
  const mode: Mode = (["start", "how", "deploy", "therapist", "patient", "autopilot"] as Mode[]).includes(m as Mode) ? (m as Mode) : "start";
  const section: Section = SECTIONS.some((x) => x.id === s) ? (s as Section) : "chat";
  return { mode, section };
}

function Shell() {
  const { state, needCode, run, setState } = useStore();
  const guide = useGuideState();
  const [{ mode, section }, setRoute] = useState(readHash());
  const [tour, setTour] = useState(false);
  const [tourShown, setTourShown] = useState(false);

  useEffect(() => {
    const on = () => setRoute(readHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  useEffect(() => {
    if (state && !state.tour_done && !tourShown && guide.on) { setTour(true); setTourShown(true); }
  }, [state, tourShown, guide.on]);

  const nav = (m: Mode, s: Section = section) => {
    window.location.hash = m === "therapist" ? `therapist/${s}` : m;
    setRoute({ mode: m, section: s });
  };
  const setMode = async (m: Mode) => {
    if (SIM_MODES.includes(m)) { const r = await run(api.setMode(m as "therapist" | "patient" | "autopilot")); if (r) setState(r); }
    nav(m, m === "therapist" ? section : section);
    window.scrollTo({ top: 0 });
  };

  // Without the guide, only the product exists: start/autopilot fall back to the therapist product.
  const shown: Mode = !guide.on && !["therapist", "patient"].includes(mode) ? "therapist" : mode;

  if (needCode) return <div className="app"><AccessScreen /><Toasts /></div>;
  return (
    <GuideContext.Provider value={guide}>
      <div className={guide.on ? "app guide-on" : "app guide-off"}>
        {guide.on && <div className="backdrop" />}
        <MockBanner />
        {guide.on ? <GuideBar mode={shown} setMode={(m) => void setMode(m)} onTour={() => setTour(true)} /> : <GuideFloat />}
        {!state ? <div className="stage empty">Opening your demo clinic…</div> : (
          <>
            {shown === "start" && <Start go={(m) => void setMode(m)} onTour={() => setTour(true)} />}
            {shown === "how" && <How go={(m) => void setMode(m)} />}
            {shown === "deploy" && <Deploy go={(m) => void setMode(m)} />}
            {shown === "therapist" && <Therapist section={section} go={(s) => nav("therapist", s)} />}
            {shown === "patient" && <Patient />}
            {shown === "autopilot" && <Autopilot />}
          </>
        )}
        {tour && guide.on && <Tour onClose={() => setTour(false)} />}
        <Toasts />
      </div>
    </GuideContext.Provider>
  );
}

export default function App() {
  return <StoreProvider><Shell /></StoreProvider>;
}
