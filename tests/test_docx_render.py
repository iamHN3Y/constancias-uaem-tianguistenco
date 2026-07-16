"""
Tests del motor de render: detección y reemplazo de placeholders.

Cubren los escenarios que Word produce en la vida real: placeholders
partidos en varios runs, en encabezados/pies, en tablas anidadas, con
espacios o minúsculas, y valores maliciosos/raros.
"""
import os
import sys

import pytest
from docx import Document

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.docx_render import analizar_plantilla, detectar_placeholders, render


@pytest.fixture
def docx_path(tmp_path):
    def _crear(builder):
        doc = Document()
        builder(doc)
        path = str(tmp_path / "plantilla.docx")
        doc.save(path)
        return path
    return _crear


def texto_completo(doc) -> str:
    partes = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                partes.extend(p.text for p in cell.paragraphs)
    for s in doc.sections:
        partes.extend(p.text for p in s.header.paragraphs)
        partes.extend(p.text for p in s.footer.paragraphs)
    return "\n".join(partes)


# ---------- Detección ----------

def test_detecta_placeholder_simple(docx_path):
    path = docx_path(lambda d: d.add_paragraph("Hola [[NOMBRE_COMPLETO]] bien"))
    assert detectar_placeholders(path) == ["NOMBRE_COMPLETO"]


def test_detecta_con_espacios_y_minusculas(docx_path):
    def b(d):
        d.add_paragraph("[[ CUENTA ]] y [[carrera_full]]")
    assert detectar_placeholders(docx_path(b)) == ["CARRERA_FULL", "CUENTA"]


def test_detecta_acentos_y_enie(docx_path):
    path = docx_path(lambda d: d.add_paragraph("[[AÑO]]"))
    assert detectar_placeholders(path) == ["AÑO"]


def test_detecta_partido_en_varios_runs(docx_path):
    def b(d):
        p = d.add_paragraph()
        p.add_run("[[NOM")
        p.add_run("BRE]]")
    assert detectar_placeholders(docx_path(b)) == ["NOMBRE"]


def test_detecta_en_tabla(docx_path):
    def b(d):
        tabla = d.add_table(rows=1, cols=1)
        tabla.cell(0, 0).paragraphs[0].add_run("[[EN_TABLA]]")
    assert detectar_placeholders(docx_path(b)) == ["EN_TABLA"]


def test_detecta_en_tabla_anidada(docx_path):
    def b(d):
        tabla = d.add_table(rows=1, cols=1)
        interna = tabla.cell(0, 0).add_table(rows=1, cols=1)
        interna.cell(0, 0).paragraphs[0].add_run("[[ANIDADO]]")
    assert detectar_placeholders(docx_path(b)) == ["ANIDADO"]


def test_detecta_en_header_y_footer(docx_path):
    def b(d):
        d.sections[0].header.paragraphs[0].add_run("[[EN_HEADER]]")
        d.sections[0].footer.paragraphs[0].add_run("[[EN_FOOTER]]")
        d.add_paragraph("cuerpo")
    assert detectar_placeholders(docx_path(b)) == ["EN_FOOTER", "EN_HEADER"]


def test_avisos_de_placeholder_mal_escrito(docx_path):
    def b(d):
        d.add_paragraph("[[NOMBRE COMPLETO]]")   # espacio dentro del nombre
        d.add_paragraph("[[SIN_CERRAR")           # sin cerrar
        d.add_paragraph("[[BIEN]]")               # correcto: no genera aviso
    placeholders, avisos = analizar_plantilla(docx_path(b))
    assert placeholders == ["BIEN"]
    assert len(avisos) == 2


# ---------- Render ----------

def test_reemplazo_simple(docx_path):
    path = docx_path(lambda d: d.add_paragraph("Se otorga a [[NOMBRE]]."))
    doc = render(path, {"NOMBRE": "JUAN PÉREZ"})
    assert "Se otorga a JUAN PÉREZ." in texto_completo(doc)


