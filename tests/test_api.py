"""
Test de integración de la API completa (sin LibreOffice: solo .docx).

Recorre el flujo real: login → subir plantilla(s) → subir datos → generar,
incluyendo los escenarios de longevidad: comodines nuevos en la plantilla,
archivos corruptos, edición directa en disco, historial/restauración,
catálogo de carreras editable, búsqueda por nombre y alumnos de nuevo ingreso.
"""
import io
import os
import sys

import pytest
from docx import Document

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXCEL_NUEVO_INGRESO = os.path.join(REPO_ROOT, "data", "Alumnos de nuevo ingreso 26B.xlsx")


def docx_bytes(*parrafos: str) -> bytes:
    doc = Document()
    for t in parrafos:
        doc.add_paragraph(t)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def client(tmp_path):
    import app.main as m
    from app.carreras import Carreras
    from app.plantilla_universal import RegistroPlantillas
    from fastapi.testclient import TestClient

    workdir = str(tmp_path)
    originales = {
        k: getattr(m, k)
        for k in ("DATA_DIR", "PLANTILLAS_DIR", "TMP_DIR", "DATOS_CSV",
                  "NUEVO_INGRESO_CSV", "AJUSTES_FILE", "CARRERAS_FILE",
                  "plantillas", "carreras")
    }
    m.DATA_DIR = workdir
    m.PLANTILLAS_DIR = os.path.join(workdir, "plantillas")
    m.TMP_DIR = os.path.join(workdir, "tmp")
    m.DATOS_CSV = os.path.join(workdir, "datos.csv")
    m.NUEVO_INGRESO_CSV = os.path.join(workdir, "nuevo_ingreso.csv")
    m.AJUSTES_FILE = os.path.join(workdir, "ajustes.json")
    m.CARRERAS_FILE = os.path.join(workdir, "carreras.json")
    os.makedirs(m.TMP_DIR, exist_ok=True)
    m.plantillas = RegistroPlantillas(m.PLANTILLAS_DIR)
    m.carreras = Carreras(m.CARRERAS_FILE)

    c = TestClient(m.app)
    c.cookies.set("rol", "admin")
    c.modulo = m
    yield c

    for k, v in originales.items():
        setattr(m, k, v)


CSV_OK = (
    "CUENTA,NombreAlumno,Plan,PerInicio,PrmGR,Per,Sit,Sexo\n"
    "2014694.0,PÉREZ / JUAN,ICO-F19,2023B,8.5,9.1,Regular,M\n"
    "2015000,GARCÍA / ANA MARÍA,ICB-F25,2024B,9.2,9.5,Regular,F\n"
    "2016000,LÓPEZ / PEDRO,XYZ-F30,2024B,,,Regular,\n"
)


def _crear_plantilla(client, nombre, contenido):
    return client.post(
        "/plantillas/crear",
        data={"nombre": nombre},
        files={"archivo": ("t.docx", contenido)},
        follow_redirects=False,
    )


def _subir_datos(client, csv=CSV_OK):
    return client.post("/datos/upload", files={"archivo": ("d.csv", csv.encode())},
                       follow_redirects=False)


def test_flujo_completo(client):
    m = client.modulo

    r = _crear_plantilla(client, "Constancia general", docx_bytes(
        "Constancia de [[ARTICULO]] [[NOMBRE_COMPLETO]] cuenta [[CUENTA]] de [[CARRERA_FULL]]",
        "[[COMODIN_NUEVO]]",
        "[[BECA_LINEA]]",
        "Examen: [[EXAMEN_FECHA]]",
    ))
    assert "ok=creada" in r.headers["location"]

    r = _subir_datos(client)
    assert "ok=1" in r.headers["location"]

    # El formulario muestra el comodín nuevo, la fecha por convención y el
    # género prellenado desde la columna Sexo.
    r = client.get("/generar", params={"cuenta": "2014694"})
    assert r.status_code == 200
    for esperado in ("COMODIN_NUEVO", "BECA_LINEA", "fecha_EXAMEN_FECHA"):
        assert esperado in r.text
    assert 'value="M" required checked' in r.text.replace("  ", " ")

    # Generar .docx.
    r = client.post("/generar/docx", data={
        "cuenta": "2014694",
        "plantilla": "constancia-general",
        "__genero__": "M",
        "campo_NOMBRE_COMPLETO": "PÉREZ JUAN",
        "campo_CUENTA": "2014694",
        "campo_CARRERA_FULL": "LICENCIATURA DE INGENIERIA EN COMPUTACION",
        "campo_COMODIN_NUEVO": "VALOR NUEVO",
        "campo_BECA_LINEA": "",
        "fecha_EXAMEN_FECHA": "2026-07-09",
    })
    assert r.status_code == 200
    textos = "\n".join(p.text for p in Document(io.BytesIO(r.content)).paragraphs)
    assert "VALOR NUEVO" in textos
    assert "09 de julio de 2026" in textos
    assert "el alumno PÉREZ JUAN" in textos
    assert "BECA_LINEA" not in textos


