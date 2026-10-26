"""
Router JSON de la API (/api/v1/*), pensado para el frontend React.

Handlers delgados: reutilizan la capa de dominio ya probada en `app.main`
(catalogo, derivar, docx_render, plantilla_universal, carreras, comodines,
pdf) y las funciones auxiliares que ya viven en `app.main` (buscar_alumno,
guardar_datos, _generar_y_servir, etc.). Accedemos a esas funciones/objetos
SIEMPRE vía el módulo (`m.xxx`), nunca importándolos por nombre, para que
los tests que hacen monkeypatch de `app.main.plantillas` / `app.main.carreras`
/ rutas de datos sigan funcionando sin cambios de comportamiento.

Auth: la cookie de sesión sin firmar ('rol') se mantiene tal cual. Aquí se
expone como dependencias FastAPI que lanzan HTTPException(401/403) en vez
de redirigir. Los errores de validación de dominio (ValueError) se
convierten a HTTPException(400, detail=str(e)); un exception handler en
app.main los serializa como {"error": "..."}.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import main as m

router = APIRouter(prefix="/api/v1")


# ---------- Auth deps ----------

def require_session(request: Request) -> str:
    rol = m.get_rol(request)
    if rol is None:
        raise HTTPException(status_code=401, detail="No has iniciado sesión.")
    return rol


def require_admin(request: Request) -> str:
    rol = require_session(request)
    if rol != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador.")
    return rol


# ---------- Modelos ----------

class LoginBody(BaseModel):
    rol: str
    password: str = ""


class AjustesBody(BaseModel):
    periodo_actual: str = ""
    periodo_inicio: str = ""
    periodo_fin: str = ""


class BuscarBody(BaseModel):
    cuenta: str
    plantilla: str = ""


class CarreraBody(BaseModel):
    codigo: str
    nombre: str


class CodigoBody(BaseModel):
    codigo: str


class DuracionBody(BaseModel):
    plan: str
    semestres: str


class PlanBody(BaseModel):
    plan: str


class ComodinBody(BaseModel):
    titulo: str
    texto: str


class PlantillaRestaurarBody(BaseModel):
    nombre: str


# ---------- Login / sesión ----------

@router.post("/login")
async def login(body: LoginBody):
    if body.rol == "admin":
        if body.password != m.ADMIN_PASSWORD:
            raise HTTPException(status_code=401, detail="Contraseña incorrecta.")
        resp = JSONResponse({"rol": "admin"})
        resp.set_cookie("rol", "admin", httponly=True, samesite="lax")
        return resp
    if body.rol == "invitado":
        resp = JSONResponse({"rol": "invitado"})
        resp.set_cookie("rol", "invitado", httponly=True, samesite="lax")
        return resp
    raise HTTPException(status_code=400, detail="Rol inválido.")


@router.post("/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("rol")
    return resp


@router.get("/session")
async def session(request: Request):
    rol = m.get_rol(request)
    if rol is None:
        raise HTTPException(status_code=401, detail="No has iniciado sesión.")
    return {"rol": rol, "es_admin": rol == "admin"}


# ---------- Home / búsqueda ----------

@router.get("/home")
async def home(rol: str = Depends(require_session)):
    aj = m.cargar_ajustes()
    return {
        "datos": m.datos_meta(),
        "ni": m.ni_meta(),
        "plantillas": m.plantillas.listar(),
        "ajustes": aj,
        "es_admin": rol == "admin",
    }


@router.get("/buscar/nombre")
async def buscar_nombre(q: str = "", rol: str = Depends(require_session)):
    if not q:
        return {"resultados": []}
    return {"resultados": m.buscar_por_nombre(q)}


@router.post("/buscar")
async def buscar(body: BuscarBody, rol: str = Depends(require_session)):
    """Un solo campo: cuenta (dígitos) o nombre (texto). Ver POST /buscar de main.py."""
    import re
    consulta = body.cuenta.strip()

    if re.fullmatch(r"\d{3,}", consulta):
        alumno = m.buscar_alumno(consulta)
        if not alumno:
            raise HTTPException(status_code=404, detail=f"No se encontró un alumno con la cuenta {consulta}.")
        if not m.plantillas.alguna_lista():
            raise HTTPException(status_code=404, detail="No hay ninguna plantilla cargada todavía.")
        return {"tipo": "cuenta", "cuenta": consulta, "alumno": alumno}

    resultados = m.buscar_por_nombre(consulta)
    return {"tipo": "nombre", "resultados": resultados}


@router.post("/ajustes")
async def actualizar_ajustes(body: AjustesBody, rol: str = Depends(require_admin)):
    di, df = m._parse_iso(body.periodo_inicio.strip()), m._parse_iso(body.periodo_fin.strip())
    if di and df and df < di:
        raise HTTPException(
            status_code=400,
            detail="La fecha de fin del periodo no puede ser anterior a la de inicio.",
        )
    aj = m.cargar_ajustes()
    aj["periodo_actual"] = body.periodo_actual.strip().upper()
    aj["periodo_fecha_inicio"] = di.isoformat() if di else ""
    aj["periodo_fecha_fin"] = df.isoformat() if df else ""
    m.guardar_ajustes(aj)
    return {"ok": True, "ajustes": aj}


# ---------- Datos ----------

@router.get("/datos")
async def datos_info(rol: str = Depends(require_admin)):
    return {
        "datos": m.datos_meta(),
        "ni": m.ni_meta(),
        "salud": m.panel_salud(),
        "ajustes": m.cargar_ajustes(),
    }


@router.post("/datos/upload")
async def datos_upload(archivo: UploadFile = File(...), rol: str = Depends(require_admin)):
    import os
    import uuid
    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in (".xls", ".xlsx", ".csv"):
        raise HTTPException(status_code=400, detail="Formato no soportado.")
    tmp_path = os.path.join(m.TMP_DIR, f"upload_{uuid.uuid4().hex[:8]}{ext}")
    with open(tmp_path, "wb") as f:
        f.write(await archivo.read())
    try:
        m.guardar_datos(tmp_path, archivo.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        m._eliminar_silenciosamente(tmp_path)
    return {"ok": True, "datos": m.datos_meta()}


@router.post("/datos/nuevo-ingreso")
async def nuevo_ingreso_upload(archivo: UploadFile = File(...), rol: str = Depends(require_admin)):
    import os
    import uuid
    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in (".xls", ".xlsx"):
        raise HTTPException(status_code=400, detail="Formato no soportado.")
    tmp_path = os.path.join(m.TMP_DIR, f"upload_ni_{uuid.uuid4().hex[:8]}{ext}")
    with open(tmp_path, "wb") as f:
        f.write(await archivo.read())
    try:
        m.guardar_nuevo_ingreso(tmp_path, archivo.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        m._eliminar_silenciosamente(tmp_path)
    return {"ok": True, "ni": m.ni_meta()}


@router.post("/datos/nuevo-ingreso/eliminar")
async def nuevo_ingreso_eliminar(rol: str = Depends(require_admin)):
    m.eliminar_nuevo_ingreso()
    return {"ok": True}


# ---------- Plantillas ----------

@router.get("/plantillas")
async def plantillas_list(rol: str = Depends(require_admin)):
    return {"items": m.plantillas.listar()}


@router.post("/plantillas/crear")
async def plantillas_crear(
    nombre: str = Form(...), archivo: UploadFile = File(...), rol: str = Depends(require_admin)
):
    if not archivo.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Sólo se aceptan archivos .docx.")
    try:
        slug = m.plantillas.crear(nombre, await archivo.read())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "slug": slug}


@router.post("/plantillas/{slug}/upload")
async def plantillas_upload(
    slug: str, archivo: UploadFile = File(...), rol: str = Depends(require_admin)
):
    p = m._plantilla_o_404(slug)
    if not archivo.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Sólo se aceptan archivos .docx.")
    try:
        p.replace(await archivo.read())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "info": p.info()}


@router.get("/plantillas/{slug}/download")
async def plantillas_download(slug: str, rol: str = Depends(require_admin)):
    p = m._plantilla_o_404(slug)
    if not p.exists():
        raise HTTPException(status_code=404, detail="No hay archivo cargado.")
    return FileResponse(
        p.path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"plantilla_{slug}.docx",
    )


@router.post("/plantillas/{slug}/restaurar")
async def plantillas_restaurar(
    slug: str, body: PlantillaRestaurarBody, rol: str = Depends(require_admin)
):
    p = m._plantilla_o_404(slug)
    try:
        p.restaurar(body.nombre)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "info": p.info()}


@router.post("/plantillas/{slug}/eliminar")
async def plantillas_eliminar(slug: str, rol: str = Depends(require_admin)):
    try:
        m.plantillas.eliminar(slug)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


# ---------- Carreras ----------

@router.get("/carreras")
async def carreras_list(rol: str = Depends(require_admin)):
    return m.carreras.listar()


@router.post("/carreras/carrera")
async def carreras_guardar(body: CarreraBody, rol: str = Depends(require_admin)):
    try:
        m.carreras.guardar_carrera(body.codigo, body.nombre)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "catalogo": m.carreras.listar()}


@router.post("/carreras/carrera/eliminar")
async def carreras_eliminar(body: CodigoBody, rol: str = Depends(require_admin)):
    m.carreras.eliminar_carrera(body.codigo)
    return {"ok": True, "catalogo": m.carreras.listar()}


@router.post("/carreras/duracion")
async def duracion_guardar(body: DuracionBody, rol: str = Depends(require_admin)):
    try:
        m.carreras.guardar_duracion(body.plan, body.semestres)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "catalogo": m.carreras.listar()}


@router.post("/carreras/duracion/eliminar")
async def duracion_eliminar(body: PlanBody, rol: str = Depends(require_admin)):
    m.carreras.eliminar_duracion(body.plan)
    return {"ok": True, "catalogo": m.carreras.listar()}


# ---------- Comodines ----------

@router.get("/comodines")
async def comodines_list(rol: str = Depends(require_session)):
    return m.comodines.list()


@router.post("/comodines")
async def comodines_crear(body: ComodinBody, rol: str = Depends(require_session)):
    if not body.titulo.strip() or not body.texto.strip():
        raise HTTPException(status_code=400, detail="Título y texto son requeridos.")
    return m.comodines.crear(body.titulo, body.texto)


@router.delete("/comodines/{cid}")
async def comodines_eliminar(cid: str, rol: str = Depends(require_session)):
    ok = m.comodines.eliminar(cid)
    if not ok:
        raise HTTPException(status_code=404, detail="Comodín no encontrado.")
    return {"ok": True}


# ---------- Generación ----------

@router.get("/generar/campos")
async def generar_campos(cuenta: str, plantilla: str = "", rol: str = Depends(require_session)):
    alumno = m.buscar_alumno(cuenta)
    if not alumno:
        raise HTTPException(status_code=404, detail="No se encontró un alumno con esa cuenta.")

    p = m._plantilla_de(plantilla)
    info = p.info() if p else None
    if not info:
        raise HTTPException(status_code=404, detail="La plantilla seleccionada ya no existe.")
    slug = (
        plantilla
        if (m.plantillas.get(plantilla) and m.plantillas.get(plantilla).exists())
        else m.plantillas.default_slug()
    )

    aj = m.cargar_ajustes()
    campos = m.catalogo.construir_campos_form(info["placeholders"], alumno, aj, m.carreras)

    return {
        "alumno": alumno,
        "plantilla": info,
        "plantilla_slug": slug,
        "plantilla_nombre": m.plantillas.nombre_de(slug),
        "campos": campos,
        "ajustes": aj,
    }


@router.post("/preview.pdf")
async def preview_pdf(request: Request, bg: BackgroundTasks, rol: str = Depends(require_session)):
    p, _form, valores = await m._plantilla_y_valores(request)
    return await m._generar_y_servir_async(p, valores, "pdf", basename="preview", bg=bg)


@router.post("/generar/docx")
async def generar_docx(request: Request, bg: BackgroundTasks, rol: str = Depends(require_session)):
    p, form, valores = await m._plantilla_y_valores(request)
    cuenta = form.get("cuenta", "")
    return m._generar_y_servir(p, valores, "docx", basename=f"Constancia_{cuenta}", bg=bg)


@router.post("/generar/pdf")
async def generar_pdf(request: Request, bg: BackgroundTasks, rol: str = Depends(require_session)):
    p, form, valores = await m._plantilla_y_valores(request)
    cuenta = form.get("cuenta", "")
    return await m._generar_y_servir_async(p, valores, "pdf", basename=f"Constancia_{cuenta}", bg=bg)
