"""
Centro de ayuda integrado: registro de guías y ayuda por campo.

Todo el texto de ayuda vive aquí o en `templates/ayuda/articulos/`, nunca
duplicado en otra parte:

  - ARTICULOS: índice de guías. El cuerpo de cada una está en
    `templates/ayuda/articulos/<slug>.html` (Jinja, puede usar el contexto
    de la app para mostrar datos reales: campos del catálogo, carreras…).
  - ayuda_campo(): explicación de cada campo del formulario de generación.
    La usa el modo ayuda (al pasar el cursor) y la guía de referencia de
    campos, así ambas dicen siempre lo mismo.

Para agregar una guía nueva: añade una entrada a ARTICULOS y crea su
archivo .html con el mismo slug. Aparece sola en el índice y en el buscador.
"""
from __future__ import annotations

from datetime import date

from . import catalogo, derivar


# ---------- Guías ----------

CATEGORIAS = (
    ("empezar", "Para empezar"),
    ("generar", "Generar constancias"),
    ("semestre", "Administración del semestre"),
    ("plantillas", "Plantillas"),
    ("problemas", "Solución de problemas"),
)

# solo_admin: la guía describe tareas que solo puede hacer un administrador.
# Se muestra a todos (alguien puede heredar el puesto), pero marcada.
# pantalla: (url, texto) para el botón «Ir a la pantalla» al pie de la guía.
ARTICULOS: list[dict] = [
    {
        "slug": "bienvenida",
        "categoria": "empezar",
        "titulo": "Conoce el sistema en 3 minutos",
        "resumen": "Qué hace la herramienta, quién puede hacer qué y cómo es el flujo de trabajo de principio a fin.",
        "palabras": "inicio introducción roles invitado administrador qué es",
        "solo_admin": False,
        "pantalla": ("/", "Ir al inicio"),
    },
    {
        "slug": "como-pedir-ayuda",
        "categoria": "empezar",
        "titulo": "Cómo pedir ayuda dentro del sistema",
        "resumen": "Modo ayuda, recorridos guiados, este centro de ayuda y atajos de teclado.",
        "palabras": "modo ayuda tutorial recorrido atajos teclado olvidé",
        "solo_admin": False,
        "pantalla": None,
    },
    {
        "slug": "generar-constancia",
        "categoria": "generar",
        "titulo": "Generar una constancia paso a paso",
        "resumen": "Buscar al alumno, revisar los datos con la vista previa y descargar en PDF o Word.",
        "palabras": "buscar alumno cuenta nombre descargar pdf word docx imprimir vista previa",
        "solo_admin": False,
        "pantalla": ("/", "Buscar un alumno"),
    },
    {
        "slug": "lineas-opcionales-y-frases",
        "categoria": "generar",
        "titulo": "Líneas opcionales y frases guardadas",
        "resumen": "Cómo incluir u omitir promedios, periodo vacacional o texto libre, y cómo reutilizar frases.",
        "palabras": "opcional interruptor promedio vacacional línea libre comodín frase guardada",
        "solo_admin": False,
        "pantalla": None,
    },
    {
        "slug": "inicio-de-semestre",
        "categoria": "semestre",
        "titulo": "Lista de tareas al iniciar cada semestre",
        "resumen": "Las 4 cosas que el administrador revisa una vez por semestre para que todo salga prellenado.",
        "palabras": "periodo activo semestre fechas checklist preparar configurar",
        "solo_admin": True,
        "pantalla": ("/", "Ir a la preparación del semestre"),
    },
    {
        "slug": "cargar-padron",
        "categoria": "semestre",
        "titulo": "Cargar o actualizar el padrón de alumnos",
        "resumen": "Qué archivo subir, qué columnas debe tener y qué hacer si el sistema lo rechaza.",
        "palabras": "padrón excel xls xlsx csv columnas subir datos alumnos control escolar",
        "solo_admin": True,
        "pantalla": ("/datos", "Ir a Datos de alumnos"),
    },
    {
        "slug": "nuevo-ingreso",
        "categoria": "semestre",
        "titulo": "Alumnos de nuevo ingreso",
        "resumen": "Cómo dar acceso a alumnos que todavía no aparecen en el padrón principal.",
        "palabras": "nuevo ingreso primer semestre secundario respaldo",
        "solo_admin": True,
        "pantalla": ("/datos", "Ir a Datos de alumnos"),
    },
    {
        "slug": "carreras",
        "categoria": "semestre",
        "titulo": "Dar de alta una carrera o cambiar la duración de un plan",
        "resumen": "Qué hacer cuando en la constancia aparece un código como ICO-F19 en lugar del nombre de la carrera.",
        "palabras": "carrera plan código licenciatura duración semestres catálogo",
        "solo_admin": True,
        "pantalla": ("/carreras", "Ir a Carreras"),
    },
    {
        "slug": "crear-plantilla",
        "categoria": "plantillas",
        "titulo": "Crear una plantilla nueva en Word",
        "resumen": "Paso a paso para preparar un nuevo tipo de constancia (inglés, prácticas, etc.) y subirlo.",
        "palabras": "plantilla nueva word docx crear diseñar subir tipo de constancia",
        "solo_admin": True,
        "pantalla": ("/plantillas", "Ir a Plantillas"),
    },
    {
        "slug": "campos-de-plantilla",
        "categoria": "plantillas",
        "titulo": "Referencia de campos [[ ]] para plantillas",
        "resumen": "Todos los campos que el sistema llena solo, con ejemplos de cómo se imprimen, y cómo inventar los tuyos.",
        "palabras": "placeholder campo corchetes referencia lista _linea _fecha",
        "solo_admin": True,
        "pantalla": ("/plantillas", "Ir a Plantillas"),
    },
    {
        "slug": "modificar-y-restaurar-plantillas",
        "categoria": "plantillas",
        "titulo": "Modificar una plantilla y recuperar versiones anteriores",
        "resumen": "Cambiar textos o firmas, y deshacer un cambio con el historial de versiones.",
        "palabras": "modificar editar reemplazar historial restaurar versión anterior firma",
        "solo_admin": True,
        "pantalla": ("/plantillas", "Ir a Plantillas"),
    },
    {
        "slug": "problemas-frecuentes",
        "categoria": "problemas",
        "titulo": "Problemas frecuentes y cómo resolverlos",
        "resumen": "Alumno no encontrado, semestre vacío, carrera con código, vista previa que no carga y más.",
        "palabras": "error problema no encuentra vacío falla no carga ayuda soporte",
        "solo_admin": False,
        "pantalla": None,
    },
    {
        "slug": "glosario",
        "categoria": "problemas",
        "titulo": "Glosario",
        "resumen": "Qué significa cada término que usa el sistema: padrón, periodo activo, plantilla, campo…",
        "palabras": "glosario términos significado definiciones",
        "solo_admin": False,
        "pantalla": None,
    },
]

