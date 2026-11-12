# Operación — instalar, mantener y resolver problemas

Guía para quien administra **el equipo** donde corre el sistema (no para quien genera constancias: eso está en la ayuda integrada, `/ayuda`). Todo se hace con Docker; no hace falta instalar Python.

Contenido: [Requisitos](#requisitos) · [Primera instalación](#primera-instalación) · [Arranque automático](#arranque-automático) · [Uso diario del contenedor](#uso-diario-del-contenedor) · [Actualizar](#actualizar-a-una-versión-nueva) · [Respaldos](#respaldos) · [Restaurar](#restaurar-un-respaldo) · [Cambiar la contraseña](#cambiar-la-contraseña-de-administrador) · [Verificar](#verificar-que-todo-funciona) · [Problemas comunes](#problemas-comunes) · [Mover a otro equipo](#mover-el-sistema-a-otro-equipo) · [Calendario](#calendario-de-mantenimiento)

---

## Requisitos

- Windows 10/11 con **Docker Desktop**, o Linux con **Docker Engine**.
- ~1 GB libre (imagen de ~500 MB con LibreOffice + datos + respaldos).
- Que los equipos de ventanilla lleguen por red al puerto **8000** del servidor (o el que elijas).
- **Solo red interna.** No publiques el puerto a Internet: el control de acceso actual no está diseñado para eso (ver [TECNICA.md §12](TECNICA.md#12-seguridad-modelo-actual-y-límites)).

## Primera instalación

En PowerShell, dentro de la carpeta del proyecto (donde está `Dockerfile`):

```powershell
git clone https://github.com/iamHN3Y/constancias-uaem-tianguistenco.git
cd constancias-uaem-tianguistenco
docker build -t constancias .
docker run -d `
  --name constancias `
  --restart unless-stopped `
  -p 8000:8000 `
  -v "${PWD}/data:/app/data" `
  -e ADMIN_PASSWORD="una-contraseña-larga-y-propia" `
  constancias
```

| Opción | Para qué |
|---|---|
| `--name constancias` | Nombre fijo para operar el contenedor después. |
| `--restart unless-stopped` | Docker lo vuelve a levantar solo cada vez que arranca. |
| `-p 8000:8000` | Puerto del equipo → puerto de la app. Para usar otro: `-p 8080:8000`. |
| `-v "${PWD}/data:/app/data"` | **Los datos viven en la carpeta `data/` del equipo**, no dentro del contenedor. Por eso sobreviven a actualizaciones. |
| `-e ADMIN_PASSWORD=…` | Contraseña de administrador. **Nunca dejes la de fábrica** (`admin2026`), está publicada. |

Abre `http://localhost:8000` en el servidor, o `http://<IP-del-servidor>:8000` desde otro equipo. La primera vez se instala sola la plantilla «Constancia general». Después sigue la guía *Lista de tareas al iniciar cada semestre* dentro del sistema.

## Arranque automático

**Windows:** Docker Desktop → *Settings* → *General* → activar **«Start Docker Desktop when you sign in»**. Con `--restart unless-stopped`, el contenedor arranca en cuanto arranca Docker.

> Docker Desktop solo corre **cuando alguien inicia sesión en Windows**. Si el servidor se reinicia (actualizaciones de Windows, cortes de luz) y nadie inicia sesión, el sistema no estará disponible. Opciones: inicio de sesión automático de Windows para el usuario del servidor, o migrar a Linux.

**Linux (systemd):**

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
sudo systemctl enable --now constancias
```

## Uso diario del contenedor

```powershell
docker ps --filter name=constancias   # ¿está corriendo? (STATUS = Up …)
docker logs --tail 100 constancias    # últimos mensajes
docker logs -f constancias            # seguir mensajes en vivo (Ctrl+C para salir)
docker restart constancias            # reiniciar
docker stop constancias               # detener
docker start constancias              # volver a arrancar el MISMO contenedor
```

> No uses `docker run` otra vez para «arrancarlo»: crea un contenedor nuevo y fallará porque el nombre ya existe. `docker run` solo se usa al instalar o actualizar.

## Actualizar a una versión nueva

```powershell
cd ruta\a\constancias-uaem-tianguistenco
git pull
docker build -t constancias .
docker rm -f constancias
docker run -d --name constancias --restart unless-stopped -p 8000:8000 `
  -v "${PWD}/data:/app/data" -e ADMIN_PASSWORD="la-misma-de-antes" constancias
```

- `data/` no se toca: padrón, plantillas, carreras y ajustes se conservan.
- **Haz un respaldo antes** (siguiente sección).
- Después de actualizar, los navegadores toman los estilos nuevos solos (la app versiona sus archivos). Si algo se ve raro, `Ctrl+F5`.
- Si algo sale mal, vuelve a la versión anterior: `git checkout <commit-anterior>` y repite `build` + `run`.

## Respaldos

**Todo el estado del sistema es la carpeta `data/`.** Respaldarla es copiarla. Contiene datos personales de alumnos: guarda los respaldos en un lugar con acceso restringido.

Respaldo manual (PowerShell):

```powershell
$fecha = Get-Date -Format "yyyy-MM-dd"
Compress-Archive -Path ".\data\*" -DestinationPath "D:\Respaldos\constancias-$fecha.zip"
```

**Respaldo automático semanal** (Programador de tareas de Windows):

1. Guarda esto como `C:\Scripts\respaldo-constancias.ps1`, ajustando las rutas:

   ```powershell
   $origen  = "C:\ruta\a\constancias-uaem-tianguistenco\data"
   $destino = "D:\Respaldos\constancias"
   New-Item -ItemType Directory -Force $destino | Out-Null
   $fecha = Get-Date -Format "yyyy-MM-dd"
   Compress-Archive -Path "$origen\*" -DestinationPath "$destino\constancias-$fecha.zip" -Force
   # Conserva los últimos 12 respaldos
   Get-ChildItem $destino -Filter "constancias-*.zip" | Sort-Object Name -Descending |
     Select-Object -Skip 12 | Remove-Item
   ```

2. Programador de tareas → *Crear tarea básica* → semanal → *Iniciar un programa*: `powershell.exe` con argumentos `-NoProfile -ExecutionPolicy Bypass -File C:\Scripts\respaldo-constancias.ps1`.

Respalda también **en otro disco o equipo**: un respaldo en el mismo disco no sirve si el disco falla.

## Restaurar un respaldo

```powershell
docker stop constancias
Rename-Item .\data .\data-antes-de-restaurar
Expand-Archive "D:\Respaldos\constancias\constancias-2026-11-01.zip" -DestinationPath .\data
docker start constancias
```

Comprueba en *Datos* y *Plantillas* que esté lo esperado, y entonces borra `data-antes-de-restaurar`.

Para recuperar **solo una plantilla** no hace falta restaurar todo: en *Plantillas → Versiones anteriores* están las últimas 10 versiones de cada una.

## Cambiar la contraseña de administrador

La contraseña se fija al crear el contenedor, así que hay que recrearlo (los datos no se pierden):

```powershell
docker rm -f constancias
docker run -d --name constancias --restart unless-stopped -p 8000:8000 `
  -v "${PWD}/data:/app/data" -e ADMIN_PASSWORD="nueva-contraseña" constancias
```

Las sesiones abiertas siguen funcionando hasta que se cierre el navegador.

## Verificar que todo funciona

Después de instalar o actualizar:

1. `http://<servidor>:8000` muestra la pantalla de acceso.
2. Entra como administrador: la tarjeta *Preparación del semestre* no muestra errores inesperados.
3. Busca un alumno, abre su constancia y espera la **vista previa**: si aparece el PDF, LibreOffice funciona dentro del contenedor.
4. `docker logs --tail 50 constancias` no muestra `Traceback` ni `ERROR`.

## Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| Nadie puede entrar; el navegador dice «no se puede acceder al sitio» | Docker Desktop no está corriendo (el servidor se reinició o se cerró) | Abrir Docker Desktop y esperar a que diga *Running*; el contenedor arranca solo. Revisar [arranque automático](#arranque-automático). |
| `docker` responde «failed to connect to the docker API» | Igual que arriba | Abrir Docker Desktop. |
| `docker ps` no muestra `constancias` | El contenedor se detuvo o se borró | `docker start constancias`; si «No such container», recrearlo con el `docker run` de la instalación (los datos siguen en `data/`). |
| Funciona en el servidor pero no desde otros equipos | Firewall de Windows | Permitir el puerto 8000 entrante en el Firewall de Windows Defender (perfil privado/dominio). |
| «port is already allocated» al crear el contenedor | Otro programa usa el 8000 | Usar otro puerto: `-p 8080:8000` y entrar por `:8080`. |
| La vista previa dice «no se pudo generar (error 500)» | LibreOffice falló o tardó más de 30 s | Ver `docker logs`; reintentar; `docker restart constancias`. Si persiste con una plantilla concreta, revisarla en Word (o restaurar una versión anterior). |
| La vista previa tarda mucho cuando varios la usan a la vez | El servidor atiende una conversión a la vez (ver [TECNICA.md §13](TECNICA.md#13-rendimiento-y-concurrencia)) | Esperar; mejora propuesta en [MEJORAS_FUTURAS.md](MEJORAS_FUTURAS.md). |
| Después de actualizar se ve con estilos viejos | Caché del navegador | `Ctrl+F5`. |
| Se borró una plantilla, carrera o frase por error | — | Plantilla eliminada o carrera: restaurar `data/` desde un respaldo (o volver a darla de alta). Plantilla modificada: *Versiones anteriores*. |
| El disco se llena | Imágenes viejas de Docker | `docker image prune` (borra imágenes sin usar; no toca `data/`). |

## Mover el sistema a otro equipo

1. En el equipo viejo: `docker stop constancias` y copiar la carpeta del proyecto completa (incluida `data/`).
2. En el nuevo: instalar Docker, y desde la carpeta copiada, `docker build` + `docker run` como en la instalación.
3. Avisar a las ventanillas la nueva dirección (`http://<nueva-IP>:8000`). Conviene que el servidor tenga **IP fija** o un nombre en la red.

## Calendario de mantenimiento

| Cuándo | Qué | Quién |
|---|---|---|
| Inicio de cada semestre (feb / ago) | Periodo activo y fechas, padrón nuevo, nuevo ingreso, carreras, constancia de prueba (guía *Lista de tareas al iniciar cada semestre*) | Administrador del sistema |
| Enero | Actualizar el **lema del año** y, si cambió, el nombre de quien firma en todas las plantillas | Administrador del sistema |
| Semanal (automático) | Respaldo de `data/` | Tarea programada |
| Mensual | Comprobar que los respaldos existen y abren | Responsable del equipo |
| Cada semestre | `git pull` + reconstruir para tomar correcciones; correr las pruebas si se cambió código | Responsable técnico |
| Cuando cambie el personal | Cambiar la contraseña de administrador | Responsable del equipo |
