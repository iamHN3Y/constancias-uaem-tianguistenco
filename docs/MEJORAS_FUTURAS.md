# Mejoras futuras

Propuestas surgidas al revisar el código y la operación del sistema (noviembre 2026). Cada una dice **qué problema resuelve, qué hacer, dónde y cuánto cuesta**, para que quien la retome no tenga que redescubrirlo.

**Esfuerzo:** S = horas · M = 1–3 días · L = una semana o más.
**Prioridad:** P0 = conviene hacerlo pronto (riesgo real o costo muy bajo) · P1 = mejora clara de operación o calidad · P2 = producto, según demanda · P3 = mantenimiento de largo plazo.

## Resumen

| # | Mejora | Área | Prioridad | Esfuerzo |
|---|---|---|---|---|
| 1 | Fijar versiones de dependencias e imagen base | Mantenimiento | P0 | S |
| 2 | Que la generación de PDF no bloquee el servidor | Rendimiento | P0 | S |
| 3 | Sesión firmada y verificación de rol en todas las rutas | Seguridad | P0 | S–M |
| 4 | No arrancar con la contraseña de fábrica | Seguridad | P0 | S |
| 5 | Respaldo descargable desde la interfaz | Datos | P0 | S |
| 6 | Escritura atómica de frases guardadas | Datos | P0 | S |
| 7 | Pruebas automáticas en GitHub (CI) | Calidad | P1 | S |
| 8 | Bitácora de constancias emitidas y folio | Trazabilidad | P1 | M |
| 9 | Vista previa del padrón antes de reemplazarlo | Proceso | P1 | M |
| 10 | Probar una plantilla con un alumno al subirla | Proceso | P1 | M |
| 11 | Decidir la regla de semestre para nuevo ingreso | Negocio | P1 | S |
| 12 | Constancias en inglés con fechas y ordinales en inglés | Producto | P1 | M |
| 13 | LibreOffice persistente (conversiones en < 1 s) | Rendimiento | P1 | M |
| 14 | Caché del padrón en memoria | Rendimiento | P1 | S |
| 15 | Límite de tamaño de archivos y ruta de salud | Operación | P1 | S |
| 16 | Usuarios individuales | Seguridad | P2 | M–L |
| 17 | Código QR de verificación de autenticidad | Producto | P2 | L |
| 18 | Editar y ordenar frases guardadas | UX | P2 | S |
| 19 | Estadísticas de uso | Gestión | P2 | M |
| 20 | Tema oscuro según el sistema operativo | UX | P2 | S |
| 21 | Dividir `main.py` en módulos de rutas | Mantenimiento | P3 | M |
| 22 | Linter, formato y tipos en CI | Mantenimiento | P3 | S |
| 23 | Pruebas de extremo a extremo (PDF real y navegador) | Calidad | P3 | M |
| 24 | Regenerar o retirar los diagramas SVG | Documentación | P3 | S |

Orden sugerido: **Fase 1** (≈2 días): 1–7. **Fase 2** (≈2 semanas): 8–15. **Fase 3**: el resto según demanda.

---

## 1. Seguridad y datos personales

### 3 · Sesión firmada y verificación de rol en todas las rutas — P0 · S–M

**Problema.** La cookie `rol` no está firmada: cualquiera puede escribir `rol=admin` y administrar. Además `/generar`, `/preview.pdf`, `/generar/docx|pdf`, `/buscar` y `/comodines` no revisan el rol, así que quien llegue al puerto puede consultar datos de alumnos sin entrar.

**Propuesta.**
- Firmar la sesión con `starlette.middleware.sessions.SessionMiddleware` (clave en variable `SECRET_KEY`) o con `itsdangerous`, y leer el rol de ahí en `get_rol`.
- Agregar una dependencia `requiere_sesion` a las rutas de generación y `requiere_admin` a `POST/DELETE /comodines` (o permitirlas a ambos roles, pero con sesión).
- Caducidad de sesión (p. ej. 8 horas) para equipos compartidos.