def test_ajustes_periodo_con_fechas(client):
    """El admin guarda periodo + fechas una vez; el formulario sale
    prellenado con ellas, y el semestre se calcula solo."""
    _crear_plantilla(client, "General", docx_bytes(
        "[[SEMESTRE_TEXTO]] semestre, del [[PERIODO_INICIO]] al [[PERIODO_FIN]]",
    ))
    _subir_datos(client)

    r = client.post("/ajustes", data={
        "periodo_actual": "2026A",
        "periodo_inicio": "2026-02-09",
        "periodo_fin": "2026-07-24",
    }, follow_redirects=False)
    assert r.status_code == 303 and "error" not in r.headers["location"]

    # Formulario individual: fechas guardadas + semestre calculado
    # (PerInicio 2023B → 2026A = sexto).
    r = client.get("/generar", params={"cuenta": "2014694"})
    assert 'value="2026-02-09"' in r.text
    assert 'value="2026-07-24"' in r.text
    assert 'value="sexto"' in r.text


def test_ajustes_rechaza_fechas_invertidas(client):
    r = client.post("/ajustes", data={
        "periodo_actual": "2026A",
        "periodo_inicio": "2026-07-24",
        "periodo_fin": "2026-02-09",
    }, follow_redirects=False)
    assert "error_ajustes=" in r.headers["location"]


def test_busqueda_por_nombre(client):
    _crear_plantilla(client, "General", docx_bytes("[[NOMBRE_COMPLETO]]"))
    _subir_datos(client)

    # 'garcia ana' encuentra a GARCÍA / ANA MARÍA sin acentos ni mayúsculas.
    r = client.post("/buscar", data={"cuenta": "garcia ana", "plantilla": "general"},
                    follow_redirects=True)
    assert "GARCÍA / ANA MARÍA" in r.text
    assert "/generar?cuenta=2015000" in r.text

    r = client.post("/buscar", data={"cuenta": "nadie asi"}, follow_redirects=True)
    assert "Ningún alumno coincide" in r.text


def test_multiples_plantillas_y_seleccion(client):
    _crear_plantilla(client, "General", docx_bytes("ES: [[NOMBRE_COMPLETO]]"))
    _crear_plantilla(client, "En inglés", docx_bytes("EN: [[NOMBRE_COMPLETO]]"))
    _subir_datos(client)

    r = client.post("/generar/docx", data={
        "cuenta": "2014694", "plantilla": "en-ingles",
        "campo_NOMBRE_COMPLETO": "JUAN",
    })
    textos = "\n".join(p.text for p in Document(io.BytesIO(r.content)).paragraphs)
    assert "EN: JUAN" in textos

    # Eliminar una plantilla funciona; la última no se puede.
    r = client.post("/plantillas/en-ingles/eliminar", follow_redirects=False)
    assert "ok=eliminada" in r.headers["location"]
    r = client.post("/plantillas/general/eliminar", follow_redirects=False)
    assert "error=" in r.headers["location"]


def test_carreras_endpoint_y_efecto_en_generar(client):
    m = client.modulo
    _crear_plantilla(client, "General", docx_bytes("[[CARRERA_FULL]]"))
    _subir_datos(client)

    # El plan XYZ-F30 no está en el catálogo: aparece crudo.
    r = client.get("/generar", params={"cuenta": "2016000"})
    assert "XYZ-F30" in r.text

    # El admin da de alta la carrera desde la UI…
    r = client.post("/carreras/carrera",
                    data={"codigo": "XYZ", "nombre": "LICENCIATURA EN PRUEBAS"},
                    follow_redirects=False)
    assert "ok=1" in r.headers["location"]

    # …y el formulario la usa de inmediato, sin reiniciar.
    r = client.get("/generar", params={"cuenta": "2016000"})
    assert "LICENCIATURA EN PRUEBAS" in r.text


