/**
 * Tour guiado (coach marks), portado de app/static/tour.js.
 *
 * Cada pantalla registra sus pasos con `useTourSteps(key, steps)`. El tour
 * arranca solo la primera vez que se visita esa `key` (localStorage) y se
 * puede relanzar con el botón de ayuda del Header (`useTour().start()`).
 * Pasos cuyo selector no exista en el DOM se omiten solos.
 */
import { useCallback, useContext, useEffect, useRef, useState, createContext } from "react";

export interface TourStep {
  sel: string;
  title: string;
  text: string;
}

export interface TourConfig {
  key: string;
  steps: TourStep[];
}

interface TourContextValue {
  registerTour: (config: TourConfig | null) => void;
  start: () => void;
}

const TourContext = createContext<TourContextValue | null>(null);
const SEEN_PREFIX = "tour_seen_";
const PAD = 8;

export function TourProvider({ children }: { children: React.ReactNode }) {
  const [activeConfig, setActiveConfig] = useState<TourConfig | null>(null);
  const [openSteps, setOpenSteps] = useState<TourStep[] | null>(null);
  const [idx, setIdx] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const popRef = useRef<HTMLDivElement | null>(null);
  const [popSize, setPopSize] = useState({ w: 360, h: 160 });
  const reduced = typeof window !== "undefined" && window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;

  const registerTour = useCallback((config: TourConfig | null) => {
    setActiveConfig(config);
  }, []);

  const openWith = useCallback((cfg: TourConfig) => {
    const found = cfg.steps.filter((s) => document.querySelector(s.sel));
    if (!found.length) return;
    setOpenSteps(found);
    setIdx(0);
  }, []);

  const finish = useCallback(() => {
    if (activeConfig) localStorage.setItem(SEEN_PREFIX + activeConfig.key, "1");
    setOpenSteps(null);
    setRect(null);
  }, [activeConfig]);

  const start = useCallback(() => {
    if (activeConfig) openWith(activeConfig);
  }, [activeConfig, openWith]);

  // Auto-arranque: solo la primera vez que se visita esta `key`.
  useEffect(() => {
    if (!activeConfig) return;
    if (localStorage.getItem(SEEN_PREFIX + activeConfig.key)) return;
    const t = setTimeout(() => openWith(activeConfig), 400);
    return () => clearTimeout(t);
  }, [activeConfig, openWith]);

  const step = openSteps ? openSteps[idx] : null;

  const position = useCallback(() => {
    if (!step) return;
    const el = document.querySelector(step.sel);
    if (!el) return;
    el.scrollIntoView({ block: "center", inline: "nearest" });
    setRect(el.getBoundingClientRect());
  }, [step]);

  useEffect(() => {
    if (!step) return;
    position();
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [step, position]);

  useEffect(() => {
    if (popRef.current) {
      setPopSize({ w: popRef.current.offsetWidth, h: popRef.current.offsetHeight });
    }
  }, [step, rect]);

  useEffect(() => {
    if (!openSteps) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        finish();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        if (idx >= openSteps!.length - 1) finish();
        else setIdx(idx + 1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setIdx(Math.max(0, idx - 1));
      }
    }
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [openSteps, idx, finish]);

  let popTop = 0;
  let popLeft = 0;
  if (rect) {
    const below = rect.bottom + 14;
    if (below + popSize.h > window.innerHeight - 10) {
      const above = rect.top - popSize.h - 14;
      popTop = above >= 10 ? above : Math.max(10, window.innerHeight - popSize.h - 10);
    } else {
      popTop = below;
    }
    popLeft = Math.max(10, Math.min(rect.left + rect.width / 2 - popSize.w / 2, window.innerWidth - popSize.w - 10));
  }

  return (
    <TourContext.Provider value={{ registerTour, start }}>
      {children}
      {step && rect && (
        <>
          <div
            className={"tour-hole" + (reduced ? " tour-hole--reduced" : "")}
            style={{ left: rect.left - PAD, top: rect.top - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 }}
          />
          <div
            ref={popRef}
            className={"tour-pop" + (reduced ? " tour-pop--reduced" : "")}
            style={{ top: popTop, left: popLeft }}
            role="dialog"
            aria-modal="true"
          >
            <div className="tour-progress">Paso {idx + 1} de {openSteps!.length}</div>
            <h3 className="tour-title">{step.title}</h3>
            <p className="tour-text">{step.text}</p>
            <div className="tour-actions">
              <button type="button" className="btn-text" onClick={finish}>Saltar</button>
              <span style={{ flex: 1 }} />
              {idx > 0 && (
                <button type="button" className="btn-ghost" onClick={() => setIdx((i) => Math.max(0, i - 1))}>
                  Anterior
                </button>
              )}
              <button
                type="button"
                onClick={() => (idx >= openSteps!.length - 1 ? finish() : setIdx((i) => i + 1))}
              >
                {idx >= openSteps!.length - 1 ? "Entendido" : "Siguiente"}
              </button>
            </div>
          </div>
        </>
      )}
    </TourContext.Provider>
  );
}

export function useTour(): TourContextValue {
  const ctx = useContext(TourContext);
  if (!ctx) throw new Error("useTour debe usarse dentro de <TourProvider>");
  return ctx;
}

/** Registra los pasos del tour de una pantalla mientras está montada. */
export function useTourSteps(key: string | null, steps: TourStep[]) {
  const { registerTour } = useTour();
  // Los pasos se recrean en cada render de la pantalla (son literales); solo
  // re-registramos cuando cambia la key real (ej. home-admin vs home-invitado).
  useEffect(() => {
    if (!key) return undefined;
    registerTour({ key, steps });
    return () => registerTour(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, registerTour]);
}
