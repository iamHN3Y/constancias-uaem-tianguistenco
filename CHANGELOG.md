# Historial de cambios

Cambios relevantes para quien usa o mantiene el sistema, del más reciente al más antiguo. Cada entrada corresponde a un commit en `main`. Al hacer un cambio, agrega una entrada nueva arriba con la fecha.

## 2026-11-11 — Documentación técnica, operación y mejoras futuras

### Interfaz
- Pie de página con enlace al repositorio en GitHub (código y documentación) y la firma del autor.

### Documentación
- Documentación técnica reescrita ([docs/TECNICA.md](docs/TECNICA.md)): módulos, modelo de datos con formato de cada archivo, flujos, reglas de negocio, endpoints con el acceso real de cada ruta, límites de seguridad y rendimiento, recetas para cambios comunes y convenciones.
- Nuevo [docs/OPERACION.md](docs/OPERACION.md): instalación, arranque automático, actualización, respaldos automáticos, restauración, cambio de contraseña, verificación y problemas comunes.
- Nuevo [docs/MEJORAS_FUTURAS.md](docs/MEJORAS_FUTURAS.md): 24 mejoras priorizadas con esfuerzo y ubicación en el código.
- README reducido a punto de entrada; este archivo de cambios.

### Correcciones
- La documentación y la ayuda afirmaban que el semestre de los alumnos de nuevo ingreso se dejaba vacío a propósito; el sistema siempre lo calcula. Se corrigieron las guías *Alumnos de nuevo ingreso* y *Problemas frecuentes*, la ayuda del campo «Semestre» y el manual.
- La documentación decía que descargar una plantilla no requería administrador (sí lo requiere) y que crear frases guardadas sí (no lo requiere).
- Guías: se aclara que una plantilla sin ningún campo `[[ ]]` se rechaza y que los nombres de carrera se guardan en mayúsculas.

## 2026-11-10 — Rediseño centrado en el usuario y ayuda integrada (`9284cf6`)
- Plantilla base común con barra de navegación, *Modo ayuda* y *Guías* en todas las pantallas.
- **Modo ayuda** (botón o tecla `?`): explica cualquier zona de la pantalla al hacer clic, sin ejecutar acciones.
- **Recorridos guiados** generados desde los mismos textos de ayuda.
- **Centro de ayuda** `/ayuda` con 13 guías, buscador, impresión y plantilla de ejemplo descargable.
- Inicio: buscador con sugerencias en vivo, **preparación del semestre** (detecta carreras del padrón sin dar de alta) y constancias recientes.
- Generar: campos agrupados en orden lógico, aviso de campos vacíos, barra de descarga fija y diálogo de siguiente paso.
- Plantillas, Datos y Carreras: pasos explicados, arrastrar y soltar archivos, fechas legibles, alta de carreras faltantes con un clic.
- Corrección: la barra superior dejaba de quedarse fija en páginas largas.

## 2026-08-20 — Alumnos de nuevo ingreso (`a2f9cde`)
- Archivo secundario de alumnos de nuevo ingreso, consultado solo como respaldo y purgado automáticamente.
- Se retira la generación por lotes (no se usaba).
- Animaciones, confirmaciones accesibles y documentación técnica y de usuario.

## 2026-07-16 — Robustez de largo plazo (`78ee559`)
- Varias plantillas con nombre, historial y restauración; cache de campos autovalidado.
- Catálogo de carreras editable desde la interfaz; búsqueda por nombre.

## 2026-06-14 — Carreras dinámicas y diseño Material (`6a05422`, `837e706`)
- Catálogo de carreras dinámico, rediseño Material Design 3 y primer tutorial integrado.
- Se eliminan del repositorio datos de prueba sensibles.

## 2026-05-08 — Primera versión (`0a6d19a`)
- Generador de constancias con padrón, plantilla universal `[[CAMPO]]`, vista previa y descarga en `.docx`/`.pdf`.
