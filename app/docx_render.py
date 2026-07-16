"""
Render de plantillas .docx con placeholders [[CAMPO]].

Diseñado para durar: tolera lo que Word y los usuarios hacen con el tiempo.

- Detecta placeholders en TODO el documento: cuerpo, tablas (incluso
  anidadas), encabezados, pies de página y cuadros de texto.
- Tolera espacios dentro de los corchetes ([[ NOMBRE ]]) y minúsculas
  ([[nombre]]); el nombre se normaliza a MAYÚSCULAS.
- Acepta acentos y Ñ en los nombres ([[AÑO]]).
- Reemplaza preservando el formato de los runs no involucrados, aunque
  Word haya partido el placeholder en varios runs.
- Si un placeholder ocupa un párrafo completo y se le pasa cadena vacía,
  el párrafo se elimina del documento (líneas opcionales).
- Reporta avisos de placeholders "sospechosos" (corchetes sueltos, nombres
  mal escritos) para que el admin los corrija al subir la plantilla.
"""
import re

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph


# Nombre válido: letras (con acentos y Ñ), dígitos y guion bajo.
# Se admiten espacios pegados a los corchetes y minúsculas; el nombre
# canónico siempre es la versión en MAYÚSCULAS.
PLACEHOLDER_RE = re.compile(r"\[\[\s*([A-Za-z0-9_ÁÉÍÓÚÜÑáéíóúüñ]+)\s*\]\]")


def normalizar_nombre(nombre: str) -> str:
    return nombre.strip().upper()


# ---------- Iteración exhaustiva de párrafos ----------

def _parrafos_de_contenedor(contenedor):
    """Párrafos directos + los de tablas (recursivo, cubre tablas anidadas)."""
    yield from contenedor.paragraphs
    for tabla in contenedor.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                yield from _parrafos_de_contenedor(celda)


def _parrafos_en_cuadros_de_texto(parte):
    """
    Párrafos dentro de cuadros de texto (w:txbxContent), que python-docx
    no expone en .paragraphs. Word los usa mucho en membretes.
    """
    for txbx in parte._element.iter(qn("w:txbxContent")):
        for p_el in txbx.iter(qn("w:p")):
            yield Paragraph(p_el, parte)


def _todos_los_parrafos(doc):
    """Todos los párrafos del documento: cuerpo, tablas, headers, footers y cuadros de texto."""
    yield from _parrafos_de_contenedor(doc)
    yield from _parrafos_en_cuadros_de_texto(doc)
    for seccion in doc.sections:
        for parte in (
            seccion.header, seccion.footer,
            seccion.first_page_header, seccion.first_page_footer,
            seccion.even_page_header, seccion.even_page_footer,
        ):
            yield from _parrafos_de_contenedor(parte)
            yield from _parrafos_en_cuadros_de_texto(parte)


# ---------- Detección + diagnóstico ----------

def analizar_plantilla(docx_path: str) -> tuple[list[str], list[str]]:
    """
    Devuelve (placeholders, avisos).

    placeholders: nombres normalizados encontrados, ordenados.
    avisos: textos donde parece haber un placeholder mal escrito
    (corchetes sueltos, nombres con espacios o símbolos), para mostrarle
    al admin qué corregir en Word.
    """
    doc = Document(docx_path)
    encontrados: set[str] = set()
    avisos: list[str] = []
    vistos_aviso: set[str] = set()

    for p in _todos_los_parrafos(doc):
        texto = p.text
        for m in PLACEHOLDER_RE.finditer(texto):
            encontrados.add(normalizar_nombre(m.group(1)))

        # Si al quitar los placeholders válidos sobran '[[' o ']]',
        # hay algo mal escrito en este párrafo.
        residuo = PLACEHOLDER_RE.sub("", texto)
        if "[[" in residuo or "]]" in residuo:
            extracto = " ".join(texto.split())
            if len(extracto) > 90:
                extracto = extracto[:90] + "…"
            if extracto not in vistos_aviso:
                vistos_aviso.add(extracto)
                avisos.append(
                    f"Posible placeholder mal escrito en: «{extracto}». "
                    "Revisa que tenga la forma [[NOMBRE]] sin espacios ni símbolos dentro del nombre."
                )

    return sorted(encontrados), avisos


