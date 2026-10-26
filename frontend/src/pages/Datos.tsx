import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { CountUp } from "../components/CountUp";
import { Header } from "../components/Header";
import { IconCalendar, IconInfo, IconUpload } from "../components/Icons";
import { Notice } from "../components/Notice";
import { StaggerItem, StaggerList } from "../components/Stagger";
import { useDialog } from "../context/DialogContext";
import { useToast } from "../context/ToastContext";
import { useTourSteps } from "../context/TourContext";

export function Datos() {
  const { avisar } = useToast();
  const { confirmar } = useDialog();
  const queryClient = useQueryClient();
  const archivoRef = useRef<HTMLInputElement>(null);
  const archivoNiRef = useRef<HTMLInputElement>(null);
  const [errorDatos, setErrorDatos] = useState<string | null>(null);
  const [errorNi, setErrorNi] = useState<string | null>(null);

  const { data, isLoading } = useQuery({ queryKey: ["datos-info"], queryFn: api.datosInfo });

  useTourSteps(data ? "datos" : null, [
    { sel: "#tour-estado", title: "Estado actual", text: "Aquí ves qué archivo de alumnos está cargado y cuántos registros tiene." },
    { sel: "#tour-salud", title: "Panel de salud", text: "Resumen rápido del padrón: cuántos alumnos hay, a cuántos les falta la columna Sexo, y cuántos solo existen en «nuevo ingreso»." },
    { sel: "#archivo", title: "Subir o reemplazar", text: "Elige un archivo .xls, .xlsx o .csv y pulsa Subir. El nuevo reemplaza por completo al anterior." },
    { sel: "#tour-nuevo-ingreso", title: "Alumnos de nuevo ingreso", text: "Archivo aparte para alumnos que todavía no están en el padrón principal. Si una cuenta existe en ambos, siempre gana el padrón principal." },
  ]);

  const invalidar = () => queryClient.invalidateQueries({ queryKey: ["datos-info"] });

  const subirDatos = useMutation({
    mutationFn: (file: File) => api.datosUpload(file),
    onSuccess: async () => {
      setErrorDatos(null);
      avisar("Datos cargados correctamente.", "exito");
      if (archivoRef.current) archivoRef.current.value = "";
      await invalidar();
    },
    onError: (e: unknown) => setErrorDatos(e instanceof ApiError ? e.message : "No se pudo subir el archivo."),
  });

  const subirNi = useMutation({
    mutationFn: (file: File) => api.nuevoIngresoUpload(file),
    onSuccess: async () => {
      setErrorNi(null);
      avisar("Archivo de nuevo ingreso cargado.", "exito");
      if (archivoNiRef.current) archivoNiRef.current.value = "";
      await invalidar();
    },
    onError: (e: unknown) => setErrorNi(e instanceof ApiError ? e.message : "No se pudo subir el archivo."),
  });

  const eliminarNi = useMutation({
    mutationFn: api.nuevoIngresoEliminar,
    onSuccess: async () => {
      avisar("Archivo eliminado.", "exito");
      await invalidar();
    },
  });

  async function onSubmitDatos(e: React.FormEvent) {
    e.preventDefault();
    const file = archivoRef.current?.files?.[0];
    if (!file) return;
    if (data?.datos) {
      const ok = await confirmar({
        titulo: "¿Reemplazar padrón?",
        mensaje: `Esto reemplazará «${data.datos.filename}» y sus ${data.datos.filas} alumnos.`,
        peligro: true,
        textoConfirmar: "Reemplazar",
      });
      if (!ok) return;
    }
    subirDatos.mutate(file);
  }

  async function onSubmitNi(e: React.FormEvent) {
    e.preventDefault();
    const file = archivoNiRef.current?.files?.[0];
    if (!file) return;
    if (data?.ni) {
      const ok = await confirmar({
        titulo: "¿Reemplazar archivo de nuevo ingreso?",
        mensaje: `Esto reemplazará «${data.ni.filename}» y sus ${data.ni.filas} alumnos.`,
        peligro: true,
        textoConfirmar: "Reemplazar",
      });
      if (!ok) return;
    }
    subirNi.mutate(file);
  }

  async function onEliminarNi() {
    const ok = await confirmar({
      titulo: "¿Eliminar archivo?",
      mensaje: "¿Eliminar el archivo de alumnos de nuevo ingreso? Esta acción no se puede deshacer.",
      peligro: true,
      textoConfirmar: "Eliminar",
    });
    if (ok) eliminarNi.mutate();
  }

  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <Header title="Datos de alumnos" subtitle="El archivo persiste hasta que lo reemplaces." backTo="/" />

      {isLoading || !data ? (
        <div className="card skeleton" style={{ height: 140 }} />
      ) : (
        <StaggerList>
          <StaggerItem>
            <div id="tour-estado" className="card">
              <h2>
                <IconInfo />
                Estado actual — padrón principal
              </h2>
              {data.datos ? (
                <p>
                  <strong>{data.datos.filename}</strong>
                  <br />
                  {data.datos.filas} alumnos · cargado {data.datos.fecha_carga}
                </p>
              ) : (
                <p>Aún no se ha cargado ningún archivo.</p>
              )}
            </div>
          </StaggerItem>

          <StaggerItem>
            <div id="tour-salud" className="card">
              <h2>
                <IconInfo />
                Panel de salud
              </h2>
              <p style={{ margin: "0 0 6px" }}>
                Total en el padrón principal: <strong><CountUp value={data.salud.total} /></strong>
              </p>
              <p style={{ margin: "0 0 6px" }}>
                Sin columna Sexo o con Sexo vacío: <strong><CountUp value={data.salud.sin_sexo} /></strong> (el
                género no se prellena para esos alumnos)
              </p>
              <p style={{ margin: 0 }}>
                Alumnos disponibles solo por «nuevo ingreso»: <strong><CountUp value={data.salud.nuevo_ingreso} /></strong>
              </p>
              {!data.ajustes.periodo_actual && (
                <div style={{ marginTop: 14 }}>
                  <Notice error>
                    No hay periodo activo configurado (en la pantalla principal). Mientras tanto, el semestre de
                    los alumnos de nuevo ingreso saldrá vacío.
                  </Notice>
                </div>
              )}
            </div>
          </StaggerItem>

          <StaggerItem>
            <div className="card">
              <h2>
                <IconUpload />
                Subir / reemplazar padrón principal
              </h2>
              <p>
                Formatos aceptados: <code>.xls</code>, <code>.xlsx</code>, <code>.csv</code>. El archivo nuevo
                sustituye al anterior.
              </p>
              {errorDatos && <Notice error>{errorDatos}</Notice>}
              <form onSubmit={onSubmitDatos}>
                <div className="field">
                  <label htmlFor="archivo">Archivo de datos</label>
                  <input id="archivo" ref={archivoRef} type="file" accept=".xls,.xlsx,.csv" required />
                </div>
                <div className="actions">
                  <button type="submit" disabled={subirDatos.isPending}>
                    Subir archivo
                  </button>
                </div>
              </form>
            </div>
          </StaggerItem>

          <StaggerItem>
            <div id="tour-nuevo-ingreso" className="card">
              <h2>
                <IconCalendar />
                Alumnos de nuevo ingreso
              </h2>
              <p>
                Archivo secundario (Excel de control escolar) para alumnos que aún no aparecen en el padrón
                principal. Se consulta <strong>solo cuando la cuenta no está en el padrón principal</strong>: si
                un alumno existe en ambos, siempre gana el padrón principal. No se fusiona con{" "}
                <code>datos.csv</code>; cuando un alumno avanza de semestre y aparece en un padrón principal
                nuevo, se elimina automáticamente de aquí.
              </p>
              {data.ni ? (
                <>
                  <p>
                    <strong>{data.ni.filename}</strong>
                    <br />
                    {data.ni.filas} alumnos · cargado {data.ni.fecha_carga}
                    {data.ni.periodo && ` · periodo ${data.ni.periodo}`}
                  </p>
                  <div className="actions">
                    <button type="button" className="btn-tonal" onClick={onEliminarNi} disabled={eliminarNi.isPending}>
                      Eliminar archivo
                    </button>
                  </div>
                </>
              ) : (
                <p>No hay archivo de nuevo ingreso cargado todavía.</p>
              )}
              {errorNi && <Notice error>{errorNi}</Notice>}
              <form onSubmit={onSubmitNi}>
                <div className="field">
                  <label htmlFor="archivoNi">Excel de alumnos de nuevo ingreso</label>
                  <input id="archivoNi" ref={archivoNiRef} type="file" accept=".xls,.xlsx" required />
                </div>
                <div className="actions">
                  <button type="submit" disabled={subirNi.isPending}>
                    Subir archivo
                  </button>
                </div>
              </form>
            </div>
          </StaggerItem>
        </StaggerList>
      )}
    </div>
  );
}
