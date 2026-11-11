# Documentación técnica — Generador de Constancias UAEM Tianguistenco

Referencia para quien mantenga o extienda el código. Para el manual de uso diario, ver [MANUAL_USUARIO.md](MANUAL_USUARIO.md). Índice general en [INDEX.md](INDEX.md).

## 1. Visión general

Aplicación web monolítica en **FastAPI + Jinja2**, sin base de datos: todo el estado vive en archivos CSV/JSON planos bajo `data/` (montado como volumen Docker). Genera constancias escolares en `.docx` (vía `python-docx`) y `.pdf` (vía LibreOffice headless) a partir de una o varias plantillas con placeholders `[[CAMPO]]`.

Principios de diseño que se repiten en todo el código:

- **El nombre del placeholder decide su comportamiento.** No hace falta tocar código para agregar un campo nuevo a una plantilla: las convenciones de sufijo (`_LINEA`, `_FECHA`) y el catálogo `ETIQUETAS` en `catalogo.py` cubren la mayoría de los casos.
- **Nunca se pierde una versión.** Plantillas, padrón y ajustes se escriben de forma atómica (`.tmp` + `os.replace`) y las plantillas llevan historial con restauración de un clic.
- **Sin CDNs ni frameworks JS.** Todo el frontend es Jinja2 + CSS propio + JS vanilla, para minimizar dependencias en un proyecto de mantenedor único.

## 2. Arquitectura

```mermaid
graph TB
    subgraph Cliente["Navegador"]
        UI["Jinja2 + CSS + JS vanilla<br/>(home, generar, datos, plantillas, carreras)"]
    end

    subgraph Servidor["FastAPI — app/main.py"]
        Auth["Sesión / roles<br/>admin · invitado"]
        Endpoints["~28 endpoints<br/>GET/POST"]
    end

    subgraph Modulos["Módulos de dominio"]
        Catalogo["catalogo.py<br/>placeholders well-known"]
        Derivar["derivar.py<br/>texto en español"]
        DocxRender["docx_render.py<br/>motor de reemplazo"]
        PlantillaU["plantilla_universal.py<br/>plantillas + historial"]
        Carreras["carreras.py<br/>catálogo de carreras"]
        Comodines["comodines.py<br/>snippets"]
        Pdf["pdf.py<br/>LibreOffice headless"]
    end

    subgraph Datos["data/ (volumen)"]
        DatosCsv[("datos.csv<br/>padrón principal")]
        NiCsv[("nuevo_ingreso.csv<br/>fallback")]
        Carrerasjson[("carreras.json")]
        Ajustesjson[("ajustes.json")]
        Plantillas[("plantillas/&lt;slug&gt;/<br/>+ historial")]
        Comodinesjson[("comodines.json")]
    end

    UI <--> Endpoints
    Auth --- Endpoints
    Endpoints --> Catalogo
    Endpoints --> DocxRender
    Endpoints --> PlantillaU
    Endpoints --> Carreras
    Endpoints --> Comodines
    Endpoints --> Pdf
    Catalogo --> Derivar
    DocxRender --> PlantillaU

    Endpoints --> DatosCsv
    Endpoints --> NiCsv
    Carreras --> Carrerasjson
    Endpoints --> Ajustesjson
    PlantillaU --> Plantillas
    Comodines --> Comodinesjson
    Pdf -.subprocess.-> LibreOffice["LibreOffice headless<br/>(soffice)"]

    style Cliente fill:#e8f0fe
    style Servidor fill:#fef3e0
    style Modulos fill:#e6f4ea
    style Datos fill:#fce8e6
```

### Módulos (`app/`)

