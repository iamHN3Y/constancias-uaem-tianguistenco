# Generador de Constancias — UAEM Tianguistenco

Aplicación web (FastAPI) para generar constancias escolares en `.docx` y `.pdf` desde una **plantilla universal** con placeholders `[[CAMPO]]`. Se distribuye como una imagen Docker.

## Características

- Carga de un padrón de alumnos (`.xls`, `.xlsx`, `.csv`) que persiste hasta que se reemplace.
- Búsqueda de alumno por número de cuenta **o por nombre** (sin importar acentos ni mayúsculas).
- **Varias plantillas con nombre** (constancia general, inglés, prácticas…), cada una con su historial.
- **Generación por lotes**: pega una lista de cuentas y descarga todas las constancias en un ZIP (.docx o .pdf).
- **Catálogo de carreras editable desde la UI** (`/carreras`): altas de carreras y duraciones de plan sin tocar código.
- Género prellenado desde la columna `Sexo` del Excel (acepta M/F, H/M, MASCULINO/FEMENINO, HOMBRE/MUJER).
- Vista previa PDF en vivo (iframe) con cada cambio del formulario.
- Selectores de fecha para periodo de inicio/fin, fecha de expedición y periodo vacacional — el texto formal en español se deriva en el backend.
- **Fechas del semestre configurables una sola vez**: el admin guarda inicio/fin del periodo junto con el periodo activo y todas las constancias (individuales y por lote) salen prellenadas; el semestre en letra se calcula solo comparando el periodo de ingreso del alumno con el periodo activo.
- Líneas opcionales (promedios, periodo vacacional, línea libre) que **se eliminan automáticamente** del documento si quedan vacías.
- Catálogo de **comodines** (snippets reutilizables) para la línea libre.
- Pseudo-login con dos roles: **admin** (carga datos y plantilla) e **invitado** (solo genera).
- Convenciones automáticas por nombre de placeholder (`_LINEA`, `_FECHA`) — extienden el formulario sin tocar código.
- **Historial de plantillas**: cada reemplazo respalda la versión anterior y se puede restaurar desde la UI.
- **Detección siempre fresca**: si la plantilla cambia en disco (aunque no sea por la UI), los placeholders se re-escanean solos.
- Validación al subir: una plantilla corrupta o un Excel sin columna `Cuenta` se rechazan sin tocar lo que ya funcionaba.

## Requisitos

- Docker Desktop (Windows/macOS) o Docker Engine (Linux).
- ~500 MB libres para la imagen (incluye `libreoffice-writer` para la conversión a PDF).

## Construcción

Desde la raíz del proyecto (donde está `Dockerfile`):

```powershell
docker build -t constancias .
```

## Ejecución

### Primera vez (recomendado)

Usa `--name` para identificar el contenedor y `--restart unless-stopped` para que Docker lo levante solo cuando arranque el daemon:

```powershell
docker run -d `
  --name constancias `
  --restart unless-stopped `
  -p 8000:8000 `
  -v "${PWD}/data:/app/data" `
  -e ADMIN_PASSWORD="cambia-esto" `
  constancias
```

- `-d` → modo detached (en background).
- `--name constancias` → identifica al contenedor.
- `--restart unless-stopped` → se relanza al reiniciar Docker; solo no arranca si tú lo detuviste explícitamente.
- `-v "${PWD}/data:/app/data"` → monta la carpeta `data/` para persistir CSV, plantilla, comodines, ajustes.
- `-e ADMIN_PASSWORD="..."` → contraseña del rol admin (default `admin2026` si se omite).

Abre <http://localhost:8000>. Verás la pantalla de login.

### Operación diaria (mismo contenedor)

```powershell
docker stop constancias        # detener
docker start constancias       # volver a arrancar (NO crea uno nuevo)
docker logs -f constancias     # seguir los logs
docker restart constancias     # reiniciar
```

> **Importante**: si vuelves a correr `docker run` lanzas un contenedor nuevo (te quejarás de que "se crean nuevos cada vez"). Usa `docker start <nombre>` para reusar el existente.

### Actualizar el código

```powershell
docker stop constancias
docker rm constancias
docker build -t constancias .
docker run -d --name constancias --restart unless-stopped -p 8000:8000 -v "${PWD}/data:/app/data" -e ADMIN_PASSWORD="..." constancias
```

El volumen `data/` sobrevive al `docker rm`, así que los datos cargados se conservan.

## Arranque automático en el servidor (Windows)

Dos pasos:

1. **Que Docker Desktop arranque al iniciar Windows**
   Abre Docker Desktop → ⚙ Settings → *General* → marca **"Start Docker Desktop when you sign in"**.

2. **Que el contenedor se levante con Docker**
   Si lo creaste con `--restart unless-stopped` (ver arriba), Docker lo iniciará automáticamente cada vez que arranque su daemon. No necesitas hacer nada más.

