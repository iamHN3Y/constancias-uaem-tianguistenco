"""
Catálogo de placeholders 'well-known'.

Cada entrada describe cómo presentar el campo en el formulario y cómo
auto-derivar su valor inicial desde el alumno + ajustes de la sesión.
Los placeholders que NO estén aquí se muestran como inputs de texto vacíos.
"""
from datetime import date

from . import derivar


# Tipos de control del frontend.
TEXT = "text"
TEXTAREA = "textarea"
DATE_CORTO = "date_corto"        # date input → "02 de febrero de 2026"
DATE_LARGO = "date_largo"        # date input → "a los X días del mes de…"
DATE_RANGO = "date_rango"        # 2 dates    → "Periodo vacacional… al …"
RADIO_GENERO = "radio_genero"
HIDDEN_DERIVADO = "hidden"       # se rellena solo, no se muestra en el form


# Sufijos que marcan a un placeholder como "línea opcional": ocupa un párrafo
# entero y el párrafo se elimina si el valor queda vacío al renderizar.
# Permite que el usuario agregue [[BECA_LINEA]], [[NOTA_LINEA]], etc. en la
# plantilla sin tocar código: aparecen como textareas opcionales.
SUFIJOS_OPCIONALES = ("_LINEA", "LINEA_LIBRE")


def es_opcional(ph: str) -> bool:
    return any(ph == s or ph.endswith(s) for s in SUFIJOS_OPCIONALES)


def opcionales_de(placeholders) -> set[str]:
    return {ph for ph in placeholders if es_opcional(ph)}


def _derivar_well_known(alumno: dict, ajustes: dict) -> dict:
    """
    Devuelve {placeholder: {"valor": str, "iso": str | None}} con los
    valores iniciales editables. `iso` se usa para popular date inputs;
    `valor` es el texto que va al .docx.
    """
    per_actual = ajustes.get("periodo_actual", "")
    per_inicio = str(alumno.get("PerInicio", "")).strip()
    plan = str(alumno.get("Plan", ""))

    semestre_num = 0
    if per_actual and per_inicio:
        try:
            semestre_num = derivar.periodo_a_semestre(per_inicio, per_actual)
        except Exception:
            semestre_num = 0

    fi, ff = (None, None)
    if per_actual:
        try:
            fi, ff = derivar.fechas_default_periodo(per_actual)
        except Exception:
            pass

    hoy = date.today()
    prm_gr = alumno.get("PrmGR")
    prm_per = alumno.get("Per")

    def fecha_pack(d: date | None, fmt):
        if not d:
            return {"valor": "", "iso": ""}
        return {"valor": fmt(d), "iso": d.isoformat()}

    return {
        "NOMBRE_COMPLETO": {"valor": derivar.formato_nombre(str(alumno.get("NombreAlumno", "")))},
        "CUENTA": {"valor": str(alumno.get("Cuenta", ""))},
        "CARRERA_FULL": {"valor": derivar.plan_a_carrera_full(plan)},
        "SEMESTRE_TEXTO": {"valor": derivar.numero_a_ordinal_texto(semestre_num)},
        # Total de semestres que dura el plan (metadato del catálogo de carreras).
        "SEMESTRES_TOTALES": {"valor": str(derivar.semestres_totales(plan))},
        "PERIODO_INICIO": fecha_pack(fi, derivar.fecha_a_texto_corto),
        "PERIODO_FIN": fecha_pack(ff, derivar.fecha_a_texto_corto),
        "FECHA_EXPEDICION": fecha_pack(hoy, derivar.fecha_a_texto_largo),
        # Género: el usuario lo elige; al cambiarlo el frontend rellena
        # ARTICULO + INTERESADO_FRASE simultáneamente.
        "ARTICULO": {"valor": ""},
        "INTERESADO_FRASE": {"valor": ""},
        # Líneas opcionales sugeridas a partir del Excel.
        "PROMEDIO_GENERAL_LINEA": {
            "valor": (
                derivar.linea_promedio_general(float(prm_gr))
                if prm_gr is not None and str(prm_gr) != "" else ""
            )
        },
        "PROMEDIO_ULTIMO_LINEA": {
            "valor": (
                derivar.linea_promedio_ultimo_periodo(float(prm_per))
                if prm_per is not None and str(prm_per) != "" else ""
            )
        },
        "PROMEDIO_PERIODO_LINEA": {"valor": ""},
        "PERIODO_VACACIONAL_LINEA": {"valor": "", "iso_inicio": "", "iso_fin": ""},
        "LINEA_LIBRE": {"valor": ""},
    }


