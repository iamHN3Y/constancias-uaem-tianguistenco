# Documentación — Generador de Constancias UAEM Tianguistenco

Toda la documentación del proyecto, separada por quién la necesita.

## Para quien usa el sistema

→ **Dentro del propio sistema** (la referencia principal, siempre actualizada):
- **Modo ayuda**: botón en la barra superior o tecla `?`; explica cualquier zona de la pantalla al hacer clic.
- **Centro de ayuda** (`/ayuda`, botón *Guías*): 13 guías paso a paso con buscador; se pueden imprimir.

→ **[MANUAL_USUARIO.md](MANUAL_USUARIO.md)**: resumen en un solo archivo para leer fuera del sistema.

## Para quien administra el servidor

→ **[OPERACION.md](OPERACION.md)**: instalación, arranque automático, actualización, respaldos y restauración, cambio de contraseña, verificación, problemas comunes, mudanza a otro equipo y calendario de mantenimiento.

## Para quien mantiene o extiende el código

→ **[TECNICA.md](TECNICA.md)**: arquitectura, módulos, modelo de datos (formato de cada archivo), flujos, motor de plantillas, reglas de negocio, frontend, sistema de ayuda, endpoints, seguridad, rendimiento, pruebas, **recetas para cambios comunes**, convenciones e historial de decisiones.

→ **[MEJORAS_FUTURAS.md](MEJORAS_FUTURAS.md)**: 24 mejoras priorizadas (P0–P3) con esfuerzo, problema que resuelven y dónde tocar el código.

→ **[../CHANGELOG.md](../CHANGELOG.md)**: qué cambió en cada versión.

## Diagramas

Los diagramas vigentes están en **Mermaid dentro de [TECNICA.md](TECNICA.md)** (GitHub los dibuja solo): arquitectura, flujo de datos, secuencia de generación y ciclo de vida de una plantilla.

Los `.svg` de [diagramas/](diagramas/) son de la versión anterior al rediseño de noviembre de 2026 (no incluyen el sistema de ayuda); se conservan como referencia hasta regenerarlos (ver mejora #24).

## Cómo mantener esta documentación

- Cambia la documentación **en el mismo commit** que el código que describe.
- Lo que el personal necesita para usar el sistema va en las guías integradas (`app/templates/ayuda/articulos/`), no aquí.
- Registra cada cambio en el [CHANGELOG](../CHANGELOG.md).
