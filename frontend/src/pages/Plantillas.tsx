import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { Header } from "../components/Header";
import { IconDownload, IconFile, IconPlus, IconTrash, IconWarning } from "../components/Icons";
import { Notice } from "../components/Notice";
import { StaggerItem, StaggerList } from "../components/Stagger";
import { useDialog } from "../context/DialogContext";
import { useToast } from "../context/ToastContext";
import { useTourSteps } from "../context/TourContext";

export function Plantillas() {
  const { avisar } = useToast();
  const { confirmar } = useDialog();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["plantillas"], queryFn: api.plantillasList });

  useTourSteps(data ? "plantillas-multi" : null, [
    { sel: ".note", title: "Convenciones por nombre", text: "El nombre del placeholder decide su comportamiento: _LINEA crea líneas opcionales, _FECHA crea selectores de fecha, y cualquier otro es texto libre. Sin tocar código." },
    { sel: ".tpl-card", title: "Cada plantilla", text: "Aquí ves sus placeholders detectados, avisos si algo quedó mal escrito en Word, y sus acciones: descargar, reemplazar, restaurar del historial o eliminar." },
    { sel: "#crear", title: "Nueva plantilla", text: "Puedes tener varios tipos de constancia. Cada una guarda su propio historial de versiones." },
  ]);

  const invalidar = () => queryClient.invalidateQueries({ queryKey: ["plantillas"] });

  const nombreRef = useRef<HTMLInputElement>(null);
  const archivoRef = useRef<HTMLInputElement>(null);
  const [errorCrear, setErrorCrear] = useState<string | null>(null);

  const crear = useMutation({
    mutationFn: (vars: { nombre: string; archivo: File }) => api.plantillaCrear(vars.nombre, vars.archivo),
    onSuccess: async () => {
      setErrorCrear(null);
      avisar("Plantilla creada. Ya aparece como opción al generar constancias.", "exito");
      if (nombreRef.current) nombreRef.current.value = "";
      if (archivoRef.current) archivoRef.current.value = "";
      await invalidar();
    },
    onError: (e: unknown) => setErrorCrear(e instanceof ApiError ? e.message : "No se pudo crear la plantilla."),
  });

  const reemplazar = useMutation({
    mutationFn: (vars: { slug: string; archivo: File }) => api.plantillaUpload(vars.slug, vars.archivo),
    onSuccess: async () => {
      avisar("Plantilla actualizada. Los campos del formulario se ajustan automáticamente.", "exito");
      await invalidar();
    },
    onError: (e: unknown) => avisar(e instanceof ApiError ? e.message : "No se pudo reemplazar.", "error"),
  });

  const restaurar = useMutation({
    mutationFn: (vars: { slug: string; nombre: string }) => api.plantillaRestaurar(vars.slug, vars.nombre),
    onSuccess: async () => {
      avisar("Versión restaurada. La que estaba activa quedó guardada en el historial.", "exito");
      await invalidar();
    },
    onError: (e: unknown) => avisar(e instanceof ApiError ? e.message : "No se pudo restaurar.", "error"),
  });

  const eliminar = useMutation({
    mutationFn: (slug: string) => api.plantillaEliminar(slug),
    onSuccess: async () => {
      avisar("Plantilla eliminada.", "exito");
      await invalidar();
    },
    onError: (e: unknown) => avisar(e instanceof ApiError ? e.message : "No se pudo eliminar.", "error"),
  });

  async function onReemplazar(slug: string, file: File | undefined) {
    if (!file) return;
    reemplazar.mutate({ slug, archivo: file });
  }

  async function onRestaurar(slug: string, nombre: string, fecha: string) {
    const ok = await confirmar({
      titulo: "¿Restaurar versión?",
      mensaje: `¿Restaurar la versión del ${fecha}? La actual quedará en el historial.`,
      peligro: true,
      textoConfirmar: "Restaurar",
    });
    if (ok) restaurar.mutate({ slug, nombre });
  }

  async function onEliminar(slug: string, nombre: string) {
    const ok = await confirmar({
      titulo: "¿Eliminar plantilla?",
      mensaje: `Esto elimina «${nombre}» y todo su historial. Esta acción no se puede deshacer. Escribe «${slug}» para confirmar.`,
      peligro: true,
      textoConfirmar: "Eliminar",
      escribirPara: slug,
    });
    if (ok) eliminar.mutate(slug);
  }

  function onCrear(e: React.FormEvent) {
    e.preventDefault();
    const nombre = nombreRef.current?.value.trim();
    const archivo = archivoRef.current?.files?.[0];
    if (!nombre || !archivo) return;
    crear.mutate({ nombre, archivo });
  }

  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <Header
        title="Plantillas"
        subtitle="Documentos .docx con placeholders [[CAMPO]]. Puedes tener varias: general, inglés, prácticas…"
        backTo="/"
      />

      <Notice>
        Convenciones por nombre — no requieren tocar código: <code>[[ALGO_LINEA]]</code> es una línea opcional
        (se elimina sola si queda vacía), <code>[[ALGO_FECHA]]</code> aparece como selector de fecha, cualquier
        otro <code>[[CAMPO]]</code> es texto libre. Funcionan también en encabezados, pies de página, tablas y
        cuadros de texto.
      </Notice>

      {isLoading || !data ? (
        <div className="card skeleton" style={{ height: 140 }} />
      ) : (
        <StaggerList>
          {data.items.map((it) => (
            <StaggerItem key={it.slug}>
              <div className="card tpl-card">
                <h2>
                  <IconFile />
                  {it.nombre}
                </h2>
                {it.info ? (
                  <>
                    <p>
                      {it.info.placeholders.length} placeholders · actualizada {it.info.fecha_carga}
                    </p>
                    <div className="phs">
                      {it.info.placeholders.map((ph) => (
                        <code key={ph}>{ph}</code>
                      ))}
                    </div>
                    {it.info.avisos.length > 0 && (
                      <div style={{ marginTop: 14 }}>
                        <div className="note note-error">
                          <IconWarning />
                          <span>
                            <strong>Revisa esta plantilla en Word:</strong>
                            <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                              {it.info.avisos.map((aviso, i) => (
                                <li key={i}>{aviso}</li>
                              ))}
                            </ul>
                          </span>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <p>El archivo de esta plantilla no se encuentra. Sube un .docx para reactivarla.</p>
                )}

                <div className="tpl-actions">
                  {it.info && (
                    <a className="btn btn-tonal" href={api.plantillaDownloadUrl(it.slug)}>
                      <IconDownload />
                      Descargar
                    </a>
                  )}
                  <form
                    className="tpl-replace"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const input = (e.currentTarget.elements.namedItem("archivo") as HTMLInputElement) || null;
                      onReemplazar(it.slug, input?.files?.[0]);
                    }}
                  >
                    <input type="file" name="archivo" accept=".docx" required />
                    <button type="submit" className="btn-tonal" style={{ minHeight: 38, padding: "8px 14px" }}>
                      Reemplazar
                    </button>
                  </form>
                  {data.items.length > 1 && (
                    <button
                      type="button"
                      className="icon-btn"
                      title="Eliminar plantilla"
                      aria-label="Eliminar plantilla"
                      onClick={() => onEliminar(it.slug, it.nombre)}
                    >
                      <IconTrash />
                    </button>
                  )}
                </div>

                {it.historial.length > 0 && (
                  <details className="historial">
                    <summary>Historial ({it.historial.length} versiones respaldadas)</summary>
                    {it.historial.map((v) => (
                      <div key={v.nombre} className="hist-row">
                        <span style={{ fontSize: 14 }}>{v.fecha}</span>
                        <button
                          type="button"
                          className="btn-tonal"
                          style={{ minHeight: 36, padding: "6px 14px" }}
                          onClick={() => onRestaurar(it.slug, v.nombre, v.fecha)}
                        >
                          Restaurar
                        </button>
                      </div>
                    ))}
                  </details>
                )}
              </div>
            </StaggerItem>
          ))}

          <StaggerItem>
            <div id="crear" className="card">
              <h2>
                <IconPlus />
                Nueva plantilla
              </h2>
              <p>
                Crea otro tipo de constancia (por ejemplo «Constancia en inglés» o «Prácticas profesionales»).
                Aparecerá como opción al generar.
              </p>
              {errorCrear && <Notice error>{errorCrear}</Notice>}
              <form onSubmit={onCrear}>
                <div className="field">
                  <label htmlFor="nombreNueva">Nombre</label>
                  <input id="nombreNueva" ref={nombreRef} type="text" placeholder="Ej. Constancia en inglés" maxLength={60} required />
                </div>
                <div className="field">
                  <label htmlFor="archivoNueva">Archivo (.docx)</label>
                  <input id="archivoNueva" ref={archivoRef} type="file" accept=".docx" required />
                </div>
                <div className="actions">
                  <button type="submit" disabled={crear.isPending}>
                    Crear plantilla
                  </button>
                </div>
              </form>
            </div>
          </StaggerItem>
        </StaggerList>
      )}

      <style>{`
        .tpl-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 14px; }
        .tpl-replace { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .tpl-replace input[type="file"] { max-width: 320px; }
        details.historial { margin-top: 14px; }
        details.historial summary { cursor: pointer; font-weight: 600; font-size: 14px; color: var(--on-surface-variant); }
        .hist-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-top: 1px solid var(--outline-variant); }
      `}</style>
    </div>
  );
}