def test_reemplazo_partido_en_runs_conserva_texto_alrededor(docx_path):
    def b(d):
        p = d.add_paragraph()
        p.add_run("Alumno: [[NOM")
        p.add_run("BRE]] fin")
    doc = render(docx_path(b), {"NOMBRE": "ANA"})
    assert "Alumno: ANA fin" in texto_completo(doc)


def test_reemplazo_en_header_footer_y_tabla(docx_path):
    def b(d):
        d.sections[0].header.paragraphs[0].add_run("Periodo [[PERIODO]]")
        d.sections[0].footer.paragraphs[0].add_run("Página de [[QUIEN]]")
        tabla = d.add_table(rows=1, cols=1)
        tabla.cell(0, 0).paragraphs[0].add_run("[[EN_TABLA]]")
    doc = render(docx_path(b), {"PERIODO": "2026A", "QUIEN": "control", "EN_TABLA": "dato"})
    full = texto_completo(doc)
    assert "Periodo 2026A" in full
    assert "Página de control" in full
    assert "dato" in full
    assert "[[" not in full


def test_reemplazo_con_espacios_y_minusculas_en_plantilla(docx_path):
    path = docx_path(lambda d: d.add_paragraph("[[ cuenta ]]"))
    doc = render(path, {"CUENTA": "2014694"})
    assert "2014694" in texto_completo(doc)


def test_multiples_ocurrencias_mismo_placeholder(docx_path):
    path = docx_path(lambda d: d.add_paragraph("[[X]] y [[X]] y [[X]]"))
    doc = render(path, {"X": "a"})
    assert "a y a y a" in texto_completo(doc)


def test_valor_con_pinta_de_placeholder_no_cicla(docx_path):
    # Un usuario travieso escribe "[[X]]" como valor: no debe colgarse
    # ni re-expandirse.
    path = docx_path(lambda d: d.add_paragraph("Hola [[X]]"))
    doc = render(path, {"X": "[[X]]"})
    assert "Hola [[X]]" in texto_completo(doc)


def test_linea_opcional_vacia_se_elimina(docx_path):
    def b(d):
        d.add_paragraph("antes")
        d.add_paragraph("[[PROMEDIO_LINEA]]")
        d.add_paragraph("después")
    doc = render(docx_path(b), {"PROMEDIO_LINEA": ""}, opcionales_vacios={"PROMEDIO_LINEA"})
    textos = [p.text for p in doc.paragraphs]
    assert textos == ["antes", "después"]


def test_linea_opcional_con_valor_se_conserva(docx_path):
    path = docx_path(lambda d: d.add_paragraph("[[PROMEDIO_LINEA]]"))
    doc = render(path, {"PROMEDIO_LINEA": "Promedio 9.5"}, opcionales_vacios={"PROMEDIO_LINEA"})
    assert "Promedio 9.5" in texto_completo(doc)


def test_linea_opcional_vacia_en_celda_unica_no_rompe_tabla(docx_path):
    # Las celdas .docx requieren al menos un párrafo: se vacía en vez de borrarse.
    def b(d):
        tabla = d.add_table(rows=1, cols=1)
        tabla.cell(0, 0).paragraphs[0].add_run("[[NOTA_LINEA]]")
    doc = render(docx_path(b), {"NOTA_LINEA": ""}, opcionales_vacios={"NOTA_LINEA"})
    cell = doc.tables[0].cell(0, 0)
    assert len(cell.paragraphs) >= 1
    assert cell.paragraphs[0].text == ""


def test_placeholder_sin_valor_queda_intacto(docx_path):
    # Si el form no envía un valor, el placeholder queda visible en el
    # documento (señal clara de que falta algo) en vez de romper.
    path = docx_path(lambda d: d.add_paragraph("[[DESCONOCIDO]]"))
    doc = render(path, {"OTRO": "x"})
    assert "[[DESCONOCIDO]]" in texto_completo(doc)


def test_valor_none_se_trata_como_vacio(docx_path):
    path = docx_path(lambda d: d.add_paragraph("a[[X]]b"))
    doc = render(path, {"X": None})
    assert "ab" in texto_completo(doc)
