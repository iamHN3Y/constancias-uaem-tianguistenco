/**
 * Cliente HTTP tipado para /api/v1/*. Todas las respuestas de error del
 * backend tienen la forma {"error": "mensaje"} (ver el exception handler en
 * app/main.py) — ApiError expone ese mensaje tal cual para mostrarlo en la UI.
 */

const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function parseErrorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (data && typeof data.error === "string") return data.error;
    if (data && typeof data.detail === "string") return data.detail;
  } catch {
    /* respuesta sin JSON */
  }
  return `Error ${res.status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers:
      init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json", ...(init?.headers || {}) }
        : init?.headers,
  });
  if (!res.ok) {
    throw new ApiError(await parseErrorMessage(res), res.status);
  }
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }
  return undefined as T;
}

function getJSON<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}
function postJSON<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
}
function delJSON<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}

async function requestBlob(path: string, init?: RequestInit, signal?: AbortSignal): Promise<Blob> {
  const res = await fetch(`${BASE}${path}`, { ...init, signal });
  if (!res.ok) throw new ApiError(await parseErrorMessage(res), res.status);
  return res.blob();
}

// ---------- Tipos ----------

export type Rol = "admin" | "invitado";

export interface Session {
  rol: Rol;
  es_admin: boolean;
}

export interface DatosMeta {
  filas: number;
  filename: string;
  fecha_carga: string;
}

export interface NuevoIngresoMeta extends DatosMeta {
  periodo: string;
}

export interface Ajustes {
  periodo_actual?: string;
  periodo_fecha_inicio?: string;
  periodo_fecha_fin?: string;
  [key: string]: unknown;
}

export interface PlantillaHistorialItem {
  nombre: string;
  fecha: string;
}

export interface PlantillaInfo {
  filename: string;
  placeholders: string[];
  avisos: string[];
  fecha_carga: string;
}

export interface PlantillaItem {
  slug: string;
  nombre: string;
  info: PlantillaInfo | null;
  historial: PlantillaHistorialItem[];
}

export interface HomeData {
  datos: DatosMeta | null;
  ni: NuevoIngresoMeta | null;
  plantillas: PlantillaItem[];
  ajustes: Ajustes;
  es_admin: boolean;
}

export interface Alumno {
  Cuenta: string;
  NombreAlumno: string;
  Plan?: string;
  PerInicio?: string;
  PrmGR?: string;
  Per?: string;
  Sit?: string;
  Sexo?: string;
  _origen?: string;
  [key: string]: unknown;
}

export interface BuscarCuentaResponse {
  tipo: "cuenta";
  cuenta: string;
  alumno: Alumno;
}
export interface BuscarNombreResponse {
  tipo: "nombre";
  resultados: Alumno[];
}
export type BuscarResponse = BuscarCuentaResponse | BuscarNombreResponse;

export interface CampoForm {
  name: string;
  label: string;
  tipo: "text" | "textarea" | "date_corto" | "date_largo" | "date_rango" | "radio_genero" | "hidden";
  valor: string;
  iso: string;
  iso_inicio: string;
  iso_fin: string;
  genero: string;
  opcional: boolean;
  de_plantilla: boolean;
}

export interface GenerarCamposResponse {
  alumno: Alumno;
  plantilla: PlantillaInfo;
  plantilla_slug: string;
  plantilla_nombre: string;
  campos: CampoForm[];
  ajustes: Ajustes;
}

export interface Comodin {
  id: string;
  titulo: string;
  texto: string;
}

export interface CarrerasCatalogo {
  carreras: Record<string, string>;
  duraciones: Record<string, number>;
  duracion_default: number;
}

export interface SaludDatos {
  total: number;
  sin_sexo: number;
  nuevo_ingreso: number;
}

export interface DatosPageResponse {
  datos: DatosMeta | null;
  ni: NuevoIngresoMeta | null;
  salud: SaludDatos;
  ajustes: Ajustes;
}

// ---------- Sesión ----------

export const api = {
  login: (rol: Rol, password = "") => postJSON<{ rol: Rol }>("/login", { rol, password }),
  logout: () => postJSON<{ ok: boolean }>("/logout"),
  session: () => getJSON<Session>("/session"),

  home: () => getJSON<HomeData>("/home"),
  buscar: (cuenta: string, plantilla = "") => postJSON<BuscarResponse>("/buscar", { cuenta, plantilla }),
  buscarNombre: (q: string) => getJSON<{ resultados: Alumno[] }>(`/buscar/nombre?q=${encodeURIComponent(q)}`),
  guardarAjustes: (body: { periodo_actual: string; periodo_inicio: string; periodo_fin: string }) =>
    postJSON<{ ok: boolean; ajustes: Ajustes }>("/ajustes", body),

  datosInfo: () => getJSON<DatosPageResponse>("/datos"),
  datosUpload: (file: File) => {
    const fd = new FormData();
    fd.append("archivo", file);
    return request<{ ok: boolean; datos: DatosMeta }>("/datos/upload", { method: "POST", body: fd });
  },
  nuevoIngresoUpload: (file: File) => {
    const fd = new FormData();
    fd.append("archivo", file);
    return request<{ ok: boolean; ni: NuevoIngresoMeta }>("/datos/nuevo-ingreso", { method: "POST", body: fd });
  },
  nuevoIngresoEliminar: () => postJSON<{ ok: boolean }>("/datos/nuevo-ingreso/eliminar"),

  plantillasList: () => getJSON<{ items: PlantillaItem[] }>("/plantillas"),
  plantillaCrear: (nombre: string, file: File) => {
    const fd = new FormData();
    fd.append("nombre", nombre);
    fd.append("archivo", file);
    return request<{ ok: boolean; slug: string }>("/plantillas/crear", { method: "POST", body: fd });
  },
  plantillaUpload: (slug: string, file: File) => {
    const fd = new FormData();
    fd.append("archivo", file);
    return request<{ ok: boolean; info: PlantillaInfo }>(`/plantillas/${slug}/upload`, { method: "POST", body: fd });
  },
  plantillaDownloadUrl: (slug: string) => `${BASE}/plantillas/${slug}/download`,
  plantillaRestaurar: (slug: string, nombre: string) =>
    postJSON<{ ok: boolean; info: PlantillaInfo }>(`/plantillas/${slug}/restaurar`, { nombre }),
  plantillaEliminar: (slug: string) => postJSON<{ ok: boolean }>(`/plantillas/${slug}/eliminar`),

  carreras: () => getJSON<CarrerasCatalogo>("/carreras"),
  carreraGuardar: (codigo: string, nombre: string) =>
    postJSON<{ ok: boolean; catalogo: CarrerasCatalogo }>("/carreras/carrera", { codigo, nombre }),
  carreraEliminar: (codigo: string) =>
    postJSON<{ ok: boolean; catalogo: CarrerasCatalogo }>("/carreras/carrera/eliminar", { codigo }),
  duracionGuardar: (plan: string, semestres: string) =>
    postJSON<{ ok: boolean; catalogo: CarrerasCatalogo }>("/carreras/duracion", { plan, semestres }),
  duracionEliminar: (plan: string) =>
    postJSON<{ ok: boolean; catalogo: CarrerasCatalogo }>("/carreras/duracion/eliminar", { plan }),

  comodines: () => getJSON<Comodin[]>("/comodines"),
  comodinCrear: (titulo: string, texto: string) => postJSON<Comodin>("/comodines", { titulo, texto }),
  comodinEliminar: (cid: string) => delJSON<{ ok: boolean }>(`/comodines/${cid}`),

  generarCampos: (cuenta: string, plantilla = "") =>
    getJSON<GenerarCamposResponse>(`/generar/campos?cuenta=${encodeURIComponent(cuenta)}&plantilla=${encodeURIComponent(plantilla)}`),

  previewPdf: (formData: FormData, signal?: AbortSignal) =>
    requestBlob("/preview.pdf", { method: "POST", body: formData }, signal),
  generarDocx: (formData: FormData) => requestBlob("/generar/docx", { method: "POST", body: formData }),
  generarPdf: (formData: FormData) => requestBlob("/generar/pdf", { method: "POST", body: formData }),
};
