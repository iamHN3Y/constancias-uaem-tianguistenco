"""
Gestión de la plantilla universal única.

A diferencia del antiguo registro multi-plantilla, aquí solo existe un .docx
en data/plantillas/universal.docx. El usuario puede reemplazarlo desde la UI;
los placeholders detectados se cachean en _meta.json para evitar reescanear.
"""
import json
import os
from datetime import datetime

from .docx_render import detectar_placeholders


META_FILENAME = "_meta.json"
PLANTILLA_FILENAME = "universal.docx"


class PlantillaUniversal:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.path = os.path.join(self.base_dir, PLANTILLA_FILENAME)
        self._meta_path = os.path.join(self.base_dir, META_FILENAME)

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def info(self) -> dict | None:
        if not self.exists():
            return None
        if os.path.exists(self._meta_path):
            with open(self._meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return self._refresh_meta()

    def _refresh_meta(self) -> dict:
        meta = {
            "filename": PLANTILLA_FILENAME,
            "placeholders": detectar_placeholders(self.path),
            "fecha_carga": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return meta

    def replace(self, contenido: bytes) -> dict:
        """Sobrescribe la plantilla universal con el .docx provisto."""
        with open(self.path, "wb") as f:
            f.write(contenido)
        try:
            return self._refresh_meta()
        except Exception as e:
            os.remove(self.path)
            if os.path.exists(self._meta_path):
                os.remove(self._meta_path)
            raise ValueError(f"No se pudo leer la plantilla: {e}") from e

    def seed_si_vacio(self, src_path: str):
        """Si no hay plantilla aún, instala la del bootstrap."""
        if self.exists():
            return
        if not os.path.exists(src_path):
            return
        with open(src_path, "rb") as f:
            self.replace(f.read())
