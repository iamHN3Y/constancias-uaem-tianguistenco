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
import zipfile
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

from . import catalogo, derivar
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

    # Excel a veces entrega las cuentas como número flotante ("2014694.0").
    df["Cuenta"] = df["Cuenta"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)

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


def buscar_alumno(cuenta: str) -> dict | None:
    df = leer_datos()
    if df.empty or "Cuenta" not in df.columns:
        return None
    fila = df.loc[df["Cuenta"].astype(str).str.strip() == str(cuenta).strip()]
    if fila.empty:
        return None
    return {k: ("" if v is None else str(v)) for k, v in fila.iloc[0].to_dict().items()}


def _sin_acentos_lower(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def buscar_por_nombre(texto: str, limite: int = 20) -> list[dict]:
    """
    Alumnos cuyo nombre contiene todas las palabras buscadas, sin distinguir
    mayúsculas ni acentos. 'perez juan' encuentra 'PÉREZ / JUAN'.
    """
    df = leer_datos()
    if df.empty or "NombreAlumno" not in df.columns:
        return []
    palabras = [_sin_acentos_lower(p) for p in texto.split() if p.strip()]
    if not palabras:
        return []
    resultados = []
    for _, fila in df.iterrows():
        nombre = _sin_acentos_lower(fila.get("NombreAlumno", ""))
        if all(p in nombre for p in palabras):
            resultados.append({k: str(v) for k, v in fila.to_dict().items()})
            if len(resultados) >= limite:
                break
    return resultados


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

    return templates.TemplateResponse(request, "home.html", {
        "datos": datos_meta(),
        "plantillas": plantillas.listar(),
        "ajustes": aj,
        "es_admin": es_admin(request),
        "q_nombre": q_nombre,
        "resultados": resultados,
    })


@app.post("/ajustes")
async def actualizar_ajustes(request: Request, periodo_actual: str = Form(""),
                             periodo_inicio: str = Form(""), periodo_fin: str = Form("")):
    """
    Guarda el periodo activo y (opcionalmente) sus fechas reales de inicio y
    fin. Se capturan UNA vez por semestre: todas las constancias —individuales
    y por lote— salen prellenadas con ellas. Si se dejan vacías, se usan las
    fechas típicas del periodo (02 feb / 02 ago) como aproximación editable.
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


# ---------- Plantilla ----------

@app.get("/plantillas", response_class=HTMLResponse)
async def plantillas_page(request: Request):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    return templates.TemplateResponse(request, "plantillas.html", {
        "items": plantillas.listar(),
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

    return templates.TemplateResponse(request, "generar.html", {
        "alumno": alumno,
        "plantilla": info,
        "plantilla_slug": slug,
        "plantilla_nombre": plantillas.nombre_de(slug),
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


# ---------- Generación por lotes ----------

# Campos que en el lote se derivan por alumno y NO se piden en el formulario
# compartido (además de los HIDDEN): ver catalogo.PLACEHOLDERS_POR_ALUMNO.

@app.get("/lote", response_class=HTMLResponse)
async def lote_page(request: Request):
    if get_rol(request) is None:
        return _redir_a_login()
    aj = cargar_ajustes()

    slug = request.query_params.get("plantilla", "") or plantillas.default_slug()
    p = plantillas.get(slug) if slug else None
    info = p.info() if p and p.exists() else None
    if not info:
        return RedirectResponse(url="/?error=plantilla_no_encontrada", status_code=303)

    # Campos compartidos: todo lo que no se deriva por alumno.
    campos = [
        c for c in catalogo.construir_campos_form(info["placeholders"], {}, aj, carreras)
        if c["name"] not in catalogo.PLACEHOLDERS_POR_ALUMNO
    ]
    # ¿La plantilla trae líneas de promedio? (para mostrar los checkboxes)
    tiene_promedios = any(
        ph in info["placeholders"]
        for ph in ("PROMEDIO_GENERAL_LINEA", "PROMEDIO_ULTIMO_LINEA")
    )

    return templates.TemplateResponse(request, "lote.html", {
        "datos": datos_meta(),
        "plantillas": plantillas.listar(),
        "plantilla_slug": slug,
        "campos": campos,
        "tiene_promedios": tiene_promedios,
        "ajustes": aj,
    })


@app.post("/lote/generar", response_class=HTMLResponse)
async def lote_generar(request: Request):
    if get_rol(request) is None:
        return _redir_a_login()
    form = await request.form()

    p = _plantilla_de(form.get("plantilla", ""))
    info = p.info() if p else None
    if not info:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")

    formato = form.get("formato", "docx")
    if formato not in ("docx", "pdf"):
        formato = "docx"

    # Cuentas: una por línea, o separadas por coma/espacio.
    cuentas = [c for c in re.split(r"[\s,;]+", form.get("cuentas", "")) if c]
    cuentas = list(dict.fromkeys(cuentas))[:200]  # únicas, máx. 200
    if not cuentas:
        return RedirectResponse(
            url=f"/lote?plantilla={quote(form.get('plantilla', ''))}", status_code=303,
        )

    aj = cargar_ajustes()
    compartidos = _form_a_valores(form, info["placeholders"])
    incluir_prom_gral = form.get("incluir_promedio_general") == "on"
    incluir_prom_ult = form.get("incluir_promedio_ultimo") == "on"

    zip_uid = uuid.uuid4().hex[:12]
    zip_path = os.path.join(TMP_DIR, f"lote_{zip_uid}.zip")
    resultados = []

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for cuenta in cuentas:
            alumno = buscar_alumno(cuenta)
            if not alumno:
                resultados.append({"cuenta": cuenta, "nombre": "", "estado": "no_encontrado", "detalle": ""})
                continue

            por_alumno, faltantes = catalogo.valores_por_alumno(
                info["placeholders"], alumno, aj, carreras,
            )
            # Checkboxes de promedios apagados → la línea se vacía y su
            # párrafo desaparece del documento.
            if not incluir_prom_gral and "PROMEDIO_GENERAL_LINEA" in info["placeholders"]:
                por_alumno["PROMEDIO_GENERAL_LINEA"] = ""
            if not incluir_prom_ult and "PROMEDIO_ULTIMO_LINEA" in info["placeholders"]:
                por_alumno["PROMEDIO_ULTIMO_LINEA"] = ""

            valores = {**compartidos, **por_alumno}
            # Los faltantes (p. ej. género sin columna Sexo) se quitan del
            # mapping: el placeholder queda visible en el documento como
            # señal de que hay que completarlo a mano.
            for ph in faltantes:
                valores.pop(ph, None)

            doc = render(p.path, valores, opcionales_vacios=catalogo.opcionales_de(valores.keys()))
            base = f"Constancia_{cuenta}"
            docx_tmp = os.path.join(TMP_DIR, f"{base}_{uuid.uuid4().hex[:8]}.docx")
            doc.save(docx_tmp)
            try:
                if formato == "pdf":
                    pdf_tmp = docx_a_pdf(docx_tmp, TMP_DIR)
                    zf.write(pdf_tmp, f"{base}.pdf")
                    _eliminar_silenciosamente(pdf_tmp)
                else:
                    zf.write(docx_tmp, f"{base}.docx")
            except ConversionError as e:
                resultados.append({
                    "cuenta": cuenta,
                    "nombre": derivar.formato_nombre(alumno.get("NombreAlumno", "")),
                    "estado": "error_pdf", "detalle": str(e)[:200],
                })
                _eliminar_silenciosamente(docx_tmp)
                continue
            finally:
                _eliminar_silenciosamente(docx_tmp)

            resultados.append({
                "cuenta": cuenta,
                "nombre": derivar.formato_nombre(alumno.get("NombreAlumno", "")),
                "estado": "revisar" if faltantes else "ok",
                "detalle": ", ".join(f"[[{f}]]" for f in faltantes),
            })

    generadas = sum(1 for r in resultados if r["estado"] in ("ok", "revisar"))
    return templates.TemplateResponse(request, "lote.html", {
        "datos": datos_meta(),
        "plantillas": plantillas.listar(),
        "plantilla_slug": form.get("plantilla", ""),
        "campos": [],
        "tiene_promedios": False,
        "ajustes": aj,
        "resultado": {
            "resultados": resultados,
            "generadas": generadas,
            "formato": formato,
            "zip": f"/lote/zip/{zip_uid}" if generadas else "",
        },
    })


@app.get("/lote/zip/{uid}")
async def lote_zip(request: Request, uid: str, bg: BackgroundTasks):
    if get_rol(request) is None:
        return _redir_a_login()
    if not re.fullmatch(r"[0-9a-f]{12}", uid):
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    zip_path = os.path.join(TMP_DIR, f"lote_{uid}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Ese lote ya expiró; genera uno nuevo.")
    fecha = datetime.now().strftime("%Y-%m-%d")
    return FileResponse(zip_path, media_type="application/zip",
                        filename=f"Constancias_{fecha}.zip")
