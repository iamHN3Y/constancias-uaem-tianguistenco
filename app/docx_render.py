"""
Render de plantillas .docx con placeholders [[CAMPO]].

- Detecta placeholders escaneando el texto unido de cada párrafo (no por run).
- Reemplaza preservando el formato de los runs no involucrados.
- Si un placeholder ocupa un párrafo completo y se le pasa cadena vacía,
  el párrafo se elimina del documento (líneas opcionales).
"""
import re
from docx import Document


PLACEHOLDER_RE = re.compile(r"\[\[([A-Z0-9_]+)\]\]")


# ---------- Detección ----------

def detectar_placeholders(docx_path: str) -> list[str]:
    """Devuelve los nombres de placeholders presentes en la plantilla, ordenados."""
    doc = Document(docx_path)
    encontrados = set()
    for p in _todos_los_parrafos(doc):
        for m in PLACEHOLDER_RE.findall(p.text):
            encontrados.add(m)
    return sorted(encontrados)


def _todos_los_parrafos(doc):
    yield from doc.paragraphs
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                yield from cell.paragraphs


# ---------- Reemplazo a nivel de run preservando formato ----------

def smart_replace(p, find: str, repl: str) -> bool:
    """
    Reemplaza la primera ocurrencia de `find` en el párrafo `p` por `repl`,
    sólo modificando los runs que cubren la coincidencia. Devuelve True si reemplazó.
    """
    runs = p.runs
    if not runs:
        return False
    full = "".join(r.text for r in runs)
    if find not in full:
        return False

    pos = 0
    bounds = []
    for r in runs:
        bounds.append((pos, pos + len(r.text)))
        pos += len(r.text)

    start = full.index(find)
    end = start + len(find)
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
    return True


def _replace_all_in_paragraph(p, mapping: dict[str, str]):
    """Aplica todos los reemplazos hasta que ya no haya cambios."""
    cambio = True
    while cambio:
        cambio = False
        for ph, val in mapping.items():
            if smart_replace(p, f"[[{ph}]]", val):
                cambio = True


def _eliminar_parrafo(p):
    """Quita el párrafo del documento (no del XML del flujo de cuerpo padre)."""
    el = p._element
    el.getparent().remove(el)


def _parrafo_es_solo_placeholder(p, ph: str) -> bool:
    """True si el texto unido del párrafo es exactamente '[[PH]]' (con espacios alrededor opcionales)."""
    return p.text.strip() == f"[[{ph}]]"


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
    opcionales_vacios = opcionales_vacios or set()
    doc = Document(template_path)

    # Eliminar párrafos opcionales vacíos primero, en cuerpo y celdas.
    for p in list(doc.paragraphs):
        for ph in opcionales_vacios:
            if not valores.get(ph) and _parrafo_es_solo_placeholder(p, ph):
                _eliminar_parrafo(p)
                break

    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in list(cell.paragraphs):
                    for ph in opcionales_vacios:
                        if not valores.get(ph) and _parrafo_es_solo_placeholder(p, ph):
                            _eliminar_parrafo(p)
                            break

    # Reemplazar el resto
    mapping = {k: (v if v is not None else "") for k, v in valores.items()}
    for p in _todos_los_parrafos(doc):
        _replace_all_in_paragraph(p, mapping)

    return doc
