# Documentación — Generador de Constancias UAEM Tianguistenco

Índice de toda la documentación del proyecto. El [README](../README.md) en la raíz cubre instalación y despliegue con Docker; aquí vive la documentación de fondo, separada por audiencia.

## Para usar el sistema día a día

→ **Dentro del propio sistema:** botón **Modo ayuda** (o tecla `?`) en cualquier pantalla, y el **Centro de ayuda** en `/ayuda`, con guías paso a paso que se pueden imprimir. Es la referencia principal para quien usa el sistema.

→ **[MANUAL_USUARIO.md](MANUAL_USUARIO.md)** — resumen en un solo archivo para leer fuera del sistema; guía para personal administrativo (admin/invitado): primeros pasos de cada semestre, cómo generar una constancia, panel de salud del padrón, preguntas frecuentes.

## Para mantener o extender el código

→ **[TECNICA.md](TECNICA.md)** — arquitectura, módulos, modelo de datos, sistema de placeholders, endpoints, pruebas y despliegue. Incluye diagramas de arquitectura, flujo de datos y secuencia de generación.

## Diagramas

Fuente editable con [Mermaid](https://mermaid.js.org/); las versiones renderizadas (`.svg`) están embebidas en los documentos de arriba y también disponibles sueltas en [diagramas/](diagramas/):

| Diagrama | Dónde se usa |
|---|---|
| [arquitectura.svg](diagramas/arquitectura.svg) | Módulos del sistema y sus relaciones — TECNICA.md §2 |
| [flujo-datos.svg](diagramas/flujo-datos.svg) | Padrón principal + nuevo ingreso → búsqueda → generación — TECNICA.md §3 |
| [secuencia-generar.svg](diagramas/secuencia-generar.svg) | Interacción navegador ↔ servidor ↔ LibreOffice al generar — TECNICA.md §4 |
| [flujo-usuario.svg](diagramas/flujo-usuario.svg) | Recorrido por rol (admin/invitado) — MANUAL_USUARIO.md |

## Historial de este proyecto

Construido de forma incremental: padrón + plantilla universal → catálogo de carreras dinámico y rediseño Material → robustez de largo plazo, multi-plantilla, lotes → alumnos de nuevo ingreso (reemplazando la generación por lotes, que no se usaba) → ronda de animaciones/confirmaciones/accesibilidad → rediseño centrado en el usuario final: barra común, modo ayuda, recorridos generados desde la ayuda, centro de ayuda integrado, buscador en vivo y lista de preparación del semestre. El detalle de cada decisión de diseño relevante está en [TECNICA.md §10](TECNICA.md#10-historial-de-decisiones-relevantes).
