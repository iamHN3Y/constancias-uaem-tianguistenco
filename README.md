# Generador de Constancias — UAEM Tianguistenco

Aplicación web (FastAPI) para generar constancias escolares en `.docx` y `.pdf` desde una **plantilla universal** con placeholders `[[CAMPO]]`. Se distribuye como una imagen Docker.

## Características

- Carga de un padrón de alumnos (`.xls`, `.xlsx`, `.csv`) que persiste hasta que se reemplace.
- Búsqueda de alumno por número de cuenta y autocompletado del formulario.
- Vista previa PDF en vivo (iframe) con cada cambio del formulario.
- Selectores de fecha para periodo de inicio/fin, fecha de expedición y periodo vacacional — el texto formal en español se deriva en el backend.
- Líneas opcionales (promedios, periodo vacacional, línea libre) que **se eliminan automáticamente** del documento si quedan vacías.
- Catálogo de **comodines** (snippets reutilizables) para la línea libre.
- Pseudo-login con dos roles: **admin** (carga datos y plantilla) e **invitado** (solo genera).
- Convención automática: cualquier placeholder con sufijo `_LINEA` se trata como párrafo opcional, sin tocar código.

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

## Editar la plantilla

La plantilla universal vive en `data/plantillas/universal.docx`. Para cambiarla:

- **Desde la UI**: login admin → "Gestionar plantilla" → subir el `.docx`.
- **Editando directo**: abre el archivo en Word, cambia textos/formato, guarda. Asegúrate de que los placeholders mantengan el formato `[[NOMBRE]]` exacto (mayúsculas, sin espacios entre los corchetes y el nombre).

### Convenciones de placeholders

- `[[NOMBRE]]` → cualquier nombre en MAYÚSCULAS con `_` y dígitos.
- Sufijo `_LINEA` o exactamente `LINEA_LIBRE` → el placeholder ocupa un párrafo entero y se considera **opcional**: si el usuario lo deja vacío, el párrafo desaparece del .docx final.
- Placeholders well-known (con etiqueta y tipo de control específico): ver `app/catalogo.py` (`ETIQUETAS`).

Ejemplo: agregas `[[BECA_LINEA]]` en Word, lo subes desde la UI, y aparece automáticamente como un textarea opcional en el formulario sin tocar código.

## Estructura del proyecto

```
constancias_app/
├── Dockerfile                       # python:3.11-slim + libreoffice-writer
├── README.md
├── requirements.txt
├── app/
│   ├── main.py                      # endpoints FastAPI
│   ├── catalogo.py                  # placeholders well-known + tipos de control
│   ├── derivar.py                   # texto formal en español (fechas, números, género)
│   ├── docx_render.py               # detección y reemplazo de placeholders
│   ├── pdf.py                       # docx → pdf vía LibreOffice headless
│   ├── plantilla_universal.py       # CRUD de la plantilla activa
│   ├── comodines.py                 # snippets reutilizables (con lock)
│   ├── bootstrap_plantillas/        # plantilla seed para el primer arranque
│   ├── templates/                   # Jinja2: login, home, datos, plantillas, generar
│   └── static/                      # CSS y JS
└── data/                            # montado como volumen (persistente)
    ├── ajustes.json                 # periodo activo + meta del CSV
    ├── datos.csv                    # padrón de alumnos
    ├── comodines.json               # generado en runtime
    ├── plantillas/
    │   ├── universal.docx           # plantilla activa
    │   └── _meta.json               # cache de placeholders detectados
    └── tmp/                         # archivos temporales
```

## Notas operativas

- **Concurrencia**: la generación de PDFs es segura entre sesiones (cada request usa UUID único + perfil temporal de LibreOffice). La creación de comodines está protegida con un lock para evitar perder uno cuando dos clics llegan al mismo tiempo.
- **Rendimiento**: LibreOffice consume ~150 MB y CPU por conversión. Para mucha concurrencia, ejecuta varias réplicas detrás de un proxy.
- **Seguridad**: el "login" es solo gating de UI con cookie sin firmar. No expongas el servicio a Internet sin un proxy con TLS y/o auth real (Basic Auth, OAuth, etc.).
