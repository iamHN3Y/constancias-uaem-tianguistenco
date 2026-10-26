/**
 * Reemplazo accesible de confirm()/prompt(), portado de app/static/ui.js
 * (confirmar/pedirTexto). Usa las clases .dialog-* ya definidas en app.css.
 *
 * Nivel 2 de confirmación ("escribir para confirmar"): si se pasa
 * `escribirPara`, el botón de confirmar queda deshabilitado hasta que el
 * usuario teclee ese texto exacto — igual que data-confirmar-escribir-para
 * en los formularios Jinja2 originales.
 */
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { createContext, useCallback, useContext, useRef, useState } from "react";

export interface ConfirmOptions {
  titulo?: string;
  mensaje?: string;
  peligro?: boolean;
  textoConfirmar?: string;
  escribirPara?: string;
}

export interface PromptOptions {
  titulo?: string;
  mensaje?: string;
  placeholder?: string;
  textoConfirmar?: string;
}

type PendingConfirm = { kind: "confirm"; opts: ConfirmOptions; resolve: (v: boolean) => void };
type PendingPrompt = { kind: "prompt"; opts: PromptOptions; resolve: (v: string | null) => void };
type Pending = PendingConfirm | PendingPrompt;

interface DialogContextValue {
  confirmar: (opts: ConfirmOptions) => Promise<boolean>;
  pedirTexto: (opts: PromptOptions) => Promise<string | null>;
}

const DialogContext = createContext<DialogContextValue | null>(null);

export function DialogProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const [texto, setTexto] = useState("");
  const reduced = useReducedMotion();
  const idRef = useRef(0);

  const confirmar = useCallback((opts: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      idRef.current++;
      setTexto("");
      setPending({ kind: "confirm", opts, resolve });
    });
  }, []);

  const pedirTexto = useCallback((opts: PromptOptions) => {
    return new Promise<string | null>((resolve) => {
      idRef.current++;
      setTexto("");
      setPending({ kind: "prompt", opts, resolve });
    });
  }, []);

  function cerrar(valor: boolean | string | null) {
    if (!pending) return;
    if (pending.kind === "confirm") pending.resolve(valor as boolean);
    else pending.resolve(valor as string | null);
    setPending(null);
  }

  const esConfirm = pending?.kind === "confirm";
  const peligro = esConfirm ? !!(pending.opts as ConfirmOptions).peligro : false;
  const escribirPara = esConfirm ? (pending.opts as ConfirmOptions).escribirPara : undefined;
  const puedeConfirmar = esConfirm
    ? !escribirPara || texto === escribirPara
    : pending
    ? texto.trim() !== ""
    : false;

  return (
    <DialogContext.Provider value={{ confirmar, pedirTexto }}>
      {children}
      <AnimatePresence>
        {pending && (
          <motion.div
            className="dialog-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduced ? 0 : 0.15 }}
            onKeyDown={(e) => {
              if (e.key === "Escape") cerrar(pending.kind === "confirm" ? false : null);
            }}
          >
            <motion.div
              className={"dialog" + (peligro ? " dialog-danger" : "")}
              role="alertdialog"
              aria-modal="true"
              initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.94, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
              transition={{ type: "spring", stiffness: 420, damping: 34 }}
            >
              <div className="dialog-body">
                <h3>{pending.opts.titulo || (pending.kind === "confirm" ? "¿Confirmar acción?" : "Escribe un valor")}</h3>
                {pending.opts.mensaje && <p>{pending.opts.mensaje}</p>}

                {pending.kind === "confirm" && escribirPara && (
                  <div className="field">
                    <label>Escribe &quot;{escribirPara}&quot; para continuar</label>
                    <input
                      type="text"
                      autoComplete="off"
                      autoFocus
                      value={texto}
                      onChange={(e) => setTexto(e.target.value)}
                    />
                  </div>
                )}

                {pending.kind === "prompt" && (
                  <div className="field">
                    <input
                      type="text"
                      autoComplete="off"
                      autoFocus
                      placeholder={(pending.opts as PromptOptions).placeholder}
                      value={texto}
                      onChange={(e) => setTexto(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && texto.trim() !== "") {
                          e.preventDefault();
                          cerrar(texto.trim());
                        }
                      }}
                    />
                  </div>
                )}

                <div className="dialog-actions">
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => cerrar(pending.kind === "confirm" ? false : null)}
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    className="dialog-confirmar"
                    disabled={!puedeConfirmar}
                    autoFocus={!(pending.kind === "confirm" && escribirPara) && pending.kind !== "prompt"}
                    onClick={() => cerrar(pending.kind === "confirm" ? true : texto.trim())}
                  >
                    {pending.opts.textoConfirmar || (pending.kind === "confirm" ? "Confirmar" : "Guardar")}
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </DialogContext.Provider>
  );
}

export function useDialog(): DialogContextValue {
  const ctx = useContext(DialogContext);
  if (!ctx) throw new Error("useDialog debe usarse dentro de <DialogProvider>");
  return ctx;
}