_POR_SLUG = {a["slug"]: a for a in ARTICULOS}


def articulo(slug: str) -> dict | None:
    return _POR_SLUG.get(slug)


def por_categoria() -> list[tuple[str, str, list[dict]]]:
    """[(clave, nombre, [artículos])] en el orden de CATEGORIAS."""
    return [
        (clave, nombre, [a for a in ARTICULOS if a["categoria"] == clave])
        for clave, nombre in CATEGORIAS
    ]


def vecinos(slug: str) -> tuple[dict | None, dict | None]:
    """Guía anterior y siguiente, para la navegación al pie."""
    slugs = [a["slug"] for a in ARTICULOS]
    if slug not in slugs:
        return None, None
    i = slugs.index(slug)
    ant = ARTICULOS[i - 1] if i > 0 else None
    sig = ARTICULOS[i + 1] if i < len(ARTICULOS) - 1 else None
    return ant, sig


# ---------- Ayuda por campo ----------

AYUDA_CAMPOS: dict[str, str] = {
    "NOMBRE_COMPLETO": "Se toma del padrón tal como viene («APELLIDOS NOMBRES»), solo sin la diagonal. Si el padrón trae un error, corrígelo aquí: el cambio solo afecta a esta constancia.",
    "CUENTA": "Número de cuenta del alumno, tal como viene en el padrón.",
    "CARRERA_FULL": "Sale del catálogo de Carreras según el plan del alumno. Si aquí ves un código (por ejemplo ICO-F19) en lugar del nombre, esa carrera no está dada de alta: el administrador la agrega en Carreras y queda corregido para siempre.",
    "SEMESTRE_TEXTO": "Se calcula solo, comparando el periodo de ingreso del alumno con el periodo activo. Si sale vacío, falta configurar el periodo activo o el padrón no trae el periodo de ingreso del alumno.",
    "SEMESTRES_TOTALES": "Cuántos semestres dura el plan del alumno, según el catálogo de Carreras.",
    "PERIODO_INICIO": "Fecha de inicio del semestre que guardó el administrador. Puedes cambiarla solo para esta constancia.",
    "PERIODO_FIN": "Fecha de fin del semestre que guardó el administrador. Puedes cambiarla solo para esta constancia.",
    "FECHA_EXPEDICION": "Por defecto es hoy. Se imprime con letra, en formato formal.",
    "ARTICULO": "Ajusta solo el texto: «el alumno / la alumna» y «del interesado / de la interesada». Se marca automáticamente si el padrón trae la columna Sexo.",
    "PROMEDIO_GENERAL_LINEA": "Línea opcional con el promedio general (columna PrmGR del padrón), escrito con número y letra. Apaga el interruptor si no debe aparecer.",
    "PROMEDIO_ULTIMO_LINEA": "Línea opcional con el promedio del último periodo (columna Per del padrón). Apaga el interruptor si no debe aparecer.",
    "PROMEDIO_PERIODO_LINEA": "Línea opcional para escribir el promedio de un periodo específico. Si la dejas vacía, no aparece.",
    "PERIODO_VACACIONAL_LINEA": "Elige el inicio y el fin de las vacaciones y la frase se redacta sola. Si no aplica, apaga el interruptor.",
    "LINEA_LIBRE": "Cualquier texto adicional. Puedes insertar una frase guardada o guardar la que escribas para usarla después.",
}


