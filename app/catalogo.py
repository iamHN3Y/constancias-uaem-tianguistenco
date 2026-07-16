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


# ---------- Convenciones por nombre ----------
# Permiten extender la plantilla sin tocar código: el nombre del placeholder
# decide cómo se comporta en el formulario y al renderizar.
#
#   *_LINEA / LINEA_LIBRE → párrafo opcional: textarea con interruptor;
#                           si queda vacío, el párrafo se elimina del .docx.
#   *_FECHA               → selector de fecha; se imprime como texto formal
#                           corto ("02 de febrero de 2026").
#   cualquier otro        → input de texto libre.

SUFIJOS_OPCIONALES = ("_LINEA", "LINEA_LIBRE")
SUFIJO_FECHA = "_FECHA"


def es_opcional(ph: str) -> bool:
    return any(ph == s or ph.endswith(s) for s in SUFIJOS_OPCIONALES)


def opcionales_de(placeholders) -> set[str]:
    return {ph for ph in placeholders if es_opcional(ph)}


def tipo_de(ph: str) -> str:
    """
    Tipo de control para un placeholder, sea well-known o nuevo. Es la única
    fuente de verdad: la usan tanto el formulario como el parseo del POST,
    así un placeholder agregado a la plantilla funciona de punta a punta.
    """
    meta = ETIQUETAS.get(ph)
    if meta:
        return meta["tipo"]
    if es_opcional(ph):
        return TEXTAREA
    if ph.endswith(SUFIJO_FECHA):
        return DATE_CORTO
    return TEXT


# Placeholders cuyo valor depende del alumno (se derivan de su fila del
# Excel). El resto son compartidos: fechas del periodo, líneas libres, y
# cualquier placeholder nuevo de la plantilla. La generación por lotes usa
# esta distinción: lo por-alumno se deriva solo, lo compartido se pide una vez.
PLACEHOLDERS_POR_ALUMNO = frozenset({
    "NOMBRE_COMPLETO", "CUENTA", "CARRERA_FULL", "SEMESTRE_TEXTO",
    "SEMESTRES_TOTALES", "ARTICULO", "INTERESADO_FRASE",
    "PROMEDIO_GENERAL_LINEA", "PROMEDIO_ULTIMO_LINEA",
})


