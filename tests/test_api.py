"""
Test de integración de la API completa (sin LibreOffice: solo .docx).

Recorre el flujo real: login → subir plantilla(s) → subir datos → generar
(individual y por lotes), incluyendo los escenarios de longevidad:
comodines nuevos en la plantilla, archivos corruptos, edición directa en
disco, historial/restauración, catálogo de carreras editable y búsqueda
por nombre.
"""
import io
import os
import sys
import zipfile

import pytest
from docx import Document

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


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
                  "AJUSTES_FILE", "CARRERAS_FILE", "plantillas", "carreras")
    }
    m.DATA_DIR = workdir
    m.PLANTILLAS_DIR = os.path.join(workdir, "plantillas")
    m.TMP_DIR = os.path.join(workdir, "tmp")
    m.DATOS_CSV = os.path.join(workdir, "datos.csv")
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
    """El admin guarda periodo + fechas una vez; el formulario y el lote
    salen prellenados con ellas, y el semestre se calcula solo."""
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

    # El lote hereda las mismas fechas.
    r = client.get("/lote")
    assert 'value="2026-02-09"' in r.text
    assert 'value="2026-07-24"' in r.text


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


def test_lote_docx(client):
    _crear_plantilla(client, "General", docx_bytes(
        "[[ARTICULO]] [[NOMBRE_COMPLETO]], cuenta [[CUENTA]]",
        "[[PROMEDIO_GENERAL_LINEA]]",
    ))
    _subir_datos(client)

    r = client.post("/lote/generar", data={
        "plantilla": "general",
        "formato": "docx",
        "cuentas": "2014694\n2015000, 9999999",
        "incluir_promedio_general": "on",
    })
    assert r.status_code == 200
    assert "Resultado del lote" in r.text
    assert "<strong>2</strong>" in r.text  # 2 generadas de 3 cuentas
    assert "cuenta no encontrada" in r.text

    # El ZIP existe y trae los dos .docx correctos.
    inicio = r.text.index("/lote/zip/")
    url_zip = r.text[inicio:r.text.index('"', inicio)]
    rz = client.get(url_zip)
    assert rz.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(rz.content))
    assert sorted(zf.namelist()) == ["Constancia_2014694.docx", "Constancia_2015000.docx"]

    doc = Document(io.BytesIO(zf.read("Constancia_2015000.docx")))
    textos = "\n".join(p.text for p in doc.paragraphs)
    assert "la alumna GARCÍA ANA MARÍA" in textos   # género desde Sexo=F
    assert "9.2" in textos                           # promedio incluido


def test_lote_sin_genero_marca_revisar(client):
    _crear_plantilla(client, "General", docx_bytes("[[ARTICULO]] [[NOMBRE_COMPLETO]]"))
    _subir_datos(client)
    r = client.post("/lote/generar", data={
        "plantilla": "general", "formato": "docx", "cuentas": "2016000",
    })
    # Sexo vacío → la constancia se genera pero se marca para revisión y
    # el placeholder queda visible.
    assert "revisar" in r.text and "ARTICULO" in r.text


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
