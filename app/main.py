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
import uuid
from datetime import datetime

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
from .comodines import Comodines
from .docx_render import render
from .pdf import ConversionError, docx_a_pdf
from .plantilla_universal import PlantillaUniversal


# ---------- Paths ----------

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))
PLANTILLAS_DIR = os.path.join(DATA_DIR, "plantillas")
TMP_DIR = os.path.join(DATA_DIR, "tmp")
BOOTSTRAP_PLANTILLA = os.path.join(BASE_DIR, "bootstrap_plantillas", "universal.docx")
DATOS_CSV = os.path.join(DATA_DIR, "datos.csv")
AJUSTES_FILE = os.path.join(DATA_DIR, "ajustes.json")
COMODINES_FILE = os.path.join(DATA_DIR, "comodines.json")

# Pseudo-login: la cookie 'rol' vale 'admin' o 'invitado'.
# La contraseña no es para seguridad seria — solo gating básico de UI.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin2026")

for d in (DATA_DIR, PLANTILLAS_DIR, TMP_DIR):
    os.makedirs(d, exist_ok=True)


# ---------- App ----------

app = FastAPI(title="Generador de Constancias")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

plantilla = PlantillaUniversal(PLANTILLAS_DIR)
comodines = Comodines(COMODINES_FILE)


@app.on_event("startup")
def _startup():
    if os.path.isdir(TMP_DIR):
        for name in os.listdir(TMP_DIR):
            try:
                os.remove(os.path.join(TMP_DIR, name))
            except OSError:
                pass
    plantilla.seed_si_vacio(BOOTSTRAP_PLANTILLA)


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
    with open(AJUSTES_FILE, "w", encoding="utf-8") as f:
        json.dump(aj, f, ensure_ascii=False, indent=2)


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


def guardar_datos(upload_path: str, original_filename: str):
    ext = os.path.splitext(original_filename)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(upload_path, dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(upload_path, dtype=str)
        df = df.fillna("")
    df.to_csv(DATOS_CSV, index=False)

    aj = cargar_ajustes()
    aj.update({
        "datos_filename": original_filename,
        "datos_fecha_carga": datetime.now().isoformat(timespec="seconds"),
        "datos_filas": int(len(df)),
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


# ---------- Limpieza de tmp ----------

def _eliminar_silenciosamente(*paths: str):
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


def _generar_y_servir(valores: dict, formato: str, basename: str,
                      bg: BackgroundTasks) -> FileResponse:
    """Genera DOCX (y opcionalmente PDF), programa borrado y devuelve la respuesta."""
    if not plantilla.exists():
        raise HTTPException(status_code=404, detail="Plantilla universal no encontrada")

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
    return templates.TemplateResponse(request, "home.html", {
        "datos": datos_meta(),
        "plantilla": plantilla.info(),
        "ajustes": aj,
        "es_admin": es_admin(request),
    })


@app.post("/ajustes")
async def actualizar_ajustes(request: Request, periodo_actual: str = Form("")):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    aj = cargar_ajustes()
    aj["periodo_actual"] = periodo_actual.strip().upper()
    guardar_ajustes(aj)
    return RedirectResponse(url="/", status_code=303)


@app.post("/buscar")
async def buscar(cuenta: str = Form(...)):
    if not buscar_alumno(cuenta):
        return RedirectResponse(
            url=f"/?error=alumno_no_encontrado&cuenta={cuenta}", status_code=303,
        )
    if not plantilla.exists():
        return RedirectResponse(url="/?error=plantilla_no_encontrada", status_code=303)
    return RedirectResponse(url=f"/generar?cuenta={cuenta}", status_code=303)


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
    finally:
        _eliminar_silenciosamente(tmp_path)
    return RedirectResponse(url="/datos", status_code=303)


# ---------- Plantilla ----------

@app.get("/plantillas", response_class=HTMLResponse)
async def plantillas_page(request: Request):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    return templates.TemplateResponse(request, "plantillas.html", {
        "plantilla": plantilla.info(),
    })


@app.post("/plantillas/upload")
async def plantillas_upload(request: Request, archivo: UploadFile = File(...)):
    bloqueo = _bloquear_si_no_admin(request)
    if bloqueo: return bloqueo
    if not archivo.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Sólo se aceptan .docx")
    contenido = await archivo.read()
    try:
        plantilla.replace(contenido)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RedirectResponse(url="/plantillas", status_code=303)


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
async def generar_page(request: Request, cuenta: str):
    alumno = buscar_alumno(cuenta)
    if not alumno:
        return RedirectResponse(url="/?error=alumno_no_encontrado", status_code=303)

    info = plantilla.info()
    if not info:
        return RedirectResponse(url="/?error=plantilla_no_encontrada", status_code=303)

    aj = cargar_ajustes()
    campos = catalogo.construir_campos_form(info["placeholders"], alumno, aj)

    return templates.TemplateResponse(request, "generar.html", {
        "alumno": alumno,
        "plantilla": info,
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
    """Extrae los valores del FormData para los placeholders esperados."""
    valores = {}
    for ph in placeholders:
        v = form_data.get(f"campo_{ph}", "")
        valores[ph] = "" if v is None else str(v)

    # Género → ARTICULO + INTERESADO_FRASE derivados.
    genero = form_data.get("__genero__", "")
    if genero and "ARTICULO" in placeholders:
        valores["ARTICULO"] = derivar.articulo_de(genero)
    if genero and "INTERESADO_FRASE" in placeholders:
        valores["INTERESADO_FRASE"] = derivar.interesado_frase(genero)

    # Fechas individuales → texto formateado.
    for ph, formatter in (
        ("PERIODO_INICIO", derivar.fecha_a_texto_corto),
        ("PERIODO_FIN", derivar.fecha_a_texto_corto),
        ("FECHA_EXPEDICION", derivar.fecha_a_texto_largo),
    ):
        if ph in placeholders:
            d = _parse_iso(form_data.get(f"fecha_{ph}", ""))
            if d:
                valores[ph] = formatter(d)

    # Rango de periodo vacacional.
    if "PERIODO_VACACIONAL_LINEA" in placeholders:
        di = _parse_iso(form_data.get("fecha_VAC_INICIO", ""))
        df = _parse_iso(form_data.get("fecha_VAC_FIN", ""))
        if di and df:
            valores["PERIODO_VACACIONAL_LINEA"] = derivar.linea_periodo_vacacional(di, df)
        else:
            valores["PERIODO_VACACIONAL_LINEA"] = ""

    return valores


@app.post("/preview.pdf")
async def preview_pdf(request: Request, bg: BackgroundTasks):
    info = plantilla.info()
    if not info:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    form = await request.form()
    valores = _form_a_valores(form, info["placeholders"])
    return _generar_y_servir(valores, "pdf", basename="preview", bg=bg)


@app.post("/generar/docx")
async def generar_docx(request: Request, bg: BackgroundTasks):
    info = plantilla.info()
    if not info:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    form = await request.form()
    cuenta = form.get("cuenta", "")
    valores = _form_a_valores(form, info["placeholders"])
    return _generar_y_servir(valores, "docx", basename=f"Constancia_{cuenta}", bg=bg)


@app.post("/generar/pdf")
async def generar_pdf(request: Request, bg: BackgroundTasks):
    info = plantilla.info()
    if not info:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    form = await request.form()
    cuenta = form.get("cuenta", "")
    valores = _form_a_valores(form, info["placeholders"])
    return _generar_y_servir(valores, "pdf", basename=f"Constancia_{cuenta}", bg=bg)