def _derivar_well_known(alumno: dict, ajustes: dict, carreras) -> dict:
    """
    Devuelve {placeholder: {"valor": str, "iso": str | None}} con los
    valores iniciales editables. `iso` se usa para popular date inputs;
    `valor` es el texto que va al .docx. `carreras` es el catálogo editable
    (app.carreras.Carreras).
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

    # Fechas de inicio/fin del periodo: primero las que el admin guardó en
    # Ajustes (se capturan UNA vez por semestre); si no hay, las fechas
    # típicas del periodo (02 feb / 02 ago) como aproximación editable.
    def _iso_o_none(s):
        try:
            return date.fromisoformat(s) if s else None
        except (TypeError, ValueError):
            return None

    fi = _iso_o_none(ajustes.get("periodo_fecha_inicio", ""))
    ff = _iso_o_none(ajustes.get("periodo_fecha_fin", ""))
    if (fi is None or ff is None) and per_actual:
        try:
            dfi, dff = derivar.fechas_default_periodo(per_actual)
            fi = fi or dfi
            ff = ff or dff
        except Exception:
            pass

    hoy = date.today()

    def _float_o_none(v):
        """Convierte a float tolerando vacíos, comas decimales y basura del Excel."""
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return None

    prm_gr = _float_o_none(alumno.get("PrmGR"))
    prm_per = _float_o_none(alumno.get("Per"))

    # Género sugerido desde la columna Sexo del Excel (si existe).
    genero = derivar.normalizar_genero(
        alumno.get("Sexo", ""), columna_usa_h=bool(ajustes.get("datos_sexo_usa_h")),
    )

    def fecha_pack(d: date | None, fmt):
        if not d:
            return {"valor": "", "iso": ""}
        return {"valor": fmt(d), "iso": d.isoformat()}

    return {
        "NOMBRE_COMPLETO": {"valor": derivar.formato_nombre(str(alumno.get("NombreAlumno", "")))},
        "CUENTA": {"valor": str(alumno.get("Cuenta", ""))},
        "CARRERA_FULL": {"valor": carreras.carrera_full(plan)},
        "SEMESTRE_TEXTO": {"valor": derivar.numero_a_ordinal_texto(semestre_num)},
        # Total de semestres que dura el plan (metadato del catálogo de carreras).
        "SEMESTRES_TOTALES": {"valor": str(carreras.semestres_totales(plan))},
        "PERIODO_INICIO": fecha_pack(fi, derivar.fecha_a_texto_corto),
        "PERIODO_FIN": fecha_pack(ff, derivar.fecha_a_texto_corto),
        "FECHA_EXPEDICION": fecha_pack(hoy, derivar.fecha_a_texto_largo),
        # Género: sugerido desde el Excel, el usuario puede cambiarlo; al
        # cambiarlo el frontend rellena ARTICULO + INTERESADO_FRASE.
        "ARTICULO": {"valor": derivar.articulo_de(genero) if genero else "", "genero": genero},
        "INTERESADO_FRASE": {"valor": derivar.interesado_frase(genero) if genero else ""},
        # Líneas opcionales sugeridas a partir del Excel.
        "PROMEDIO_GENERAL_LINEA": {
            "valor": derivar.linea_promedio_general(prm_gr) if prm_gr is not None else ""
        },
        "PROMEDIO_ULTIMO_LINEA": {
            "valor": derivar.linea_promedio_ultimo_periodo(prm_per) if prm_per is not None else ""
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


def construir_campos_form(placeholders: list[str], alumno: dict, ajustes: dict,
                          carreras) -> list[dict]:
    """
    Para cada placeholder de la plantilla, devuelve un dict listo para pintar
    en el formulario. Los placeholders con tipo HIDDEN_DERIVADO no se incluyen.
    """
    derivados = _derivar_well_known(alumno, ajustes, carreras)
    campos = []
    for ph in placeholders:
        meta = ETIQUETAS.get(ph)
        tipo = tipo_de(ph)
        if tipo == HIDDEN_DERIVADO:
            continue

        d = derivados.get(ph, {})
        campos.append({
            "name": ph,
            "label": meta["label"] if meta else ph.replace("_", " ").capitalize(),
            "tipo": tipo,
            "valor": d.get("valor", ""),
            "iso": d.get("iso", ""),
            "iso_inicio": d.get("iso_inicio", ""),
            "iso_fin": d.get("iso_fin", ""),
            "genero": d.get("genero", ""),
            "opcional": es_opcional(ph),
            # Campo que no está en el catálogo: viene directo de la plantilla
            # (alguien lo agregó en Word). Se marca para avisarlo en la UI.
            "de_plantilla": meta is None,
        })
    return campos


def valores_por_alumno(placeholders: list[str], alumno: dict, ajustes: dict,
                       carreras) -> tuple[dict, list[str]]:
    """
    Valores derivados automáticamente para los placeholders POR ALUMNO de una
    plantilla (generación por lotes). Devuelve (valores, faltantes):

    - valores: {placeholder: texto} solo para los que se pudieron derivar.
    - faltantes: placeholders por-alumno que quedaron sin valor (p. ej.
      ARTICULO sin columna Sexo) — el placeholder queda visible en el .docx
      y el lote lo reporta para revisión manual.
    """
    derivados = _derivar_well_known(alumno, ajustes, carreras)
    valores, faltantes = {}, []
    for ph in placeholders:
        if ph not in PLACEHOLDERS_POR_ALUMNO:
            continue
        v = derivados.get(ph, {}).get("valor", "")
        if v or es_opcional(ph):
            # Las líneas opcionales sin dato se pasan vacías: su párrafo
            # se elimina solo, no es un faltante.
            valores[ph] = v
        else:
            faltantes.append(ph)
    return valores, faltantes
