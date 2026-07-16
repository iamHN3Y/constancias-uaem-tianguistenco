"""
Tests de las convenciones del catálogo y de las derivaciones de texto.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import catalogo, derivar
from app.carreras import Carreras


@pytest.fixture
def carreras(tmp_path):
    return Carreras(str(tmp_path / "carreras.json"))


# ---------- Convenciones por nombre ----------

def test_tipo_well_known():
    assert catalogo.tipo_de("NOMBRE_COMPLETO") == catalogo.TEXT
    assert catalogo.tipo_de("FECHA_EXPEDICION") == catalogo.DATE_LARGO
    assert catalogo.tipo_de("PERIODO_VACACIONAL_LINEA") == catalogo.DATE_RANGO
    assert catalogo.tipo_de("ARTICULO") == catalogo.RADIO_GENERO


def test_convencion_linea_es_textarea_opcional():
    assert catalogo.tipo_de("BECA_LINEA") == catalogo.TEXTAREA
    assert catalogo.es_opcional("BECA_LINEA")
    assert catalogo.es_opcional("LINEA_LIBRE")
    assert not catalogo.es_opcional("NOMBRE_COMPLETO")


def test_convencion_fecha_es_date():
    assert catalogo.tipo_de("EXAMEN_FECHA") == catalogo.DATE_CORTO
    assert not catalogo.es_opcional("EXAMEN_FECHA")


def test_placeholder_desconocido_es_texto():
    assert catalogo.tipo_de("MATRICULA_SEP") == catalogo.TEXT


def test_construir_campos_incluye_desconocidos(carreras):
    campos = catalogo.construir_campos_form(
        ["NOMBRE_COMPLETO", "COMODIN_NUEVO", "BECA_LINEA", "EXAMEN_FECHA"],
        alumno={}, ajustes={}, carreras=carreras,
    )
    por_nombre = {c["name"]: c for c in campos}
    assert set(por_nombre) == {"NOMBRE_COMPLETO", "COMODIN_NUEVO", "BECA_LINEA", "EXAMEN_FECHA"}
    assert por_nombre["COMODIN_NUEVO"]["de_plantilla"] is True
    assert por_nombre["NOMBRE_COMPLETO"]["de_plantilla"] is False
    assert por_nombre["BECA_LINEA"]["opcional"] is True
    assert por_nombre["EXAMEN_FECHA"]["tipo"] == catalogo.DATE_CORTO


def test_hidden_derivado_no_aparece_en_form(carreras):
    campos = catalogo.construir_campos_form(["INTERESADO_FRASE"], alumno={}, ajustes={},
                                            carreras=carreras)
    assert campos == []


def test_construir_campos_con_alumno_vacio_no_truena(carreras):
    # Datos faltantes en el Excel no deben tirar la página de generación.
    campos = catalogo.construir_campos_form(
        list(catalogo.ETIQUETAS.keys()), alumno={}, ajustes={}, carreras=carreras,
    )
    assert campos  # se construyó algo sin lanzar


def test_fechas_de_periodo_guardadas_en_ajustes(carreras):
    """Las fechas capturadas una vez en Ajustes prellenan todas las constancias."""
    campos = catalogo.construir_campos_form(
        ["PERIODO_INICIO", "PERIODO_FIN"], alumno={},
        ajustes={"periodo_actual": "2026A",
                 "periodo_fecha_inicio": "2026-02-09",
                 "periodo_fecha_fin": "2026-07-24"},
        carreras=carreras,
    )
    por_nombre = {c["name"]: c for c in campos}
    assert por_nombre["PERIODO_INICIO"]["iso"] == "2026-02-09"
    assert por_nombre["PERIODO_INICIO"]["valor"] == "09 de febrero de 2026"
    assert por_nombre["PERIODO_FIN"]["iso"] == "2026-07-24"


def test_fechas_de_periodo_fallback_a_defaults(carreras):
    """Sin fechas guardadas, se usan las típicas del periodo (02 feb / 02 ago)."""
    campos = catalogo.construir_campos_form(
        ["PERIODO_INICIO", "PERIODO_FIN"], alumno={},
        ajustes={"periodo_actual": "2026A"}, carreras=carreras,
    )
    por_nombre = {c["name"]: c for c in campos}
    assert por_nombre["PERIODO_INICIO"]["iso"] == "2026-02-02"
    assert por_nombre["PERIODO_FIN"]["iso"] == "2026-08-02"


def test_fecha_guardada_invalida_no_truena(carreras):
    campos = catalogo.construir_campos_form(
        ["PERIODO_INICIO"], alumno={},
        ajustes={"periodo_actual": "2026A", "periodo_fecha_inicio": "basura"},
        carreras=carreras,
    )
    assert campos[0]["iso"] == "2026-02-02"  # cae al default


def test_semestre_calculado_desde_periodos(carreras):
    """PerInicio 2023B + periodo activo 2026A → sexto semestre, en letra."""
    campos = catalogo.construir_campos_form(
        ["SEMESTRE_TEXTO"], alumno={"PerInicio": "2023B"},
        ajustes={"periodo_actual": "2026A"}, carreras=carreras,
    )
    assert campos[0]["valor"] == "sexto"


def test_genero_prellenado_desde_columna_sexo(carreras):
    campos = catalogo.construir_campos_form(
        ["ARTICULO"], alumno={"Sexo": "F"}, ajustes={}, carreras=carreras,
    )
    assert campos[0]["genero"] == "F"
    assert campos[0]["valor"] == "la alumna"


def test_valores_por_alumno_deriva_y_reporta_faltantes(carreras):
    placeholders = ["NOMBRE_COMPLETO", "CUENTA", "ARTICULO", "PROMEDIO_GENERAL_LINEA",
                    "LINEA_LIBRE", "FECHA_EXPEDICION"]
    alumno = {"NombreAlumno": "PEREZ / JUAN", "Cuenta": "123", "PrmGR": "8.5"}
    valores, faltantes = catalogo.valores_por_alumno(placeholders, alumno, {}, carreras)
    assert valores["NOMBRE_COMPLETO"] == "PEREZ JUAN"
    assert valores["CUENTA"] == "123"
    assert "8.5" in valores["PROMEDIO_GENERAL_LINEA"]
    # Sin columna Sexo, ARTICULO no se puede derivar → va en faltantes.
    assert faltantes == ["ARTICULO"]
    # Lo compartido (LINEA_LIBRE, FECHA_EXPEDICION) no lo toca esta función.
    assert "LINEA_LIBRE" not in valores
    assert "FECHA_EXPEDICION" not in valores


def test_valores_por_alumno_con_sexo(carreras):
    valores, faltantes = catalogo.valores_por_alumno(
        ["ARTICULO", "INTERESADO_FRASE"], {"Sexo": "FEMENINO"}, {}, carreras,
    )
    assert valores["ARTICULO"] == "la alumna"
    assert valores["INTERESADO_FRASE"] == "de la interesada"
    assert faltantes == []


# ---------- Derivaciones ----------

def test_fecha_texto_corto():
    assert derivar.fecha_a_texto_corto(date(2026, 2, 2)) == "02 de febrero de 2026"


def test_fecha_texto_largo():
    assert derivar.fecha_a_texto_largo(date(2026, 2, 6)) == (
        "a los seis días del mes de febrero del año dos mil veintiséis"
    )
    assert derivar.fecha_a_texto_largo(date(2026, 3, 1)).startswith("al primer día")


def test_periodo_a_semestre():
    assert derivar.periodo_a_semestre("2023B", "2026A") == 6
    assert derivar.periodo_a_semestre("2026A", "2026A") == 1


def test_formato_nombre():
    assert derivar.formato_nombre("ARMAS ARAUJO / RICARDO ISMAEL") == "ARMAS ARAUJO RICARDO ISMAEL"


def test_genero():
    assert derivar.articulo_de("F") == "la alumna"
    assert derivar.articulo_de("M") == "el alumno"
    assert derivar.interesado_frase("f") == "de la interesada"


def test_decimal_a_letra():
    assert derivar.decimal_a_letra(9.2) == "nueve punto dos"
    assert derivar.decimal_a_letra(10.0) == "diez"


def test_normalizar_genero():
    assert derivar.normalizar_genero("F") == "F"
    assert derivar.normalizar_genero("FEMENINO") == "F"
    assert derivar.normalizar_genero("MUJER") == "F"
    assert derivar.normalizar_genero("MASCULINO") == "M"
    assert derivar.normalizar_genero("HOMBRE") == "M"
    assert derivar.normalizar_genero("H") == "M"
    assert derivar.normalizar_genero("") == ""
    assert derivar.normalizar_genero("X") == ""
    # 'M' es ambigua: Masculino en esquema M/F, Mujer en esquema H/M.
    assert derivar.normalizar_genero("M", columna_usa_h=False) == "M"
    assert derivar.normalizar_genero("M", columna_usa_h=True) == "F"


# ---------- Catálogo de carreras editable ----------

def test_carreras_seed_y_lookup(carreras):
    assert carreras.carrera_full("ICO-F19") == "LICENCIATURA DE INGENIERIA EN COMPUTACION"
    assert carreras.semestres_totales("ICB-F25") == 8
    assert carreras.semestres_totales("ICO-F19") == 10  # default


def test_plan_desconocido_devuelve_crudo(carreras):
    # Carrera nueva que aún no está en el catálogo: el sistema no truena,
    # muestra el código crudo y el usuario lo corrige en el formulario.
    assert carreras.carrera_full("XYZ-F30") == "XYZ-F30"


def test_alta_de_carrera_nueva_sin_codigo(carreras):
    carreras.guardar_carrera("xyz", "licenciatura en pruebas")
    assert carreras.carrera_full("XYZ-F30") == "LICENCIATURA EN PRUEBAS"
    assert carreras.eliminar_carrera("XYZ")
    assert carreras.carrera_full("XYZ-F30") == "XYZ-F30"


def test_alta_de_duracion(carreras):
    carreras.guardar_duracion("ico-f30", "9")
    assert carreras.semestres_totales("ICO-F30") == 9
    assert carreras.eliminar_duracion("ICO-F30")
    assert carreras.semestres_totales("ICO-F30") == 10


def test_carrera_validaciones(carreras):
    with pytest.raises(ValueError):
        carreras.guardar_carrera("ICO-F19", "X")  # código con guion
    with pytest.raises(ValueError):
        carreras.guardar_carrera("ICO", "")       # sin nombre
    with pytest.raises(ValueError):
        carreras.guardar_duracion("IPI-F26", "muchos")


def test_edicion_manual_del_json_se_refleja(carreras, tmp_path):
    # Alguien edita data/carreras.json a mano: se refleja sin reiniciar.
    import json
    with open(carreras.path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["carreras"]["ZZZ"] = "CARRERA EDITADA A MANO"
    with open(carreras.path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    assert carreras.carrera_full("ZZZ-F99") == "CARRERA EDITADA A MANO"


def test_json_corrupto_no_truena(carreras):
    with open(carreras.path, "w", encoding="utf-8") as f:
        f.write("{roto")
    assert carreras.carrera_full("ICO-F19") == "ICO-F19"  # degrada al crudo
    assert carreras.semestres_totales("X") == 10