> En Windows, Docker Desktop se ejecuta cuando el usuario inicia sesión. Si la PC servidor reinicia, asegúrate de que ese usuario haga login (o configura inicio automático de sesión de Windows). Para auto-arranque sin login interactivo, considera correr Docker Engine en WSL2 con un servicio o migrar a Linux con systemd.

### Linux con systemd (alternativa)

```ini
# /etc/systemd/system/constancias.service
[Unit]
Description=Generador de Constancias
Requires=docker.service
After=docker.service

[Service]
Restart=always
ExecStart=/usr/bin/docker start -a constancias
ExecStop=/usr/bin/docker stop -t 10 constancias

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable constancias
sudo systemctl start constancias
```

## Roles y contraseña admin

- **Invitado**: genera constancias. No puede subir datos ni plantilla.
- **Admin**: todo lo anterior + subir base de datos, reemplazar la plantilla universal, definir el periodo activo.

La contraseña admin se lee de la variable `ADMIN_PASSWORD` al arranque (default `admin2026`). Cambia siempre el default antes de usarlo en un entorno real.

## Plantillas

Puede haber **varias plantillas** (p. ej. "Constancia general", "Constancia en inglés", "Prácticas profesionales"). Cada una vive en su propia carpeta `data/plantillas/<slug>/universal.docx`, con su historial y su cache de placeholders. El registro de nombres está en `data/plantillas/registro.json`. Si vienes de una versión anterior (un solo `universal.docx` suelto), la migración al nuevo layout es automática al arrancar.

Cuando hay más de una plantilla, en la pantalla principal (y en el lote) aparece un selector de "Tipo de constancia".

Para editar una plantilla:

- **Desde la UI** (recomendado): login admin → "Gestionar plantillas" → *Descargar* → editar en Word → *Reemplazar*. La subida se valida antes de aceptarse y la versión anterior queda en el historial.
- **Editando directo**: abre el `.docx` en `data/plantillas/<slug>/` en Word, cambia textos/formato, guarda. El sistema detecta el cambio automáticamente (compara tamaño y fecha del archivo) y re-escanea los placeholders — no hace falta reiniciar ni volver a subir nada. *Ojo*: por esta vía no se genera respaldo en el historial.

### Convenciones de placeholders

El **nombre** del placeholder decide su comportamiento; ninguna requiere tocar código:

| Forma | Comportamiento |
|---|---|
| `[[CUALQUIER_NOMBRE]]` | Input de texto libre en el formulario. |
| `[[ALGO_LINEA]]` o `[[LINEA_LIBRE]]` | Párrafo **opcional**: textarea con interruptor; si queda vacío, el párrafo desaparece del .docx final. |
| `[[ALGO_FECHA]]` | Selector de fecha; se imprime como texto formal corto ("02 de febrero de 2026"). |
| Well-known (`[[NOMBRE_COMPLETO]]`, `[[CUENTA]]`, …) | Etiqueta y control específicos + valor prellenado desde el Excel. Ver `app/catalogo.py` (`ETIQUETAS`). |

Detalles que perdonan errores humanos:

- Se aceptan espacios pegados a los corchetes (`[[ NOMBRE ]]`) y minúsculas (`[[nombre]]`); el nombre se normaliza a MAYÚSCULAS. También se admiten acentos y Ñ (`[[AÑO]]`).
- Los placeholders funcionan en el cuerpo, en **tablas** (incluso anidadas), en **encabezados y pies de página** y en **cuadros de texto** de Word.
- Si un placeholder quedó **mal escrito** (corchetes sin cerrar, espacios dentro del nombre), la página "Gestionar plantilla" muestra un aviso indicando el texto exacto a corregir.
- Word suele partir el texto en fragmentos internos ("runs") al editar; el sistema los une antes de buscar, así que no importa cómo quedó guardado.

Ejemplo: agregas `[[BECA_LINEA]]` en Word, lo subes desde la UI (o lo guardas directo en `data/plantillas/`), y aparece automáticamente como textarea opcional en el formulario, marcado con la etiqueta «plantilla».

### Historial de versiones

Cada reemplazo de plantilla guarda una copia de la anterior en `data/plantillas/<slug>/historial/` (se conservan las últimas 10). Desde "Gestionar plantillas" puedes restaurar cualquier versión con un clic; restaurar también respalda la versión activa, así que nunca se pierde nada.

## Periodo activo y fechas del semestre

En la pantalla principal (solo admin) se configura **una vez por semestre**:

- **Periodo** (ej. `2026A`): con él se calcula el semestre en letra de cada alumno (`PerInicio` 2023B + periodo 2026A → "sexto").
- **Inicio y fin del periodo**: fechas reales del calendario escolar. Prellenan los campos «Inicio/Fin del periodo» de todas las constancias, individuales y por lote. Si se dejan vacías se usan las fechas típicas (02 de febrero / 02 de agosto) como aproximación, siempre editables en cada constancia.

Si no hay periodo activo configurado, la página de generación lo avisa (es la causa típica de que «Semestre» y las fechas aparezcan vacíos).

## Catálogo de carreras (`/carreras`, solo admin)

