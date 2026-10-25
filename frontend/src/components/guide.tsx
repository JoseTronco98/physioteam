import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { cx } from "../util";

/* The demo guide is everything that only exists to test the app (blue glass).
   The product is what a clinic would actually use (white window / iPhone). */

const KEY = "physioteam.guide";
export const GuideContext = createContext<{ on: boolean; set: (v: boolean) => void }>({ on: true, set: () => {} });
export const useGuide = () => useContext(GuideContext);

export function useGuideState() {
  const [on, setOn] = useState<boolean>(() => localStorage.getItem(KEY) !== "off");
  const set = (v: boolean) => { localStorage.setItem(KEY, v ? "on" : "off"); setOn(v); };
  return { on, set };
}

export function GuideLabel({ children = "Demo guide" }: { children?: ReactNode }) {
  return <span className="glabel">{children}</span>;
}

export function GuideSwitch({ compact }: { compact?: boolean }) {
  const { on, set } = useGuide();
  return (
    <button className={cx("gswitch", on && "on", compact && "compact")} onClick={() => set(!on)} title="Show or hide everything that is only part of the demo">
      <span>Show guide</span><i />
    </button>
  );
}

/** Floating pill shown when the guide is hidden, to bring it back. */
export function GuideFloat() {
  return <div className="gfloatpill g"><GuideSwitch compact /></div>;
}

function wide(px: number) { return typeof window !== "undefined" && window.innerWidth >= px; }

/** A guide side panel: inline when there is room, a narrow blue tab otherwise (opens as a floating sheet). */
export function GuideSide({ side, label, minWidth, width, children }: {
  side: "left" | "right"; label: string; minWidth: number; width: number; children: ReactNode;
}) {
  const [userMode, setUserMode] = useState<"inline" | "strip" | null>(null);
  const [roomy, setRoomy] = useState(wide(minWidth));
  const [floatOpen, setFloatOpen] = useState(false);
  useEffect(() => {
    const on = () => setRoomy(wide(minWidth));
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, [minWidth]);
  const mode = userMode ?? (roomy ? "inline" : "strip");

  if (mode === "inline") {
    return (
      <aside className={cx("gside g", side)} style={{ width }}>
        <div className="gside-head">
          <GuideLabel />
          <span className="spacer" />
          <button className="gicon" title="Collapse" onClick={() => setUserMode("strip")}>{side === "left" ? "‹" : "›"}</button>
        </div>
        {children}
      </aside>
    );
  }
  return (
    <div className={cx("gstrip-wrap", side)}>
      <button className="gstrip g" onClick={() => setFloatOpen((o) => !o)} title={`Open ${label}`}>
        <span className="gstrip-dot" />
        <span className="gstrip-t">{label}</span>
      </button>
      {floatOpen && (
        <aside className={cx("gside g gfloat", side)} style={{ width }}>
          <div className="gside-head">
            <GuideLabel />
            <span className="spacer" />
            {roomy && <button className="gicon" title="Pin open" onClick={() => { setUserMode("inline"); setFloatOpen(false); }}>⇤</button>}
            <button className="gicon" title="Close" onClick={() => setFloatOpen(false)}>✕</button>
          </div>
          {children}
        </aside>
      )}
    </div>
  );
}