| Archivo | Líneas | Responsabilidad |
|---|---|---|
| `main.py` | ~920 | Endpoints FastAPI, sesión/roles, orquestación de todos los flujos |
| `catalogo.py` | ~200 | Placeholders "well-known", convenciones por sufijo, derivación de valores por alumno |
| `docx_render.py` | ~210 | Detección y reemplazo de placeholders en cuerpo/tablas/headers/footers/cuadros de texto |
| `plantilla_universal.py` | ~350 | Gestión de plantillas con nombre: historial, cache autovalidada por mtime/tamaño |
| `derivar.py` | ~190 | Texto formal en español: fechas, semestre en letra, género, promedios |
| `carreras.py` | ~160 | Catálogo editable de carreras y duración de planes |
| `comodines.py` | ~50 | Snippets reutilizables para la línea libre, con lock de concurrencia |
| `pdf.py` | ~80 | Conversión `.docx` → `.pdf` vía `soffice --headless`, perfil temporal por invocación |

### Frontend (`app/templates/`, `app/static/`)

Todas las vistas heredan de **`base.html`** (barra superior común con navegación, *Modo ayuda*, *Guías*, tema y sesión; encabezado de página; pie). Cada vista solo llena bloques: `titulo`, `subtitulo`, `acciones_pagina`, `contenido`, `scripts`, `recorrido`, `ancho`. **`_macros.html`** tiene los íconos SVG (`icono("nombre")`), los avisos (`{% call aviso("exito") %}…{% endcall %}`) y la macro `ayuda(...)` del sistema de ayuda (ver «Sistema de ayuda integrado», abajo).

Vistas: login, home, generar, datos, plantillas, carreras y el centro de ayuda (`ayuda/index.html`, `ayuda/articulo.html`, `ayuda/articulos/<slug>.html`). CSS Material Design 3 propio en un solo `styles.css` (tokens de color/elevación/movimiento, modo oscuro por `data-theme`). JS vanilla, sin dependencias ni CDNs:

- `theme.js`: tema claro/oscuro y ripple.
- `ui.js`: snackbars `avisar()`, diálogos `confirmar()` / `pedirTexto()`, `protegerFormulario()` + formularios `data-confirmar` declarativos, zonas para soltar archivos (`<label class="dropzone">`) y `window.recientes` (constancias recientes en `localStorage`, solo en ese navegador).
- `ayuda.js`: **modo ayuda**.
- `tour.js`: **recorrido guiado**, generado desde los mismos textos de ayuda.
- `buscador.js`: Inicio. Sugerencias en vivo (combobox ARIA contra `/api/alumnos`), atajo `/`, lista de recientes.
- `generar.js`: vista previa en vivo, interruptores de líneas opcionales, revisión de campos vacíos antes de descargar, diálogo «¿Qué sigue?», frases guardadas.

**Caché de estáticos:** las vistas piden `styles.css?v={{ V }}`. Al cambiar CSS/JS, sube `templates.env.globals["V"]` en `main.py` para que los navegadores no usen la copia vieja.

### Sistema de ayuda integrado

Pensado para que el texto de ayuda **viva en un solo lugar** y no se contradiga con el tiempo:

| Pieza | Dónde | Qué hace |
|---|---|---|
| Macro `ayuda(titulo, texto, articulo="", paso=0)` | `_macros.html`, usada en cada vista | Pone `data-ayuda*` en un elemento. El **modo ayuda** lo marca y al hacer clic muestra la explicación; con `paso=N` forma parte del **recorrido guiado** de esa pantalla, en ese orden; `articulo` (slug o `slug#ancla`) añade «Leer la guía completa». |
| `ayuda.js` | `static/` | Modo ayuda: botón de la barra o tecla `?`. Marca cada `[data-ayuda]` visible con un «?», intercepta los clics en esas zonas (no ejecutan nada mientras el modo está activo) y abre una tarjeta navegable (‹ ›, flechas, `Esc`). `?ayuda=1` en la URL abre la pantalla ya en modo ayuda. |
| `tour.js` | `static/` | Recorrido guiado: toma los elementos con `data-recorrido`, en orden, y agrega un último paso que señala el botón *Modo ayuda*. Se lanza solo la primera vez por pantalla y navegador (clave del bloque `recorrido`; **cambia la clave**, p. ej. `-v3`, si quieres que todos lo vuelvan a ver tras un rediseño), con `window.iniciarRecorrido()` o con `?recorrido=1`. |
| `app/ayuda.py` | backend | `ARTICULOS` (índice de guías: slug, categoría, título, resumen, palabras clave, si es de administrador, botón «Ir a la pantalla»), `AYUDA_CAMPOS` (explicación de cada campo del formulario, usada por el modo ayuda en `/generar` y por la guía de referencia) y `referencia_campos()` (tabla de campos con ejemplos calculados con `derivar`, así nunca se desactualiza). |
| Guías | `templates/ayuda/articulos/<slug>.html` | Cuerpo de cada guía (Jinja; reciben `campos`, `catalogo`, `columnas_padron`). Componentes: `ol.pasos`, `div.consejo` / `.consejo--atencion`, `table.tabla`, `details.faq` (se abre solo si la URL trae su `#id`), `div.word-mock` + `span.ph-demo`. |

