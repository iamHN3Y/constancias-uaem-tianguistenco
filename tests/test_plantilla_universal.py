"""
Tests de la gestión de la plantilla universal: cache auto-validado,
reemplazo seguro e historial.
"""
import io
import os
import sys

import pytest
from docx import Document

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.plantilla_universal import PlantillaUniversal, RegistroPlantillas


def docx_bytes(*parrafos: str) -> bytes:
    doc = Document()
    for t in parrafos:
        doc.add_paragraph(t)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def pu(tmp_path):
    return PlantillaUniversal(str(tmp_path / "plantillas"))


def test_replace_y_deteccion(pu):
    meta = pu.replace(docx_bytes("Hola [[NOMBRE]] con [[CUENTA]]"))
    assert meta["placeholders"] == ["CUENTA", "NOMBRE"]
    assert pu.exists()


def test_edicion_directa_en_disco_se_detecta_sola(pu):
    """El caso clave: alguien reemplaza el .docx en data/ sin usar la UI."""
    pu.replace(docx_bytes("[[VIEJO]]"))
    assert pu.info()["placeholders"] == ["VIEJO"]

    # Simula copiar un archivo encima (mtime/tamaño cambian).
    with open(pu.path, "wb") as f:
        f.write(docx_bytes("[[VIEJO]] y ahora [[COMODIN_NUEVO]]"))

    assert pu.info()["placeholders"] == ["COMODIN_NUEVO", "VIEJO"]


def test_meta_corrupto_se_regenera(pu):
    pu.replace(docx_bytes("[[X]]"))
    with open(pu._meta_path, "w", encoding="utf-8") as f:
        f.write("{esto no es json")
    assert pu.info()["placeholders"] == ["X"]


def test_subida_corrupta_no_destruye_plantilla(pu):
    pu.replace(docx_bytes("[[BUENO]]"))
    with pytest.raises(ValueError):
        pu.replace(b"esto no es un docx")
    assert pu.exists()
    assert pu.info()["placeholders"] == ["BUENO"]


def test_docx_sin_placeholders_se_rechaza(pu):
    pu.replace(docx_bytes("[[BUENO]]"))
    with pytest.raises(ValueError):
        pu.replace(docx_bytes("un documento sin campos"))
    assert pu.info()["placeholders"] == ["BUENO"]


def test_historial_y_restauracion(pu):
    pu.replace(docx_bytes("[[V1]]"))
    pu.replace(docx_bytes("[[V2]]"))
    assert pu.info()["placeholders"] == ["V2"]

    historial = pu.historial()
    assert len(historial) == 1  # la V1 respaldada

    meta = pu.restaurar(historial[0]["nombre"])
    assert meta["placeholders"] == ["V1"]
    # Restaurar respaldó a su vez la V2.
    assert any("V2" for _ in pu.historial())
    assert len(pu.historial()) == 2


def test_restaurar_nombre_invalido(pu):
    pu.replace(docx_bytes("[[X]]"))
    with pytest.raises(ValueError):
        pu.restaurar("../../etc/passwd")
    with pytest.raises(ValueError):
        pu.restaurar("universal_99999999_999999.docx")


def test_avisos_se_guardan_en_meta(pu):
    meta = pu.replace(docx_bytes("[[BIEN]]", "[[MAL ESCRITO]]"))
    assert meta["placeholders"] == ["BIEN"]
    assert len(meta["avisos"]) == 1


# ---------- Registro de plantillas con nombre ----------

@pytest.fixture
def registro(tmp_path):
    return RegistroPlantillas(str(tmp_path / "plantillas"))


def test_crear_y_listar(registro):
    slug = registro.crear("Constancia en inglés", docx_bytes("[[NAME]]"))
    assert slug == "constancia-en-ingles"
    items = registro.listar()
    assert len(items) == 1
    assert items[0]["nombre"] == "Constancia en inglés"
    assert items[0]["info"]["placeholders"] == ["NAME"]
    assert registro.default_slug() == slug


def test_nombres_repetidos_generan_slugs_distintos(registro):
    s1 = registro.crear("Prácticas", docx_bytes("[[A]]"))
    s2 = registro.crear("Prácticas", docx_bytes("[[B]]"))
    assert s1 == "practicas" and s2 == "practicas-2"


def test_crear_con_docx_invalido_no_registra(registro):
    with pytest.raises(ValueError):
        registro.crear("Rota", b"no es docx")
    assert registro.slugs() == []


def test_no_se_puede_eliminar_la_ultima(registro):
    slug = registro.crear("Única", docx_bytes("[[X]]"))
    with pytest.raises(ValueError):
        registro.eliminar(slug)
    otro = registro.crear("Otra", docx_bytes("[[Y]]"))
    registro.eliminar(slug)
    assert registro.slugs() == [otro]


def test_slug_invalido_devuelve_none(registro):
    registro.crear("Normal", docx_bytes("[[X]]"))
    assert registro.get("../../../etc") is None
    assert registro.get("no-existe") is None


def test_migracion_de_layout_viejo(tmp_path):
    """Un data/plantillas/ con universal.docx suelto (formato anterior) se
    migra solo a carpeta propia + registro, conservando meta e historial."""
    base = tmp_path / "plantillas"
    base.mkdir()
    (base / "universal.docx").write_bytes(docx_bytes("[[VIEJO]]"))
    (base / "_meta.json").write_text('{"placeholders": ["VIEJO"]}', encoding="utf-8")
    (base / "historial").mkdir()
    (base / "historial" / "universal_20250101_120000.docx").write_bytes(docx_bytes("[[V0]]"))

    registro = RegistroPlantillas(str(base))
    assert registro.slugs() == ["universal"]
    assert registro.nombre_de("universal") == "Constancia general"
    p = registro.get("universal")
    assert p.info()["placeholders"] == ["VIEJO"]
    assert len(p.historial()) == 1  # el historial viejo sobrevive

    # Re-instanciar no duplica ni rompe nada (idempotente).
    registro2 = RegistroPlantillas(str(base))
    assert registro2.slugs() == ["universal"]
