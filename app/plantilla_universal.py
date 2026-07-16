"""
Gestión de plantillas .docx con nombre (una carpeta por plantilla).

Layout en data/plantillas/:
    registro.json            # {slug: {"nombre": "Constancia general"}, ...}
    <slug>/universal.docx    # archivo activo de esa plantilla
    <slug>/_meta.json        # cache de placeholders (autovalidado)
    <slug>/historial/        # respaldos automáticos

Garantías pensadas para que el sistema dure años sin mantenimiento:

- El cache de placeholders (_meta.json) guarda la firma del archivo
  (tamaño + mtime). Si alguien reemplaza o edita el .docx directamente en
  disco —sin pasar por la UI— se detecta y se re-escanea solo: los
  comodines nuevos SIEMPRE aparecen en el formulario.
- Reemplazar una plantilla valida el archivo ANTES de tocar la actual:
  una subida corrupta nunca deja al sistema sin plantilla.
- Cada reemplazo guarda la versión anterior en el historial de esa plantilla
  (se conservan las últimas HISTORIAL_MAX) y se puede restaurar desde la UI.
- El layout viejo (un único universal.docx suelto) se migra solo al arrancar.
"""
import json
import os
import re
import shutil
import threading
import unicodedata
from datetime import datetime

from .docx_render import analizar_plantilla


META_FILENAME = "_meta.json"
PLANTILLA_FILENAME = "universal.docx"
HISTORIAL_DIRNAME = "historial"
HISTORIAL_MAX = 10

_RESPALDO_RE = re.compile(r"^universal_\d{8}_\d{6}(?:-\d+)?\.docx$")