**Para agregar una guía:** una entrada en `ARTICULOS` + su archivo `.html` con el mismo slug. Aparece sola en el índice, el buscador, la navegación lateral y anterior/siguiente; `test_centro_de_ayuda_renderiza_todas_las_guias` verifica que renderice.

**Para agregar un campo well-known al catálogo:** además de `catalogo.ETIQUETAS`, añade su explicación en `ayuda.AYUDA_CAMPOS` (un test falla si falta) y, si aplica, su ejemplo en `referencia_campos()`.

**Rutas:** `/ayuda`, `/ayuda/{slug}` y `/ayuda/plantilla-ejemplo.docx` (la plantilla seed, como base para crear otras) son públicas: es documentación y sirve también desde la pantalla de acceso.

## 3. Modelo de datos (archivos, no BD)

```mermaid
flowchart LR
    ExcelP["Excel/CSV<br/>padrón principal"] -->|"/datos/upload<br/>(reemplaza todo)"| DatosCsv[("datos.csv")]
    ExcelN["Excel<br/>nuevo ingreso<br/>(sin encabezado)"] -->|"/datos/nuevo-ingreso<br/>(upsert)"| NiCsv[("nuevo_ingreso.csv")]
    DatosCsv -.->|"purga automática<br/>al subir padrón nuevo"| NiCsv

    Busqueda{"Buscar alumno<br/>por cuenta o nombre"}
    DatosCsv --> Busqueda
    NiCsv -->|"solo si NO<br/>está en el padrón"| Busqueda

    Busqueda --> Encontrado["Alumno encontrado<br/>(+ _origen)"]
    Encontrado --> Formulario["Formulario /generar<br/>campos derivados"]
    Formulario --> Preview["Vista previa PDF<br/>en vivo"]
    Formulario --> Descarga{"Descargar"}
    Descarga -->|".docx"| Docx["docx_render.py"]
    Descarga -->|".pdf"| PdfPy["pdf.py → LibreOffice"]

    style ExcelP fill:#fef3e0
    style ExcelN fill:#fef3e0
    style DatosCsv fill:#e8f0fe
    style NiCsv fill:#e8f0fe
    style Busqueda fill:#e6f4ea
    style Descarga fill:#e6f4ea
```

### `data/datos.csv` — padrón principal

Columnas: `Cuenta, NombreAlumno, Plan, PerInicio, PrmGR, Per, Acr, Crd, Rpr, Sit, PrmAnual` (+ `Sexo` opcional). `NombreAlumno` sigue el formato `"APELLIDOS / NOMBRES"`. Se reemplaza por completo en cada subida (`guardar_datos`); las columnas se emparejan tolerando mayúsculas/acentos/espacios.

### `data/nuevo_ingreso.csv` — fallback de alumnos sin padrón

Se puebla desde un Excel **sin fila de encabezado real** (columnas posicionales: Cuenta, Apellido paterno, Apellido materno, Nombre(s), Plan, Periodo). Se consulta **solo** cuando la cuenta no aparece en el padrón principal — nunca se fusiona. Se purga automáticamente (en ambos sentidos) cuando una cuenta ya presente aparece en el otro archivo, para no dejar duplicados fantasma cuando un alumno avanza de semestre.

### `data/ajustes.json`

Periodo activo, fechas de inicio/fin de semestre, metadatos de la última carga de cada fuente (`datos_*`, `ni_*`).

