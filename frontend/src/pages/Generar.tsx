import { useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError, type CampoForm, type Comodin } from "../api/client";
import { Header } from "../components/Header";
import { IconDownload, IconFields, IconEye, IconTrash } from "../components/Icons";
import { Notice } from "../components/Notice";
import { useDialog } from "../context/DialogContext";
import { useToast } from "../context/ToastContext";
import { useTourSteps } from "../context/TourContext";

interface CampoState extends CampoForm {
  incluido: boolean;
}

function inicialIncluido(c: CampoForm): boolean {
  if (c.tipo === "date_rango") return !!(c.iso_inicio && c.iso_fin);
  return c.valor.trim() !== "";
}

export function Generar() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { avisar } = useToast();
  const { confirmar, pedirTexto } = useDialog();
  const reduced = useReducedMotion();

  const cuenta = params.get("cuenta") || "";
  const plantillaParam = params.get("plantilla") || "";

  const { data, isLoading, error } = useQuery({
    queryKey: ["generar-campos", cuenta, plantillaParam],
    queryFn: () => api.generarCampos(cuenta, plantillaParam),
    enabled: !!cuenta,
    retry: false,
  });

  const [campos, setCampos] = useState<CampoState[] | null>(null);

  useEffect(() => {
    if (data) {
      setCampos(data.campos.map((c) => ({ ...c, incluido: inicialIncluido(c) })));
    }
  }, [data]);

  // ---------- Vista previa PDF ----------
  const [status, setStatus] = useState("listo");
  const [statusError, setStatusError] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [hasPreview, setHasPreview] = useState(false);
  const [skeletonTexto, setSkeletonTexto] = useState("Generando vista previa…");
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevUrlRef = useRef<string | null>(null);
  const mensajeTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const loadTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function buildFormData(): FormData | null {
    if (!campos || !data) return null;
    const fd = new FormData();
    fd.append("cuenta", data.alumno.Cuenta);
    fd.append("plantilla", data.plantilla_slug);
    for (const c of campos) {
      if (c.tipo === "radio_genero") {
        fd.append("__genero__", c.genero || "");
        fd.append(`campo_${c.name}`, "");
        continue;
      }
      if (c.opcional && !c.incluido) continue;
      if (c.tipo === "date_corto" || c.tipo === "date_largo") {
        fd.append(`fecha_${c.name}`, c.iso || "");
      } else if (c.tipo === "date_rango") {
        fd.append("fecha_VAC_INICIO", c.iso_inicio || "");
        fd.append("fecha_VAC_FIN", c.iso_fin || "");
      } else {
        fd.append(`campo_${c.name}`, c.valor || "");
      }
    }
    return fd;
  }

  function limpiarMensajeTimers() {
    mensajeTimersRef.current.forEach(clearTimeout);
    mensajeTimersRef.current = [];
  }

  async function refreshPreview() {
    const fd = buildFormData();
    if (!fd) return;
    if (abortRef.current) abortRef.current.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setStatus("generando…");
    setStatusError(false);
    setCargando(true);
    setSkeletonTexto("Generando vista previa…");
    limpiarMensajeTimers();
    mensajeTimersRef.current.push(setTimeout(() => setSkeletonTexto("Un momento, casi lista…"), 1200));
    mensajeTimersRef.current.push(
      setTimeout(() => setSkeletonTexto("LibreOffice está componiendo el documento…"), 2500)
    );

    try {
      const blob = await api.previewPdf(fd, ctrl.signal);
      const url = URL.createObjectURL(blob);
      const anterior = prevUrlRef.current;
      prevUrlRef.current = url;
      setStatus("actualizado");
      setHasPreview(true);

      // El iframe pinta el PDF de forma asíncrona: espera a "load" antes de
      // quitar el skeleton, con un timeout de respaldo por si no dispara.
      const terminar = () => {
        if (loadTimeoutRef.current) {
          clearTimeout(loadTimeoutRef.current);
          loadTimeoutRef.current = null;
        }
        setCargando(false);
        limpiarMensajeTimers();
        if (anterior) URL.revokeObjectURL(anterior);
      };

      const iframe = iframeRef.current;
      if (iframe) {
        // Mantener la página actual del visor cuando se regenera.
        const hash = iframe.src.includes("#") ? "#" + iframe.src.split("#")[1] : "";
        iframe.onload = () => {
          iframe.onload = null;
          terminar();
        };
        loadTimeoutRef.current = setTimeout(terminar, 1500);
        iframe.src = url + hash;
      } else {
        terminar();
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setStatus(e instanceof ApiError ? `error ${e.status}` : "error");
      setStatusError(true);
      setCargando(false);
      limpiarMensajeTimers();
    }
  }

  function debouncedRefresh() {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(refreshPreview, 700);
  }

  useEffect(() => {
    if (campos) debouncedRefresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campos]);

  useEffect(() => {
    return () => {
      if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (abortRef.current) abortRef.current.abort();
      limpiarMensajeTimers();
    };
  }, []);

  // ---------- Descarga ----------
  const [descargando, setDescargando] = useState<"docx" | "pdf" | null>(null);

  async function descargar(ext: "docx" | "pdf") {
    if (!campos || !data) return;
    const tieneGenero = campos.some((c) => c.tipo === "radio_genero");
    if (tieneGenero && !campos.find((c) => c.tipo === "radio_genero")?.genero) {
      avisar("Selecciona el género antes de descargar.", "error");
      return;
    }
    const fd = buildFormData();
    if (!fd) return;
    setDescargando(ext);
    try {
      const blob = ext === "docx" ? await api.generarDocx(fd) : await api.generarPdf(fd);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `Constancia_${data.alumno.Cuenta}.${ext}`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      avisar("Constancia descargada", "exito");
    } catch (e) {
      avisar(e instanceof ApiError ? e.message : "Error generando archivo.", "error");
    } finally {
      setDescargando(null);
    }
  }

  // ---------- Comodines ----------
  const tieneLineaLibre = useMemo(() => campos?.some((c) => c.name === "LINEA_LIBRE"), [campos]);
  const { data: comodines, refetch: refetchComodines } = useQuery<Comodin[]>({
    queryKey: ["comodines"],
    queryFn: api.comodines,
    enabled: !!tieneLineaLibre,
  });
  const [comodinSel, setComodinSel] = useState("");

  function setCampoValor(name: string, patch: Partial<CampoState>) {
    setCampos((prev) => (prev ? prev.map((c) => (c.name === name ? { ...c, ...patch } : c)) : prev));
  }

  async function insertarComodin(id: string) {
    const c = comodines?.find((x) => x.id === id);
    if (!c) return;
    setCampoValor("LINEA_LIBRE", { valor: c.texto, incluido: true });
  }

  async function guardarComodin() {
    const campo = campos?.find((c) => c.name === "LINEA_LIBRE");
    const texto = (campo?.valor || "").trim();
    if (!texto) {
      avisar("Escribe algo en la línea libre antes de guardarlo.", "error");
      return;
    }
    const titulo = await pedirTexto({ titulo: "Guardar comodín", placeholder: "Título del comodín", textoConfirmar: "Guardar" });
    if (!titulo) return;
    try {
      const nuevo = await api.comodinCrear(titulo, texto);
      await refetchComodines();
      setComodinSel(nuevo.id);
    } catch {
      avisar("No se pudo guardar.", "error");
    }
  }

  async function eliminarComodinSel() {
    if (!comodinSel) {
      avisar("Selecciona un comodín a eliminar.", "error");
      return;
    }
    const c = comodines?.find((x) => x.id === comodinSel);
    const ok = await confirmar({
      titulo: "¿Eliminar comodín?",
      mensaje: `¿Eliminar el comodín "${c?.titulo ?? ""}"?`,
      peligro: true,
      textoConfirmar: "Eliminar",
    });
    if (!ok) return;
    try {
      await api.comodinEliminar(comodinSel);
      setComodinSel("");
      await refetchComodines();
    } catch {
      avisar("No se pudo eliminar.", "error");
    }
  }

  useTourSteps(campos ? "generar" : null, [
    { sel: ".alumno-info", title: "Datos del alumno", text: "Resumen del alumno encontrado (plan, periodos, situación). Es solo de referencia." },
    { sel: "#formCampos", title: "Campos del documento", text: "Vienen prellenados desde los datos y el catálogo de carreras. Edita cualquiera si necesitas corregirlo." },
    { sel: ".radio-row", title: "Género", text: "Elige el género: el texto de la constancia (el/la alumno/a, del/de la interesada) se ajusta automáticamente." },
    { sel: ".switch", title: "Líneas opcionales", text: "Cada línea opcional tiene este interruptor. Enciéndelo para incluirla o apágalo para omitirla, sin tener que borrar el texto." },
    { sel: ".comodin-bar", title: "Comodines", text: "En la línea libre puedes guardar frases que usas seguido e insertarlas con un clic." },
    { sel: "#pdfFrame", title: "Vista previa en vivo", text: "Se regenera con cada cambio que haces en el formulario, para que veas el resultado real." },
    { sel: "#btnPdf", title: "Descargar", text: "Cuando esté listo, descarga la constancia en Word (.docx) o en PDF." },
  ]);

  // ---------- Render ----------

  if (!cuenta) {
    return (
      <div className="page">
        <Header title="Generar constancia" backTo="/" />
        <Notice error>Falta el número de cuenta. Vuelve a la búsqueda.</Notice>
      </div>
    );
  }

  if (isLoading || !data || !campos) {
    return (
      <div className="page" style={{ maxWidth: 1600 }}>
        <Header title="Generar constancia" backTo="/" backLabel="Cancelar" />
        {error ? (
          <Notice error>{error instanceof ApiError ? error.message : "No se pudo cargar el formulario."}</Notice>
        ) : (
          <div className="card skeleton" style={{ height: 220 }} />
        )}
      </div>
    );
  }

  const alumno = data.alumno;
  const ajustes = data.ajustes;

  return (
    <motion.div
      className="page"
      style={{ maxWidth: 1600 }}
      initial={reduced ? { opacity: 0 } : { opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
    >
      <Header title={data.plantilla_nombre || "Constancia"} subtitle={`${alumno.NombreAlumno} · cuenta ${alumno.Cuenta}`} backTo="/" backLabel="Cancelar" />

      {!ajustes.periodo_actual && (
        <Notice error>
          No hay <strong>periodo activo</strong> configurado: el semestre y las fechas del periodo no se pueden
          calcular solos. Pídele al administrador que lo defina en la pantalla principal (se hace una sola vez por
          semestre).
        </Notice>
      )}

      <motion.div layoutId={reduced ? undefined : "tarjeta-generar"} className="alumno-info">
        <div>
          <b>Plan</b>
          <span className="v">{alumno.Plan}</span>
        </div>
        <div>
          <b>Periodo inicio</b>
          <span className="v">{alumno.PerInicio}</span>
        </div>
        <div>
          <b>Periodo activo</b>
          <span className="v">{ajustes.periodo_actual || "—"}</span>
        </div>
        <div>
          <b>PrmGR</b>
          <span className="v">{alumno.PrmGR}</span>
        </div>
        <div>
          <b>Per (último)</b>
          <span className="v">{alumno.Per}</span>
        </div>
        <div>
          <b>Sit</b>
          <span className="v">{alumno.Sit}</span>
        </div>
      </motion.div>

      <div className="layout">
        <div className="form-col">
          <div className="card">
            <h2>
              <IconFields />
              Campos
            </h2>
            <form id="formCampos" onSubmit={(e) => e.preventDefault()}>
              {campos.map((c) => {
                const offClass = c.opcional && !c.incluido ? " field--off" : "";
                return (
                  <div key={c.name} className={"field" + (c.opcional ? " field-opcional" + offClass : "")}>
                    {c.opcional ? (
                      <div className="field-head">
                        <label>
                          {c.label} <span className="field-tag">opcional</span>
                          {c.de_plantilla && (
                            <span className="field-tag" title={`Campo detectado automáticamente en la plantilla [[${c.name}]]`}>
                              plantilla
                            </span>
                          )}
                        </label>
                        <label className="switch" title="Incluir u omitir esta línea en la constancia">
                          <input
                            type="checkbox"
                            checked={c.incluido}
                            onChange={(e) => setCampoValor(c.name, { incluido: e.target.checked })}
                          />
                          <span className="track" />
                        </label>
                      </div>
                    ) : (
                      <label>
                        {c.label}
                        {c.de_plantilla && (
                          <span className="field-tag" title={`Campo detectado automáticamente en la plantilla [[${c.name}]]`}>
                            plantilla
                          </span>
                        )}
                      </label>
                    )}

                    {c.tipo === "radio_genero" && (
                      <div className="radio-row">
                        <label>
                          <input
                            type="radio"
                            name="__genero__"
                            value="M"
                            required
                            checked={c.genero === "M"}
                            onChange={() => setCampoValor(c.name, { genero: "M" })}
                          />
                          <span>Masculino</span>
                        </label>
                        <label>
                          <input
                            type="radio"
                            name="__genero__"
                            value="F"
                            checked={c.genero === "F"}
                            onChange={() => setCampoValor(c.name, { genero: "F" })}
                          />
                          <span>Femenino</span>
                        </label>
                      </div>
                    )}

                    {c.tipo === "textarea" && (
                      <>
                        {c.name === "LINEA_LIBRE" && (
                          <div className="comodin-bar">
                            <select value={comodinSel} onChange={(e) => { setComodinSel(e.target.value); if (e.target.value) insertarComodin(e.target.value); }}>
                              <option value="">— Insertar comodín —</option>
                              {(comodines || []).map((cm) => (
                                <option key={cm.id} value={cm.id}>
                                  {cm.titulo}
                                </option>
                              ))}
                            </select>
                            <button type="button" className="btn-tonal" style={{ minHeight: 38, padding: "8px 14px" }} onClick={guardarComodin}>
                              + Guardar
                            </button>
                            <button type="button" className="icon-btn" title="Eliminar el comodín seleccionado" aria-label="Eliminar comodín" onClick={eliminarComodinSel}>
                              <IconTrash />
                            </button>
                          </div>
                        )}
                        <textarea
                          rows={2}
                          disabled={c.opcional && !c.incluido}
                          placeholder={c.opcional ? "Déjalo vacío para omitir esta línea" : undefined}
                          value={c.valor}
                          onChange={(e) => setCampoValor(c.name, { valor: e.target.value })}
                        />
                      </>
                    )}

                    {(c.tipo === "date_corto" || c.tipo === "date_largo") && (
                      <input
                        type="date"
                        disabled={c.opcional && !c.incluido}
                        value={c.iso}
                        onChange={(e) => setCampoValor(c.name, { iso: e.target.value })}
                      />
                    )}

                    {c.tipo === "date_rango" && (
                      <div className="date-row">
                        <div>
                          <div className="small">Inicio</div>
                          <input
                            type="date"
                            disabled={c.opcional && !c.incluido}
                            value={c.iso_inicio}
                            onChange={(e) => setCampoValor(c.name, { iso_inicio: e.target.value })}
                          />
                        </div>
                        <div>
                          <div className="small">Fin</div>
                          <input
                            type="date"
                            disabled={c.opcional && !c.incluido}
                            value={c.iso_fin}
                            onChange={(e) => setCampoValor(c.name, { iso_fin: e.target.value })}
                          />
                        </div>
                      </div>
                    )}

                    {c.tipo === "text" && (
                      <input
                        type="text"
                        disabled={c.opcional && !c.incluido}
                        value={c.valor}
                        onChange={(e) => setCampoValor(c.name, { valor: e.target.value })}
                      />
                    )}
                  </div>
                );
              })}

              <div className="hr" />
              <div className="actions">
                <button type="button" disabled={descargando !== null} onClick={() => descargar("docx")}>
                  <IconDownload />
                  Descargar .docx
                </button>
                <button id="btnPdf" type="button" className="btn-tonal" disabled={descargando !== null} onClick={() => descargar("pdf")}>
                  <IconDownload />
                  Descargar .pdf
                </button>
              </div>
            </form>
          </div>
        </div>

        <div className="preview-col">
          <div className="card">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <h2 style={{ margin: 0 }}>
                <IconEye />
                Vista previa
              </h2>
              <span
                className="preview-status"
                role="status"
                aria-live="polite"
                style={{
                  borderColor: statusError ? "var(--error)" : "var(--outline-variant)",
                  background: statusError ? "var(--error-container)" : "var(--surface)",
                  color: statusError ? "var(--on-error-container)" : "var(--on-surface-variant)",
                }}
              >
                {status}
              </span>
            </div>
            <div className={"pdf-frame-wrap" + (cargando ? " pdf-frame-wrap--cargando" : "")}>
              <motion.iframe
                id="pdfFrame"
                ref={iframeRef}
                title="Vista previa PDF"
                className={"pdf-frame" + (cargando ? " pdf-frame--cargando" : "")}
                animate={{ opacity: !hasPreview ? 0 : cargando ? 0.35 : 1 }}
                transition={{ duration: reduced ? 0 : 0.22 }}
              />
              <div className={"pdf-skeleton" + (cargando ? " visible" : "")}>
                <span className="skeleton">{skeletonTexto}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .layout { display: grid; grid-template-columns: 400px 1fr; gap: 16px; align-items: start; }
        @media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } }
        .preview-col { position: sticky; top: 84px; }
        .radio-row { display: flex; gap: 10px; flex-wrap: wrap; }
        .radio-row label { display: flex; align-items: center; gap: 8px; cursor: pointer; padding: 9px 16px; border: 1.5px solid var(--outline-variant); border-radius: var(--radius-pill); color: var(--on-surface); font-weight: 500; font-size: 14px; transition: border-color .15s, background .15s; }
        .radio-row label:hover { border-color: var(--outline); }
        .radio-row input { accent-color: var(--primary); width: 18px; height: 18px; }
        .radio-row input:checked + span { color: var(--primary); font-weight: 600; }
        .date-row { display: flex; gap: 10px; align-items: flex-end; }
        .date-row > div { flex: 1; }
        .date-row .small { font-size: 12px; color: var(--on-surface-variant); margin-bottom: 6px; font-weight: 600; }
        .comodin-bar { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
        .comodin-bar select { flex: 1; }
        .pdf-frame-wrap { position: relative; width: 100%; height: calc(100vh - 150px); min-height: 720px; border-radius: var(--radius-sm); transition: box-shadow var(--dur-slow) var(--ease-emph); }
        .pdf-frame-wrap.pdf-frame-wrap--cargando { box-shadow: 0 0 0 3px color-mix(in srgb, var(--secondary) 45%, transparent); }
        .pdf-frame { width: 100%; height: 100%; border: 1px solid var(--outline-variant); border-radius: var(--radius-sm); background: var(--surface); position: absolute; inset: 0; }
        .pdf-skeleton { position: absolute; inset: 0; border-radius: var(--radius-sm); display: none; align-items: center; justify-content: center; text-align: center; padding: 24px; pointer-events: none; }
        .pdf-skeleton.visible { display: flex; }
        .pdf-skeleton span { background: var(--surface-1); border: 1px solid var(--outline-variant); border-radius: var(--radius-pill); padding: 8px 18px; font-size: 13px; font-weight: 600; color: var(--on-surface-variant); box-shadow: var(--elev-1); }
        .alumno-info { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px 16px; font-size: 13px; color: var(--on-surface-variant); padding: 14px 18px; border: 1px solid var(--outline-variant); border-radius: var(--radius-md); background: var(--surface-1); margin-bottom: 16px; box-shadow: var(--elev-1); }
        .alumno-info b { color: var(--on-surface); display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .4px; margin-bottom: 2px; }
        .alumno-info .v { font-size: 15px; color: var(--on-surface); }
        @media (max-width: 560px) { .alumno-info { grid-template-columns: 1fr 1fr; } }
      `}</style>
    </motion.div>
  );
}
