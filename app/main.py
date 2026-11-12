"""
Generador de Constancias — backend FastAPI.

Flujo:
  1. Subir datos (.xls/.xlsx/.csv) — persisten hasta que se reemplacen.
  2. Hay UNA plantilla universal .docx con placeholders [[CAMPO]].
  3. Buscar alumno por número de cuenta.
  4. Formulario auto-rellenado con los placeholders detectados.
  5. Vista previa en PDF (iframe) que se actualiza con cada cambio.
  6. Descarga final en .docx o .pdf.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import quote

import pandas as pd
from fastapi import (
    BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
)
from fastapi.responses import (
    FileResponse, HTMLResponse, JSONResponse, RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import ayuda, catalogo, derivar
from .carreras import Carreras
from .comodines import Comodines
from .docx_render import render
from .pdf import ConversionError, docx_a_pdf
from .plantilla_universal import RegistroPlantillas


# ---------- Paths ----------

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))
PLANTILLAS_DIR = os.path.join(DATA_DIR, "plantillas")
TMP_DIR = os.path.join(DATA_DIR, "tmp")
BOOTSTRAP_PLANTILLA = os.path.join(BASE_DIR, "bootstrap_plantillas", "universal.docx")
DATOS_CSV = os.path.join(DATA_DIR, "datos.csv")
NUEVO_INGRESO_CSV = os.path.join(DATA_DIR, "nuevo_ingreso.csv")
AJUSTES_FILE = os.path.join(DATA_DIR, "ajustes.json")
COMODINES_FILE = os.path.join(DATA_DIR, "comodines.json")
CARRERAS_FILE = os.path.join(DATA_DIR, "carreras.json")

# Pseudo-login: la cookie 'rol' vale 'admin' o 'invitado'.
# La contraseña no es para seguridad seria — solo gating básico de UI.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin2026")

for d in (DATA_DIR, PLANTILLAS_DIR, TMP_DIR):
    os.makedirs(d, exist_ok=True)


# ---------- App ----------

plantillas = RegistroPlantillas(PLANTILLAS_DIR)
comodines = Comodines(COMODINES_FILE)
carreras = Carreras(CARRERAS_FILE)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if os.path.isdir(TMP_DIR):
        for name in os.listdir(TMP_DIR):
            try:
                os.remove(os.path.join(TMP_DIR, name))
            except OSError:
                pass
    plantillas.seed_si_vacio(BOOTSTRAP_PLANTILLA)
    yield


app = FastAPI(title="Generador de Constancias", lifespan=_lifespan)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
# Versión de los estáticos: súbela al cambiar CSS/JS para que los navegadores
# no usen la copia vieja en caché.
templates.env.globals["V"] = "14"
templates.env.globals["ayuda_campo"] = ayuda.ayuda_campo
templates.env.filters["nombre_legible"] = derivar.formato_nombre


def _fecha_legible(valor) -> str:
    """'2026-11-10T23:44:52' → '10 nov 2026, 23:44'. Si no es ISO, lo deja igual."""
    try:
        d = datetime.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return str(valor or "")
    mes = derivar.MESES[d.month - 1][:3]
    return f"{d.day} {mes} {d.year}, {d:%H:%M}" if (d.hour or d.minute) else f"{d.day} {mes} {d.year}"


templates.env.filters["fecha_legible"] = _fecha_legible
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


# ---------- Auth (pseudo-login con cookie sin firmar) ----------

def get_rol(request: Request) -> str | None:
    return request.cookies.get("rol")


def es_admin(request: Request) -> bool:
    return get_rol(request) == "admin"


def _redir_a_login() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)


def _bloquear_si_no_admin(request: Request) -> RedirectResponse | None:
    rol = get_rol(request)
    if rol is None:
        return _redir_a_login()
    if rol != "admin":
        return RedirectResponse(url="/", status_code=303)
    return None


# ---------- Ajustes / sesión ----------

def cargar_ajustes() -> dict:
    if not os.path.exists(AJUSTES_FILE):
        return {"periodo_actual": ""}
    with open(AJUSTES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_ajustes(aj: dict):
    # Escritura atómica: nunca deja un ajustes.json a medias si el proceso muere.
    tmp = AJUSTES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(aj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, AJUSTES_FILE)


# ---------- Datos del Excel ----------

def datos_meta() -> dict | None:
    if not os.path.exists(DATOS_CSV):
        return None
    aj = cargar_ajustes()
    return {
        "filas": aj.get("datos_filas", 0),
        "filename": aj.get("datos_filename", ""),
        "fecha_carga": aj.get("datos_fecha_carga", ""),
    }


def leer_datos() -> pd.DataFrame:
    if not os.path.exists(DATOS_CSV):
        return pd.DataFrame()
    return pd.read_csv(DATOS_CSV, dtype=str, keep_default_na=False)


# Columnas que el sistema usa para prellenar el formulario. Al subir un
# archivo se emparejan sin importar mayúsculas, acentos ni espacios
# ("CUENTA", "per inicio", "Núm. cuenta" → columnas canónicas), para que un
# cambio de formato en el Excel de control escolar no rompa el sistema.
COLUMNAS_CANONICAS = ("Cuenta", "NombreAlumno", "Plan", "PerInicio", "PrmGR", "Per", "Sit", "Sexo")


def _clave_columna(nombre: str) -> str:
    s = unicodedata.normalize("NFKD", str(nombre))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    canonicas = {_clave_columna(c): c for c in COLUMNAS_CANONICAS}
    renombres = {}
    for col in df.columns:
        canon = canonicas.get(_clave_columna(col))
        if canon and canon != col:
            renombres[col] = canon
    return df.rename(columns=renombres) if renombres else df


def _normalizar_cuenta(serie: pd.Series) -> pd.Series:
    # Excel a veces entrega las cuentas como número flotante ("2014694.0").
    return serie.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def guardar_datos(upload_path: str, original_filename: str):
    ext = os.path.splitext(original_filename)[1].lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(upload_path, dtype=str, keep_default_na=False)
        else:
            df = pd.read_excel(upload_path, dtype=str)
            df = df.fillna("")
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo ({e}). Se conservan los datos anteriores.") from e

    df = _normalizar_columnas(df)
    if "Cuenta" not in df.columns:
        raise ValueError(
            "El archivo no tiene una columna 'Cuenta' (se buscó sin distinguir "
            "mayúsculas ni acentos). Se conservan los datos anteriores. "
            f"Columnas encontradas: {', '.join(map(str, df.columns[:12]))}"
        )
    if df.empty:
        raise ValueError("El archivo no tiene filas de alumnos. Se conservan los datos anteriores.")

    df["Cuenta"] = _normalizar_cuenta(df["Cuenta"])

    # Si hay columna Sexo, determinar el esquema: con valores 'H' presentes,
    # una 'M' significa Mujer; sin 'H', significa Masculino. Se decide una vez
    # por padrón y se guarda en ajustes (lo usa derivar.normalizar_genero).
    sexo_usa_h = False
    if "Sexo" in df.columns:
        vals = {str(v).strip().upper() for v in df["Sexo"]}
        sexo_usa_h = any(v.startswith("H") for v in vals)

    # Escritura atómica: el padrón anterior sigue íntegro si algo falla a medias.
    tmp = DATOS_CSV + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, DATOS_CSV)

    aj = cargar_ajustes()
    aj.update({
        "datos_filename": original_filename,
        "datos_fecha_carga": datetime.now().isoformat(timespec="seconds"),
        "datos_filas": int(len(df)),
        "datos_sexo_usa_h": sexo_usa_h,
    })
    guardar_ajustes(aj)

    # Purga automática: si algún alumno de nuevo ingreso ya avanzó de
    # semestre y aparece en el padrón académico normal, se quita de
    # nuevo_ingreso.csv para no dejar duplicados fantasma.
    _purgar_nuevo_ingreso(set(df["Cuenta"].astype(str).str.strip()))


def buscar_alumno(cuenta: str) -> dict | None:
    cuenta = str(cuenta).strip()
    df = leer_datos()
    if not df.empty and "Cuenta" in df.columns:
        fila = df.loc[df["Cuenta"].astype(str).str.strip() == cuenta]
        if not fila.empty:
            return {k: ("" if v is None else str(v)) for k, v in fila.iloc[0].to_dict().items()}

    # Fallback: solo si la cuenta no está en el padrón principal.
    dfni = leer_nuevo_ingreso()
    if not dfni.empty and "Cuenta" in dfni.columns:
        fila = dfni.loc[dfni["Cuenta"].astype(str).str.strip() == cuenta]
        if not fila.empty:
            reg = {k: ("" if v is None else str(v)) for k, v in fila.iloc[0].to_dict().items()}
            reg["_origen"] = "nuevo_ingreso"
            return reg
    return None


def _sin_acentos_lower(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def buscar_por_nombre(texto: str, limite: int = 20) -> list[dict]:
    """
    Alumnos cuyo nombre contiene todas las palabras buscadas, sin distinguir
    mayúsculas ni acentos. 'perez juan' encuentra 'PÉREZ / JUAN'.

    Busca primero en el padrón principal; completa con nuevo_ingreso.csv sin
    repetir cuentas que ya hayan salido del padrón.
    """
    palabras = [_sin_acentos_lower(p) for p in texto.split() if p.strip()]
    if not palabras:
        return []

    resultados: list[dict] = []
    vistos: set[str] = set()

    df = leer_datos()
    if not df.empty and "NombreAlumno" in df.columns:
        for _, fila in df.iterrows():
            nombre = _sin_acentos_lower(fila.get("NombreAlumno", ""))
            if not all(p in nombre for p in palabras):
                continue
            cuenta = str(fila.get("Cuenta", "")).strip()
            if cuenta in vistos:
                continue
            vistos.add(cuenta)
            resultados.append({k: str(v) for k, v in fila.to_dict().items()})
            if len(resultados) >= limite:
                return resultados

    dfni = leer_nuevo_ingreso()
    if not dfni.empty and "NombreAlumno" in dfni.columns:
        for _, fila in dfni.iterrows():
            if len(resultados) >= limite:
                break
            nombre = _sin_acentos_lower(fila.get("NombreAlumno", ""))
            if not all(p in nombre for p in palabras):
                continue
            cuenta = str(fila.get("Cuenta", "")).strip()
            if cuenta in vistos:
                continue
            vistos.add(cuenta)
            reg = {k: str(v) for k, v in fila.to_dict().items()}
            reg["_origen"] = "nuevo_ingreso"
            resultados.append(reg)

    return resultados


# ---------- Alumnos de nuevo ingreso (archivo secundario con fallback) ----------
#
# Fuente secundaria consultada SOLO cuando una cuenta no está en el padrón
# principal (datos.csv). Nunca se fusiona con él: vive aparte en
# nuevo_ingreso.csv y se purga sola cuando esas cuentas aparecen en un
# padrón nuevo (ver _purgar_nuevo_ingreso, llamada desde guardar_datos).

COLUMNAS_NUEVO_INGRESO = ("Cuenta", "Paterno", "Materno", "Nombres", "Plan", "Periodo")


def ni_meta() -> dict | None:
    if not os.path.exists(NUEVO_INGRESO_CSV):
        return None
    aj = cargar_ajustes()
    return {
        "filas": aj.get("ni_filas", 0),
        "filename": aj.get("ni_filename", ""),
        "fecha_carga": aj.get("ni_fecha_carga", ""),
        "periodo": aj.get("ni_periodo", ""),
    }


def leer_nuevo_ingreso() -> pd.DataFrame:
    if not os.path.exists(NUEVO_INGRESO_CSV):
        return pd.DataFrame()
    return pd.read_csv(NUEVO_INGRESO_CSV, dtype=str, keep_default_na=False)


def _fila_vacia_o_incompleta(fila) -> bool:
    """Descarta filas de título sueltas u otra basura: 3+ celdas vacías."""
    vacios = sum(1 for v in fila if str(v).strip() in ("", "nan", "NaN"))
    return vacios >= 3


def guardar_nuevo_ingreso(upload_path: str, original_filename: str):
    try:
        df = pd.read_excel(upload_path, header=None, dtype=str)
    except Exception as e:
        raise ValueError(
            f"No se pudo leer el archivo ({e}). Se conservan los datos anteriores."
        ) from e

    if df.shape[1] != 6:
        raise ValueError(
            "El archivo debe tener exactamente 6 columnas (Cuenta, Apellido paterno, "
            "Apellido materno, Nombre(s), Plan, Periodo). Se conservan los datos "
            f"anteriores. Columnas encontradas: {df.shape[1]}."
        )

    df = df.fillna("")
    df = df[~df.apply(_fila_vacia_o_incompleta, axis=1)].reset_index(drop=True)
    if df.empty:
        raise ValueError(
            "El archivo no tiene filas de alumnos utilizables. Se conservan los datos anteriores."
        )

    # Fila de encabezado falsa: si la primera fila trae la columna 0 (Cuenta)
    # no numérica, es un título/encabezado suelto y no un alumno.
    primera_cuenta = str(df.iloc[0, 0]).strip()
    if primera_cuenta and not primera_cuenta.replace(".", "", 1).isdigit():
        df = df.iloc[1:].reset_index(drop=True)
    if df.empty:
        raise ValueError(
            "El archivo no tiene filas de alumnos utilizables. Se conservan los datos anteriores."
        )

    df.columns = list(COLUMNAS_NUEVO_INGRESO)
    df["Cuenta"] = _normalizar_cuenta(df["Cuenta"])

    def _nombre_alumno(fila) -> str:
        apellidos = re.sub(r"\s+", " ", f"{fila['Paterno']} {fila['Materno']}").strip()
        nombres = str(fila["Nombres"]).strip()
        return f"{apellidos} / {nombres}".strip(" /")

    df["NombreAlumno"] = df.apply(_nombre_alumno, axis=1)
    df["PerInicio"] = df["Periodo"].astype(str).str.strip()

    df = df.drop_duplicates(subset="Cuenta", keep="last")
    salida = df[["Cuenta", "NombreAlumno", "Plan", "PerInicio"]].copy()

    tmp = NUEVO_INGRESO_CSV + ".tmp"
    salida.to_csv(tmp, index=False)
    os.replace(tmp, NUEVO_INGRESO_CSV)

    periodos = [v for v in salida["PerInicio"] if v]
    periodo = max(set(periodos), key=periodos.count) if periodos else ""

    aj = cargar_ajustes()
    aj.update({
        "ni_filename": original_filename,
        "ni_fecha_carga": datetime.now().isoformat(timespec="seconds"),
        "ni_filas": int(len(salida)),
        "ni_periodo": periodo,
    })
    guardar_ajustes(aj)

    # Si el padrón principal ya existe, purga de inmediato las cuentas que
    # ya estén ahí (orden típico: nuevo ingreso se sube después del padrón).
    dfp = leer_datos()
    if not dfp.empty and "Cuenta" in dfp.columns:
        _purgar_nuevo_ingreso(set(dfp["Cuenta"].astype(str).str.strip()))


def eliminar_nuevo_ingreso():
    _eliminar_silenciosamente(NUEVO_INGRESO_CSV)
    aj = cargar_ajustes()
    for k in ("ni_filename", "ni_fecha_carga", "ni_filas", "ni_periodo"):
        aj.pop(k, None)
    guardar_ajustes(aj)


def _purgar_nuevo_ingreso(cuentas_padron: set[str]):
    """
    Quita de nuevo_ingreso.csv cualquier cuenta que ya esté en el padrón
    principal recién subido, para no dejar duplicados fantasma cuando esos
    alumnos avanzan de semestre y aparecen en el padrón académico normal.
    """
    if not cuentas_padron or not os.path.exists(NUEVO_INGRESO_CSV):
        return
    df = leer_nuevo_ingreso()
    if df.empty or "Cuenta" not in df.columns:
        return
    antes = len(df)
    df = df.loc[~df["Cuenta"].astype(str).str.strip().isin(cuentas_padron)]
    if len(df) == antes:
        return

    tmp = NUEVO_INGRESO_CSV + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, NUEVO_INGRESO_CSV)

    aj = cargar_ajustes()
    aj["ni_filas"] = int(len(df))
    guardar_ajustes(aj)


def panel_salud() -> dict:
    """Resumen de solo lectura para la vista /datos."""
    df = leer_datos()
    total = int(len(df)) if not df.empty else 0
    if total and "Sexo" in df.columns:
        sin_sexo = int((df["Sexo"].astype(str).str.strip() == "").sum())
    else:
        sin_sexo = total

    dfni = leer_nuevo_ingreso()
    nuevo_ingreso = int(len(dfni)) if not dfni.empty else 0

    return {"total": total, "sin_sexo": sin_sexo, "nuevo_ingreso": nuevo_ingreso}


# ---------- Limpieza de tmp ----------

def _eliminar_silenciosamente(*paths: str):
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


def _plantilla_de(slug: str | None):
    """Plantilla activa para un slug del form/query; None si no hay usable."""
    p = plantillas.get(slug) if slug else None
    if p is None or not p.exists():
        slug_def = plantillas.default_slug()
        p = plantillas.get(slug_def) if slug_def else None
    return p


def _generar_y_servir(plantilla, valores: dict, formato: str, basename: str,
                      bg: BackgroundTasks) -> FileResponse:
    """Genera DOCX (y opcionalmente PDF), programa borrado y devuelve la respuesta."""
    if plantilla is None or not plantilla.exists():
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")

    doc = render(plantilla.path, valores, opcionales_vacios=catalogo.opcionales_de(valores.keys()))

    uid = uuid.uuid4().hex[:8]
    docx_path = os.path.join(TMP_DIR, f"{basename}_{uid}.docx")
    doc.save(docx_path)

    if formato == "docx":
        bg.add_task(_eliminar_silenciosamente, docx_path)
        return FileResponse(
            docx_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"{basename}.docx",
        )

    try:
        pdf_path = docx_a_pdf(docx_path, TMP_DIR)
    except ConversionError as e:
        _eliminar_silenciosamente(docx_path)
        raise HTTPException(status_code=500, detail=str(e)) from e

    bg.add_task(_eliminar_silenciosamente, docx_path, pdf_path)
    return FileResponse(
        pdf_path, media_type="application/pdf", filename=f"{basename}.pdf"
    )


# ---------- Login ----------

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@app.post("/login")
async def login(rol: str = Form(...), password: str = Form("")):
    if rol == "admin":
        if password != ADMIN_PASSWORD:
            return RedirectResponse(url="/login?error=password", status_code=303)
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie("rol", "admin", httponly=True, samesite="lax")
        return resp
    if rol == "invitado":
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie("rol", "invitado", httponly=True, samesite="lax")
        return resp
    raise HTTPException(status_code=400, detail="Rol inválido")


@app.post("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("rol")
    return resp


# ---------- Rutas: home / búsqueda ----------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if get_rol(request) is None:
        return _redir_a_login()
    aj = cargar_ajustes()

    # Resultados de búsqueda por nombre (si venimos de /buscar con texto).
    q_nombre = request.query_params.get("nombre", "")
    resultados = buscar_por_nombre(q_nombre) if q_nombre else []

    lista_plantillas = plantillas.listar()
    admin = es_admin(request)
    return templates.TemplateResponse(request, "home.html", {
        "datos": datos_meta(),
        "ni": ni_meta(),
        "plantillas": lista_plantillas,
        "ajustes": aj,
        "es_admin": admin,
        "q_nombre": q_nombre,
        "resultados": resultados,
        "preparacion": preparacion_semestre(aj, lista_plantillas) if admin else None,
    })


def planes_sin_carrera() -> list[dict]:
    """
    Planes del padrón cuyo prefijo no está en el catálogo de carreras: en la
    constancia saldrían como código crudo (ICO-F19) en lugar del nombre.
    [{codigo, alumnos}] ordenado por cantidad de alumnos afectados.
    """
    df = leer_datos()
    if df.empty or "Plan" not in df.columns:
        return []
    conocidas = carreras.listar()["carreras"]
    conteo: dict[str, int] = {}
    for plan in df["Plan"].astype(str):
        codigo = plan.split("-", 1)[0].strip().upper()
        if codigo and codigo not in conocidas:
            conteo[codigo] = conteo.get(codigo, 0) + 1
    return [{"codigo": c, "alumnos": n}
            for c, n in sorted(conteo.items(), key=lambda kv: -kv[1])]


def preparacion_semestre(aj: dict, lista_plantillas: list[dict]) -> dict:
    """
    Lista de verificación del administrador para dejar el semestre listo.
    Cada paso: {clave, titulo, ok, detalle, url, accion}. `listo` es True
    cuando todos los pasos obligatorios están completos.
    """
    datos = datos_meta()
    listas = [it for it in lista_plantillas if it["info"]]
    con_avisos = [it["nombre"] for it in listas if it["info"].get("avisos")]
    sin_carrera = planes_sin_carrera() if datos else []

    periodo = aj.get("periodo_actual", "")
    fechas_ok = bool(aj.get("periodo_fecha_inicio") and aj.get("periodo_fecha_fin"))
    if not periodo:
        det_periodo = "Sin periodo: el semestre y las fechas no se pueden calcular."
    elif not fechas_ok:
        det_periodo = f"Periodo {periodo}. Faltan las fechas reales de inicio y fin (se usarán las típicas)."
    else:
        det_periodo = f"Periodo {periodo} configurado con sus fechas."

    pasos = [
        {
            "clave": "periodo", "titulo": "Periodo activo y fechas",
            "ok": bool(periodo), "parcial": bool(periodo) and not fechas_ok,
            "detalle": det_periodo, "url": "#periodo", "accion": "Configurar",
        },
        {
            "clave": "padron", "titulo": "Padrón de alumnos",
            "ok": bool(datos), "parcial": False,
            "detalle": (f"{datos['filas']} alumno{'s' if datos['filas'] != 1 else ''} · {datos['filename']}" if datos
                        else "Aún no hay alumnos cargados."),
            "url": "/datos", "accion": "Actualizar" if datos else "Subir padrón",
        },
        {
            "clave": "plantillas", "titulo": "Plantillas",
            "ok": bool(listas), "parcial": bool(con_avisos),
            "detalle": (f"Revisa en Word: {', '.join(con_avisos)} tiene campos mal escritos." if con_avisos
                        else f"{len(listas)} lista{'s' if len(listas) != 1 else ''} para usarse." if listas
                        else "No hay ninguna plantilla."),
            "url": "/plantillas", "accion": "Revisar" if listas else "Subir plantilla",
        },
        {
            "clave": "carreras", "titulo": "Carreras del padrón",
            "ok": bool(datos) and not sin_carrera, "parcial": False,
            "detalle": (
                "Sube primero el padrón." if not datos
                else "Todas las carreras del padrón están dadas de alta." if not sin_carrera
                else "Sin nombre de carrera: " + ", ".join(
                    f"{x['codigo']} ({x['alumnos']} alumno{'s' if x['alumnos'] != 1 else ''})"
                    for x in sin_carrera[:4]) + ("…" if len(sin_carrera) > 4 else "")
            ),
            "url": "/carreras", "accion": "Dar de alta" if sin_carrera else "Ver catálogo",
        },
    ]
    hechos = sum(1 for p in pasos if p["ok"])
    return {"pasos": pasos, "hechos": hechos, "total": len(pasos),
            "listo": hechos == len(pasos) and not any(p["parcial"] for p in pasos)}


# ---------- API: búsqueda en vivo ----------

@app.get("/api/alumnos")
async def api_alumnos(request: Request, q: str = ""):
    """
    Sugerencias para el buscador mientras se escribe: por inicio del número
    de cuenta si son dígitos, por nombre en cualquier otro caso.
    """
    if get_rol(request) is None:
        raise HTTPException(status_code=401, detail="Inicia sesión")
    q = q.strip()
    if len(q) < 2:
        return JSONResponse([])
    limite = 8
    if q.isdigit():
        encontrados, vistos = [], set()
        for df, origen in ((leer_datos(), ""), (leer_nuevo_ingreso(), "nuevo_ingreso")):
            if df.empty or "Cuenta" not in df.columns:
                continue
            for _, fila in df.loc[df["Cuenta"].astype(str).str.startswith(q)].iterrows():
                cuenta = str(fila.get("Cuenta", "")).strip()
                if cuenta in vistos:
                    continue
                vistos.add(cuenta)
                reg = {k: str(v) for k, v in fila.to_dict().items()}
                if origen:
                    reg["_origen"] = origen
                encontrados.append(reg)
                if len(encontrados) >= limite:
                    break
            if len(encontrados) >= limite:
                break
    else:
        encontrados = buscar_por_nombre(q, limite=limite)
    return JSONResponse([
        {
            "cuenta": r.get("Cuenta", ""),
            "nombre": derivar.formato_nombre(r.get("NombreAlumno", "")),
            "plan": r.get("Plan", ""),
            "nuevo_ingreso": r.get("_origen") == "nuevo_ingreso",
        }
        for r in encontrados
    ])


# ---------- Centro de ayuda ----------
# Abierto sin sesión: es documentación, sirve también desde la pantalla de acceso.

@app.get("/ayuda", response_class=HTMLResponse)
async def ayuda_index(request: Request):
    return templates.TemplateResponse(request, "ayuda/index.html", {
        "categorias": ayuda.por_categoria(),
        "q": request.query_params.get("q", ""),
    })


@app.get("/ayuda/plantilla-ejemplo.docx")
async def ayuda_plantilla_ejemplo():
    """La plantilla original del sistema, como punto de partida para crear otras."""
    return FileResponse(
        BOOTSTRAP_PLANTILLA,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="Plantilla de ejemplo - Constancia.docx",
    )


@app.get("/ayuda/{slug}", response_class=HTMLResponse)
async def ayuda_articulo(request: Request, slug: str):
    art = ayuda.articulo(slug)
    if not art:
        return RedirectResponse(url="/ayuda", status_code=303)
    ant, sig = ayuda.vecinos(slug)
    cat = carreras.listar()
    return templates.TemplateResponse(request, "ayuda/articulo.html", {
        "art": art,
        "anterior": ant,
        "siguiente": sig,
        "categorias": ayuda.por_categoria(),
        "campos": ayuda.referencia_campos(),
        "columnas_padron": COLUMNAS_CANONICAS,
        "catalogo": cat,
    })


@app.post("/ajustes")
async def actualizar_ajustes(request: Request, periodo_actual: str = Form(""),
                             periodo_inicio: str = Form(""), periodo_fin: str = Form("")):
    """
    Guarda el periodo activo y (opcionalmente) sus fechas reales de inicio y
    fin. Se capturan UNA vez por semestre: todas las constancias salen
    prellenadas con ellas. Si se dejan vacías, se usan las fechas típicas
    del periodo (02 feb / 02 ago) como aproximación editable.
    """
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo

    di, df = _parse_iso(periodo_inicio.strip()), _parse_iso(periodo_fin.strip())
    if di and df and df < di:
        return RedirectResponse(
            url=f"/?error_ajustes={quote('La fecha de fin del periodo no puede ser anterior a la de inicio.')}",
            status_code=303,
        )

    aj = cargar_ajustes()
    aj["periodo_actual"] = periodo_actual.strip().upper()
    aj["periodo_fecha_inicio"] = di.isoformat() if di else ""
    aj["periodo_fecha_fin"] = df.isoformat() if df else ""
    guardar_ajustes(aj)
    return RedirectResponse(url="/", status_code=303)


@app.post("/buscar")
async def buscar(cuenta: str = Form(...), plantilla: str = Form("")):
    """Un solo campo: número de cuenta (dígitos) o nombre (texto)."""
    consulta = cuenta.strip()
    slug = quote(plantilla or "")

    if re.fullmatch(r"\d{3,}", consulta):
        if not buscar_alumno(consulta):
            return RedirectResponse(
                url=f"/?error=alumno_no_encontrado&cuenta={consulta}", status_code=303,
            )
        if not plantillas.alguna_lista():
            return RedirectResponse(url="/?error=plantilla_no_encontrada", status_code=303)
        return RedirectResponse(
            url=f"/generar?cuenta={consulta}&plantilla={slug}", status_code=303,
        )

    # No parece cuenta: buscar por nombre y mostrar los resultados en home.
    return RedirectResponse(
        url=f"/?nombre={quote(consulta)}&plantilla={slug}", status_code=303,
    )


# ---------- Datos ----------

@app.get("/datos", response_class=HTMLResponse)
async def datos_page(request: Request):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    return templates.TemplateResponse(request, "datos.html", {
        "datos": datos_meta(),
        "ni": ni_meta(),
        "salud": panel_salud(),
        "ajustes": cargar_ajustes(),
    })


@app.post("/datos/upload")
async def datos_upload(request: Request, archivo: UploadFile = File(...)):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in (".xls", ".xlsx", ".csv"):
        raise HTTPException(status_code=400, detail="Formato no soportado")
    tmp_path = os.path.join(TMP_DIR, f"upload_{uuid.uuid4().hex[:8]}{ext}")
    with open(tmp_path, "wb") as f:
        f.write(await archivo.read())
    try:
        guardar_datos(tmp_path, archivo.filename)
    except ValueError as e:
        return RedirectResponse(url=f"/datos?error={quote(str(e))}", status_code=303)
    finally:
        _eliminar_silenciosamente(tmp_path)
    return RedirectResponse(url="/datos?ok=1", status_code=303)


@app.post("/datos/nuevo-ingreso")
async def nuevo_ingreso_upload(request: Request, archivo: UploadFile = File(...)):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in (".xls", ".xlsx"):
        raise HTTPException(status_code=400, detail="Formato no soportado")
    tmp_path = os.path.join(TMP_DIR, f"upload_ni_{uuid.uuid4().hex[:8]}{ext}")
    with open(tmp_path, "wb") as f:
        f.write(await archivo.read())
    try:
        guardar_nuevo_ingreso(tmp_path, archivo.filename)
    except ValueError as e:
        return RedirectResponse(url=f"/datos?error={quote(str(e))}", status_code=303)
    finally:
        _eliminar_silenciosamente(tmp_path)
    return RedirectResponse(url="/datos?ok=1", status_code=303)


@app.post("/datos/nuevo-ingreso/eliminar")
async def nuevo_ingreso_eliminar(request: Request):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    eliminar_nuevo_ingreso()
    return RedirectResponse(url="/datos?ok=1", status_code=303)


# ---------- Plantilla ----------

@app.get("/plantillas", response_class=HTMLResponse)
async def plantillas_page(request: Request):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    return templates.TemplateResponse(request, "plantillas.html", {
        "items": plantillas.listar(),
        "etiquetas": {k: v["label"] for k, v in catalogo.ETIQUETAS.items()},
    })


@app.post("/plantillas/crear")
async def plantillas_crear(request: Request, nombre: str = Form(...),
                           archivo: UploadFile = File(...)):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    if not archivo.filename.lower().endswith(".docx"):
        return RedirectResponse(
            url=f"/plantillas?error={quote('Sólo se aceptan archivos .docx.')}", status_code=303,
        )
    try:
        plantillas.crear(nombre, await archivo.read())
    except ValueError as e:
        return RedirectResponse(url=f"/plantillas?error={quote(str(e))}", status_code=303)
    return RedirectResponse(url="/plantillas?ok=creada", status_code=303)


def _plantilla_o_404(slug: str):
    p = plantillas.get(slug)
    if p is None:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return p


@app.post("/plantillas/{slug}/upload")
async def plantillas_upload(request: Request, slug: str, archivo: UploadFile = File(...)):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    p = _plantilla_o_404(slug)
    if not archivo.filename.lower().endswith(".docx"):
        return RedirectResponse(
            url=f"/plantillas?error={quote('Sólo se aceptan archivos .docx.')}", status_code=303,
        )
    try:
        p.replace(await archivo.read())
    except ValueError as e:
        return RedirectResponse(url=f"/plantillas?error={quote(str(e))}", status_code=303)
    return RedirectResponse(url="/plantillas?ok=subida", status_code=303)


@app.get("/plantillas/{slug}/download")
async def plantillas_download(request: Request, slug: str):
    """Descarga el .docx activo, para editarlo en Word y volverlo a subir."""
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    p = _plantilla_o_404(slug)
    if not p.exists():
        raise HTTPException(status_code=404, detail="No hay archivo cargado")
    return FileResponse(
        p.path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"plantilla_{slug}.docx",
    )


@app.post("/plantillas/{slug}/restaurar")
async def plantillas_restaurar(request: Request, slug: str, nombre: str = Form(...)):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    p = _plantilla_o_404(slug)
    try:
        p.restaurar(nombre)
    except ValueError as e:
        return RedirectResponse(url=f"/plantillas?error={quote(str(e))}", status_code=303)
    return RedirectResponse(url="/plantillas?ok=restaurada", status_code=303)


@app.post("/plantillas/{slug}/eliminar")
async def plantillas_eliminar(request: Request, slug: str):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    try:
        plantillas.eliminar(slug)
    except ValueError as e:
        return RedirectResponse(url=f"/plantillas?error={quote(str(e))}", status_code=303)
    return RedirectResponse(url="/plantillas?ok=eliminada", status_code=303)


# ---------- Carreras (catálogo editable) ----------

@app.get("/carreras", response_class=HTMLResponse)
async def carreras_page(request: Request):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    return templates.TemplateResponse(request, "carreras.html", {
        "catalogo": carreras.listar(),
        "sin_carrera": planes_sin_carrera(),
    })


@app.post("/carreras/carrera")
async def carreras_guardar(request: Request, codigo: str = Form(...), nombre: str = Form(...)):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    try:
        carreras.guardar_carrera(codigo, nombre)
    except ValueError as e:
        return RedirectResponse(url=f"/carreras?error={quote(str(e))}", status_code=303)
    return RedirectResponse(url="/carreras?ok=1", status_code=303)


@app.post("/carreras/carrera/eliminar")
async def carreras_eliminar(request: Request, codigo: str = Form(...)):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    carreras.eliminar_carrera(codigo)
    return RedirectResponse(url="/carreras?ok=1", status_code=303)


@app.post("/carreras/duracion")
async def duracion_guardar(request: Request, plan: str = Form(...), semestres: str = Form(...)):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    try:
        carreras.guardar_duracion(plan, semestres)
    except ValueError as e:
        return RedirectResponse(url=f"/carreras?error={quote(str(e))}", status_code=303)
    return RedirectResponse(url="/carreras?ok=1", status_code=303)


@app.post("/carreras/duracion/eliminar")
async def duracion_eliminar(request: Request, plan: str = Form(...)):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    carreras.eliminar_duracion(plan)
    return RedirectResponse(url="/carreras?ok=1", status_code=303)


# ---------- Comodines (snippets reutilizables para LINEA_LIBRE) ----------

@app.get("/comodines")
async def comodines_list():
    return JSONResponse(comodines.list())


@app.post("/comodines")
async def comodines_crear(titulo: str = Form(...), texto: str = Form(...)):
    if not titulo.strip() or not texto.strip():
        raise HTTPException(status_code=400, detail="Título y texto son requeridos")
    return JSONResponse(comodines.crear(titulo, texto))


@app.delete("/comodines/{cid}")
async def comodines_eliminar(cid: str):
    ok = comodines.eliminar(cid)
    if not ok:
        raise HTTPException(status_code=404, detail="Comodín no encontrado")
    return JSONResponse({"ok": True})


# ---------- Generación ----------

@app.get("/generar", response_class=HTMLResponse)
async def generar_page(request: Request, cuenta: str, plantilla: str = ""):
    alumno = buscar_alumno(cuenta)
    if not alumno:
        return RedirectResponse(url="/?error=alumno_no_encontrado", status_code=303)

    p = _plantilla_de(plantilla)
    info = p.info() if p else None
    if not info:
        return RedirectResponse(url="/?error=plantilla_no_encontrada", status_code=303)
    slug = plantilla if (plantillas.get(plantilla) and plantillas.get(plantilla).exists()) \
        else plantillas.default_slug()

    aj = cargar_ajustes()
    campos = catalogo.construir_campos_form(info["placeholders"], alumno, aj, carreras)
    # Orden lógico (el del catálogo: nombre, cuenta, carrera… inicio antes que
    # fin) en vez del alfabético de la detección; los campos propios de la
    # plantilla van después, en su orden.
    orden = {nombre: i for i, nombre in enumerate(catalogo.ETIQUETAS)}
    orden["ARTICULO"] = -1  # el género primero: es el dato que más se revisa a mano
    campos.sort(key=lambda c: orden.get(c["name"], len(orden)))

    return templates.TemplateResponse(request, "generar.html", {
        "alumno": alumno,
        "plantilla": info,
        "plantilla_slug": slug,
        "plantilla_nombre": plantillas.nombre_de(slug),
        "plantillas_listas": [it for it in plantillas.listar() if it["info"]],
        "campos": campos,
        "ajustes": aj,
    })


def _parse_iso(s: str):
    from datetime import date
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def _form_a_valores(form_data, placeholders: list[str]) -> dict:
    """
    Extrae los valores del FormData para los placeholders esperados.

    El parseo lo decide catalogo.tipo_de(), la misma fuente que pinta el
    formulario: cualquier placeholder nuevo en la plantilla (texto, *_LINEA,
    *_FECHA) funciona de punta a punta sin tocar este código.
    """
    valores = {}
    for ph in placeholders:
        tipo = catalogo.tipo_de(ph)

        if tipo in (catalogo.DATE_CORTO, catalogo.DATE_LARGO):
            d = _parse_iso(form_data.get(f"fecha_{ph}", ""))
            fmt = (derivar.fecha_a_texto_largo if tipo == catalogo.DATE_LARGO
                   else derivar.fecha_a_texto_corto)
            valores[ph] = fmt(d) if d else ""
        elif tipo == catalogo.DATE_RANGO:
            di = _parse_iso(form_data.get("fecha_VAC_INICIO", ""))
            df = _parse_iso(form_data.get("fecha_VAC_FIN", ""))
            valores[ph] = derivar.linea_periodo_vacacional(di, df) if di and df else ""
        else:
            v = form_data.get(f"campo_{ph}", "")
            valores[ph] = "" if v is None else str(v)

    # Género → ARTICULO + INTERESADO_FRASE derivados.
    genero = form_data.get("__genero__", "")
    if genero and "ARTICULO" in placeholders:
        valores["ARTICULO"] = derivar.articulo_de(genero)
    if genero and "INTERESADO_FRASE" in placeholders:
        valores["INTERESADO_FRASE"] = derivar.interesado_frase(genero)

    return valores


async def _plantilla_y_valores(request: Request):
    form = await request.form()
    p = _plantilla_de(form.get("plantilla", ""))
    info = p.info() if p else None
    if not info:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return p, form, _form_a_valores(form, info["placeholders"])


@app.post("/preview.pdf")
async def preview_pdf(request: Request, bg: BackgroundTasks):
    p, _form, valores = await _plantilla_y_valores(request)
    return _generar_y_servir(p, valores, "pdf", basename="preview", bg=bg)


@app.post("/generar/docx")
async def generar_docx(request: Request, bg: BackgroundTasks):
    p, form, valores = await _plantilla_y_valores(request)
    cuenta = form.get("cuenta", "")
    return _generar_y_servir(p, valores, "docx", basename=f"Constancia_{cuenta}", bg=bg)


@app.post("/generar/pdf")
async def generar_pdf(request: Request, bg: BackgroundTasks):
    p, form, valores = await _plantilla_y_valores(request)
    cuenta = form.get("cuenta", "")
    return _generar_y_servir(p, valores, "pdf", basename=f"Constancia_{cuenta}", bg=bg)