### `data/carreras.json`, `data/comodines.json`, `data/plantillas/`

Catálogo de carreras editable desde `/carreras`; snippets de línea libre; una carpeta por plantilla (`universal.docx` + `_meta.json` con cache de placeholders + `historial/` con hasta 10 versiones respaldadas).

## 4. Flujo de generación de una constancia

```mermaid
sequenceDiagram
    actor U as Usuario
    participant B as Navegador
    participant S as FastAPI
    participant D as docx_render.py
    participant L as LibreOffice

    U->>B: Escribe cuenta o nombre
    B->>S: POST /buscar
    S-->>B: Redirige a /generar?cuenta=...
    B->>S: GET /generar
    S-->>B: Formulario con campos derivados

    loop cada tecla (debounce 700ms)
        B->>S: POST /preview.pdf (FormData)
        S->>D: render(plantilla, valores)
        D-->>S: .docx en memoria
        S->>L: soffice --convert-to pdf
        L-->>S: .pdf
        S-->>B: blob PDF
        B->>B: cross-fade del iframe
    end

    U->>B: Descargar .pdf
    B->>S: POST /generar/pdf
    S->>D: render(plantilla, valores)
    S->>L: convertir a PDF
    L-->>S: .pdf
    S-->>B: archivo descargado
    B-->>U: snackbar "Constancia descargada"
```

Nota de rendimiento: `pdf.py` crea un perfil de usuario temporal de LibreOffice **en cada invocación** (no hay proceso `soffice` persistente), así que cada conversión tarda ~2-5s por el arranque en frío. La vista previa lo compensa con skeleton + mensajes escalonados, no con progreso granular (no hay infraestructura de streaming en el backend).

## 5. Sistema de placeholders

El nombre del placeholder en el `.docx` decide todo (`catalogo.py:tipo_de`):

| Convención | Comportamiento |
|---|---|
| `[[CUALQUIER_NOMBRE]]` | Input de texto libre |
| `[[ALGO_LINEA]]` / `[[LINEA_LIBRE]]` | Párrafo opcional: textarea + switch; si queda vacío, el párrafo se borra del `.docx` final |
| `[[ALGO_FECHA]]` | Selector de fecha → texto formal corto |
| Well-known (`NOMBRE_COMPLETO`, `CUENTA`, `CARRERA_FULL`, `SEMESTRE_TEXTO`, `SEMESTRES_TOTALES`, `PERIODO_INICIO/FIN`, `FECHA_EXPEDICION`, `ARTICULO`, `INTERESADO_FRASE`, `PROMEDIO_*_LINEA`, `PERIODO_VACACIONAL_LINEA`) | Etiqueta + control específico + valor prellenado, definidos en `ETIQUETAS` (`catalogo.py`) |

`docx_render.py` busca placeholders en cuerpo, tablas (incluso anidadas), headers/footers y cuadros de texto, y **une runs de Word partidos** antes de reemplazar (Word fragmenta el texto internamente al editar).

Para alumnos con `_origen == "nuevo_ingreso"`, `SEMESTRE_TEXTO` se deja vacío deliberadamente en vez de calcularse con `periodo_a_semestre`: el `PerInicio` de ese archivo no siempre representa el semestre real del alumno en este plantel (ver `catalogo.py`, comentario en `_derivar_well_known`).

## 6. Autenticación y roles

Pseudo-login con cookie **sin firmar** (`rol=admin|invitado`, `httponly`, `samesite=lax`) — es solo *gating de UI*, no seguridad real. `_bloquear_si_no_admin()` protege cada endpoint de administración (subir datos, plantillas, carreras, comodines). **No exponer el servicio a Internet sin un proxy con TLS + autenticación real** (Basic Auth, OAuth, etc.) — señalado también en el README.

## 7. Endpoints (`app/main.py`)