def _escribir_json_atomico(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class PlantillaUniversal:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.historial_dir = os.path.join(base_dir, HISTORIAL_DIRNAME)
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.historial_dir, exist_ok=True)
        self.path = os.path.join(self.base_dir, PLANTILLA_FILENAME)
        self._meta_path = os.path.join(self.base_dir, META_FILENAME)

    def exists(self) -> bool:
        return os.path.exists(self.path)

    # ---------- Meta / detección ----------

    def _firma_actual(self) -> dict:
        st = os.stat(self.path)
        return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}

    def info(self) -> dict | None:
        """
        Meta de la plantilla activa (placeholders, avisos, fecha). Revalida
        contra el archivo real: si cambió en disco, re-escanea automáticamente.
        """
        if not self.exists():
            return None
        firma = self._firma_actual()
        if os.path.exists(self._meta_path):
            try:
                with open(self._meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if (meta.get("size") == firma["size"]
                        and meta.get("mtime_ns") == firma["mtime_ns"]
                        and "placeholders" in meta):
                    return meta
            except (OSError, json.JSONDecodeError):
                pass  # meta corrupto o ilegible: se regenera abajo
        return self._refresh_meta()

    def _refresh_meta(self) -> dict:
        placeholders, avisos = analizar_plantilla(self.path)
        meta = {
            "filename": PLANTILLA_FILENAME,
            "placeholders": placeholders,
            "avisos": avisos,
            "fecha_carga": datetime.now().isoformat(timespec="seconds"),
            **self._firma_actual(),
        }
        _escribir_json_atomico(self._meta_path, meta)
        return meta

    # ---------- Reemplazo seguro ----------

    def replace(self, contenido: bytes) -> dict:
        """
        Sustituye la plantilla universal por el .docx provisto.

        Valida primero sobre un archivo temporal; si el contenido no es un
        .docx legible o no trae ningún placeholder, lanza ValueError y la
        plantilla actual queda intacta. Si es válido, respalda la actual en
        historial/ y hace el cambio de forma atómica.
        """
        tmp = os.path.join(self.base_dir, f"_subida_{os.getpid()}.docx.tmp")
        with open(tmp, "wb") as f:
            f.write(contenido)
        try:
            try:
                placeholders, _avisos = analizar_plantilla(tmp)
            except Exception as e:
                raise ValueError(
                    f"El archivo no es un .docx legible ({e}). "
                    "Se conserva la plantilla anterior."
                ) from e
            if not placeholders:
                raise ValueError(
                    "El .docx no contiene ningún placeholder [[CAMPO]]. "
                    "Se conserva la plantilla anterior."
                )
            self._respaldar_actual()
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        return self._refresh_meta()

    def seed_si_vacio(self, src_path: str):
        """Si no hay plantilla aún, instala la del bootstrap."""
        if self.exists():
            return
        if not os.path.exists(src_path):
            return
        with open(src_path, "rb") as f:
            self.replace(f.read())

    # ---------- Historial ----------

    def _respaldar_actual(self):
        if not self.exists():
            return
        base = f"universal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        nombre = f"{base}.docx"
        # Dos reemplazos en el mismo segundo no deben pisarse el respaldo.
        n = 2
        while os.path.exists(os.path.join(self.historial_dir, nombre)):
            nombre = f"{base}-{n}.docx"
            n += 1
        shutil.copy2(self.path, os.path.join(self.historial_dir, nombre))
        self._podar_historial()

    def _podar_historial(self):
        respaldos = sorted(self._nombres_respaldo())
        for viejo in respaldos[:-HISTORIAL_MAX]:
            try:
                os.remove(os.path.join(self.historial_dir, viejo))
            except OSError:
                pass

    def _nombres_respaldo(self) -> list[str]:
        try:
            return [n for n in os.listdir(self.historial_dir) if _RESPALDO_RE.match(n)]
        except OSError:
            return []

    def historial(self) -> list[dict]:
        """Respaldos disponibles, del más reciente al más antiguo."""
        items = []
        for nombre in sorted(self._nombres_respaldo(), reverse=True):
            # universal_YYYYMMDD_HHMMSS[-n].docx → fecha legible
            crudo = nombre[len("universal_"):-len(".docx")].split("-")[0]
            try:
                fecha = datetime.strptime(crudo, "%Y%m%d_%H%M%S").isoformat(sep=" ")
            except ValueError:
                fecha = crudo
            items.append({"nombre": nombre, "fecha": fecha})
        return items

    def restaurar(self, nombre: str) -> dict:
        """
        Vuelve a una versión del historial. La plantilla actual se respalda
        antes, así que restaurar nunca pierde nada.
        """
        if not _RESPALDO_RE.match(nombre or ""):
            raise ValueError("Nombre de respaldo inválido.")
        origen = os.path.join(self.historial_dir, nombre)
        if not os.path.exists(origen):
            raise ValueError("Ese respaldo ya no existe.")
        with open(origen, "rb") as f:
            return self.replace(f.read())


# ---------- Registro de plantillas con nombre ----------

REGISTRO_FILENAME = "registro.json"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")


def _slug_de(nombre: str) -> str:
    """'Constancia de Prácticas' → 'constancia-de-practicas'."""
    s = unicodedata.normalize("NFKD", str(nombre))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:60] or "plantilla"


