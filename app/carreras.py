"""
Catálogo editable de carreras y duraciones de plan.

Vive en data/carreras.json (volumen persistente) y se administra desde la UI,
así abrir una carrera nueva o reestructurar un plan NO requiere tocar código
ni reconstruir la imagen Docker.

Estructura del JSON:
  {
    "carreras":  {"ICO": "LICENCIATURA DE INGENIERIA EN COMPUTACION", ...},
    "duraciones": {"ICB-F25": 8, ...},     # llaveado por código COMPLETO de plan
    "duracion_default": 10
  }

- "carreras" se llavea por PREFIJO del plan (lo que va antes del guion):
  'ICO-F19' → busca 'ICO'.
- "duraciones" se llavea por el código completo, porque una reestructuración
  cambia la duración sin cambiar el prefijo (IPI-F26 dura 9, IPI-F19 dura 10).
- Cualquier plan sin entrada usa duracion_default.
"""
import json
import os
import threading


# Valores con los que se siembra el catálogo la primera vez (o si el JSON
# desaparece). Después de eso, la fuente de verdad es data/carreras.json.
CARRERAS_SEED = {
    "ICB": "LICENCIATURA EN INGENIERIA EN CIBERSEGURIDAD",
    "ICO": "LICENCIATURA DE INGENIERIA EN COMPUTACION",
    "IME": "LICENCIATURA DE INGENIERIA MECANICA",
    "IPI": "LICENCIATURA DE INGENIERO EN PRODUCCION INDUSTRIAL",
    "IPL": "LICENCIATURA DE INGENIERO EN PLASTICOS",
    "IPLS": "LICENCIATURA DE INGENIERO EN PLASTICOS",
    "ISW": "LICENCIATURA DE INGENIERO EN SOFTWARE",
    "LSD": "LICENCIATURA EN SEGURIDAD CIUDADANA",
}

DURACIONES_SEED = {
    "ICB-F25": 8,
    "IPI-F26": 9,
    "IPLS-F26": 9,
    "ISW-F26": 9,
}

DURACION_DEFAULT = 10


class Carreras:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        if not os.path.exists(self.path):
            self._save({
                "carreras": dict(CARRERAS_SEED),
                "duraciones": dict(DURACIONES_SEED),
                "duracion_default": DURACION_DEFAULT,
            })

    # ---------- Lectura ----------

    def _load(self) -> dict:
        # Se lee del disco en cada consulta (el archivo es diminuto): así
        # una edición manual del JSON también se refleja sin reiniciar.
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
        data.setdefault("carreras", {})
        data.setdefault("duraciones", {})
        data.setdefault("duracion_default", DURACION_DEFAULT)
        return data

    def listar(self) -> dict:
        """Snapshot completo del catálogo, para la UI de administración."""
        data = self._load()
        return {
            "carreras": dict(sorted(data["carreras"].items())),
            "duraciones": dict(sorted(data["duraciones"].items())),
            "duracion_default": data["duracion_default"],
        }

    def carrera_full(self, plan: str) -> str:
        """'ICO-F19' → 'LICENCIATURA DE INGENIERIA EN COMPUTACION'.

        Si el prefijo no está en el catálogo devuelve el plan crudo; el
        usuario puede corregirlo a mano en el formulario (y darlo de alta
        en /carreras para la próxima).
        """
        if not plan:
            return ""
        codigo = str(plan).split("-", 1)[0].strip().upper()
        return self._load()["carreras"].get(codigo, plan)

    def semestres_totales(self, plan: str) -> int:
        """'IPI-F26' → 9; cualquier plan sin entrada usa la duración default."""
        data = self._load()
        if not plan:
            return int(data["duracion_default"])
        codigo = str(plan).strip().upper()
        try:
            return int(data["duraciones"].get(codigo, data["duracion_default"]))
        except (TypeError, ValueError):
            return DURACION_DEFAULT

    # ---------- Escritura (desde la UI admin) ----------

    def guardar_carrera(self, codigo: str, nombre: str):
        codigo = str(codigo).strip().upper()
        nombre = " ".join(str(nombre).split()).upper()
        if not codigo or not codigo.replace("_", "").isalnum():
            raise ValueError("El código debe ser el prefijo del plan (ej. ICO), sin espacios ni guiones.")
        if "-" in codigo:
            raise ValueError("Usa solo el prefijo del plan (ej. ICO), sin la parte '-F19'.")
        if not nombre:
            raise ValueError("El nombre de la carrera es requerido.")
        with self._lock:
            data = self._load()
            data["carreras"][codigo] = nombre
            self._save(data)

    def eliminar_carrera(self, codigo: str) -> bool:
        codigo = str(codigo).strip().upper()
        with self._lock:
            data = self._load()
            if codigo not in data["carreras"]:
                return False
            del data["carreras"][codigo]
            self._save(data)
            return True

    def guardar_duracion(self, plan: str, semestres) -> None:
        plan = str(plan).strip().upper()
        if not plan:
            raise ValueError("El código de plan es requerido (ej. IPI-F26).")
        try:
            n = int(semestres)
        except (TypeError, ValueError):
            raise ValueError("La duración debe ser un número de semestres.")
        if not 1 <= n <= 20:
            raise ValueError("La duración debe estar entre 1 y 20 semestres.")
        with self._lock:
            data = self._load()
            data["duraciones"][plan] = n
            self._save(data)

    def eliminar_duracion(self, plan: str) -> bool:
        plan = str(plan).strip().upper()
        with self._lock:
            data = self._load()
            if plan not in data["duraciones"]:
                return False
            del data["duraciones"][plan]
            self._save(data)
            return True

    def _save(self, data: dict):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