def ayuda_campo(nombre: str) -> str:
    """Explicación de un campo del formulario (well-known o inventado en Word)."""
    if nombre in AYUDA_CAMPOS:
        return AYUDA_CAMPOS[nombre]
    tipo = catalogo.tipo_de(nombre)
    if catalogo.es_opcional(nombre):
        return (f"Línea opcional que se agregó en la plantilla como [[{nombre}]]. "
                "Escribe el texto o apaga el interruptor: si queda vacía, el párrafo desaparece del documento.")
    if tipo in (catalogo.DATE_CORTO, catalogo.DATE_LARGO):
        return (f"Fecha que se agregó en la plantilla como [[{nombre}]]. "
                "Elígela en el calendario; se imprime como «02 de febrero de 2026».")
    return (f"Campo que se agregó en la plantilla como [[{nombre}]]. "
            "Escribe el texto exactamente como debe imprimirse.")


def referencia_campos() -> list[dict]:
    """
    Tabla para la guía «Referencia de campos»: cada campo well-known con su
    etiqueta, explicación y un ejemplo real de cómo se imprime (calculado con
    las mismas funciones que usa el sistema, así nunca se desactualiza).
    """
    ejemplo_fecha = date(2026, 2, 2)
    ejemplos = {
        "NOMBRE_COMPLETO": derivar.formato_nombre("PÉREZ LÓPEZ / JUAN CARLOS"),
        "CUENTA": "2014694",
        "CARRERA_FULL": "LICENCIATURA DE INGENIERIA EN COMPUTACION",
        "SEMESTRE_TEXTO": derivar.numero_a_ordinal_texto(6),
        "SEMESTRES_TOTALES": "10",
        "PERIODO_INICIO": derivar.fecha_a_texto_corto(ejemplo_fecha),
        "PERIODO_FIN": derivar.fecha_a_texto_corto(date(2026, 7, 24)),
        "FECHA_EXPEDICION": derivar.fecha_a_texto_largo(date(2026, 3, 6)),
        "ARTICULO": f"{derivar.articulo_de('M')} / {derivar.articulo_de('F')}",
        "INTERESADO_FRASE": f"{derivar.interesado_frase('M')} / {derivar.interesado_frase('F')}",
        "PROMEDIO_GENERAL_LINEA": derivar.linea_promedio_general(8.6),
        "PROMEDIO_ULTIMO_LINEA": derivar.linea_promedio_ultimo_periodo(9.1),
        "PROMEDIO_PERIODO_LINEA": derivar.linea_promedio_periodo("2025B", 8.4),
        "PERIODO_VACACIONAL_LINEA": derivar.linea_periodo_vacacional(date(2026, 7, 20), date(2026, 7, 31)),
        "LINEA_LIBRE": "(el texto que se escriba)",
    }
    filas = []
    for nombre, meta in catalogo.ETIQUETAS.items():
        filas.append({
            "nombre": nombre,
            "etiqueta": meta["label"],
            "opcional": catalogo.es_opcional(nombre),
            "ayuda": AYUDA_CAMPOS.get(nombre, "Se llena solo a partir del género elegido."),
            "ejemplo": ejemplos.get(nombre, ""),
        })
    return filas