class RegistroPlantillas:
    """
    Varias plantillas con nombre (constancia general, inglés, prácticas…).
    Cada una es una PlantillaUniversal en su propia carpeta, con su propio
    historial y su cache autovalidado.
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self._registro_path = os.path.join(self.base_dir, REGISTRO_FILENAME)
        self._lock = threading.Lock()
        self._migrar_layout_viejo()

    # ---------- Registro ----------

    def _cargar_registro(self) -> dict:
        try:
            with open(self._registro_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _guardar_registro(self, data: dict):
        _escribir_json_atomico(self._registro_path, data)

    def _migrar_layout_viejo(self):
        """
        Layout anterior: data/plantillas/universal.docx suelto (+ _meta.json
        + historial/). Se mueve a data/plantillas/universal/ y se registra
        como "Constancia general". Idempotente.
        """
        viejo_docx = os.path.join(self.base_dir, PLANTILLA_FILENAME)
        if not os.path.isfile(viejo_docx):
            return
        destino = os.path.join(self.base_dir, "universal")
        os.makedirs(destino, exist_ok=True)
        os.replace(viejo_docx, os.path.join(destino, PLANTILLA_FILENAME))
        for extra in (META_FILENAME, HISTORIAL_DIRNAME):
            origen = os.path.join(self.base_dir, extra)
            if os.path.exists(origen) and not os.path.exists(os.path.join(destino, extra)):
                shutil.move(origen, os.path.join(destino, extra))
        registro = self._cargar_registro()
        registro.setdefault("universal", {"nombre": "Constancia general"})
        self._guardar_registro(registro)

    # ---------- Consulta ----------

    def slugs(self) -> list[str]:
        return list(self._cargar_registro().keys())

    def get(self, slug: str) -> PlantillaUniversal | None:
        """Plantilla por slug, o None si no está registrada."""
        if not slug or not SLUG_RE.match(slug) or slug not in self._cargar_registro():
            return None
        return PlantillaUniversal(os.path.join(self.base_dir, slug))

    def nombre_de(self, slug: str) -> str:
        return self._cargar_registro().get(slug, {}).get("nombre", slug)

    def listar(self) -> list[dict]:
        """[{slug, nombre, info, historial}] para la UI; info es None si el .docx falta."""
        items = []
        for slug in self.slugs():
            p = self.get(slug)
            items.append({
                "slug": slug,
                "nombre": self.nombre_de(slug),
                "info": p.info() if p else None,
                "historial": p.historial() if p else [],
            })
        return items

    def alguna_lista(self) -> bool:
        """True si existe al menos una plantilla con .docx utilizable."""
        return any(it["info"] for it in self.listar())

    def default_slug(self) -> str | None:
        for it in self.listar():
            if it["info"]:
                return it["slug"]
        return None

    # ---------- Altas / bajas ----------

    def crear(self, nombre: str, contenido: bytes) -> str:
        """Registra una plantilla nueva. Valida el .docx antes de aceptarla."""
        nombre = " ".join(str(nombre).split())
        if not nombre:
            raise ValueError("El nombre de la plantilla es requerido.")
        with self._lock:
            registro = self._cargar_registro()
            base = _slug_de(nombre)
            slug, n = base, 2
            while slug in registro:
                slug = f"{base}-{n}"
                n += 1
            p = PlantillaUniversal(os.path.join(self.base_dir, slug))
            p.replace(contenido)  # ValueError si el .docx es inválido
            registro[slug] = {"nombre": nombre}
            self._guardar_registro(registro)
            return slug

    def eliminar(self, slug: str):
        """Elimina una plantilla (incluido su historial). No permite dejar cero."""
        with self._lock:
            registro = self._cargar_registro()
            if slug not in registro:
                raise ValueError("Esa plantilla no existe.")
            if len(registro) <= 1:
                raise ValueError(
                    "No se puede eliminar la única plantilla del sistema. "
                    "Crea otra primero."
                )
            del registro[slug]
            self._guardar_registro(registro)
        carpeta = os.path.join(self.base_dir, slug)
        if os.path.isdir(carpeta):
            shutil.rmtree(carpeta, ignore_errors=True)

    def seed_si_vacio(self, src_path: str):
        """Primer arranque: registra la plantilla bootstrap como 'Constancia general'."""
        if self.slugs():
            return
        if not os.path.exists(src_path):
            return
        with open(src_path, "rb") as f:
            contenido = f.read()
        with self._lock:
            registro = self._cargar_registro()
            if registro:
                return
            p = PlantillaUniversal(os.path.join(self.base_dir, "universal"))
            p.replace(contenido)
            self._guardar_registro({"universal": {"nombre": "Constancia general"}})
