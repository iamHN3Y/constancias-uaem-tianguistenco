import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { createContext, useCallback, useContext, useRef, useState } from "react";

export type ToastTipo = "info" | "exito" | "error";
interface ToastItem {
  id: number;
  mensaje: string;
  tipo: ToastTipo;
}

interface ToastContextValue {
  avisar: (mensaje: string, tipo?: ToastTipo) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const SNACKBAR_MS = 5000;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const idRef = useRef(0);
  const reduced = useReducedMotion();

  const avisar = useCallback((mensaje: string, tipo: ToastTipo = "info") => {
    const id = ++idRef.current;
    setItems((prev) => [...prev, { id, mensaje, tipo }]);
    setTimeout(() => {
      setItems((prev) => prev.filter((i) => i.id !== id));
    }, SNACKBAR_MS);
  }, []);

  return (
    <ToastContext.Provider value={{ avisar }}>
      {children}
      <div className="snackbar-region" role="status" aria-live="polite">
        <AnimatePresence>
          {items.map((item) => (
            <motion.div
              key={item.id}
              className={
                "snackbar" +
                (item.tipo === "exito" ? " snackbar-exito" : item.tipo === "error" ? " snackbar-error" : "")
              }
              initial={reduced ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={reduced ? { opacity: 0 } : { opacity: 0, y: 10, scale: 0.96 }}
              transition={{ type: "spring", stiffness: 420, damping: 32 }}
            >
              {item.mensaje}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast debe usarse dentro de <ToastProvider>");
  return ctx;
}
