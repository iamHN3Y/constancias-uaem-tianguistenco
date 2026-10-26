import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { api, ApiError } from "../api/client";
import { Header } from "../components/Header";
import { IconCalendar, IconCareer, IconTrash } from "../components/Icons";
import { Notice } from "../components/Notice";
import { StaggerItem, StaggerList } from "../components/Stagger";
import { useDialog } from "../context/DialogContext";
import { useToast } from "../context/ToastContext";
import { useTourSteps } from "../context/TourContext";

export function Carreras() {
  const { avisar } = useToast();
  const { confirmar } = useDialog();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["carreras"], queryFn: api.carreras });

  useTourSteps(data ? "carreras" : null, [
    { sel: "#card-carreras", title: "Carreras", text: "Cuando abran una carrera nueva, agrégala aquí con su prefijo de plan y el nombre completo tal como debe imprimirse en la constancia. Sin tocar código." },
    { sel: "#card-duraciones", title: "Duración de planes", text: "Registra aquí los planes que NO duran 10 semestres (por reestructuración). Usa el código completo, con sufijo." },
  ]);

  const invalidar = () => queryClient.invalidateQueries({ queryKey: ["carreras"] });

  const codigoRef = useRef<HTMLInputElement>(null);
  const nombreRef = useRef<HTMLInputElement>(null);
  const planRef = useRef<HTMLInputElement>(null);
  const semRef = useRef<HTMLInputElement>(null);

  const guardarCarrera = useMutation({
    mutationFn: (v: { codigo: string; nombre: string }) => api.carreraGuardar(v.codigo, v.nombre),
    onSuccess: async () => {
      avisar("Catálogo actualizado. El cambio aplica de inmediato al generar constancias.", "exito");
      if (codigoRef.current) codigoRef.current.value = "";
      if (nombreRef.current) nombreRef.current.value = "";
      await invalidar();
    },
    onError: (e: unknown) => avisar(e instanceof ApiError ? e.message : "No se pudo guardar.", "error"),
  });

  const eliminarCarrera = useMutation({
    mutationFn: (codigo: string) => api.carreraEliminar(codigo),
    onSuccess: async () => {
      avisar("Catálogo actualizado.", "exito");
      await invalidar();
    },
  });

  const guardarDuracion = useMutation({
    mutationFn: (v: { plan: string; semestres: string }) => api.duracionGuardar(v.plan, v.semestres),
    onSuccess: async () => {
      avisar("Catálogo actualizado. El cambio aplica de inmediato al generar constancias.", "exito");
      if (planRef.current) planRef.current.value = "";
      if (semRef.current) semRef.current.value = "";
      await invalidar();
    },
    onError: (e: unknown) => avisar(e instanceof ApiError ? e.message : "No se pudo guardar.", "error"),
  });

  const eliminarDuracion = useMutation({
    mutationFn: (plan: string) => api.duracionEliminar(plan),
    onSuccess: async () => {
      avisar("Catálogo actualizado.", "exito");
      await invalidar();
    },
  });

  async function onEliminarCarrera(codigo: string) {
    const ok = await confirmar({
      titulo: "¿Eliminar carrera?",
      mensaje: `¿Eliminar la carrera ${codigo}? Los alumnos con ese plan mostrarán el código crudo hasta que la vuelvas a dar de alta.`,
      peligro: true,
      textoConfirmar: "Eliminar",
    });
    if (ok) eliminarCarrera.mutate(codigo);
  }

  async function onEliminarDuracion(plan: string, duracionDefault: number) {
    const ok = await confirmar({
      titulo: "¿Eliminar duración?",
      mensaje: `¿Eliminar la duración de ${plan}? Volverá al default de ${duracionDefault} semestres.`,
      peligro: true,
      textoConfirmar: "Eliminar",
    });
    if (ok) eliminarDuracion.mutate(plan);
  }

  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <Header
        title="Catálogo de carreras"
        subtitle="Se usa para convertir el plan del Excel (ej. ICO-F19) en el nombre completo de la carrera."
        backTo="/"
      />

      {isLoading || !data ? (
        <div className="card skeleton" style={{ height: 140 }} />
      ) : (
        <StaggerList>
          <StaggerItem>
            <div id="card-carreras" className="card">
              <h2>
                <IconCareer />
                Carreras
              </h2>
              <p>
                El código es el <strong>prefijo</strong> del plan: para alumnos con plan <code>ICO-F19</code> o{" "}
                <code>ICO-F26</code>, el código es <code>ICO</code>. Para actualizar un nombre, vuelve a
                guardarlo con el mismo código.
              </p>
              {Object.entries(data.carreras).map(([codigo, nombre]) => (
                <div key={codigo} className="fila">
                  <code>{codigo}</code>
                  <span className="nombre">{nombre}</span>
                  <button type="button" className="icon-btn" title="Eliminar" aria-label="Eliminar carrera" onClick={() => onEliminarCarrera(codigo)}>
                    <IconTrash />
                  </button>
                </div>
              ))}
              <form
                className="form-inline"
                onSubmit={(e) => {
                  e.preventDefault();
                  const codigo = codigoRef.current?.value.trim().toUpperCase();
                  const nombre = nombreRef.current?.value.trim();
                  if (!codigo || !nombre) return;
                  guardarCarrera.mutate({ codigo, nombre });
                }}
              >
                <div className="field">
                  <label htmlFor="codigoNueva">Código</label>
                  <input id="codigoNueva" ref={codigoRef} className="cod" type="text" placeholder="ICO" maxLength={10} required style={{ textTransform: "uppercase" }} />
                </div>
                <div className="field" style={{ flex: 1, minWidth: 260 }}>
                  <label htmlFor="nombreNueva">Nombre completo (como debe imprimirse)</label>
                  <input id="nombreNueva" ref={nombreRef} type="text" placeholder="LICENCIATURA DE INGENIERIA EN..." maxLength={120} required />
                </div>
                <button type="submit" disabled={guardarCarrera.isPending}>
                  Guardar
                </button>
              </form>
            </div>
          </StaggerItem>

          <StaggerItem>
            <div id="card-duraciones" className="card">
              <h2>
                <IconCalendar />
                Duración de planes
              </h2>
              <p>
                Solo para planes que <strong>no</strong> duran {data.duracion_default} semestres. Se llavea por
                el código <strong>completo</strong> del plan, porque una reestructuración cambia la duración sin
                cambiar el prefijo (<code>IPI-F26</code> dura 9, <code>IPI-F19</code> sigue durando 10).
              </p>
              {Object.entries(data.duraciones).map(([plan, sem]) => (
                <div key={plan} className="fila">
                  <code>{plan}</code>
                  <span className="nombre">{sem} semestres</span>
                  <button type="button" className="icon-btn" title="Eliminar" aria-label="Eliminar duración" onClick={() => onEliminarDuracion(plan, data.duracion_default)}>
                    <IconTrash />
                  </button>
                </div>
              ))}
              <form
                className="form-inline"
                onSubmit={(e) => {
                  e.preventDefault();
                  const plan = planRef.current?.value.trim().toUpperCase();
                  const semestres = semRef.current?.value.trim();
                  if (!plan || !semestres) return;
                  guardarDuracion.mutate({ plan, semestres });
                }}
              >
                <div className="field">
                  <label htmlFor="planNuevo">Plan completo</label>
                  <input id="planNuevo" ref={planRef} className="cod" type="text" placeholder="IPI-F26" maxLength={15} required style={{ textTransform: "uppercase", width: 130 }} />
                </div>
                <div className="field">
                  <label htmlFor="semNuevo">Semestres</label>
                  <input id="semNuevo" ref={semRef} className="sem" type="number" min={1} max={20} placeholder="9" required />
                </div>
                <button type="submit" disabled={guardarDuracion.isPending}>
                  Guardar
                </button>
              </form>
            </div>
          </StaggerItem>
        </StaggerList>
      )}

      {!data && !isLoading && <Notice error>No se pudo cargar el catálogo de carreras.</Notice>}

      <style>{`
        .fila { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-top: 1px solid var(--outline-variant); }
        .fila code { font-size: 13px; }
        .fila .nombre { flex: 1; font-size: 14px; }
        .form-inline { display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-end; margin-top: 12px; }
        .form-inline .field { margin: 0; }
        .form-inline .field input { min-width: 0; }
        .cod { width: 110px; }
        .sem { width: 90px; }
      `}</style>
    </div>
  );
}