def test_subidas_corruptas_no_rompen_nada(client):
    m = client.modulo
    _crear_plantilla(client, "General", docx_bytes("[[BUENO]]"))

    r = client.post("/plantillas/general/upload",
                    files={"archivo": ("malo.docx", b"garbage")}, follow_redirects=False)
    assert "error=" in r.headers["location"]
    assert m.plantillas.get("general").info()["placeholders"] == ["BUENO"]

    _subir_datos(client)
    r = _subir_datos(client, csv="a,b\n1,2\n")
    assert "error=" in r.headers["location"]
    assert m.buscar_alumno("2014694") is not None  # datos previos intactos


def test_edicion_directa_en_disco_refresca_placeholders(client):
    m = client.modulo
    _crear_plantilla(client, "General", docx_bytes("[[VIEJO]]"))
    p = m.plantillas.get("general")
    with open(p.path, "wb") as f:
        f.write(docx_bytes("[[VIEJO]] [[COMODIN_NUEVO]]"))
    r = client.get("/plantillas")
    assert "COMODIN_NUEVO" in r.text


def test_historial_restauracion_y_descarga(client):
    m = client.modulo
    _crear_plantilla(client, "General", docx_bytes("[[V1]]"))
    client.post("/plantillas/general/upload",
                files={"archivo": ("v2.docx", docx_bytes("[[V2]]"))}, follow_redirects=False)

    h = m.plantillas.get("general").historial()
    assert h

    r = client.post("/plantillas/general/restaurar", data={"nombre": h[0]["nombre"]},
                    follow_redirects=False)
    assert "ok=restaurada" in r.headers["location"]
    assert m.plantillas.get("general").info()["placeholders"] == ["V1"]

    r = client.get("/plantillas/general/download")
    assert r.status_code == 200
    assert len(r.content) > 1000