# Etiqueta y tipo de control por placeholder.
ETIQUETAS: dict[str, dict] = {
    "NOMBRE_COMPLETO":  {"label": "Nombre completo",          "tipo": TEXT},
    "CUENTA":           {"label": "Número de cuenta",         "tipo": TEXT},
    "CARRERA_FULL":     {"label": "Carrera (texto largo)",    "tipo": TEXT},
    "SEMESTRE_TEXTO":   {"label": "Semestre (en letra)",      "tipo": TEXT},
    "SEMESTRES_TOTALES":{"label": "Total de semestres del plan", "tipo": TEXT},
    "PERIODO_INICIO":   {"label": "Inicio del periodo",       "tipo": DATE_CORTO},
    "PERIODO_FIN":      {"label": "Fin del periodo",          "tipo": DATE_CORTO},
    "FECHA_EXPEDICION": {"label": "Fecha de expedición",      "tipo": DATE_LARGO},
    "ARTICULO":         {"label": "Género",                   "tipo": RADIO_GENERO},
    "INTERESADO_FRASE": {"label": "Frase del interesado",     "tipo": HIDDEN_DERIVADO},
    "PROMEDIO_GENERAL_LINEA":   {"label": "Línea: promedio general",          "tipo": TEXTAREA},
    "PROMEDIO_ULTIMO_LINEA":    {"label": "Línea: promedio del último",       "tipo": TEXTAREA},
    "PROMEDIO_PERIODO_LINEA":   {"label": "Línea: promedio de un periodo",    "tipo": TEXTAREA},
    "PERIODO_VACACIONAL_LINEA": {"label": "Línea: periodo vacacional",        "tipo": DATE_RANGO},
    "LINEA_LIBRE":              {"label": "Línea libre",                       "tipo": TEXTAREA},
}


def construir_campos_form(placeholders: list[str], alumno: dict, ajustes: dict) -> list[dict]:
    """
    Para cada placeholder de la plantilla, devuelve un dict listo para pintar
    en el formulario. Los placeholders con tipo HIDDEN_DERIVADO no se incluyen.
    """
    derivados = _derivar_well_known(alumno, ajustes)
    campos = []
    for ph in placeholders:
        meta = ETIQUETAS.get(ph)
        if meta and meta["tipo"] == HIDDEN_DERIVADO:
            continue

        d = derivados.get(ph, {})
        opcional = es_opcional(ph)
        if meta:
            campos.append({
                "name": ph,
                "label": meta["label"],
                "tipo": meta["tipo"],
                "valor": d.get("valor", ""),
                "iso": d.get("iso", ""),
                "iso_inicio": d.get("iso_inicio", ""),
                "iso_fin": d.get("iso_fin", ""),
                "opcional": opcional,
            })
        else:
            # Placeholder no listado: si su nombre sigue la convención
            # _LINEA lo tratamos como textarea opcional (su párrafo se borra
            # si queda vacío). En otro caso queda como input de texto.
            campos.append({
                "name": ph,
                "label": ph.replace("_", " ").capitalize(),
                "tipo": TEXTAREA if opcional else TEXT,
                "valor": "",
                "iso": "",
                "iso_inicio": "",
                "iso_fin": "",
                "opcional": opcional,
            })
    return campos
