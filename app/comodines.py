"""
Persistencia de comodines (snippets reutilizables) para la línea libre.

Cada comodín tiene un id, un título corto y el texto que se inserta. Se
guardan en data/comodines.json. No es thread-safe; basta para un uvicorn.
"""
from __future__ import annotations

import json
import os
import threading
import uuid


class Comodines:
    def __init__(self, path: str):
        self.path = path
        # Serializa read-modify-write entre requests concurrentes (uvicorn
        # corre handlers async en un solo thread, pero los endpoints sync
        # se despachan en un threadpool y podrían intercalar escrituras).
        self._lock = threading.Lock()

    def list(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def crear(self, titulo: str, texto: str) -> dict:
        with self._lock:
            items = self.list()
            item = {
                "id": uuid.uuid4().hex[:8],
                "titulo": titulo.strip(),
                "texto": texto.strip(),
            }
            items.append(item)
            self._save(items)
            return item

    def eliminar(self, cid: str) -> bool:
        with self._lock:
            items = self.list()
            nuevos = [c for c in items if c["id"] != cid]
            if len(nuevos) == len(items):
                return False
            self._save(nuevos)
            return True

    def _save(self, items: list[dict]):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
