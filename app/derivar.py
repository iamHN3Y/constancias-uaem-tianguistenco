"""
Funciones de derivación: convierten datos crudos del Excel (o entradas
del usuario) a los textos exactos que van en una constancia.
"""
from datetime import date
from num2words import num2words


# ---------- Catálogos ----------

PLAN_A_CARRERA = {
    "ICB": "LICENCIATURA EN INGENIERIA EN CIBERSEGURIDAD",
    "ICO": "LICENCIATURA DE INGENIERIA EN COMPUTACION",
    "IME": "LICENCIATURA DE INGENIERIA MECANICA",
    "IPI": "LICENCIATURA DE INGENIERO EN PRODUCCION INDUSTRIAL",
    "IPL": "LICENCIATURA DE INGENIERO EN PLASTICOS",
    "IPLS": "LICENCIATURA DE INGENIERO EN PLASTICOS",
    "ISW": "LICENCIATURA DE INGENIERO EN SOFTWARE",
    "LSD": "LICENCIATURA EN SEGURIDAD CIUDADANA",
}

# Total de semestres por plan de estudios (metadato; la plantilla actual no lo
# imprime). Se llavea por el código COMPLETO del plan —con sufijo— porque la
# reestructuración baja la duración SIN cambiar el prefijo: un alumno de
# IPI-F26 cursa 9 semestres, pero IPI-F19 sigue durando 10. Cualquier plan que
# no esté aquí se asume de 10 semestres (ver semestres_totales).
SEMESTRES_TOTALES_DEFAULT = 10

PLAN_A_SEMESTRES_TOTALES = {
    "ICB-F25": 8,
    "IPI-F26": 9,
    "IPLS-F26": 9,
    "ISW-F26": 9,
}

ORDINALES = {
    1: "primer", 2: "segundo", 3: "tercer", 4: "cuarto", 5: "quinto",
    6: "sexto", 7: "septimo", 8: "octavo", 9: "noveno", 10: "decimo",
    11: "undecimo", 12: "duodecimo",
}

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


# ---------- Conversores básicos ----------

def entero_a_letra(n: int) -> str:
    """2026 → 'dos mil veintiséis'."""
    return num2words(n, lang="es")


def decimal_a_letra(valor: float) -> str:
    """
    9.2 → 'nueve punto dos'
    10.0 → 'diez'  (sin decimal)
    8.45 → 'ocho punto cuarenta y cinco'  (lee los decimales como entero)
    """
    if valor != valor:  # NaN
        return ""
    entero = int(valor)
    decimal = round((valor - entero) * 100)
    if decimal == 0:
        return num2words(entero, lang="es")
    # Si el decimal es múltiplo de 10, leemos solo el dígito significativo
    if decimal % 10 == 0:
        decimal //= 10
    return f"{num2words(entero, lang='es')} punto {num2words(decimal, lang='es')}"


def numero_a_ordinal_texto(n: int) -> str:
    """6 → 'sexto'.  Para n>12, devuelve cadena vacía."""
    return ORDINALES.get(n, "")


# ---------- Datos del alumno ----------

def formato_nombre(nombre_excel: str) -> str:
    """'ARMAS ARAUJO / RICARDO ISMAEL' → 'ARMAS ARAUJO RICARDO ISMAEL'."""
    if not nombre_excel:
        return ""
    sin_barra = nombre_excel.replace("/", " ")
    return " ".join(sin_barra.split())


def plan_a_carrera_full(plan: str) -> str:
    """'ICO-F19' → 'LICENCIATURA DE INGENIERIA EN COMPUTACION'.

    Si el código no está en el catálogo devuelve la cadena cruda; el usuario
    podrá corregirla manualmente en el formulario.
    """
    if not plan:
        return ""
    codigo = plan.split("-", 1)[0].strip().upper()
    return PLAN_A_CARRERA.get(codigo, plan)


def semestres_totales(plan: str) -> int:
    """Total de semestres del plan de estudios.

    'IPI-F26' → 9, 'ICB-F25' → 8. Cualquier plan no reestructurado (incluido
    el mismo prefijo en su versión anterior, p. ej. 'IPI-F19') dura 10.
    Es metadato: la plantilla actual no imprime este dato.
    """
    if not plan:
        return SEMESTRES_TOTALES_DEFAULT
    codigo = plan.strip().upper()
    return PLAN_A_SEMESTRES_TOTALES.get(codigo, SEMESTRES_TOTALES_DEFAULT)


