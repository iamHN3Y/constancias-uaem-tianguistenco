import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, type Alumno } from "../api/client";
import { Header } from "../components/Header";
import { IconAdmin, IconCalendar, IconCareer, IconFile, IconInvitado, IconSearch } from "../components/Icons";
import { Notice } from "../components/Notice";
import { StaggerItem, StaggerList } from "../components/Stagger";
import { useToast } from "../context/ToastContext";
import { useTourSteps } from "../context/TourContext";

export function Home() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { avisar } = useToast();
  const reduced = useReducedMotion();
  const cuentaRef = useRef<HTMLInputElement>(null);

  const { data, isLoading } = useQuery({ queryKey: ["home"], queryFn: api.home });

  const [consulta, setConsulta] = useState("");
  const [plantilla, setPlantilla] = useState("");
  const [resultados, setResultados] = useState<Alumno[] | null>(null);
  const [errorBusqueda, setErrorBusqueda] = useState<string | null>(null);

  const [periodoActual, setPeriodoActual] = useState("");
  const [periodoInicio, setPeriodoInicio] = useState("");
  const [periodoFin, setPeriodoFin] = useState("");
  const ajustesInicializados = useRef(false);

  useEffect(() => {
    if (data && !ajustesInicializados.current) {
      setPeriodoActual(data.ajustes.periodo_actual || "");
      setPeriodoInicio(data.ajustes.periodo_fecha_inicio || "");
      setPeriodoFin(data.ajustes.periodo_fecha_fin || "");
      ajustesInicializados.current = true;
    }
  }, [data]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "/") return;
      const el = document.activeElement as HTMLElement | null;
      const enCampo =
        el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
      if (enCampo) return;
      e.preventDefault();
      cuentaRef.current?.focus();
      cuentaRef.current?.select();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const buscarMutation = useMutation({
    mutationFn: (c: string) => api.buscar(c, plantilla),
    onSuccess: (res) => {
      setErrorBusqueda(null);
      if (res.tipo === "cuenta") {
        navigate(`/generar?cuenta=${encodeURIComponent(res.cuenta)}&plantilla=${encodeURIComponent(plantilla)}`);
      } else {
        setResultados(res.resultados);
      }
    },
    onError: (e: unknown) => {
      setResultados(null);
      setErrorBusqueda(e instanceof ApiError ? e.message : "No se pudo buscar.");
    },
  });

  const ajustesMutation = useMutation({
    mutationFn: () => api.guardarAjustes({ periodo_actual: periodoActual, periodo_inicio: periodoInicio, periodo_fin: periodoFin }),
    onSuccess: async () => {
      avisar("Periodo guardado.", "exito");
      await queryClient.invalidateQueries({ queryKey: ["home"] });
    },
    onError: (e: unknown) => avisar(e instanceof ApiError ? e.message : "No se pudo guardar el periodo.", "error"),
  });

  const logoutMutation = useMutation({
    mutationFn: api.logout,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["session"] });
      navigate("/login", { replace: true });
    },
  });

  const plantillasListas = data ? data.plantillas.filter((p) => p.info) : [];

  useEffect(() => {
    if (plantillasListas.length === 1 && plantilla === "") {
      setPlantilla(plantillasListas[0].slug);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plantillasListas.length]);

  function irAGenerar(cuenta: string) {
    navigate(`/generar?cuenta=${encodeURIComponent(cuenta)}&plantilla=${encodeURIComponent(plantilla)}`);
  }

  useTourSteps(
    data ? `home-${data.es_admin ? "admin" : "invitado"}` : null,
    data?.es_admin
      ? [
          { sel: ".chip", title: "Tu sesión", text: "Aquí ves con qué rol entraste: Administrador (puede subir datos y plantillas) o Invitado (solo genera)." },
          { sel: "#cuenta", title: "Generar una constancia", text: "Escribe el número de cuenta o parte del nombre del alumno y pulsa «Buscar y continuar»." },
          { sel: "#selPlantilla", title: "Tipo de constancia", text: "Si hay varias plantillas (general, inglés, prácticas…), elige aquí cuál usar." },
          { sel: "#periodo_actual", title: "Periodo activo", text: "Define el periodo en curso (ej. 2026A) una vez por semestre. Con él se calcula automáticamente el semestre del alumno (comparándolo con su periodo de ingreso)." },
          { sel: "#periodo_inicio", title: "Fechas del periodo", text: "Guarda aquí las fechas reales de inicio y fin del semestre según el calendario escolar: todas las constancias saldrán prellenadas con ellas." },
          { sel: "#tour-datos", title: "Datos de alumnos", text: "Consulta y reemplaza aquí la base de datos (.xls, .xlsx o .csv). El archivo se conserva hasta que subas otro." },
          { sel: "#tour-plantilla", title: "Plantillas", text: "Gestiona los documentos .docx con placeholders [[CAMPO]]. Puedes tener varias: constancia general, en inglés, de prácticas…" },
          { sel: "#tour-carreras", title: "Carreras", text: "Cuando abran una carrera nueva o cambie la duración de un plan, dala de alta aquí. Sin programador." },
        ]
      : [
          { sel: ".chip", title: "Tu sesión", text: "Aquí ves con qué rol entraste: Administrador (puede subir datos y plantillas) o Invitado (solo genera)." },
          { sel: "#cuenta", title: "Generar una constancia", text: "Escribe el número de cuenta o parte del nombre del alumno y pulsa «Buscar y continuar»." },
        ]
  );

  if (isLoading || !data) {
    return (
      <div className="page">
        <Header title="Generador de Constancias" subtitle="Centro Universitario UAEM Tianguistenco" />
        <div className="card skeleton" style={{ height: 140 }} />
      </div>
    );
  }

  const esAdmin = data.es_admin;

  return (
    <div className="page">
      <Header title="Generador de Constancias" subtitle="Centro Universitario UAEM Tianguistenco">
        <span className={"chip" + (esAdmin ? " chip-primary" : "")}>
          {esAdmin ? <IconAdmin style={{ width: 16, height: 16 }} /> : <IconInvitado style={{ width: 16, height: 16 }} />}
          {esAdmin ? "Administrador" : "Invitado"}
        </span>
        <button type="button" className="btn-text" onClick={() => logoutMutation.mutate()}>
          Cerrar sesión
        </button>
      </Header>

      {resultados && (
        <div className="card" tabIndex={-1}>
          <h2>
            <IconSearch />
            Resultados para «{consulta}»
          </h2>
          {resultados.length > 0 ? (
            <StaggerList>
              {resultados.map((r) => (
                <StaggerItem key={r.Cuenta}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 12,
                      padding: "10px 0",
                      borderTop: "1px solid var(--outline-variant)",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600 }}>{r.NombreAlumno}</div>
                      <div style={{ fontSize: 13, color: "var(--on-surface-variant)" }}>
                        Cuenta {r.Cuenta} · {r.Plan}
                      </div>
                    </div>
                    <button type="button" className="btn-tonal" onClick={() => irAGenerar(r.Cuenta)}>
                      Generar
                    </button>
                  </div>
                </StaggerItem>
              ))}
            </StaggerList>
          ) : (
            <p>Ningún alumno coincide con ese nombre. Revisa la ortografía (los acentos no importan).</p>
          )}
          {resultados.length >= 20 && (
            <p style={{ fontSize: 13, color: "var(--on-surface-variant)", marginTop: 10 }}>
              Se muestran los primeros 20. Escribe más palabras del nombre para afinar.
            </p>
          )}
        </div>
      )}

      {esAdmin && (
        <div className="grid">
          <div className="card">
            <h2>
              <IconCalendar />
              Periodo activo
            </h2>
            <p>
              Se configura <strong>una vez por semestre</strong>. El periodo (ej. <code>2026A</code>) se usa para
              calcular el semestre del alumno; las fechas prellenan «Inicio/Fin del periodo» en todas las
              constancias.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                ajustesMutation.mutate();
              }}
            >
              <div className="field">
                <label htmlFor="periodo_actual">Periodo</label>
                <input
                  id="periodo_actual"
                  type="text"
                  maxLength={6}
                  placeholder="2026A"
                  pattern="[0-9]{4}[ABab]"
                  required
                  value={periodoActual}
                  onChange={(e) => setPeriodoActual(e.target.value)}
                />
              </div>
              <div className="field" style={{ display: "flex", gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <label htmlFor="periodo_inicio">Inicio del periodo</label>
                  <input
                    id="periodo_inicio"
                    type="date"
                    value={periodoInicio}
                    onChange={(e) => setPeriodoInicio(e.target.value)}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label htmlFor="periodo_fin">Fin del periodo</label>
                  <input id="periodo_fin" type="date" value={periodoFin} onChange={(e) => setPeriodoFin(e.target.value)} />
                </div>
              </div>
              <p style={{ fontSize: 12, color: "var(--on-surface-variant)", margin: "-4px 0 12px" }}>
                Si las dejas vacías se usan las fechas típicas (02 de febrero / 02 de agosto). Siempre puedes
                ajustarlas en una constancia concreta.
              </p>
              <div className="actions">
                <button type="submit" disabled={ajustesMutation.isPending}>
                  Guardar periodo
                </button>
              </div>
            </form>
          </div>

          <div id="tour-datos" className={"card" + (!data.datos ? " card--protagonista" : "")}>
            <h2>
              <IconFile />
              Datos cargados
            </h2>
            {data.datos ? (
              <p>
                <strong>{data.datos.filename}</strong>
                <br />
                {data.datos.filas} alumnos · cargado {data.datos.fecha_carga}
              </p>
            ) : (
              <p>No hay datos cargados todavía.</p>
            )}
            {data.ni && (
              <p>
                <strong>{data.ni.filename}</strong> <span className="field-tag">nuevo ingreso</span>
                <br />
                {data.ni.filas} alumnos · periodo {data.ni.periodo} · cargado {data.ni.fecha_carga}
              </p>
            )}
            <div className="actions">
              <a className="btn btn-tonal" href="/datos" onClick={(e) => { e.preventDefault(); navigate("/datos"); }}>
                Gestionar datos
              </a>
            </div>
          </div>
        </div>
      )}

      {!esAdmin && (
        <div className="card">
          <h2>Estado del sistema</h2>
          <p style={{ margin: 0 }}>
            Periodo activo <strong>{data.ajustes.periodo_actual || "—"}</strong>
            {data.datos && ` · ${data.datos.filas} alumnos cargados`}
            {data.ni && ` · ${data.ni.filas} de nuevo ingreso`}
          </p>
        </div>
      )}

      <motion.div layoutId={reduced ? undefined : "tarjeta-generar"} className={"card" + (data.datos && plantillasListas.length ? " card--protagonista" : "")}>
        <h2>
          <IconSearch />
          Generar constancia
        </h2>
        {!data.datos ? (
          <p>{esAdmin ? "Sube primero un archivo de datos." : "No hay datos cargados. Pídele al administrador que los suba."}</p>
        ) : plantillasListas.length === 0 ? (
          <p>
            {esAdmin ? (
              <>
                No hay plantilla cargada.{" "}
                <a href="/plantillas" onClick={(e) => { e.preventDefault(); navigate("/plantillas"); }}>
                  Sube una
                </a>{" "}
                antes de generar.
              </>
            ) : (
              "No hay plantilla cargada. Pídele al administrador que la suba."
            )}
          </p>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setErrorBusqueda(null);
              setResultados(null);
              buscarMutation.mutate(consulta);
            }}
          >
            <div className="field">
              <label htmlFor="cuenta">
                Número de cuenta o nombre <span className="hint">— pulsa <kbd>/</kbd> para saltar aquí</span>
              </label>
              <input
                id="cuenta"
                ref={cuentaRef}
                type="text"
                placeholder="Ej. 2014694 o «perez juan»"
                required
                autoFocus
                value={consulta}
                onChange={(e) => setConsulta(e.target.value)}
              />
            </div>
            {plantillasListas.length > 1 ? (
              <div className="field">
                <label htmlFor="selPlantilla">Tipo de constancia</label>
                <select id="selPlantilla" value={plantilla} onChange={(e) => setPlantilla(e.target.value)}>
                  {plantillasListas.map((it) => (
                    <option key={it.slug} value={it.slug}>
                      {it.nombre}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
            {errorBusqueda && <Notice error>{errorBusqueda}</Notice>}
            <div className="actions">
              <button type="submit" disabled={buscarMutation.isPending}>
                <IconSearch />
                Buscar y continuar
              </button>
            </div>
          </form>
        )}
      </motion.div>

      {esAdmin && (
        <div className="grid">
          <div id="tour-plantilla" className="card">
            <h2>
              <IconFile />
              Plantillas
            </h2>
            {plantillasListas.length > 0 ? (
              <p>
                {plantillasListas.length} plantilla{plantillasListas.length !== 1 ? "s" : ""} activa
                {plantillasListas.length !== 1 ? "s" : ""}: {plantillasListas.map((it) => it.nombre).join(" · ")}
              </p>
            ) : (
              <p>No hay plantilla cargada todavía.</p>
            )}
            <div className="actions">
              <a className="btn btn-tonal" href="/plantillas" onClick={(e) => { e.preventDefault(); navigate("/plantillas"); }}>
                Gestionar plantillas
              </a>
            </div>
          </div>

          <div id="tour-carreras" className="card">
            <h2>
              <IconCareer />
              Carreras
            </h2>
            <p>Catálogo de carreras y duración de planes. Aquí das de alta una carrera nueva sin tocar código.</p>
            <div className="actions">
              <a className="btn btn-tonal" href="/carreras" onClick={(e) => { e.preventDefault(); navigate("/carreras"); }}>
                Gestionar carreras
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
