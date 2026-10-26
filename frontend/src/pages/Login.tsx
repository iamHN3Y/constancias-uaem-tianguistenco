import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, type Rol } from "../api/client";
import { Notice } from "../components/Notice";
import { ThemeToggle } from "../components/Header";
import { IconAdmin, IconHelp, IconInvitado } from "../components/Icons";
import { useTour, useTourSteps } from "../context/TourContext";

const TITULO = "Generador de Constancias";

function TituloReveal() {
  const reduced = useReducedMotion();
  if (reduced) return <h1>{TITULO}</h1>;
  const palabras = TITULO.split(" ");
  return (
    <h1 aria-label={TITULO}>
      {palabras.map((palabra, wi) => (
        <span key={wi} style={{ display: "inline-block", overflow: "hidden", marginRight: "0.28em" }}>
          <motion.span
            style={{ display: "inline-block" }}
            initial={{ y: "110%", opacity: 0 }}
            animate={{ y: "0%", opacity: 1 }}
            transition={{ duration: 0.55, delay: 0.05 * wi, ease: [0.2, 0, 0, 1] }}
          >
            {palabra}
          </motion.span>
        </span>
      ))}
    </h1>
  );
}

export function Login() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const [errorAdmin, setErrorAdmin] = useState<string | null>(null);
  const reduced = useReducedMotion();
  const { start } = useTour();

  useTourSteps("login", [
    { sel: ".role-card", title: "Entrar como Invitado", text: "Genera constancias usando los datos y la plantilla ya cargados. No puede subir archivos." },
    { sel: "#password", title: "Entrar como Administrador", text: "Además de generar, sube la base de datos y la plantilla, y define el periodo activo. Requiere contraseña." },
  ]);

  const mutation = useMutation({
    mutationFn: (rol: Rol) => api.login(rol, password),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["session"] });
      navigate("/", { replace: true });
    },
    onError: (e: unknown) => {
      setErrorAdmin(e instanceof ApiError ? e.message : "No se pudo iniciar sesión.");
    },
  });

  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <header className="header">
        <div className="brand">
          <TituloReveal />
          <p>Centro Universitario UAEM Tianguistenco</p>
        </div>
        <div className="appbar-actions">
          <button className="icon-btn" type="button" onClick={start} title="Ver tutorial" aria-label="Ver tutorial">
            <IconHelp />
          </button>
          <ThemeToggle />
        </div>
      </header>

      {errorAdmin && <Notice error>{errorAdmin}</Notice>}

      <p className="muted" style={{ margin: "0 0 18px", fontSize: 15 }}>
        Elige cómo quieres entrar:
      </p>

      <div className="grid">
        <motion.div
          className="card role-card"
          style={{ display: "flex", flexDirection: "column" }}
          initial={reduced ? { opacity: 0 } : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.15 }}
        >
          <h2>
            <IconInvitado style={{ width: 22, height: 22, fill: "var(--primary)" }} />
            Invitado
          </h2>
          <p>
            Genera constancias con la base de datos y la plantilla actuales. No puede subir archivos ni
            cambiar la configuración.
          </p>
          <div className="actions" style={{ marginTop: "auto" }}>
            <button
              type="button"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate("invitado")}
            >
              Entrar como invitado
            </button>
          </div>
        </motion.div>

        <motion.div
          className="card role-card"
          style={{ display: "flex", flexDirection: "column" }}
          initial={reduced ? { opacity: 0 } : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.25 }}
        >
          <h2>
            <IconAdmin style={{ width: 22, height: 22, fill: "var(--primary)" }} />
            Administrador
          </h2>
          <p>
            Acceso completo: subir base de datos, reemplazar la plantilla universal y configurar el
            periodo activo.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setErrorAdmin(null);
              mutation.mutate("admin");
            }}
          >
            <div className="field">
              <label htmlFor="password">Contraseña</label>
              <input
                id="password"
                type="password"
                required
                autoFocus
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <div className="actions">
              <button type="submit" disabled={mutation.isPending}>
                Entrar como admin
              </button>
            </div>
          </form>
        </motion.div>
      </div>
    </div>
  );
}