Convierte el plan del Excel (`ICO-F19`) en el nombre completo de la carrera y define cuántos semestres dura cada plan. Vive en `data/carreras.json` y se edita desde la UI:

- **Carreras**: código = prefijo del plan (`ICO`), más el nombre completo tal como debe imprimirse. Un plan cuyo prefijo no esté en el catálogo se muestra crudo (el usuario puede corregirlo a mano en el formulario) — dar de alta la carrera lo arregla para siempre.
- **Duraciones**: solo para planes que no duran 10 semestres, llaveado por código completo (`IPI-F26` → 9) porque una reestructuración cambia la duración sin cambiar el prefijo.

Los cambios aplican de inmediato, sin reiniciar. El archivo también se puede editar a mano si hiciera falta.

## Generación por lotes (`/lote`)

Pega una lista de cuentas (una por línea o separadas por comas, máx. 200), elige plantilla y formato (.docx o .pdf) y descarga un ZIP. Lo individual (nombre, carrera, semestre, género, promedios) se deriva solo del Excel; las fechas y líneas opcionales se definen una vez para todo el lote. El resumen final marca por alumno:

- **generada** — todo derivado correctamente.
- **revisar** — se generó pero quedaron placeholders sin dato visibles en el documento (p. ej. `[[ARTICULO]]` si el padrón no trae columna `Sexo`); ábrela en Word o genera esa cuenta individual.
- **cuenta no encontrada** — no está en el padrón.

## Datos de alumnos

Al subir el padrón:

- Las columnas se emparejan **sin importar mayúsculas, acentos ni espacios** (`CUENTA`, `per inicio` → `Cuenta`, `PerInicio`), para tolerar cambios de formato del Excel de control escolar.
- Un archivo sin columna `Cuenta`, vacío o ilegible se **rechaza con un mensaje claro** y los datos anteriores quedan intactos.
- Las cuentas que Excel entrega como número flotante (`2014694.0`) se normalizan solas.
- Si `PrmGR`/`Per` traen valores no numéricos, las líneas de promedio simplemente quedan vacías (editables a mano) en lugar de fallar.
- Si existe columna `Sexo`, el género se prellena en el formulario y se deriva en los lotes. Se aceptan los esquemas M/F, H/M, MASCULINO/FEMENINO y HOMBRE/MUJER; la letra `M` ambigua se interpreta según el esquema del propio archivo.

## Tests

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest tests -q
```

Cubren el motor de render (placeholders partidos en runs, headers/footers, tablas anidadas, líneas opcionales), la gestión de plantilla (cache auto-validado, subidas corruptas, historial/restauración), las convenciones del catálogo y un flujo completo de API. Ejecútalos antes de desplegar cualquier cambio.

## Estructura del proyecto

```
constancias_app/
├── Dockerfile                       # python:3.11-slim + libreoffice-writer
├── README.md
├── requirements.txt
├── app/
│   ├── main.py                      # endpoints FastAPI
│   ├── catalogo.py                  # placeholders well-known + convenciones (tipo_de)
│   ├── carreras.py                  # catálogo editable de carreras y duraciones
│   ├── derivar.py                   # texto formal en español (fechas, números, género)
│   ├── docx_render.py               # detección y reemplazo de placeholders
│   ├── pdf.py                       # docx → pdf vía LibreOffice headless
│   ├── plantilla_universal.py       # plantillas con nombre + historial + cache autovalidado
│   ├── comodines.py                 # snippets reutilizables (con lock)
│   ├── bootstrap_plantillas/        # plantilla seed para el primer arranque
│   ├── templates/                   # Jinja2: login, home, datos, plantillas, carreras, generar, lote
│   └── static/                      # CSS y JS
├── tests/                           # pytest: render, plantillas, catálogo, carreras, API
└── data/                            # montado como volumen (persistente)
    ├── ajustes.json                 # periodo activo + meta del CSV
    ├── datos.csv                    # padrón de alumnos
    ├── comodines.json               # generado en runtime
    ├── carreras.json                # catálogo de carreras (editable desde /carreras)
    ├── plantillas/
    │   ├── registro.json            # nombres y slugs de las plantillas
    │   └── <slug>/                  # una carpeta por plantilla
    │       ├── universal.docx       # archivo activo
    │       ├── _meta.json           # cache de placeholders (autovalidado por mtime/tamaño)
    │       └── historial/           # respaldos automáticos (últimas 10 versiones)
    └── tmp/                         # archivos temporales
```

## Notas operativas

- **Concurrencia**: la generación de PDFs es segura entre sesiones (cada request usa UUID único + perfil temporal de LibreOffice). La creación de comodines está protegida con un lock para evitar perder uno cuando dos clics llegan al mismo tiempo.
- **Rendimiento**: LibreOffice consume ~150 MB y CPU por conversión. Para mucha concurrencia, ejecuta varias réplicas detrás de un proxy.
- **Seguridad**: el "login" es solo gating de UI con cookie sin firmar. No expongas el servicio a Internet sin un proxy con TLS y/o auth real (Basic Auth, OAuth, etc.).