# ---------- Periodos ----------

def parse_periodo(per: str) -> tuple[int, str]:
    """'2023B' → (2023, 'B')."""
    per = per.strip().upper()
    return int(per[:-1]), per[-1]


def periodo_a_indice(per: str) -> int:
    """Convierte un periodo a un índice secuencial: 2023A=0, 2023B=1, 2024A=2, ..."""
    anio, mitad = parse_periodo(per)
    return anio * 2 + (1 if mitad == "B" else 0)


def periodo_a_semestre(per_inicio: str, per_actual: str) -> int:
    """('2023B', '2026A') → 6 (es decir, sexto semestre)."""
    return periodo_a_indice(per_actual) - periodo_a_indice(per_inicio) + 1


def fechas_default_periodo(per: str) -> tuple[date, date]:
    """
    Fechas tentativas de inicio/fin del periodo.
    A → 02 de febrero a 02 de agosto.
    B → 02 de agosto a 02 de febrero del año siguiente.

    Son sólo defaults editables; el calendario real lo ajusta el usuario.
    """
    anio, mitad = parse_periodo(per)
    if mitad == "A":
        return date(anio, 2, 2), date(anio, 8, 2)
    return date(anio, 8, 2), date(anio + 1, 2, 2)


# ---------- Fechas en texto ----------

def fecha_a_texto_corto(d: date) -> str:
    """date(2026, 2, 2) → '02 de febrero de 2026'."""
    return f"{d.day:02d} de {MESES[d.month - 1]} de {d.year}"


def fecha_a_texto_largo(d: date) -> str:
    """
    date(2026, 2, 6) →
    'a los seis días del mes de febrero del año dos mil veintiséis'.

    Para día 1 usa 'al primer día del mes...'.
    """
    if d.day == 1:
        return (f"al primer día del mes de {MESES[d.month - 1]} "
                f"del año {entero_a_letra(d.year)}")
    return (f"a los {entero_a_letra(d.day)} días del mes de "
            f"{MESES[d.month - 1]} del año {entero_a_letra(d.year)}")


# ---------- Líneas opcionales auto-armadas ----------

def linea_promedio_general(valor: float) -> str:
    """8.6 → 'Promedio general 8.6 (ocho punto seis)'."""
    if not valor and valor != 0:
        return ""
    return f"Promedio general {valor} ({decimal_a_letra(valor)})"


def linea_promedio_ultimo_periodo(valor: float) -> str:
    """8.4 → 'Promedio del último periodo 8.4 (ocho punto cuatro)'."""
    if not valor and valor != 0:
        return ""
    return f"Promedio del último periodo {valor} ({decimal_a_letra(valor)})"


def linea_promedio_periodo(periodo: str, valor: float) -> str:
    """('2025B', 8.4) → 'Promedio del periodo 2025B 8.4 (ocho punto cuatro).'."""
    if not valor and valor != 0:
        return ""
    return f"Promedio del periodo {periodo} {valor} ({decimal_a_letra(valor)})."


def linea_periodo_vacacional(inicio: date, fin: date) -> str:
    """
    (date(2026, 7, 20), date(2026, 7, 31)) →
    'Periodo vacacional comprendido a partir del 20 al 31 de julio del 2026.'
    """
    if not inicio or not fin:
        return ""
    if inicio.month == fin.month and inicio.year == fin.year:
        return (f"Periodo vacacional comprendido a partir del {inicio.day} "
                f"al {fin.day} de {MESES[inicio.month - 1]} del {inicio.year}.")
    return (f"Periodo vacacional comprendido a partir del {fecha_a_texto_corto(inicio)} "
            f"al {fecha_a_texto_corto(fin)}.")


# ---------- Género ----------

def articulo_de(genero: str) -> str:
    """'M'→'el alumno', 'F'→'la alumna'."""
    return "la alumna" if genero.upper().startswith("F") else "el alumno"


def interesado_frase(genero: str) -> str:
    """'M'→'del interesado', 'F'→'de la interesada'."""
    return "de la interesada" if genero.upper().startswith("F") else "del interesado"