| Ruta | Método | Rol | Función |
|---|---|---|---|
| `/login`, `/logout` | GET/POST | — | Pseudo-sesión por cookie |
| `/` | GET | — | Home: búsqueda, estado, atajos por rol |
| `/ajustes` | POST | admin | Periodo activo y fechas del semestre |
| `/buscar` | POST | — | Búsqueda por cuenta o nombre (padrón + nuevo ingreso) |
| `/datos`, `/datos/upload` | GET/POST | admin | Padrón principal + panel de salud |
| `/datos/nuevo-ingreso`, `/datos/nuevo-ingreso/eliminar` | POST | admin | Archivo secundario de alumnos nuevos |
| `/plantillas`, `/plantillas/crear`, `/plantillas/{slug}/upload\|download\|restaurar\|eliminar` | GET/POST | admin (excepto download) | CRUD + historial de plantillas |
| `/carreras`, `/carreras/carrera*`, `/carreras/duracion*` | GET/POST | admin | Catálogo de carreras |
| `/comodines` | GET/POST/DELETE | admin (POST/DELETE) | Snippets de línea libre |
| `/generar` | GET | — | Formulario de una constancia |
| `/preview.pdf` | POST | — | Vista previa PDF en vivo |
| `/generar/docx`, `/generar/pdf` | POST | — | Descarga final |
| `/api/alumnos?q=` | GET | cualquier sesión | Sugerencias del buscador (máx. 8): prefijo de cuenta si son dígitos, nombre en otro caso |
| `/ayuda`, `/ayuda/{slug}`, `/ayuda/plantilla-ejemplo.docx` | GET | público | Centro de ayuda y plantilla base |

## 8. Pruebas

`tests/` (pytest, `TestClient` de FastAPI, sin LibreOffice real — solo se prueba `.docx`): 82 casos cubriendo motor de render, gestión de plantillas, catálogo/derivación, carreras, un flujo de API de punta a punta, la búsqueda en vivo, la lista de preparación del semestre y que todas las guías del centro de ayuda rendericen. Fixtures aíslan cada test con `tmp_path` + monkeypatch de las rutas de datos.

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest tests -q
```

Dos tests (`test_nuevo_ingreso_*`) dependen de un Excel real gitignorado (`data/Alumnos de nuevo ingreso 26B.xlsx`) y se saltan automáticamente (`skipif`) si no está presente — no rompen CI/clones limpios.

## 9. Despliegue

Imagen Docker (`python:3.11-slim` + `libreoffice-writer`), variable `ADMIN_PASSWORD` para la contraseña de admin (default `admin2026`, **cambiar siempre** en producción), volumen `data/` para persistencia. Detalle completo de arranque/actualización/auto-inicio en Windows y Linux (systemd) en el [README](../README.md#ejecución).

## 10. Historial de decisiones relevantes

- **Generación por lotes eliminada.** Existió (`/lote`) pero no se usaba en la práctica; se retiró por completo (endpoints, template, tests, menciones en README) para reducir superficie de mantenimiento.
- **`nuevo_ingreso.csv` como archivo separado, no fusión.** `guardar_datos` trunca el padrón en cada subida; fusionar habría obligado a resubir el Excel de nuevo ingreso cada semestre. El fallback con purga automática resuelve el mismo problema sin ese costo.
- **Sin SSE ni progreso granular.** El cuello de botella real es el arranque en frío de LibreOffice (2-5s), no el parseo de Excel (decenas de ms para cientos de filas); implementar streaming de progreso no tendría beneficio proporcional a su costo para un mantenedor único.
- **Ayuda integrada en lugar de manuales externos.** El personal cambia y un manual suelto se pierde o se desactualiza. La ayuda vive dentro de la app (modo ayuda + recorridos + centro de ayuda), escrita una sola vez junto al elemento que explica (macro `ayuda()`), y lo que depende de datos (campos, carreras) se genera del propio código.
- **Preparación del semestre calculada, no recordada.** En vez de confiar en que el administrador recuerde los pasos, Inicio revisa periodo, padrón, plantillas y carreras faltantes en cada carga (`preparacion_semestre`, `planes_sin_carrera`). Es barato: lee el mismo CSV que ya se lee para buscar.
- **Recientes en `localStorage`, no en el servidor.** Evita guardar un historial de alumnos en el servidor; cada equipo ve solo lo que descargó y puede borrarlo.