def test_invitado_no_puede_administrar(client):
    _crear_plantilla(client, "General", docx_bytes("[[X]]"))
    client.cookies.set("rol", "invitado")

    for url, data in (
        ("/plantillas/general/eliminar", {}),
        ("/carreras/carrera", {"codigo": "AAA", "nombre": "X"}),
    ):
        r = client.post(url, data=data, follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"

    r = client.get("/plantillas/general/download", follow_redirects=False)
    assert r.status_code == 303

    r = client.post("/plantillas/crear", data={"nombre": "Y"},
                    files={"archivo": ("t.docx", docx_bytes("[[X]]"))}, follow_redirects=False)
    assert r.headers["location"] == "/"


# ---------- Alumnos de nuevo ingreso ----------

def _subir_nuevo_ingreso(client, contenido: bytes, nombre="Alumnos de nuevo ingreso 26B.xlsx"):
    return client.post("/datos/nuevo-ingreso", files={"archivo": (nombre, contenido)},
                       follow_redirects=False)


@pytest.mark.skipif(not os.path.exists(EXCEL_NUEVO_INGRESO), reason="requiere el xlsx real (gitignorado)")
def test_nuevo_ingreso_importa_excel_real(client):
    m = client.modulo
    with open(EXCEL_NUEVO_INGRESO, "rb") as f:
        contenido = f.read()

    r = _subir_nuevo_ingreso(client, contenido)
    assert "ok=1" in r.headers["location"]

    df = m.leer_nuevo_ingreso()
    assert len(df) == 633  # todas las filas del Excel, sin fila de encabezado real
    assert list(df.columns) == ["Cuenta", "NombreAlumno", "Plan", "PerInicio"]

    meta = m.ni_meta()
    assert meta["filas"] == 633
    assert meta["filename"] == "Alumnos de nuevo ingreso 26B.xlsx"
    assert meta["periodo"] == "2026B"

    # Una cuenta cualquiera del archivo se compone bien: "PATERNO MATERNO / NOMBRES".
    fila = df.loc[df["Cuenta"] == "2671789"].iloc[0]
    assert fila["NombreAlumno"] == "ANTONIO MORALES / VANESSA"
    assert fila["Plan"] == "ICB-F25"
    assert fila["PerInicio"] == "2026B"


@pytest.mark.skipif(not os.path.exists(EXCEL_NUEVO_INGRESO), reason="requiere el xlsx real (gitignorado)")
def test_nuevo_ingreso_nombre_con_materno_vacio(client):
    m = client.modulo
    with open(EXCEL_NUEVO_INGRESO, "rb") as f:
        _subir_nuevo_ingreso(client, f.read())

    df = m.leer_nuevo_ingreso()
    fila = df.loc[df["Cuenta"] == "2671606"].iloc[0]
    # Sin apellido materno: no debe quedar doble espacio ni un espacio suelto.
    assert fila["NombreAlumno"] == "GUTIERREZ / ALEXANDRA GUADALUPE"


def test_padron_principal_tiene_prioridad_sobre_nuevo_ingreso(client):
    m = client.modulo
    _crear_plantilla(client, "General", docx_bytes("[[NOMBRE_COMPLETO]]"))
    _subir_datos(client)  # incluye la cuenta 2014694 = PÉREZ / JUAN

    ni_csv = (
        "Cuenta,NombreAlumno,Plan,PerInicio\n"
        "2014694,OTRO NOMBRE / DUPLICADO,ICO-F26,2026B\n"
        "9000001,NUEVO / ALUMNO,ICO-F26,2026B\n"
    )
    with open(m.NUEVO_INGRESO_CSV, "w", encoding="utf-8") as f:
        f.write(ni_csv)

    alumno = m.buscar_alumno("2014694")
    assert alumno["NombreAlumno"] == "PÉREZ / JUAN"
    assert "_origen" not in alumno

    # Cuenta que solo existe en nuevo ingreso: se marca su origen.
    alumno_ni = m.buscar_alumno("9000001")
    assert alumno_ni["NombreAlumno"] == "NUEVO / ALUMNO"
    assert alumno_ni["_origen"] == "nuevo_ingreso"

    # Cuenta que no existe en ningún lado.
    assert m.buscar_alumno("0000000") is None


def test_purga_automatica_al_subir_padron_nuevo(client):
    m = client.modulo
    ni_csv = (
        "Cuenta,NombreAlumno,Plan,PerInicio\n"
        "2014694,PÉREZ / JUAN,ICO-F26,2026B\n"
        "9000002,OTRO / ALUMNO,ICO-F26,2026B\n"
    )
    with open(m.NUEVO_INGRESO_CSV, "w", encoding="utf-8") as f:
        f.write(ni_csv)
    aj = m.cargar_ajustes()
    aj["ni_filas"] = 2
    m.guardar_ajustes(aj)

    _crear_plantilla(client, "General", docx_bytes("[[NOMBRE_COMPLETO]]"))
    _subir_datos(client)  # el padrón trae la cuenta 2014694

    df = m.leer_nuevo_ingreso()
    assert "2014694" not in set(df["Cuenta"])
    assert "9000002" in set(df["Cuenta"])
    assert m.ni_meta()["filas"] == 1


def test_buscar_por_nombre_no_duplica(client):
    m = client.modulo
    _crear_plantilla(client, "General", docx_bytes("[[NOMBRE_COMPLETO]]"))
    _subir_datos(client)  # 2014694 = PÉREZ / JUAN

    ni_csv = (
        "Cuenta,NombreAlumno,Plan,PerInicio\n"
        "2014694,PÉREZ / JUAN,ICO-F26,2026B\n"
        "9000003,PÉREZ / OTRO,ICO-F26,2026B\n"
    )
    with open(m.NUEVO_INGRESO_CSV, "w", encoding="utf-8") as f:
        f.write(ni_csv)

    resultados = m.buscar_por_nombre("perez")
    cuentas = [r["Cuenta"] for r in resultados]
    assert cuentas.count("2014694") == 1  # no se repite aunque esté en ambas fuentes
    assert "9000003" in cuentas


def test_nuevo_ingreso_eliminar(client):
    m = client.modulo
    with open(m.NUEVO_INGRESO_CSV, "w", encoding="utf-8") as f:
        f.write("Cuenta,NombreAlumno,Plan,PerInicio\n9000004,X / Y,ICO-F26,2026B\n")
    aj = m.cargar_ajustes()
    aj.update({"ni_filename": "x.xlsx", "ni_fecha_carga": "hoy", "ni_filas": 1, "ni_periodo": "2026B"})
    m.guardar_ajustes(aj)

    r = client.post("/datos/nuevo-ingreso/eliminar", follow_redirects=False)
    assert "ok=1" in r.headers["location"]
    assert m.ni_meta() is None
    assert not os.path.exists(m.NUEVO_INGRESO_CSV)


def test_nuevo_ingreso_rechaza_columnas_incorrectas(client):
    import pandas as pd

    buf = io.BytesIO()
    pd.DataFrame([[1, 2, 3], [4, 5, 6]]).to_excel(buf, index=False, header=False)
    r = _subir_nuevo_ingreso(client, buf.getvalue())
    assert "error=" in r.headers["location"]


# ---------- Rediseño: búsqueda en vivo, preparación del semestre, ayuda ----------

def test_api_alumnos_sugerencias(client):
    _crear_plantilla(client, "General", docx_bytes("[[NOMBRE_COMPLETO]]"))
    _subir_datos(client)

    # Por inicio de cuenta.
    r = client.get("/api/alumnos", params={"q": "2015"})
    assert r.status_code == 200
    assert [a["cuenta"] for a in r.json()] == ["2015000"]
    assert r.json()[0]["nombre"] == "GARCÍA ANA MARÍA"

    # Por nombre, sin acentos.
    r = client.get("/api/alumnos", params={"q": "garcia ana"})
    assert [a["cuenta"] for a in r.json()] == ["2015000"]

    # Consultas muy cortas no buscan nada.
    assert client.get("/api/alumnos", params={"q": "2"}).json() == []

    # Sin sesión no hay datos de alumnos.
    client.cookies.clear()
    assert client.get("/api/alumnos", params={"q": "2015"}).status_code == 401


def test_preparacion_detecta_carreras_faltantes(client):
    m = client.modulo
    _crear_plantilla(client, "General", docx_bytes("[[CARRERA_FULL]]"))
    _subir_datos(client)  # trae un plan XYZ-F30 que no está en el catálogo

    faltan = m.planes_sin_carrera()
    assert {"codigo": "XYZ", "alumnos": 1} in faltan

    prep = m.preparacion_semestre(m.cargar_ajustes(), m.plantillas.listar())
    pasos = {p["clave"]: p for p in prep["pasos"]}
    assert not pasos["periodo"]["ok"]          # sin periodo configurado
    assert pasos["padron"]["ok"]
    assert pasos["plantillas"]["ok"]
    assert not pasos["carreras"]["ok"]
    assert "XYZ" in pasos["carreras"]["detalle"]
    assert not prep["listo"]

    r = client.get("/")
    assert "Preparación del semestre" in r.text
    r = client.get("/carreras")
    assert "Dar de alta" in r.text and "XYZ" in r.text


def test_centro_de_ayuda_renderiza_todas_las_guias(client):
    from app import ayuda

    r = client.get("/ayuda")
    assert r.status_code == 200
    for a in ayuda.ARTICULOS:
        assert f'/ayuda/{a["slug"]}' in r.text
        ra = client.get(f'/ayuda/{a["slug"]}')
        assert ra.status_code == 200, a["slug"]
        assert a["titulo"] in ra.text

    # La referencia de campos se genera desde el catálogo real.
    r = client.get("/ayuda/campos-de-plantilla")
    for nombre in ("NOMBRE_COMPLETO", "FECHA_EXPEDICION", "PERIODO_VACACIONAL_LINEA"):
        assert f"[[{nombre}]]" in r.text

    # Slug desconocido vuelve al índice.
    r = client.get("/ayuda/no-existe", follow_redirects=False)
    assert r.headers["location"] == "/ayuda"


def test_ayuda_disponible_sin_sesion_y_plantilla_ejemplo(client):
    client.cookies.clear()
    assert client.get("/ayuda").status_code == 200
    assert client.get("/ayuda/bienvenida").status_code == 200
    r = client.get("/ayuda/plantilla-ejemplo.docx")
    assert r.status_code == 200
    Document(io.BytesIO(r.content))  # es un .docx válido


def test_cada_campo_tiene_ayuda_para_el_modo_ayuda(client):
    from app import ayuda, catalogo

    for nombre in catalogo.ETIQUETAS:
        if catalogo.tipo_de(nombre) != catalogo.HIDDEN_DERIVADO:
            assert nombre in ayuda.AYUDA_CAMPOS, f"falta ayuda para {nombre}"
    # Los campos inventados en Word también reciben una explicación.
    assert "opcional" in ayuda.ayuda_campo("BECA_LINEA")
    assert "calendario" in ayuda.ayuda_campo("EXAMEN_FECHA")


def test_pantallas_admin_tienen_modo_ayuda_y_recorrido(client):
    _crear_plantilla(client, "General", docx_bytes("[[NOMBRE_COMPLETO]] [[ARTICULO]] [[BECA_LINEA]]"))
    _subir_datos(client)
    for url in ("/", "/datos", "/plantillas", "/carreras", "/generar?cuenta=2014694"):
        r = client.get(url)
        assert r.status_code == 200, url
        assert 'id="btnModoAyuda"' in r.text, url
        assert "data-ayuda=" in r.text, url
        assert "data-recorrido=" in r.text, url