**Dónde.** `main.py`: `get_rol`, `_bloquear_si_no_admin`, rutas listadas. Pruebas: `test_invitado_no_puede_administrar` + nuevas para rutas sin sesión.

### 4 · No arrancar con la contraseña de fábrica — P0 · S

**Problema.** `ADMIN_PASSWORD` cae a `admin2026`, que está en el README público.

**Propuesta.** Si la variable no está definida o vale `admin2026`, mostrar un aviso permanente al administrador («Cambia la contraseña: ver Operación») o negarse a arrancar en producción. Comparar con `secrets.compare_digest`.

### 16 · Usuarios individuales — P2 · M–L

**Problema.** Dos roles compartidos: no se sabe quién hizo qué y cambiar la contraseña afecta a todos.

**Propuesta.** Archivo `data/usuarios.json` con usuario, nombre, rol y hash de contraseña (`hashlib.scrypt`), pantalla de administración de usuarios y registro del usuario en la bitácora (#8). Si el plantel tiene directorio institucional, valorar SSO.

### Datos personales (transversal)

El padrón contiene datos personales. Mientras no se cifren: acceso restringido a la carpeta `data/` y a los respaldos, no copiar padrones a memorias USB, borrar respaldos viejos, y documentar el aviso de privacidad institucional aplicable.

---

## 2. Rendimiento

### 2 · Que la generación de PDF no bloquee el servidor — P0 · S

**Problema.** `preview_pdf`, `generar_pdf` y `generar_docx` son `async def` pero ejecutan código bloqueante (LibreOffice con `subprocess.run`, pandas). Con un solo proceso de Uvicorn, **mientras se convierte un PDF nadie más es atendido** (ni siquiera la búsqueda). Con varias ventanillas, la espera se acumula.

**Propuesta.** Cualquiera de estas, de menor a mayor esfuerzo:
- Declarar esas rutas (y las que leen el padrón) como `def` en vez de `async def`: FastAPI las ejecuta en un *threadpool*.
- O envolver la llamada: `await run_in_threadpool(_generar_y_servir, ...)`.
- Además, `--workers 2` en el `CMD` del `Dockerfile` (cada worker consume memoria; LibreOffice ~150 MB por conversión).

**Dónde.** `main.py` (rutas de generación), `Dockerfile`. Verificar a mano con dos navegadores generando a la vez.

### 13 · LibreOffice persistente — P1 · M

**Problema.** Cada conversión arranca LibreOffice desde cero (1–5 s). Es la mayor parte de la espera de la vista previa.

**Propuesta.** Usar [`unoserver`](https://github.com/unoconv/unoserver) (un `soffice` residente + cliente `unoconvert`) dentro del contenedor y cambiar `pdf.docx_a_pdf` para hablarle; mantener el modo actual como respaldo si el servidor no responde. Reduce la conversión a fracciones de segundo.

### 14 · Caché del padrón en memoria — P1 · S

**Problema.** Cada búsqueda, incluida cada sugerencia mientras se escribe, lee `datos.csv` completo con pandas.

**Propuesta.** Cachear el `DataFrame` (y una columna de nombres sin acentos precalculada) invalidando por `os.stat().st_mtime_ns`, igual que hace `_meta.json` con las plantillas.

---

## 3. Datos y operación

### 1 · Fijar versiones de dependencias e imagen base — P0 · S

**Problema.** `requirements.txt` no fija versiones y el `Dockerfile` usa `python:3.11-slim` flotante. Un `docker build` dentro de un año puede instalar pandas, python-docx o FastAPI con cambios incompatibles y romper el sistema sin tocar el código. Es el principal riesgo para que el sistema «dure mucho tiempo».

**Propuesta.** Fijar versiones exactas (`pip freeze` de una instalación que pase las pruebas → `requirements.txt` con `==`), y la imagen a una etiqueta concreta (p. ej. `python:3.11.x-slim-bookworm`). Actualizar a propósito una vez por semestre, corriendo las pruebas.

### 5 · Respaldo descargable desde la interfaz — P0 · S

**Problema.** Respaldar exige acceso al servidor y saber PowerShell ([OPERACION.md](OPERACION.md#respaldos)).

**Propuesta.** Botón «Descargar respaldo» en *Datos* (solo admin) que genere un `.zip` de `data/` (sin `tmp/`) con `shutil.make_archive`. Opcional: «Restaurar respaldo» que valide el zip antes de reemplazar. Agregar a la preparación del semestre un aviso «último respaldo hace N días».

### 6 · Escritura atómica de frases guardadas — P0 · S

**Problema.** `comodines.Comodines._save` escribe directo sobre `comodines.json`. Si el proceso se interrumpe a mitad, el archivo queda corrupto y `list()` falla al leerlo, rompiendo la línea libre.

**Propuesta.** `tmp` + `os.replace` como el resto de módulos, y tolerar JSON corrupto en `list()` (devolver `[]` y registrar el error).

### 15 · Límite de tamaño de archivos y ruta de salud — P1 · S

- Rechazar subidas mayores a, p. ej., 20 MB antes de escribirlas en `tmp/`.
- `GET /salud` que devuelva `200` con `{"libreoffice": true, "padron": true, "plantillas": 2}` para monitorearlo (o para un `HEALTHCHECK` en el `Dockerfile`).

---

## 4. Proceso y producto

### 8 · Bitácora de constancias emitidas y folio — P1 · M

**Problema.** No queda registro de qué constancias se emitieron, cuándo ni para quién; no hay forma de responder «¿se le dio constancia a este alumno?» ni de numerarlas.

**Propuesta.** Al descargar, añadir una línea a `data/bitacora.csv` (fecha, cuenta, nombre, plantilla, formato, rol/usuario) y un folio consecutivo por año. Nuevo campo conocido `[[FOLIO]]` en `catalogo.ETIQUETAS` para imprimirlo. Pantalla de consulta para administradores con filtro por fecha y cuenta, y exportación a Excel. Es la base de #17 y #19.

### 9 · Vista previa del padrón antes de reemplazarlo — P1 · M

**Problema.** Al subir un padrón se reemplaza de inmediato. Si control escolar entrega un archivo incompleto (otra hoja, un filtro activo), se nota después.

**Propuesta.** Subir → pantalla de confirmación con: columnas detectadas y faltantes, número de alumnos (antes/después, altas/bajas), cuántos sin género, planes sin carrera, y botón «Confirmar reemplazo». Guardar el padrón anterior como `datos.anterior.csv` para deshacer.

### 10 · Probar una plantilla con un alumno al subirla — P1 · M

**Problema.** Después de crear o reemplazar una plantilla, hay que ir a Inicio, buscar a alguien y generar para ver el resultado.

**Propuesta.** En la tarjeta de cada plantilla, «Probar con…» que abra `/generar` con el primer alumno del padrón (o uno elegido) y esa plantilla. Más ambicioso: subir la plantilla en «modo prueba» y activarla solo después de ver la vista previa.

### 11 · Decidir la regla de semestre para nuevo ingreso — P1 · S

**Situación.** La documentación anterior afirmaba que el semestre de alumnos de nuevo ingreso se dejaba vacío a propósito, pero el código siempre lo calculó con la columna Periodo del archivo. Se corrigió la documentación para que diga lo que hace el código.

**Decisión pendiente (de Servicios Escolares).** ¿Calcularlo (comportamiento actual, correcto para primer ingreso) o dejarlo vacío para forzar la revisión (útil si el archivo trae alumnos que vienen de otro plantel)? Si se elige vacío: en `catalogo._derivar_well_known`, no calcular `semestre_num` cuando `alumno.get("_origen") == "nuevo_ingreso"`, y actualizar la guía *Alumnos de nuevo ingreso*.

### 12 · Constancias en inglés con fechas y ordinales en inglés — P1 · M

**Problema.** Se pueden crear plantillas en inglés, pero los campos calculados (fechas, semestre en letra, promedios, «el alumno / la alumna») siempre salen en español.

**Propuesta.** Idioma por plantilla en `registro.json` (`"idioma": "en"`), funciones equivalentes en `derivar.py` (`num2words` soporta inglés) y selección en `_derivar_well_known`. Mientras tanto, en plantillas en inglés no conviene usar campos calculados de fecha o semestre: mejor campos propios de texto libre (p. ej. `[[ISSUE_DATE]]`, `[[SEMESTER]]`) que se escriben a mano, porque `_FECHA` también se imprime en español.

### 17 · Código QR de verificación — P2 · L

Imprimir en la constancia un QR con una URL de verificación (folio + hash) que confirme su autenticidad. Requiere #8 y que la verificación sea accesible desde fuera de la red interna, lo que a su vez exige #3 y #16 resueltos.

### 18 · Editar y ordenar frases guardadas — P2 · S

Hoy solo se crean y borran. Pantalla pequeña (o diálogo) para renombrar, editar el texto y ordenar; registrar quién la creó.

### 19 · Estadísticas de uso — P2 · M

Con la bitácora (#8): constancias por mes, por tipo, horas pico. Útil para planear personal de ventanilla y justificar el sistema.

### 20 · Tema oscuro según el sistema operativo — P2 · S

`theme.js` arranca siempre en claro. Usar `prefers-color-scheme` cuando el usuario no haya elegido.

### Otras ideas (según demanda)

- **Envío por correo** al alumno (requiere SMTP institucional y correo en el padrón).
- **Generación múltiple** (varios alumnos en un `.zip`): existió y se retiró por no usarse; solo si vuelve a pedirse.
- **Firma electrónica** o sello digital: depende de la política institucional.
- **Semestre por avance académico** (créditos) en lugar de periodos transcurridos, si el padrón trae ese dato de forma confiable.

---

## 5. Calidad y mantenimiento

### 7 · Pruebas automáticas en GitHub (CI) — P1 · S

Workflow de GitHub Actions que en cada push instale `requirements-dev.txt`, corra `pytest` y haga `docker build`. Evita subir algo roto sin darse cuenta.

### 21 · Dividir `main.py` en módulos de rutas — P3 · M

`main.py` tiene ~1100 líneas con rutas, lectura del padrón y reglas. Separarlo con `APIRouter`: `rutas/acceso.py`, `rutas/datos.py`, `rutas/plantillas.py`, `rutas/carreras.py`, `rutas/generar.py`, `rutas/ayuda.py`, y la lógica del padrón en `padron.py`. Mantener las rutas iguales; las pruebas existentes son la red de seguridad.

### 22 · Linter, formato y tipos — P3 · S

`ruff` (lint + formato) y, opcionalmente, `mypy` sobre los módulos de dominio, en CI.

### 23 · Pruebas de extremo a extremo — P3 · M

- Marcador `pytest -m pdf` que convierta con LibreOffice real dentro del contenedor.
- Unas pocas pruebas con Playwright: buscar → generar → descargar, modo ayuda (activar, clic en zona, tarjeta), recorrido guiado y ausencia de desbordamiento a 375 px.

### 24 · Regenerar o retirar los diagramas SVG — P3 · S

Los `.svg` de `docs/diagramas/` son de antes del rediseño (no incluyen el sistema de ayuda). La fuente de verdad son los diagramas Mermaid dentro de [TECNICA.md](TECNICA.md), que GitHub dibuja solo. Regenerarlos con `mermaid-cli` o eliminarlos para que no confundan.
