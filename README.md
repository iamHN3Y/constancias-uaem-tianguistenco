# Generador de Constancias — UAEM Tianguistenco

Aplicación web para que el personal de Servicios Escolares genere constancias escolares en **PDF** o **Word** en menos de un minuto: se busca al alumno, el sistema llena sus datos desde el padrón en una plantilla de Word con campos `[[CAMPO]]`, se revisa con la vista previa y se descarga. Se distribuye como imagen Docker (FastAPI + LibreOffice), sin base de datos.

## Documentación

| Si quieres… | Lee |
|---|---|
| Usar el sistema (generar, plantillas, inicio de semestre) | La ayuda **dentro del sistema**: botón *Modo ayuda* (tecla `?`) y *Guías* (`/ayuda`). Resumen: [docs/MANUAL_USUARIO.md](docs/MANUAL_USUARIO.md) |
| Instalar, actualizar, respaldar o resolver problemas del servidor | [docs/OPERACION.md](docs/OPERACION.md) |
| Entender o modificar el código | [docs/TECNICA.md](docs/TECNICA.md) |
| Saber qué mejorar y en qué orden | [docs/MEJORAS_FUTURAS.md](docs/MEJORAS_FUTURAS.md) |
| Ver qué cambió en cada versión | [CHANGELOG.md](CHANGELOG.md) |

Índice completo: [docs/INDEX.md](docs/INDEX.md).

## Características

**Para quien genera constancias**
- Buscador con **sugerencias en vivo** por número de cuenta o nombre (sin importar acentos ni mayúsculas).
- Formulario **prellenado**: nombre, carrera, semestre en letra, fechas del periodo, género, promedios con número y letra.
- **Vista previa PDF en vivo** con cada cambio; aviso de campos vacíos antes de descargar.
- **Líneas opcionales** (promedios, periodo vacacional, línea libre) que desaparecen del documento si se apagan, y **frases guardadas** reutilizables.
- **Constancias recientes** por equipo para regenerarlas con un clic.

**Para quien administra**
- **Preparación del semestre**: Inicio revisa periodo, padrón, plantillas y carreras del padrón sin dar de alta, con el botón para arreglar cada cosa.
- Padrón en `.xls`, `.xlsx` o `.csv`, tolerante a cambios de formato; archivo aparte para **alumnos de nuevo ingreso**.
- **Varias plantillas** (general, inglés, prácticas…) con **historial de 10 versiones** y restauración en un clic; campos nuevos con solo escribirlos en Word (`[[ALGO]]`, `[[ALGO_FECHA]]`, `[[ALGO_LINEA]]`).
- **Catálogo de carreras** editable desde la interfaz.

**Ayuda integrada**
- **Modo ayuda**: al activarlo, cualquier zona de la pantalla explica qué hace al hacer clic.
- **Recorridos guiados** la primera vez que se abre cada pantalla.
- **Centro de ayuda** con 13 guías, buscador e impresión (crear plantillas, inicio de semestre, problemas frecuentes…).

## Inicio rápido

Requisitos: Docker Desktop (Windows/macOS) o Docker Engine (Linux), ~1 GB libre.

```powershell
docker build -t constancias .
docker run -d --name constancias --restart unless-stopped -p 8000:8000 `
  -v "${PWD}/data:/app/data" -e ADMIN_PASSWORD="una-contraseña-propia" constancias
```

Abre <http://localhost:8000>. Arranque automático, actualizaciones, respaldos y solución de problemas: [docs/OPERACION.md](docs/OPERACION.md).

> **Importante.** Cambia siempre `ADMIN_PASSWORD` (la de fábrica, `admin2026`, es pública). El control de acceso es básico y está pensado para la **red interna**: no expongas el puerto a Internet sin un proxy con TLS y autenticación real. Detalle en [TECNICA.md §12](docs/TECNICA.md#12-seguridad-modelo-actual-y-límites).

## Roles

- **Invitado** (sin contraseña): busca alumnos y genera constancias.
- **Administrador** (`ADMIN_PASSWORD`): además carga el padrón y el archivo de nuevo ingreso, gestiona plantillas y carreras y configura el periodo activo.

## Desarrollo

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest tests -q
.venv\Scripts\uvicorn app.main:app --reload
```

Sin LibreOffice instalado localmente, todo funciona salvo la vista previa y la descarga en PDF (Word sí). Las pruebas no necesitan LibreOffice. Antes de desplegar cualquier cambio: pruebas en verde y un recorrido manual Inicio → Generar → Descargar. Estructura del código, convenciones y recetas para cambios comunes: [docs/TECNICA.md](docs/TECNICA.md).

```
app/        código (main.py, módulos de dominio, templates/, static/)
tests/      pruebas (pytest)
docs/       documentación
data/       estado del sistema: padrón, plantillas, ajustes (volumen Docker, no se versiona)
```
