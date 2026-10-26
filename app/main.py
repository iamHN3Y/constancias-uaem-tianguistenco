"""
Generador de Constancias — backend FastAPI.

Flujo:
  1. Subir datos (.xls/.xlsx/.csv) — persisten hasta que se reemplacen.
  2. Hay UNA plantilla universal .docx con placeholders [[CAMPO]].
  3. Buscar alumno por número de cuenta.
  4. Formulario auto-rellenado con los placeholders detectados.
  5. Vista previa en PDF (iframe) que se actualiza con cada cambio.
  6. Descarga final en .docx o .pdf.

El frontend es una SPA de React (ver frontend/) que consume la API JSON en
/api/v1/* (definida en app/api.py). Este módulo concentra: la lógica de
dominio (lectura/escritura de datos.csv, ajustes, alumnos), la app FastAPI,
y el montaje del router de la API + el estático de la SPA compilada.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import catalogo, derivar
from .carreras import Carreras
from .comodines import Comodines
from .docx_render import render
from .pdf import ConversionError, docx_a_pdf, docx_a_pdf_async
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


# ---------- Auth (pseudo-login con cookie sin firmar) ----------
# Se exponen como funciones simples; app.api las envuelve en dependencias
# FastAPI (Depends) que lanzan HTTPException(401/403) en vez de redirigir.

def get_rol(request: Request) -> str | None:
    return request.cookies.get("rol")


def es_admin(request: Request) -> bool:
    return get_rol(request) == "admin"


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


async def _generar_y_servir_async(plantilla, valores: dict, formato: str, basename: str,
                                  bg: BackgroundTasks) -> FileResponse:
    """
    Igual que `_generar_y_servir`, pero para el caso 'pdf' usa la conversión
    asíncrona (threadpool + semáforo) para no bloquear el event loop con
    conversiones de LibreOffice concurrentes. El caso 'docx' no necesita
    LibreOffice, así que se resuelve igual que la versión síncrona.
    """
    if formato != "pdf":
        return _generar_y_servir(plantilla, valores, formato, basename, bg)

    if plantilla is None or not plantilla.exists():
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")

    doc = render(plantilla.path, valores, opcionales_vacios=catalogo.opcionales_de(valores.keys()))

    uid = uuid.uuid4().hex[:8]
    docx_path = os.path.join(TMP_DIR, f"{basename}_{uid}.docx")
    doc.save(docx_path)

    try:
        pdf_path = await docx_a_pdf_async(docx_path, TMP_DIR)
    except ConversionError as e:
        _eliminar_silenciosamente(docx_path)
        raise HTTPException(status_code=500, detail=str(e)) from e

    bg.add_task(_eliminar_silenciosamente, docx_path, pdf_path)
    return FileResponse(
        pdf_path, media_type="application/pdf", filename=f"{basename}.pdf"
    )


# ---------- Helpers usados por app.api (router JSON /api/v1) ----------

def _plantilla_o_404(slug: str):
    p = plantillas.get(slug)
    if p is None:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return p


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


# ---------- Router JSON (/api/v1/*) ----------
# Import diferido: app.api hace `from . import main as m` y accede a las
# funciones/objetos de este módulo por atributo, así que main.py debe estar
# completamente definido antes de importarlo.
from .api import router as api_router  # noqa: E402

app.include_router(api_router)


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    """Toda la API responde errores como {"error": "mensaje"} en vez del
    {"detail": "..."} por defecto de FastAPI."""
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


# ---------- Frontend React (SPA) ----------
# En producción, `frontend/dist` (generado por `npm run build`) se sirve
# como estático con fallback a index.html para las rutas del router de
# React (deep links tipo /generar, /datos, etc. deben servir la SPA, no
# un 404). En desarrollo (sin build todavía) simplemente no hay nada que
# montar aquí y el frontend corre aparte con `npm run dev` (Vite, con
# proxy a este backend).
FRONTEND_DIST = os.path.join(BASE_DIR, "..", "frontend", "dist")
FRONTEND_DIST = os.path.abspath(FRONTEND_DIST)

if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """Sirve archivos estáticos del build de Vite si existen; si no,
        cae en index.html para que React Router resuelva la ruta cliente.

        `full_path` viene del cliente sin normalizar: hay que resolverlo y
        confirmar que sigue dentro de FRONTEND_DIST antes de servirlo, o un
        "../../data/datos.csv" serviría archivos arbitrarios del servidor
        sin pasar por ninguna autenticación.
        """
        candidato = os.path.realpath(os.path.join(FRONTEND_DIST, full_path))
        try:
            dentro = os.path.commonpath([candidato, FRONTEND_DIST]) == FRONTEND_DIST
        except ValueError:
            dentro = False  # rutas en unidades distintas (Windows) → nunca "dentro"
        if full_path and dentro and os.path.isfile(candidato):
            return FileResponse(candidato)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