def detectar_placeholders(docx_path: str) -> list[str]:
    """Devuelve los nombres de placeholders presentes en la plantilla, ordenados."""
    return analizar_plantilla(docx_path)[0]


# ---------- Reemplazo a nivel de run preservando formato ----------

def _reemplazar_span(p, start: int, end: int, repl: str):
    """
    Reemplaza el rango [start, end) del texto unido del párrafo por `repl`,
    tocando solo los runs que cubren ese rango.
    """
    runs = p.runs
    pos = 0
    bounds = []
    for r in runs:
        bounds.append((pos, pos + len(r.text)))
        pos += len(r.text)

    first_idx = next(i for i, (s, e) in enumerate(bounds) if s <= start < e)
    last_idx = next(i for i, (s, e) in enumerate(bounds) if s < end <= e)
    fs, _ = bounds[first_idx]
    ls, _ = bounds[last_idx]
    before = runs[first_idx].text[: start - fs]
    after = runs[last_idx].text[end - ls:]

    if first_idx == last_idx:
        runs[first_idx].text = before + repl + after
    else:
        runs[first_idx].text = before + repl
        for k in range(first_idx + 1, last_idx):
            runs[k].text = ""
        runs[last_idx].text = after


def _reemplazar_en_parrafo(p, valores: dict[str, str]):
    """
    Sustituye en el párrafo todos los placeholders cuyo nombre esté en
    `valores` (llaves ya normalizadas). Un solo pase de derecha a izquierda:
    los offsets previos no se mueven y un valor que contenga texto tipo
    [[X]] no se vuelve a procesar (evita bucles infinitos).
    """
    if not p.runs:
        return
    full = "".join(r.text for r in p.runs)
    matches = [
        m for m in PLACEHOLDER_RE.finditer(full)
        if normalizar_nombre(m.group(1)) in valores
    ]
    for m in reversed(matches):
        _reemplazar_span(p, m.start(), m.end(), valores[normalizar_nombre(m.group(1))])


def _eliminar_parrafo(p):
    """
    Quita el párrafo del documento. Las celdas de tabla deben conservar al
    menos un párrafo (requisito del formato .docx): en ese caso solo se vacía.
    """
    el = p._element
    parent = el.getparent()
    if parent is None:  # ya eliminado (celdas combinadas se visitan 2 veces)
        return
    if parent.tag == qn("w:tc") and len(parent.findall(qn("w:p"))) <= 1:
        for r in p.runs:
            r.text = ""
        return
    parent.remove(el)


def _nombre_si_parrafo_es_solo_placeholder(p) -> str | None:
    """Nombre normalizado si el texto del párrafo es exactamente un placeholder."""
    m = PLACEHOLDER_RE.fullmatch(p.text.strip())
    return normalizar_nombre(m.group(1)) if m else None


# ---------- Render principal ----------

def render(template_path: str, valores: dict[str, str],
           opcionales_vacios: set[str] | None = None) -> "Document":
    """
    Devuelve un Document con la plantilla renderizada.

    valores: mapping {placeholder_name: texto}.
    opcionales_vacios: nombres de placeholders cuyo párrafo debe eliminarse
    si su valor viene vacío. Estos placeholders normalmente ocupan
    un párrafo completo (líneas opcionales).
    """
    opcionales_vacios = {normalizar_nombre(ph) for ph in (opcionales_vacios or set())}
    mapping = {
        normalizar_nombre(k): ("" if v is None else str(v))
        for k, v in valores.items()
    }

    doc = Document(template_path)
    for p in list(_todos_los_parrafos(doc)):
        nombre = _nombre_si_parrafo_es_solo_placeholder(p)
        if nombre and nombre in opcionales_vacios and not mapping.get(nombre):
            _eliminar_parrafo(p)
            continue
        _reemplazar_en_parrafo(p, mapping)
    return doc
